import sys
import unittest

from .compatibility_test import TestCompat
from .framing_test import TestFraming
from .main_test import TestMain
from .register_test import TestRegisters, TestUniqueNames
from .transaction_test import TestTransaction

TESTS = (TestCompat, TestFraming, TestMain, TestRegisters, TestUniqueNames, TestTransaction)

if __name__ == "__main__":
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(test) for test in TESTS)
    verbosity = 2 if "-v" in sys.argv else 1
    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    raise SystemExit(not result.wasSuccessful())