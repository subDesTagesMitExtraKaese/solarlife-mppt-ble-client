import asyncio
import struct
from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic

from src.crc import crc16
from src.protocol import LumiaxClient, Result

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

    async def notification_handler(self, characteristic: BleakGATTCharacteristic, data: bytearray):
        if characteristic.uuid != self.NOTIFY_UUID:
            return
        self.buffer += data  # Append the received data to the buffer
        if not self.is_complete(self.buffer):
            return
        results = self.parse(self.start_address, buffer)
        self.response_queue.put_nowait({r.name: r for r in results})

    async def read(self, start_address: int, count: int, repeat = 10, timeout = 5) -> dict[str, Result]:
        async with self.lock:
            self.start_address = start_address
            command = self.get_read_command(0xFE, start_address, count)
            self.response_queue = asyncio.Queue() # Clear the queue
            i = 0
            # send the command multiple times
            while self.response_queue.empty() and i < repeat:
                i += 1
                await self.client.write_gatt_char(self.WRITE_UUID, command)
                try:
                    # Wait for either a response or timeout
                    return await asyncio.wait_for(self.response_queue.get(), timeout=timeout)
                except asyncio.TimeoutError:
                    pass
            return None

    async def request_details(self) -> dict[str, Result]:
        return await self.read(0x3030, 43)

    async def get_device_name(self):
        device_name = await self.client.read_gatt_char(self.DEVICE_NAME_UUID)  # Read the device name from the BLE device
        return "".join(map(chr, device_name))

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