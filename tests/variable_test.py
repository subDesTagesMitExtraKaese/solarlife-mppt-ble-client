from itertools import groupby

import unittest
import sys
sys.path.append("..")

from src.variables import variables

class TestVariables(unittest.TestCase):
    def test_multiplier_func_exclusion(self):
        for variable in variables:
            if variable.multiplier and variable.func:
                result = variable.func(0)
                self.assertTrue(isinstance(result, (int, float)))
    def test_func_32_bit_exclusion(self):
        for variable in variables:
            if variable.is_32_bit:
                self.assertIsNone(variable.func)
    def test_common_lengths(self):
        for key, group in groupby(variables, lambda x: x.address):
            is_32_bit = next(group).is_32_bit
            for variable in group:
                self.assertEqual(variable.is_32_bit, is_32_bit)
    def test_indexer(self):
        variable = variables['battery_percentage']
        self.assertEqual('battery_percentage', variable.name)
        variable = variables.get('battery_percentage')
        self.assertEqual('battery_percentage', variable.name)
        self.assertIsNotNone(variables.items())
    def test_slice(self):
        x = variables[4:12]
        self.assertEqual(8, len(x))
if __name__ == "__main__":
    unittest.main()