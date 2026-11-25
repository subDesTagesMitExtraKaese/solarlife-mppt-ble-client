import asyncio
import sys
import unittest

sys.path.append("..")

from src.bleclient import BleClient

# Real 87 byte details response captured from a 12 V controller.
FRAME = bytes.fromhex(
    "0104520001019E04B0000000200001083406400018000000"
    "050000000000000000000000000000000000000000005505"
    "23000000000000052800000000000000D200000000000000"
    "010B580000000A134F0000050FEF1D"
)
START_ADDRESS = 0x3030


class Characteristic:
    uuid = BleClient.NOTIFY_UUID


class TestFraming(unittest.TestCase):
    def setUp(self):
        self.client = BleClient("00:00:00:00:00:00")
        self.client.start_address = START_ADDRESS
        self.client.expected = (FRAME[0], FRAME[1])
        self.client.expected_byte_count = FRAME[2]
        self.client.response_queue = asyncio.Queue()

    def feed(self, data: bytes) -> None:
        self.client.notification_handler(Characteristic(), bytearray(data))

    def results(self) -> list:
        found = []
        while not self.client.response_queue.empty():
            found.append(self.client.response_queue.get_nowait())
        return found

    def test_frame_split_across_notifications(self):
        for index in range(0, len(FRAME), 20):
            self.assertEqual([], self.results())
            self.feed(FRAME[index:index + 20])
        results = self.results()
        self.assertEqual(1, len(results))
        self.assertAlmostEqual(0.0, results[0]["load_current"].value)

    def test_late_byte_before_response(self):
        self.feed(b"\x41" + FRAME)
        results = self.results()
        self.assertEqual(1, len(results))
        self.assertAlmostEqual(13.2, results[0]["load_voltage"].value)

    def test_garbage_before_response(self):
        self.feed(b"\x00\xff\xfe\x01" + FRAME)
        self.assertEqual(1, len(self.results()))

    def test_garbage_inside_frame_is_rejected(self):
        # Bytes injected inside a frame cannot be resynchronised.
        self.feed(FRAME[:40])
        self.feed(b"\x99\x98" + FRAME[40:])
        self.assertEqual([], self.results())

    def test_crc_failure_resynchronises(self):
        broken = bytearray(FRAME)
        broken[-1] ^= 0xFF
        self.feed(bytes(broken) + FRAME)
        results = self.results()
        self.assertEqual(1, len(results))
        self.assertAlmostEqual(13.2, results[0]["load_voltage"].value)

    def test_duplicate_frame_yields_one_reading(self):
        self.feed(FRAME + FRAME)
        self.assertEqual(1, len(self.results()))

    def test_ignores_notifications_without_request(self):
        self.client.expected = None
        self.feed(FRAME)
        self.assertEqual([], self.results())
        self.assertEqual(0, len(self.client.buffer))

    def test_broadcast_request_accepts_controller_id(self):
        # The first request is addressed to the broadcast id, but the answer
        # carries the controller's own id (1 by protocol default).
        self.client.expected = (0xFE, 0x04)
        self.client.response_id = None
        self.client.expected_byte_count = FRAME[2]
        self.feed(FRAME)
        self.assertEqual(1, len(self.results()))
        self.assertEqual(1, self.client.response_id)

    def test_requests_use_learned_controller_id(self):
        self.client.device_id = 0x01
        command = self.client.get_read_command(self.client.device_id, START_ADDRESS, 41)
        self.assertEqual(bytes([0x01, 0x04, 0x30, 0x30, 0x00, 0x29]), command[:6])

    def test_foreign_id_is_not_accepted_once_known(self):
        self.client.expected = (0xFE, 0x04)
        self.client.response_id = 0x02
        self.feed(FRAME)
        self.assertEqual([], self.results())

    def test_write_acknowledgement_is_eight_bytes(self):
        # Write acknowledgements have no byte-count field and are always 8 bytes.
        self.assertEqual(8, self.client.frame_length(0x10, 0))

    def test_wrong_range_is_not_parsed(self):
        # A response to the parameter block must not be used for the details.
        self.client.expected = (0x01, 0x03)
        self.feed(FRAME)
        self.assertEqual([], self.results())


if __name__ == "__main__":
    unittest.main()
