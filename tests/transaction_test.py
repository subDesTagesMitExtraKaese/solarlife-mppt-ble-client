import unittest
import sys
sys.path.append("..")

from src.protocol import LumiaxClient

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
        self.assertEqual(send_buf, self.client.get_read_command(device_id, start_address, count))

        recv_buf = bytes([0x01, 0x04, 0x38, 0x41, 0x01, 0x13, 0xF7, 0x00, 0x0F, 0x00, 0x00, 0x04, 0x38, 0x04, 0xB0, 0x04, 0x60, 0x04, 0x74, 0x05, 0x00, 0x04,0xB0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x2C, 0x03, 0x20, 0x03, 0x20, 0x00, 0x00, 0x00,0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x3C, 0x00, 0x00, 0xB1, 0xB7])
        self.assertEqual(len(recv_buf) - 5, byte_count)

        results = self.client.parse(start_address, recv_buf)
        for variable, value in results:
            self.assertIsNotNone(value, f"{variable.name} ({hex(variable.address)})")
        self.assertGreaterEqual(len(results), byte_count / 2)
        self.assertEqual(hex(results[0][0].address), hex(start_address))
        self.assertEqual(hex(results[-1][0].address), hex(end_address))

    def test_2(self):
        device_id = 0x01
        byte_count = 80
        count = int(byte_count / 2)
        start_address = 0x3030
        end_address = start_address + count - 1

        self.assertEqual(end_address - start_address + 1, count)

        send_buf = bytes([0x01, 0x04, 0x30, 0x30, 0x00, 0x28, 0xFF, 0x1B])
        self.assertEqual(send_buf, self.client.get_read_command(device_id, start_address, count))

        recv_buf = bytes([0x01, 0x04, 0x50, 0x00, 0x01, 0x00, 0x00, 0x09, 0x60, 0x00, 0x00, 0x00, 0x20, 0x00, 0x01, 0x09, 0xC4, 0x0B, 0x54, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1F, 0x09, 0x24, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x09, 0x24, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0x44, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x70, 0x04])
        self.assertEqual(len(recv_buf) - 5, byte_count)

        results = self.client.parse(start_address, recv_buf)
        for variable, value in results:
            self.assertIsNotNone(value, f"{variable.name} ({hex(variable.address)})")
        self.assertGreaterEqual(len(results), byte_count / 2)
        self.assertEqual(hex(results[0][0].address), hex(start_address))
        self.assertEqual(results[-1][0].is_32_bit, True)
        self.assertEqual(hex(results[-1][0].address), hex(end_address-1))

    def test_3(self):
        device_id = 0x01
        byte_count = 2
        count = int(byte_count / 2)
        start_address = 0X3000
        end_address = start_address + count - 1

        self.assertEqual(end_address - start_address + 1, count)

        send_buf = bytes([0x01, 0x04, 0x30, 0x00, 0x00, 0x01, 0x3E, 0xCA])
        self.assertEqual(send_buf, self.client.get_read_command(device_id, start_address, count))

        recv_buf = bytes([0x01, 0x04, 0x02, 0x17, 0x70, 0xB7, 0x24])
        self.assertEqual(len(recv_buf) - 5, byte_count)

        results = self.client.parse(start_address, recv_buf)
        for variable, value in results:
            self.assertIsNotNone(value, f"{variable.name} ({hex(variable.address)})")
        self.assertGreaterEqual(len(results), byte_count / 2)
        self.assertEqual(hex(results[0][0].address), hex(start_address))
        self.assertEqual(hex(results[-1][0].address), hex(end_address))
        self.assertEqual(results[0][1], 60.0)

    def test_4(self):
        device_id = 0x01
        byte_count = 58
        count = int(byte_count / 2)
        start_address = 0X8FF0
        end_address = start_address + count - 1

        self.assertEqual(end_address - start_address + 1, count)

        send_buf = bytes([0x01, 0x03, 0x8F, 0xF0, 0x00, 0x1D, 0xAF, 0x24])
        self.assertEqual(send_buf, self.client.get_read_command(device_id, start_address, count))

        recv_buf = bytes([0x01, 0x03, 0x3A, 0x41, 0x01, 0x13, 0xF7, 0x00, 0x0F, 0x00, 0x00, 0x04, 0x38, 0x04, 0xB0, 0x04, 0x60, 0x04, 0x74, 0x05, 0x00, 0x04, 0xB0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x2C, 0x03, 0x20, 0x03, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x09, 0x60, 0x00, 0x00, 0x00, 0x00, 0x00, 0x3C, 0x00, 0x00, 0x7B, 0xB4])
        self.assertEqual(len(recv_buf) - 5, byte_count)

        results = self.client.parse(start_address, recv_buf)
        for variable, value in results:
            self.assertIsNotNone(value, f"{variable.name} ({hex(variable.address)})")
        self.assertEqual(hex(results[0][0].address), hex(start_address))
        self.assertEqual(hex(results[-1][0].address), hex(end_address))

    def test_5(self):
        device_id = 0x01
        byte_count = 20
        count = int(byte_count / 2)
        start_address = 0x9017
        end_address = start_address + count - 1

        self.assertEqual(end_address - start_address + 1, count)

        send_buf = bytes([0x01, 0x03, 0x90, 0x17, 0x00, 0x0A, 0x58, 0xC9])
        self.assertEqual(send_buf, self.client.get_read_command(device_id, start_address, count))

        recv_buf = bytes([0x01, 0x03, 0x14, 0x00, 0x34, 0x00, 0x24, 0x00, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x12, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x45, 0x85])
        self.assertEqual(len(recv_buf) - 5, byte_count)

        results = self.client.parse(start_address, recv_buf)
        for variable, value in results:
            self.assertIsNotNone(value, f"{variable.name} ({hex(variable.address)})")
        self.assertGreaterEqual(len(results), byte_count / 2)
        self.assertEqual(hex(results[0][0].address), hex(start_address))
        self.assertEqual(hex(results[-1][0].address), hex(end_address))

    def test_6(self):
        device_id = 0x01
        byte_count = 20
        count = int(byte_count / 2)
        start_address = 0x9021
        end_address = start_address + count - 1

        self.assertEqual(end_address - start_address + 1, count)

        variables = [v for v in self.client.variables if v.address >= start_address and v.address <= end_address]
        values = list(zip(variables, ["Lithium", 10.6, 11.8, 14.4, 14.7, 13.6, "Auto", 14.4, 14.0, "Normal charging"]))

        send_buf = bytes([0x01, 0x10, 0x90, 0x21, 0x00, 0x0A, 0x14, 0x00, 0x00, 0x04, 0x24, 0x04, 0x9C, 0x05, 0xA0, 0x05, 0xBE, 0x05, 0x50, 0x00, 0x00, 0x05, 0xA0, 0x05, 0x78, 0x00, 0x00, 0xCC, 0xE7])
        self.assertEqual(send_buf, self.client.get_write_command(device_id, values))

        recv_buf = bytes([0x01, 0x10, 0x90, 0x21, 0x00, 0x0A, 0x3D, 0x04])
        self.assertEqual(len(recv_buf) - 4, 4)
        results = self.client.parse(start_address, recv_buf)
        self.assertListEqual(results, [])
if __name__ == "__main__":
    unittest.main()