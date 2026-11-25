import tomllib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

Value = str | int | float | bool


class FunctionCodes(Enum):
    # Read
    READ_STATUS_REGISTER = 0x02  # Read the switch input status
    READ_PARAMETER = 0x03  # Read multiple hold registers
    READ_MEMORY = 0x04  # Read input register
    # Write
    WRITE_STATUS_REGISTER = 0x05  # Write single register
    WRITE_MEMORY_SINGLE = 0x06  # Write single hold register
    WRITE_MEMORY_RANGE = 0x10  # Write multiple hold registers


class ValueKind(Enum):
    NUMBER = "number"
    FLAG = "flag"
    ENUM = "enum"
    DIGITS = "digits"
    PACKED_TIME = "packed_time"


@dataclass(frozen=True)
class ValueFormat:
    kind: ValueKind
    unit: str = ""
    divisor: float = 1
    shift: int = 0
    mask: int = 0
    labels: tuple[str, ...] = ()
    digits: int = 0
    clamp: int | None = None

    def decode(self, raw: int) -> Value:
        if self.kind is ValueKind.NUMBER:
            return raw / self.divisor if self.divisor else raw
        if self.kind is ValueKind.FLAG:
            return bool((raw >> self.shift) & self.mask)
        if self.kind is ValueKind.ENUM:
            index = (raw >> self.shift) & self.mask
            return self.labels[index] if index < len(self.labels) else ""
        if self.kind is ValueKind.DIGITS:
            limit = 9 if self.clamp is None else self.clamp
            return "".join(
                str(min((raw >> shift) & 0xF, limit))
                for shift in range((self.digits - 1) * 4, -1, -4)
            )
        if self.kind is ValueKind.PACKED_TIME:
            hours = (raw >> 8) & 0xFF
            minutes = raw & 0xFF
            return hours * 60 + min(minutes, 59)
        raise ValueError(f"unsupported value kind {self.kind}")

    def encode(self, value: Value) -> int:
        if self.kind is ValueKind.NUMBER:
            raw = round(float(value) * self.divisor)
            return raw
        if self.kind is ValueKind.FLAG:
            on = value in (True, 1, "1", "True", "On", "ON")
            return int(on) << self.shift
        if self.kind is ValueKind.ENUM:
            if isinstance(value, bool):
                index = int(value)
            elif isinstance(value, int):
                index = value
            else:
                index = self.labels.index(str(value))
            return index << self.shift
        if self.kind is ValueKind.DIGITS:
            text = str(value)
            if len(text) != self.digits or not text.isdigit():
                raise ValueError(f"expected {self.digits} digits, got '{value}'")
            raw = 0
            for char in text:
                raw = (raw << 4) | int(char)
            return raw
        if self.kind is ValueKind.PACKED_TIME:
            minutes = round(float(value))
            hours, minutes = divmod(minutes, 60)
            if hours > 0xFF:
                raise ValueError(f"packed time is out of range: {value}")
            return (hours << 8) | minutes
        raise ValueError(f"unsupported value kind {self.kind}")


@dataclass
class Register:
    address: int
    name: str
    friendly_name: str
    function_codes: tuple[int, ...]
    format: ValueFormat
    is_32_bit: bool
    is_signed: bool

    @property
    def is_writable(self) -> bool:
        return any(
            code in self.function_codes
            for code in (
                FunctionCodes.WRITE_STATUS_REGISTER.value,
                FunctionCodes.WRITE_MEMORY_SINGLE.value,
                FunctionCodes.WRITE_MEMORY_RANGE.value,
            )
        )

    @property
    def write_function_code(self) -> int:
        if FunctionCodes.WRITE_STATUS_REGISTER.value in self.function_codes:
            return FunctionCodes.WRITE_STATUS_REGISTER.value
        return FunctionCodes.WRITE_MEMORY_SINGLE.value

    @property
    def unit(self) -> str:
        return self.format.unit

    @property
    def payload_on(self) -> str:
        if self.format.kind is ValueKind.ENUM and len(self.format.labels) > 1:
            return self.format.labels[1]
        return "True"

    @property
    def payload_off(self) -> str:
        if self.format.kind is ValueKind.ENUM and self.format.labels:
            return self.format.labels[0]
        return "False"


