import asyncio
import struct
from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic

from crc import crc16

class BleClient:
    DEVICE_NAME_UUID = "00002a00-0000-1000-8000-00805f9b34fb"
    NOTIFY_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
    WRITE_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"

    buffer = bytearray()

    def __init__(self, mac_address: str):
        self.client = BleakClient(mac_address)
        self.details_queue = asyncio.Queue()  # Queue to store the received details

    async def __aenter__(self):
        await self.client.connect()  # Connect to the BLE device
        await self.client.start_notify(self.NOTIFY_UUID, self.notification_handler)  # Start receiving notifications
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.client.stop_notify(self.NOTIFY_UUID)  # Stop receiving notifications
        await self.client.disconnect()  # Disconnect from the BLE device

    async def write(self, cmd: int):
        data = cmd.to_bytes(8, 'big')  # Convert the command to a byte array
        crc = data[-2:]  # Extract the CRC from the data
        values = data[:-2]  # Extract the values from the data
        crc2 = crc16(values)  # Calculate the CRC of the values
        if crc != crc2:
            # If the calculated CRC doesn't match the extracted CRC, replace it with the calculated CRC
            data = values + crc2
        #print("write ", self.WRITE_UUID, data.hex())
        await self.client.write_gatt_char(self.WRITE_UUID, data)  # Write the data to the BLE device

    async def notification_handler(self, characteristic: BleakGATTCharacteristic, data: bytearray):
        if characteristic.uuid != self.NOTIFY_UUID:
            return
        self.buffer += data  # Append the received data to the buffer
        if len(self.buffer) < 3:
            return

        crc = self.buffer[-2:]  # Extract the CRC from the buffer
        values = data[:-2]  # Extract the values from the buffer
        crc2 = crc16(values)  # Calculate the CRC of the values
        if crc != crc2:
            # If the calculated CRC doesn't match the extracted CRC, ignore the data
            pass
        if self.buffer[0] != 0x01:
            print("invalid start byte", self.buffer.hex())
            self.buffer = bytearray()
            return
        if len(self.buffer) == 91:
            response = BleClient.parse_details_response(self.buffer)  # Parse the details response from the buffer
            self.details_queue.put_nowait(response)  # Add the parsed response to the queue
            self.buffer = bytearray()
        if len(self.buffer) >= 91:
            print(f"received too many bytes ({len(self.buffer)})")
            self.buffer = bytearray()  # Clear the buffer

    async def list_services(self):
        for service in self.client.services:
            print("[Service] %s", service)
            for char in service.characteristics:
                print("  [Characteristic] ", char, ",".join(char.properties))
                for descriptor in char.descriptors:
                    try:
                        value = await self.client.read_gatt_descriptor(descriptor.handle)
                        print("    [Descriptor] ", descriptor, value)
                    except Exception as e:
                        print("    [Descriptor] ", descriptor, e)

    async def get_device_name(self):
        device_name = await self.client.read_gatt_char(self.DEVICE_NAME_UUID)  # Read the device name from the BLE device
        return "".join(map(chr, device_name))

    async def request_details(self):
        self.details_queue = asyncio.Queue()  # Clear the queue
        i = 0
        while self.details_queue.empty() and i < 10:
            i += 1
            await self.write(0xFE043030002bbf1a)  # Send a request for details to the BLE device
            await asyncio.sleep(0.1)  # Wait for the response to be received
        return await self.details_queue.get()  # Return the first item in the queue

    @staticmethod
    def solar_panel_charge_state(v: int):
        if 0:
            return "invalid"
        elif 1:
            return "float_charge"
        elif 2: 
            return "boost_charge"
        elif 3:
            return "equal_charge"
        else:
            return "fault"
        
    @staticmethod
    def load_discharge_state(v: int):
        fault = v & 2 == 1
        if not fault and v & 1:
            return "enabled"
        elif not fault:
            return "disabled"
        elif (v >> 2) & 1:
            return  "over_temperature"
        elif (v >> 3) & 1:
            return "open_circuit_protection"
        elif (v >> 4) & 1:
            return "hardware_protection"
        elif (v >> 11) & 1:
            return "short_circuit_protection"
        else:
            return str((v >> 12) & 0b11)

    @staticmethod
    def parse_details_response(data):
        if len(data) != 91:
            return None
        subdata = data[3:-2]
        return {
            "equipment_id": struct.unpack_from(">H", subdata, 0)[0],
            "run_days": struct.unpack_from(">H", subdata, 2)[0],
            "battery_full_level": struct.unpack_from(">H", subdata, 4)[0] / 100,
            "battery_state_1": struct.unpack_from(">H", subdata, 6)[0] & 0xF0 >> 4,
            "battery_state_2": struct.unpack_from(">H", subdata, 6)[0] & 0x0F,
            "solar_panel_is_charging": struct.unpack_from(">H", subdata, 8)[0] & 1 > 0,
            "solar_panel_is_night": struct.unpack_from(">H", subdata, 8)[0] & 32 > 0,
            "solar_panel_charge_state": BleClient.solar_panel_charge_state(struct.unpack_from(">H", subdata, 8)[0] & 0b1100 >> 2),
            "solar_panel_state": struct.unpack_from(">H", subdata, 8)[0] & 16 > 0,
            "load_is_enabled": struct.unpack_from(">H", subdata, 10)[0] & 1 > 0,
            "load_state": BleClient.load_discharge_state(struct.unpack_from(">H", subdata, 10)[0]),
            "temperature_1": struct.unpack_from(">H", subdata, 12)[0] / 100,
            "temperature_2": struct.unpack_from(">H", subdata, 14)[0] / 100,
            "battery_empty_times": struct.unpack_from(">H", subdata, 16)[0],
            "battery_full_times": struct.unpack_from(">H", subdata, 18)[0],
            "battery_percentage": struct.unpack_from(">H", subdata, 42)[0],
            "battery_voltage": struct.unpack_from(">H", subdata, 44)[0] / 100,
            "battery_current": struct.unpack_from(">h", subdata, 46)[0] / 100,
            "battery_power": (struct.unpack_from(">H", subdata, 48)[0] + struct.unpack_from(">h", subdata, 50)[0]  * 0x100) / 100,
            "load_voltage": struct.unpack_from(">H", subdata, 52)[0] / 100,
            "load_current": struct.unpack_from(">H", subdata, 54)[0] / 100,
            "load_power": (struct.unpack_from(">H", subdata, 56)[0] | struct.unpack_from(">H", subdata, 58)[0] << 16) / 100,
            "solar_panel_voltage": struct.unpack_from(">H", subdata, 60)[0] / 100,
            "solar_panel_current": struct.unpack_from(">H", subdata, 62)[0] / 100,
            "solar_panel_power": (struct.unpack_from(">H", subdata, 64)[0] | struct.unpack_from(">H", subdata, 66)[0] << 16) / 100,
            "solar_panel_daily_energy": struct.unpack_from(">H", subdata, 68)[0] / 100,
            "solar_panel_total_energy": (struct.unpack_from(">H", subdata, 70)[0] | struct.unpack_from(">H", subdata, 72)[0] << 16) / 100,
            "load_daily_energy": struct.unpack_from(">H", subdata, 74)[0] / 100,
            "load_total_energy": struct.unpack_from(">I", subdata, 78)[0] / 100,
        }

    # Map the keys to their respective units of measurement
    @staticmethod
    def get_unit_of_measurement(key):
        unit_mapping = {
            "solar_panel_is_charging": None,
            "solar_panel_is_night": None,
            "solar_panel_charge_state": None,
            "solar_panel_state": None,
            "load_is_enabled": None,
            "load_state": None,
            "temperature_1": "°C",
            "temperature_2": "°C",
            "battery_percentage": "%",
            "battery_voltage": "V",
            "battery_current": "A",
            "battery_power": "W",
            "load_voltage": "V",
            "load_current": "A",
            "load_power": "W",
            "solar_panel_voltage": "V",
            "solar_panel_current": "A",
            "solar_panel_power": "W",
            "solar_panel_daily_energy": "kWh",
            "solar_panel_total_energy": "kWh",
            "load_daily_energy": "kWh",
            "load_total_energy": "kWh",
        }
        return unit_mapping.get(key, None)