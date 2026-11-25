import sys
import unittest

sys.path.append("..")

from src.protocol import LumiaxClient, Result
from src.registers import registers


class TestTransaction(unittest.TestCase):
    def setUp(self):
        self.client = LumiaxClient()

    def test_1(self):
        device_id = 0x01
        byte_count = 56
        count = int(byte_count / 2)
        start_address = 0x3011
        end_address = 0x302C

        self.assertEqual(end_address - start_address + 1, count)

        send_buf = bytes([0x01, 0x04, 0x30, 0x11, 0x00, 0x1C, 0xAE, 0xC6])
        self.assertEqual(
            send_buf, self.client.get_read_command(device_id, start_address, count)
        )

        recv_buf = bytes(
            [
                0x01,
                0x04,
                0x38,
                0x41,
                0x01,
                0x13,
                0xF7,
                0x00,
                0x0F,
                0x00,
                0x00,
                0x04,
                0x38,
                0x04,
                0xB0,
                0x04,
                0x60,
                0x04,
                0x74,
                0x05,
                0x00,
                0x04,
                0xB0,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x01,
                0x2C,
                0x03,
                0x20,
                0x03,
                0x20,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x3C,
                0x00,
                0x00,
                0xB1,
                0xB7,
            ]
        )
        self.assertEqual(len(recv_buf) - 5, byte_count)

        results = self.client.parse(start_address, recv_buf)
        for result in results:
            self.assertIsNotNone(result.value, f"{result.name} ({hex(result.address)})")
        self.assertGreaterEqual(len(results), byte_count / 2)
        self.assertEqual(hex(results[0].address), hex(start_address))
        self.assertEqual(hex(results[-1].address), hex(end_address))

    def test_2(self):
        device_id = 0x01
        byte_count = 80
        count = int(byte_count / 2)
        start_address = 0x3030
        end_address = start_address + count - 1

        self.assertEqual(end_address - start_address + 1, count)

        send_buf = bytes([0x01, 0x04, 0x30, 0x30, 0x00, 0x28, 0xFF, 0x1B])
        self.assertEqual(
            send_buf, self.client.get_read_command(device_id, start_address, count)
        )

        recv_buf = bytes(
            [
                0x01,
                0x04,
                0x50,
                0x00,
                0x01,
                0x00,
                0x00,
                0x09,
                0x60,
                0x00,
                0x00,
                0x00,
                0x20,
                0x00,
                0x01,
                0x09,
                0xC4,
                0x0B,
                0x54,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x1F,
                0x09,
                0x24,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x09,
                0x24,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x02,
                0x44,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x70,
                0x04,
            ]
        )
        self.assertEqual(len(recv_buf) - 5, byte_count)

        results = self.client.parse(start_address, recv_buf)
        for result in results:
            self.assertIsNotNone(result.value, f"{result.name} ({hex(result.address)})")
        self.assertGreaterEqual(len(results), byte_count / 2)
        self.assertEqual(hex(results[0].address), hex(start_address))
        self.assertEqual(results[-1].is_32_bit, True)
        self.assertEqual(hex(results[-1].address), hex(end_address - 1))

    def test_3(self):
        device_id = 0x01
        byte_count = 2
        count = int(byte_count / 2)
        start_address = 0x3000
        end_address = start_address + count - 1

        self.assertEqual(end_address - start_address + 1, count)

        send_buf = bytes([0x01, 0x04, 0x30, 0x00, 0x00, 0x01, 0x3E, 0xCA])
        self.assertEqual(
            send_buf, self.client.get_read_command(device_id, start_address, count)
        )

        recv_buf = bytes([0x01, 0x04, 0x02, 0x17, 0x70, 0xB7, 0x24])
        self.assertEqual(len(recv_buf) - 5, byte_count)

        results = self.client.parse(start_address, recv_buf)
        for result in results:
            self.assertIsNotNone(result.value, f"{result.name} ({hex(result.address)})")
        self.assertGreaterEqual(len(results), byte_count / 2)
        self.assertEqual(hex(results[0].address), hex(start_address))
        self.assertEqual(hex(results[-1].address), hex(end_address))
        self.assertEqual(results[0].value, 60.0)

    def test_4(self):
        device_id = 0x01
        byte_count = 58
        count = int(byte_count / 2)
        start_address = 0x8FF0
        end_address = start_address + count - 1

        self.assertEqual(end_address - start_address + 1, count)

        send_buf = bytes([0x01, 0x03, 0x8F, 0xF0, 0x00, 0x1D, 0xAF, 0x24])
        self.assertEqual(
            send_buf, self.client.get_read_command(device_id, start_address, count)
        )

        recv_buf = bytes(
            [
                0x01,
                0x03,
                0x3A,
                0x41,
                0x01,
                0x13,
                0xF7,
                0x00,
                0x0F,
                0x00,
                0x00,
                0x04,
                0x38,
                0x04,
                0xB0,
                0x04,
                0x60,
                0x04,
                0x74,
                0x05,
                0x00,
                0x04,
                0xB0,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x01,
                0x2C,
                0x03,
                0x20,
                0x03,
                0x20,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x09,
                0x60,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x3C,
                0x00,
                0x00,
                0x7B,
                0xB4,
            ]
        )
        self.assertEqual(len(recv_buf) - 5, byte_count)

        results = self.client.parse(start_address, recv_buf)
        for result in results:
            self.assertIsNotNone(result.value, f"{result.name} ({hex(result.address)})")
        self.assertEqual(hex(results[0].address), hex(start_address))
        self.assertEqual(hex(results[-1].address), hex(end_address))

    def test_5(self):
        device_id = 0x01
        byte_count = 20
        count = int(byte_count / 2)
        start_address = 0x9017
        end_address = start_address + count - 1

        self.assertEqual(end_address - start_address + 1, count)

        send_buf = bytes([0x01, 0x03, 0x90, 0x17, 0x00, 0x0A, 0x58, 0xC9])
        self.assertEqual(
            send_buf, self.client.get_read_command(device_id, start_address, count)
        )

        recv_buf = bytes(
            [
                0x01,
                0x03,
                0x14,
                0x00,
                0x34,
                0x00,
                0x24,
                0x00,
                0x00,
                0x00,
                0x01,
                0x00,
                0x01,
                0x00,
                0x12,
                0x00,
                0x01,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x01,
                0x45,
                0x85,
            ]
        )
        self.assertEqual(len(recv_buf) - 5, byte_count)

        results = self.client.parse(start_address, recv_buf)
        for result in results:
            self.assertIsNotNone(result.value, f"{result.name} ({hex(result.address)})")
        self.assertGreaterEqual(len(results), byte_count / 2)
        self.assertEqual(hex(results[0].address), hex(start_address))
        self.assertEqual(hex(results[-1].address), hex(end_address))

    def test_6(self):
        device_id = 0x01
        byte_count = 20
        count = int(byte_count / 2)
        start_address = 0x9021
        end_address = start_address + count - 1

        self.assertEqual(end_address - start_address + 1, count)

        items = [
            register
            for register in registers
            if register.address >= start_address and register.address <= end_address
        ]
        values = [
            "Lithium",
            10.6,
            11.8,
            14.4,
            14.7,
            13.6,
            "Auto",
            14.4,
            14.0,
            "Normal charging",
        ]
        results = [
            Result(**vars(register), value=value)
            for register, value in zip(items, values)
        ]

        send_buf = bytes(
            [
                0x01,
                0x10,
                0x90,
                0x21,
                0x00,
                0x0A,
                0x14,
                0x00,
                0x00,
                0x04,
                0x24,
                0x04,
                0x9C,
                0x05,
                0xA0,
                0x05,
                0xBE,
                0x05,
                0x50,
                0x00,
                0x00,
                0x05,
                0xA0,
                0x05,
                0x78,
                0x00,
                0x00,
                0xCC,
                0xE7,
            ]
        )
        start_address, data = self.client.get_write_command(device_id, results)
        self.assertEqual(send_buf, data)

        recv_buf = bytes([0x01, 0x10, 0x90, 0x21, 0x00, 0x0A, 0x3D, 0x04])
        self.assertEqual(len(recv_buf) - 4, 4)
        results = self.client.parse(start_address, recv_buf)
        self.assertListEqual(list(results), [])

    def test_7(self):
        # Captured from a real controller (12 V, load output enabled but unloaded).
        recv_buf = bytes.fromhex(
            "0104520001019E04B0000000200001083406400018000000"
            "050000000000000000000000000000000000000000005505"
            "23000000000000052800000000000000D200000000000000"
            "010B580000000A134F0000050FEF1D"
        )
        results = self.client.parse(0x3030, recv_buf)
        self.assertEqual(len(recv_buf) - 5, recv_buf[2])
        self.assertAlmostEqual(results["battery_voltage"].value, 13.15)
        self.assertAlmostEqual(results["battery_current"].value, 0.0)
        self.assertAlmostEqual(results["load_voltage"].value, 13.2)
        self.assertAlmostEqual(results["load_current"].value, 0.0)
        self.assertAlmostEqual(results["load_power"].value, 0.0)
        self.assertTrue(results["load_is_enabled"].value)
        self.assertEqual("Light load", results["load_state"].value)
        self.assertEqual(85.0, results["battery_percentage"].value)


if __name__ == "__main__":
    unittest.main()
