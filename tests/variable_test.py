from itertools import groupby

import unittest
import sys
sys.path.append("..")

from src.variables import variables

class TestVariables(unittest.TestCase):
    def test_multiplier_func_exclusion(self):
        for variable in variables:
            if variable.multiplier:
                self.assertIsNone(variable.func)
    def test_func_32_bit_exclusion(self):
        for variable in variables:
            if variable.is_32_bit:
                self.assertIsNone(variable.func)
    def test_common_lengths(self):
        for key, group in groupby(variables, lambda x: x.address):
            is_32_bit = next(group).is_32_bit
            for variable in group:
                self.assertEqual(variable.is_32_bit, is_32_bit)
if __name__ == "__main__":
    unittest.main()