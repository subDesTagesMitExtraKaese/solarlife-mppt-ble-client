import struct
from dataclasses import dataclass
from typing import Any

from .variables import variables, Variable, FunctionCodes
from .crc import crc16

type Value = str|int|float

@dataclass
class Result(Variable):
    value: Value

class LumiaxClient:
    def __init__(self):
        self.device_id = 0xFE

    def bytes_to_value(self, variable: Variable, buffer: bytes, offset: int) -> Value:
        if variable.is_32_bit and variable.is_signed:
            raw_value = struct.unpack_from(">H", buffer, offset)[0] | struct.unpack_from(">h", buffer, offset + 2)[0] << 16
        elif variable.is_32_bit:
            raw_value = struct.unpack_from(">H", buffer, offset)[0] | struct.unpack_from(">H", buffer, offset + 2)[0] << 16
        elif variable.is_signed:
            raw_value = struct.unpack_from(">h", buffer, offset)[0]
        else:
            raw_value = struct.unpack_from(">H", buffer, offset)[0]

        if variable.multiplier:
            value = raw_value / variable.multiplier
        elif variable.func:
            try:
                value = variable.func(raw_value)
            except IndexError as e:
                raise Exception(f"unexpected value for {variable.name} ({hex(variable.address)}): '{raw_value}'")
        else:
            value = raw_value
        return value

    def value_to_bytes(self, variable: Variable, buffer: bytearray, offset: int, value: Value) -> int:
        if variable.multiplier:
            raw_value = round(float(value) * variable.multiplier)
        elif variable.func:
            raw_value = self._find_raw_value_by_brute_force(variable, value)
            if raw_value == None:
                raise Exception(f"invalid value for {variable.name}: '{value}'")
        else:
            raw_value = int(value)

        if variable.is_32_bit and variable.is_signed:
            struct.pack_into(">H", buffer, offset, raw_value & 0xFFFF)
            struct.pack_into(">h", buffer, offset + 2, raw_value >> 16)
        elif variable.is_32_bit:
            struct.pack_into(">H", buffer, offset, raw_value & 0xFFFF)
            struct.pack_into(">H", buffer, offset + 2, raw_value >> 16)
        elif variable.is_signed:
            struct.pack_into(">h", buffer, offset, raw_value)
        else:
            struct.pack_into(">H", buffer, offset, raw_value)

        length = 4 if variable.is_32_bit else 2
        return offset + length

    def get_read_command(self, device_id: int, start_address: int, count: int) -> bytes:
        items = [v for v in variables if v.address >= start_address and v.address < start_address + count]
        if not items:
            raise Exception(f"the range {hex(start_address)}-{hex(start_address+count-1)} contains no variables")
        
        function_code = items[0].function_codes[0]
        if not all(function_code in v.function_codes for v in items):
            raise Exception(f"the range {hex(start_address)}-{hex(start_address+count-1)} spans multiple function codes")

        result = bytes([
            device_id, 
            function_code,
            start_address >> 8,
            start_address & 0xFF,
            count >> 8,
            count & 0xFF
        ])
        return result + crc16(result)

    def get_write_command(self, device_id: int, values: list[(Variable, Any)]) -> bytes:
        if not values:
            raise Exception(f"values list is empty")
        values.sort(key=lambda x: x[0].address)
        address = values[0][0].address
        for variable, value in values:
            if value is None:
                raise Exception(f"value of {variable.name} ({hex(variable.address)}) is empty")
            if address < variable.address:
                raise Exception(f"variables are not continuous at {hex(variable.address)}")
            address = variable.address + (2 if variable.is_32_bit else 1)

        start_variable = values[0][0]
        end_variable = values[-1][0]
        start_address = start_variable.address
        end_address = end_variable.address + (1 if end_variable.is_32_bit else 0)
        count = end_address - start_address + 1
        byte_count = count * 2
        if byte_count > 255:
            raise Exception(f"address range is too large")

        if count > 1:
            function_code = FunctionCodes.WRITE_MEMORY_RANGE
            header = bytes([
                device_id,
                function_code.value,
                start_address >> 8,
                start_address & 0xFF,
                count >> 8,
                count & 0xFF,
                byte_count,
            ])
        else:
            if FunctionCodes.WRITE_STATUS_REGISTER.value in values[0][0].function_codes:
                function_code = FunctionCodes.WRITE_STATUS_REGISTER
            else:
                function_code = FunctionCodes.WRITE_MEMORY_SINGLE
            header = bytes([
                device_id,
                function_code.value,
                start_address >> 8,
                start_address & 0xFF,
            ])

        if not all(function_code.value in x[0].function_codes for x in values):
            raise Exception(f"function code {function_code.name} is not supported for all addresses")

        data = bytearray(byte_count)
        for variable, value in values:
            offset = (variable.address - start_address) * 2
            self.value_to_bytes(variable, data, offset, value)

        result = header + bytes(data)
        return result + crc16(result)

    def is_complete(self, buffer: bytes) -> bool:
        if len(buffer) < 4:
            return False
        device_id = buffer[0]
        function_code = FunctionCodes(buffer[1])
        if function_code in [FunctionCodes.READ_MEMORY, FunctionCodes.READ_PARAMETER, FunctionCodes.READ_STATUS_REGISTER]:
            data_length = buffer[2]
            return len(buffer) >= data_length + 5
        else:
            return len(buffer) >= 8

    def parse(self, start_address: int, buffer: bytes) -> list[Result]:
        self.device_id = buffer[0]
        function_code = FunctionCodes(buffer[1])
        if function_code in [FunctionCodes.READ_MEMORY, FunctionCodes.READ_PARAMETER, FunctionCodes.READ_STATUS_REGISTER]:
            data_length = buffer[2]
            received_crc = buffer[3+data_length:3+data_length+2]
            calculated_crc = crc16(buffer[:3+data_length])
            if received_crc != calculated_crc:
                raise Exception(f"CRC mismatch ({calculated_crc} != {received_crc})")

            results = []
            address = start_address
            cursor = 3
            while cursor < data_length + 3:
                items = [v for v in variables if address == v.address and function_code.value in v.function_codes]
                for variable in items:
                    value = self.bytes_to_value(variable, buffer, cursor)
                    results.append(Result(**vars(variable), value=value))
                cursor += 2
                address += 1

            return results
        else:
            address = struct.unpack_from('>H', buffer, 2)[0]
            if address != start_address:
                raise Exception(f"Write result address mismatch ({hex(address)} != {hex(start_address)})")
            received_crc = buffer[6:8]
            calculated_crc = crc16(buffer[:6])
            if received_crc != calculated_crc:
                raise Exception(f"CRC mismatch ({calculated_crc} != {received_crc})")
            return []

    def _find_raw_value_by_brute_force(self, variable: Variable, value):
        n_bits = 32 if variable.is_32_bit else 16
        if variable.is_signed:
            for i in range(0, 2**(n_bits-1) + 1):
                try:
                    if variable.func(i) == value:
                        return i
                except IndexError:
                    pass
            for i in range(0, -2**(n_bits-1) - 2, -1):
                try:
                    if variable.func(i) == value:
                        return i
                except IndexError:
                    pass
        else:
            for i in range(0, 2**n_bits + 1):
                try:
                    if variable.func(i) == value:
                        return i
                except IndexError:
                    pass
        return None
