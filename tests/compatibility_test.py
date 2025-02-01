from itertools import groupby

import unittest
import sys
sys.path.append("..")

from src.variables import variables

class TestCompat(unittest.TestCase):
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
            self.assertIn(name, [v.name for v in variables], f"variable {name} doesn't exist anymore")
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
            self.assertNotIn(name, [v.name for v in variables], f"variable {name} still exists")

    def test_units(self):
        unit_mapping = {
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
        for name, unit in unit_mapping.items():
            items = [v for v in variables if name == v.name]
            self.assertTrue(items, f"variable {name} doesn't exist anymore")
            self.assertEqual(items[0].unit, unit)
