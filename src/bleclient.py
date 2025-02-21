import asyncio
import struct
from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic

from src.crc import crc16
from src.protocol import LumiaxClient, ResultContainer, Result

class BleClient(LumiaxClient):
    DEVICE_NAME_UUID = "00002a00-0000-1000-8000-00805f9b34fb"
    NOTIFY_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
    WRITE_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"

    buffer = bytearray()

    def __init__(self, mac_address: str):
        self.client = BleakClient(mac_address)
        self.response_queue = asyncio.Queue()
        self.lock = asyncio.Lock()

    async def __aenter__(self):
        await self.client.connect()  # Connect to the BLE device
        await self.client.start_notify(self.NOTIFY_UUID, self.notification_handler)  # Start receiving notifications
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.client.stop_notify(self.NOTIFY_UUID)  # Stop receiving notifications
        await self.client.disconnect()  # Disconnect from the BLE device

    def notification_handler(self, characteristic: BleakGATTCharacteristic, data: bytearray):
        if characteristic.uuid != self.NOTIFY_UUID:
            return
        self.buffer += data  # Append the received data to the buffer
        try:
            if not self.is_complete(self.buffer):
                return
            results = self.parse(self.start_address, self.buffer)
            self.response_queue.put_nowait(results)
        except Exception as e:
            print(f"Response from device: 0x{self.buffer.hex()}")
            print(f"Error while parsing response: {e}")

    async def read(self, start_address: int, count: int, repeat = 10, timeout = 5) -> ResultContainer:
        async with self.lock:
            self.start_address = start_address
            command = self.get_read_command(0xFE, start_address, count)
            self.response_queue = asyncio.Queue() # Clear the queue
            i = 0
            # send the command multiple times
            while i < repeat:
                i += 1
                self.buffer = bytearray()
                await self.client.write_gatt_char(self.WRITE_UUID, command)
                try:
                    # Wait for either a response or timeout
                    return await asyncio.wait_for(self.response_queue.get(), timeout=timeout)
                except asyncio.TimeoutError:
                    if self.buffer:
                        print(f"Got partial response: 0x{self.buffer.hex()}")
                    print(f"Repeating read command...")
            return ResultContainer([])

    async def request_details(self) -> ResultContainer:
        return await self.read(0x3030, 41)

    async def request_parameters(self) -> ResultContainer:
        return await self.read(0x9021, 12)
    
    async def write(self, results: list[Result], repeat = 10, timeout = 2) -> ResultContainer:
        async with self.lock:
            start_address, command = self.get_write_command(self.device_id, results)
            self.start_address = start_address
            self.response_queue = asyncio.Queue() # Clear the queue
            i = 0
            # send the command multiple times
            while i < repeat:
                i += 1
                self.buffer = bytearray()
                await self.client.write_gatt_char(self.WRITE_UUID, command)
                print(f"Wrote command 0x{command.hex()}")
                try:
                    # Wait for either a response or timeout
                    await asyncio.wait_for(self.response_queue.get(), timeout=timeout)
                    return ResultContainer(results)
                except asyncio.TimeoutError:
                    if self.buffer:
                        print(f"Got partial response: 0x{self.buffer.hex()}")
                    print(f"Repeating write command...")
            return ResultContainer([])

    async def get_device_name(self):
        device_name = await self.client.read_gatt_char(self.DEVICE_NAME_UUID)  # Read the device name from the BLE device
        return "".join(map(chr, device_name))

    async def list_services(self):
        service_text = "[Service]          "
        charact_text = "  [Characteristic] "
        descrip_text = "    [Descriptor]   "
        value_text   = "      Value = "
        for service in self.client.services:
            print(service_text, service)
            for char in service.characteristics:
                print(charact_text, char, ",".join(char.properties))
                for descriptor in char.descriptors:
                    try:
                        print(descrip_text, descriptor)
                        value = await self.client.read_gatt_descriptor(descriptor.handle)
                        print(value_text, "0x" + value.hex())
                    except Exception as e:
                        pass