import asyncio
import struct

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.exc import BleakError

from src.protocol import LumiaxClient, ProtocolError, Result, ResultContainer


class BleClient(LumiaxClient):
    DEVICE_NAME_UUID = "00002a00-0000-1000-8000-00805f9b34fb"
    NOTIFY_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
    WRITE_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"

    def __init__(self, mac_address: str):
        self.client = BleakClient(mac_address)
        self.buffer = bytearray()
        self.response_queue = asyncio.Queue()
        self.lock = asyncio.Lock()
        # Device id and function code of the response we are waiting for.
        self.expected: tuple[int, int] | None = None
        # Id the controller answers with, learned from the first response. The
        # first request goes to the broadcast id, the answers carry the
        # controller's own id (protocol default 1).
        self.response_id: int | None = None
        # Byte count the pending read asks for; a candidate that announces a
        # different length is a shifted frame and must not block the real one.
        self.expected_byte_count: int | None = None
        super().__init__()

    async def __aenter__(self):
        await self.client.connect()  # Connect to the BLE device
        await self.client.start_notify(
            self.NOTIFY_UUID, self.notification_handler
        )  # Start receiving notifications
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.client.stop_notify(self.NOTIFY_UUID)  # Stop receiving notifications
        try:
            await self.client.disconnect()  # Disconnect from the BLE device
        except EOFError:
            pass

    def notification_handler(
        self, characteristic: BleakGATTCharacteristic, data: bytearray
    ):
        if characteristic.uuid != self.NOTIFY_UUID:
            return
        if self.expected is None:
            # Nothing is pending. A late notification belongs to a transaction
            # that already timed out, so it must not reach the next one.
            self.buffer = bytearray()
            return

        self.buffer += data
        device_id, function_code = self.expected
        while True:
            frame = self.take_frame(
                self.buffer,
                device_id,
                function_code,
                self.response_id,
                self.expected_byte_count,
            )
            if frame is None:
                return
            try:
                results = self.parse(self.start_address, frame)
            except (ProtocolError, ValueError, IndexError, struct.error) as e:
                print(f"Discarding frame 0x{frame.hex()}: {e}")
                # The frame was shifted by a stray byte; resynchronise inside
                # the same bytes instead of throwing them away.
                self.buffer = bytearray(frame[1:]) + self.buffer
                if not self.buffer:
                    return
                continue
            self.response_id = frame[0]
            self.response_queue.put_nowait(results)
            return

    async def read(
        self, start_address: int, count: int, repeat=10, timeout=2
    ) -> ResultContainer:
        async with self.lock:
            self.start_address = start_address
            command = self.get_read_command(self.device_id, start_address, count)
            self.expected = (command[0], command[1])
            self.expected_byte_count = count * 2
            self.response_queue = asyncio.Queue()  # Clear the queue
            try:
                i = 0
                # send the command multiple times
                while i < repeat:
                    i += 1
                    self.buffer = bytearray()
                    await self.client.write_gatt_char(self.WRITE_UUID, command)
                    try:
                        # Wait for either a response or timeout
                        return await asyncio.wait_for(
                            self.response_queue.get(), timeout=timeout
                        )
                    except TimeoutError:
                        if self.buffer:
                            print(f"Got partial response: 0x{self.buffer.hex()}")
                        print("Repeating read command...")
                return ResultContainer([])
            finally:
                self.expected = None

    async def request_details(self) -> ResultContainer:
        return await self.read(0x3030, 41)

    async def request_parameters(self) -> ResultContainer:
        return await self.read(0x9021, 12)

    async def write(
        self, results: list[Result], repeat=10, timeout=2
    ) -> ResultContainer:
        async with self.lock:
            start_address, command = self.get_write_command(self.device_id, results)
            self.start_address = start_address
            self.expected = (command[0], command[1])
            self.response_queue = asyncio.Queue()  # Clear the queue
            try:
                i = 0
                # send the command multiple times
                while i < repeat:
                    i += 1
                    self.buffer = bytearray()
                    await self.client.write_gatt_char(self.WRITE_UUID, command)
                    print(f"Wrote command 0x{command.hex()}")
                    try:
                        # Wait for either a response or timeout
                        await asyncio.wait_for(
                            self.response_queue.get(), timeout=timeout
                        )
                        return ResultContainer(results)
                    except TimeoutError:
                        if self.buffer:
                            print(f"Got partial response: 0x{self.buffer.hex()}")
                        print("Repeating write command...")
                return ResultContainer([])
            finally:
                self.expected = None

    async def get_device_name(self):
        device_name = await self.client.read_gatt_char(
            self.DEVICE_NAME_UUID
        )  # Read the device name from the BLE device
        return "".join(map(chr, device_name))

    async def list_services(self):
        service_text = "[Service]          "
        charact_text = "  [Characteristic] "
        descrip_text = "    [Descriptor]   "
        value_text = "      Value = "
        for service in self.client.services:
            print(service_text, service)
            for char in service.characteristics:
                print(charact_text, char, ",".join(char.properties))
                for descriptor in char.descriptors:
                    try:
                        print(descrip_text, descriptor)
                        value = await self.client.read_gatt_descriptor(
                            descriptor.handle
                        )
                        print(value_text, "0x" + value.hex())
                    except (BleakError, OSError) as error:
                        print(f"Could not read descriptor: {error}")