# The ranges the client polls. Names repeat across controller blocks, so a name
# lookup inside these ranges is what the client actually reads and writes.
_POLLED_RANGES = ((0x3030, 0x3058), (0x9021, 0x902C))


def _lookup_priority(register: Register) -> int:
    for index, (start, end) in enumerate(_POLLED_RANGES):
        if start <= register.address <= end:
            return index
    return len(_POLLED_RANGES)


class RegisterContainer:
    def __init__(self, registers: list[Register]):
        self._registers = registers
        self._register_map = {}
        for register in registers:
            current = self._register_map.get(register.name)
            if current is None or _lookup_priority(register) < _lookup_priority(
                current
            ):
                self._register_map[register.name] = register

    def __getitem__(self, key: int | str | slice) -> Register:
        if isinstance(key, int):
            return self._registers[key]
        elif isinstance(key, str):
            return self._register_map[key]
        elif isinstance(key, slice):
            return RegisterContainer(self._registers[key])
        else:
            raise TypeError(
                "Key must be an integer index, a register name string, or a slice."
            )

    def __len__(self):
        return len(self._registers)

    def __iter__(self):
        return iter(self._registers)

    def __add__(self, other):
        return RegisterContainer(self._registers + other._registers)

    def __bool__(self):
        return len(self._registers) > 0

    def items(self):
        return self._register_map.items()

    def get(self, key: str) -> Register | None:
        if isinstance(key, str):
            return self._register_map.get(key)
        else:
            raise TypeError("Key must be a register name string.")


_DATA_FILE = Path(__file__).resolve().parents[1] / "registers.toml"
_GROUP_ORDER = (
    "real_time_status",
    "status_registers",
    "rated_parameters",
    "read_only_registers",
    "device_parameters",
    "battery_and_load_parameters",
    "switches",
)


def _as_int(value: int | str) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def _load_registers() -> dict[str, list[Register]]:
    with _DATA_FILE.open("rb") as file:
        data = tomllib.load(file)

    groups = {name: [] for name in _GROUP_ORDER}
    for item in data["register"]:
        group = item["group"]
        if group not in groups:
            raise ValueError(f"unknown register group '{group}' in {_DATA_FILE}")

        raw_format = dict(item.get("format", {"kind": "number"}))
        raw_format["kind"] = ValueKind(raw_format["kind"])
        raw_format["labels"] = tuple(raw_format.get("labels", ()))
        if raw_format["kind"] is ValueKind.FLAG:
            raw_format.setdefault("mask", 1)

        groups[group].append(
            Register(
                address=_as_int(item["address"]),
                name=item["name"],
                friendly_name=item["friendly_name"],
                function_codes=tuple(_as_int(code) for code in item["function_codes"]),
                format=ValueFormat(**raw_format),
                is_32_bit=bool(item.get("is_32_bit", False)),
                is_signed=bool(item.get("is_signed", False)),
            )
        )
    return groups


_GROUPS = _load_registers()

real_time_status = RegisterContainer(_GROUPS["real_time_status"])
status_registers = RegisterContainer(_GROUPS["status_registers"])
rated_parameters = RegisterContainer(_GROUPS["rated_parameters"])
read_only_registers = RegisterContainer(_GROUPS["read_only_registers"])
device_parameters = RegisterContainer(_GROUPS["device_parameters"])
battery_and_load_parameters = RegisterContainer(_GROUPS["battery_and_load_parameters"])
switches = RegisterContainer(_GROUPS["switches"])

registers = (
    real_time_status
    + status_registers
    + rated_parameters
    + read_only_registers
    + device_parameters
    + battery_and_load_parameters
    + switches
)
