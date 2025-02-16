import unittest
import sys
sys.path.append("..")

class TestMain(unittest.TestCase):
    def test_main(self):
        import main
if __name__ == "__main__":
    unittest.main()