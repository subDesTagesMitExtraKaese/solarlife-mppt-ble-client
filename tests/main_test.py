import importlib
import sys
import unittest

sys.path.append("..")


class TestMain(unittest.TestCase):
    def test_main(self):
        module = importlib.import_module("main")
        self.assertIsNotNone(module)


if __name__ == "__main__":
    unittest.main()
