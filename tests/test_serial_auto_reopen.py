from pathlib import Path
import unittest


class SerialAutoReopenContractTests(unittest.TestCase):
    def test_open_serial_falls_back_to_auto_when_static_dev_path_disappears(self):
        source = Path("library/lcd/lcd_comm.py").read_text(encoding="utf-8")
        self.assertIn("Static COM port {self.com_port} disappeared", source)
        self.assertIn('self.com_port = "AUTO"', source)
        self.assertIn("return self.openSerial()", source)


if __name__ == "__main__":
    unittest.main()
