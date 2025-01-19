import unittest
import sys
sys.path.append("..")

from src.parser import ModbusParser

class TestParser(unittest.TestCase):
    def setUp(self):
        self.parser = ModbusParser()

    def test_includes_names(self):
        names = [
            "equipment_id",
            "run_days",
            "solar_panel_is_charging",
            "solar_panel_is_night",
            "solar_panel_charge_state",
            "load_is_enabled",
            "load_state",
            "battery_empty_times",
            "battery_full_times",
            "battery_percentage",
            "battery_voltage",
            "battery_current",
            "battery_power",
            "load_voltage",
            "load_current",
            "load_power",
            "solar_panel_voltage",
            "solar_panel_current",
            "solar_panel_power",
            "solar_panel_daily_energy",
            "solar_panel_total_energy",
            "load_daily_energy",
            "load_total_energy",
        ]
        for name in names:
            self.assertIn(name, [v.name for v in self.parser.variables], f"variable {name} doesn't exist anymore")
    def test_excludes_names(self):
        bad_names = [
            "battery_full_level",
            "battery_state_1",
            "battery_state_2",
            "solar_panel_state",
            "temperature_1",
            "temperature_2",
        ]
        for name in bad_names:
            self.assertNotIn(name, [v.name for v in self.parser.variables], f"variable {name} still exists")

    def test_multiplier_func_exclusion(self):
        for variable in self.parser.variables:
            if variable.multiplier:
                self.assertIsNone(variable.func)
    def test_func_32_bit_exclusion(self):
        for variable in self.parser.variables:
            if variable.is_32_bit:
                self.assertIsNone(variable.func)
if __name__ == "__main__":
    unittest.main()