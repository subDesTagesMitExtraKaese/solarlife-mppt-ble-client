import struct
from dataclasses import dataclass

from .crc import crc16
from .registers import FunctionCodes, Register, registers

type Value = str | int | float


class ProtocolError(Exception):
    pass


@dataclass
class Result(Register):
    value: Value


class ResultContainer:
    def __init__(self, results: list[Result]):
        self._results = results
        self._result_map = {res.name: res for res in results}

    def __getitem__(self, key: int | str | slice) -> Result:
        if isinstance(key, int):
            return self._results[key]
        elif isinstance(key, str):
            return self._result_map[key]
        elif isinstance(key, slice):
            return ResultContainer(self._results[key])
        else:
            raise TypeError("Key must be an integer index or a result name string.")

    def __len__(self):
        return len(self._results)

    def __iter__(self):
        return iter(self._results)

    def __add__(self, other) -> list[Result]:
        return ResultContainer(self._results + other._results)

    def __bool__(self):
        return len(self._results) > 0

    def items(self):
        return self._result_map.items()

    def get(self, key: str) -> Result | None:
        if isinstance(key, str):
            return self._result_map.get(key)
        else:
            raise TypeError("Key must be a register name string.")


class LumiaxClient:
    def __init__(self):
        self.device_id = 0xFE

    def _read_raw(self, register: Register, buffer: bytes, offset: int) -> int:
        if register.is_32_bit:
            low = struct.unpack_from(">H", buffer, offset)[0]
            high_format = ">h" if register.is_signed else ">H"
            high = struct.unpack_from(high_format, buffer, offset + 2)[0]
            return low | (high << 16)
        if register.is_signed:
            return struct.unpack_from(">h", buffer, offset)[0]
        return struct.unpack_from(">H", buffer, offset)[0]

    def bytes_to_value(self, register: Register, buffer: bytes, offset: int) -> Value:
        raw_value = self._read_raw(register, buffer, offset)
        try:
            return register.format.decode(raw_value)
        except (IndexError, ValueError) as error:
            raise ProtocolError(
                f"unexpected value for {register.name} ({hex(register.address)}): '{raw_value}'"
            ) from error

    def value_to_bytes(
        self, register: Register, buffer: bytearray, offset: int, value: Value
    ) -> int:
        raw_value = register.format.encode(value)
        if register.write_function_code == FunctionCodes.WRITE_STATUS_REGISTER.value:
            raw_value = 0xFF00 if raw_value else 0

        if register.is_32_bit and register.is_signed:
            struct.pack_into(">H", buffer, offset, raw_value & 0xFFFF)
            struct.pack_into(">h", buffer, offset + 2, raw_value >> 16)
        elif register.is_32_bit:
            struct.pack_into(">H", buffer, offset, raw_value & 0xFFFF)
            struct.pack_into(">H", buffer, offset + 2, raw_value >> 16)
        elif register.is_signed:
            struct.pack_into(">h", buffer, offset, raw_value)
        else:
            struct.pack_into(">H", buffer, offset, raw_value)

        length = 4 if register.is_32_bit else 2
        return offset + length

    def get_read_command(self, device_id: int, start_address: int, count: int) -> bytes:
        items = [
            v
            for v in registers
            if v.address >= start_address and v.address < start_address + count
        ]
        if not items:
            raise ProtocolError(
                f"the range {hex(start_address)}-{hex(start_address + count - 1)} contains no registers"
            )

        function_code = items[0].function_codes[0]
        if not all(function_code in v.function_codes for v in items):
            raise ProtocolError(
                f"the range {hex(start_address)}-{hex(start_address + count - 1)} spans multiple function codes"
            )

        result = bytes(
            [
                device_id,
                function_code,
                start_address >> 8,
                start_address & 0xFF,
                count >> 8,
                count & 0xFF,
            ]
        )
        return result + crc16(result)

    def get_write_command(
        self, device_id: int, results: list[Result]
    ) -> tuple[int, bytes]:
        if not results:
            raise ProtocolError("values list is empty")
        results.sort(key=lambda x: x.address)
        address = results[0].address
        for result in results:
            if result.value is None:
                raise ProtocolError(
                    f"value of {result.name} ({hex(result.address)}) is empty"
                )
            if address < result.address:
                raise ProtocolError(
                    f"registers are not continuous at {hex(result.address)}"
                )
            address = result.address + (2 if result.is_32_bit else 1)

        start_register = results[0]
        end_register = results[-1]
        start_address = start_register.address
        end_address = end_register.address + (1 if end_register.is_32_bit else 0)
        count = end_address - start_address + 1
        byte_count = count * 2
        if byte_count > 255:
            raise ProtocolError("address range is too large")

        if count > 1:
            function_code = FunctionCodes.WRITE_MEMORY_RANGE
            header = bytes(
                [
                    device_id,
                    function_code.value,
                    start_address >> 8,
                    start_address & 0xFF,
                    count >> 8,
                    count & 0xFF,
                    byte_count,
                ]
            )
        else:
            if FunctionCodes.WRITE_STATUS_REGISTER.value in results[0].function_codes:
                function_code = FunctionCodes.WRITE_STATUS_REGISTER
            else:
                function_code = FunctionCodes.WRITE_MEMORY_SINGLE
            header = bytes(
                [
                    device_id,
                    function_code.value,
                    start_address >> 8,
                    start_address & 0xFF,
                ]
            )

        if not all(function_code.value in x.function_codes for x in results):
            raise ProtocolError(
                f"function code {function_code.name} is not supported for all addresses"
            )

        data = bytearray(byte_count)
        for result in results:
            offset = (result.address - start_address) * 2
            self.value_to_bytes(result, data, offset, result.value)

        result = header + bytes(data)
        return start_address, result + crc16(result)

    @staticmethod
    def is_read(function_code: int) -> bool:
        return function_code in (
            FunctionCodes.READ_STATUS_REGISTER.value,
            FunctionCodes.READ_PARAMETER.value,
            FunctionCodes.READ_MEMORY.value,
        )

    def frame_length(self, function_code: int, byte_count: int) -> int:
        # Device id, function code and byte count lead the frame, two CRC bytes end it.
        return 3 + byte_count + 2 if self.is_read(function_code) else 8

    def take_frame(
        self,
        buffer: bytearray,
        device_id: int | None,
        function_code: int,
        response_id: int | None = None,
        expected_byte_count: int | None = None,
        max_byte_count: int = 250,
    ) -> bytes | None:
        """Remove one complete response frame from the front of buffer.

        Bytes that do not belong to the response are dropped: a late byte or a
        repeated frame from a previous transaction otherwise ends up in front of
        the next response and shifts it. A response carries the controller's own
        id, which differs from the broadcast id used for the first request, so
        both are accepted. Returns None while the frame is still incomplete.
        """
        accepted_ids = {
            value for value in (device_id, response_id) if value is not None
        }
        while len(buffer) >= 2:
            if buffer[1] == function_code and (
                response_id is None or buffer[0] in accepted_ids
            ):
                break
            del buffer[0]
        if len(buffer) < 3:
            return None

        byte_count = buffer[2]
        if self.is_read(function_code) and (
            byte_count == 0
            or byte_count % 2
            or byte_count > max_byte_count
            or (expected_byte_count is not None and byte_count != expected_byte_count)
        ):
            del buffer[0]
            return self.take_frame(
                buffer,
                device_id,
                function_code,
                response_id,
                expected_byte_count,
                max_byte_count,
            )

        length = self.frame_length(function_code, byte_count)
        if len(buffer) < length:
            return None

        frame = bytes(buffer[:length])
        del buffer[:length]
        return frame

    def parse(self, start_address: int, buffer: bytes) -> ResultContainer:
        function_code = FunctionCodes(buffer[1])
        results = []
        if function_code in [
            FunctionCodes.READ_MEMORY,
            FunctionCodes.READ_PARAMETER,
            FunctionCodes.READ_STATUS_REGISTER,
        ]:
            data_length = buffer[2]
            received_crc = buffer[3 + data_length : 3 + data_length + 2]
            calculated_crc = crc16(buffer[: 3 + data_length])
            if received_crc != calculated_crc:
                raise ProtocolError(
                    f"CRC mismatch (0x{calculated_crc.hex()} != 0x{received_crc.hex()})"
                )

            address = start_address
            cursor = 3
            while cursor < data_length + 3:
                items = [
                    v
                    for v in registers
                    if address == v.address and function_code.value in v.function_codes
                ]
                for register in items:
                    value = self.bytes_to_value(register, buffer, cursor)
                    results.append(Result(**vars(register), value=value))
                cursor += 2
                address += 1
        else:
            address = struct.unpack_from(">H", buffer, 2)[0]
            if address != start_address:
                raise ProtocolError(
                    f"Write result address mismatch ({hex(address)} != {hex(start_address)})"
                )
            received_crc = buffer[6:8]
            calculated_crc = crc16(buffer[:6])
            if received_crc != calculated_crc:
                raise ProtocolError(
                    f"CRC mismatch (0x{calculated_crc.hex()} != 0x{received_crc.hex()})"
                )

            if function_code in [
                FunctionCodes.WRITE_MEMORY_SINGLE,
                FunctionCodes.WRITE_STATUS_REGISTER,
            ]:
                register = next(
                    v
                    for v in registers
                    if address == v.address and function_code.value in v.function_codes
                )
                value = self.bytes_to_value(register, buffer, 4)
                results.append(Result(**vars(register), value=value))
        self.device_id = buffer[0]
        return ResultContainer(results)
