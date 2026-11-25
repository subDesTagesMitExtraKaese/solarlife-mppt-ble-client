import re
import sys
import unittest
from itertools import groupby
from pathlib import Path
from typing import ClassVar

sys.path.append("..")

from src.registers import ValueKind, registers


class TestRegisters(unittest.TestCase):
    def test_formats_round_trip(self):
        samples = {
            "battery_voltage": 12.34,
            "battery_current": -1.25,
            "battery_power": -100,
            "manual_control_switch": "On",
            "solar_panel_charge_state": "Boost charge",
            "device_password": "1234",
            "mt_series_timing_period_1": 125,
        }
        for name, value in samples.items():
            register = registers[name]
            raw = register.format.encode(value)
            self.assertEqual(register.format.decode(raw), value)
    def test_common_lengths(self):
        for _, group in groupby(registers, lambda x: x.address):
            widths = {register.is_32_bit for register in group}
            self.assertEqual(1, len(widths))
    def test_overlap(self):
        for register in registers:
            if register.is_32_bit:
                overlapping = [r for r in registers if r.address == register.address + 1]
                self.assertEqual([], overlapping)
    def test_indexer(self):
        register = registers['battery_percentage']
        self.assertEqual('battery_percentage', register.name)
        register = registers.get('battery_percentage')
        self.assertEqual('battery_percentage', register.name)
        self.assertIsNotNone(registers.items())
    def test_slice(self):
        x = registers[4:12]
        self.assertEqual(8, len(x))
    def test_enum_decode(self):
        register = registers['solar_panel_charge_state']
        self.assertIs(register.format.kind, ValueKind.ENUM)
        self.assertEqual('Boost charge', register.format.decode(0b0010 << 2))
    def test_flag_decode(self):
        register = registers['solar_panel_is_charging']
        self.assertIs(register.format.kind, ValueKind.FLAG)
        self.assertFalse(register.format.decode(0))
        self.assertTrue(register.format.decode(1))
if __name__ == "__main__":
    unittest.main()


class TestUniqueNames(unittest.TestCase):
    # Ranges the clients poll. Inside one range a name must be unique, because
    # results and MQTT topics are keyed by name.
    READ_RANGES: ClassVar[list[tuple[int, int]]] = [(0x3030, 41), (0x9021, 12)]

    def test_names_unique_per_read_range(self):
        for start, count in self.READ_RANGES:
            names = [r.name for r in registers if start <= r.address < start + count]
            duplicates = {name for name in names if names.count(name) > 1}
            self.assertEqual(set(), duplicates, f"duplicate names in {hex(start)}+{count}")

    def test_ambiguous_names_resolve_to_a_polled_register(self):
        # Same name in a different controller block must not win the lookup.
        self.assertEqual(0x304B, registers["load_current"].address)
        self.assertEqual(0x304A, registers["load_voltage"].address)
        self.assertEqual(0x304C, registers["load_power"].address)
        self.assertEqual(0x3046, registers["battery_voltage"].address)
        self.assertEqual(0x3047, registers["battery_current"].address)
        self.assertEqual(0x3036, registers["environment_temperature"].address)
        self.assertEqual(0x3031, registers["run_days"].address)
        self.assertEqual(0x9021, registers["battery_type"].address)

    def test_generated_entities_pin_an_unambiguous_address(self):
        package = (Path(__file__).resolve().parents[1] / "esphome" / "packages" / "solarlife_mppt.yaml").read_text()
        entities = re.findall(r"- platform: solarlife_mppt\n(.*?)(?=\n  - platform:|\Z)", package, re.DOTALL)
        self.assertGreater(len(entities), 0)
        for entity in entities:
            name = re.search(r"^    register: (\S+)$", entity, re.MULTILINE).group(1)
            address = int(re.search(r"^    address: 0x([0-9A-Fa-f]+)$", entity, re.MULTILINE).group(1), 16)
            matches = [r for r in registers if r.name == name and r.address == address]
            self.assertEqual(1, len(matches), f"{name} at {hex(address)}")
            polled = any(start <= address < start + count for start, count in self.READ_RANGES + [(0x0000, 13)])
            self.assertTrue(polled, f"{name} at {hex(address)} is never polled")
