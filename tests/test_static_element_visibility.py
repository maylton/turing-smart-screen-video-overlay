from __future__ import annotations

import copy
import sys
import types
import unittest

serial_stub = types.ModuleType("serial")
serial_stub.Serial = object
serial_stub.SerialException = Exception
serial_stub.SerialTimeoutException = Exception
serial_tools_stub = types.ModuleType("serial.tools")
serial_ports_stub = types.ModuleType("serial.tools.list_ports")
serial_ports_stub.comports = lambda: []
serial_tools_stub.list_ports = serial_ports_stub
serial_stub.tools = serial_tools_stub
sys.modules.setdefault("serial", serial_stub)
sys.modules.setdefault("serial.tools", serial_tools_stub)
sys.modules.setdefault("serial.tools.list_ports", serial_ports_stub)
usb_stub = types.ModuleType("usb")
usb_core_stub = types.ModuleType("usb.core")
usb_util_stub = types.ModuleType("usb.util")
usb_core_stub.find = lambda *args, **kwargs: None
usb_stub.core = usb_core_stub
usb_stub.util = usb_util_stub
sys.modules.setdefault("usb", usb_stub)
sys.modules.setdefault("usb.core", usb_core_stub)
sys.modules.setdefault("usb.util", usb_util_stub)
crypto_stub = types.ModuleType("Crypto")
crypto_cipher_stub = types.ModuleType("Crypto.Cipher")
crypto_des_stub = types.ModuleType("Crypto.Cipher.DES")
crypto_cipher_stub.DES = crypto_des_stub
crypto_stub.Cipher = crypto_cipher_stub
sys.modules.setdefault("Crypto", crypto_stub)
sys.modules.setdefault("Crypto.Cipher", crypto_cipher_stub)
sys.modules.setdefault("Crypto.Cipher.DES", crypto_des_stub)
lcd_simulated_stub = types.ModuleType("library.lcd.lcd_simulated")


class LcdSimulatedStub:
    def __init__(self, *args, **kwargs):
        pass


lcd_simulated_stub.LcdSimulated = LcdSimulatedStub
sys.modules.setdefault("library.lcd.lcd_simulated", lcd_simulated_stub)

from library import config

config.CONFIG_DATA.setdefault("display", {})["REVISION"] = "SIMU"
from library import display as display_module


class FakeLcd:
    def __init__(self):
        self.bitmaps = []
        self.texts = []

    def DisplayBitmap(self, **kwargs):
        self.bitmaps.append(kwargs)

    def DisplayText(self, **kwargs):
        self.texts.append(kwargs)


class StaticElementVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.old_theme_data = config.THEME_DATA
        self.display = display_module.Display.__new__(display_module.Display)
        self.display.lcd = FakeLcd()

    def tearDown(self):
        config.THEME_DATA = self.old_theme_data

    def set_theme(self, **sections):
        config.THEME_DATA = {"PATH": "/theme/", "display": {}}
        config.THEME_DATA.update(sections)

    def test_static_image_without_show_is_drawn(self):
        self.set_theme(static_images={"logo": {"PATH": "logo.png"}})
        self.display.display_static_images()
        self.assertEqual(len(self.display.lcd.bitmaps), 1)

    def test_static_image_with_show_true_is_drawn(self):
        self.set_theme(static_images={"logo": {"PATH": "logo.png", "SHOW": True}})
        self.display.display_static_images()
        self.assertEqual(len(self.display.lcd.bitmaps), 1)

    def test_static_image_with_show_false_is_not_drawn(self):
        self.set_theme(static_images={"logo": {"PATH": "logo.png", "SHOW": False}})
        self.display.display_static_images()
        self.assertEqual(self.display.lcd.bitmaps, [])

    def test_static_text_without_show_is_drawn(self):
        self.set_theme(static_text={"title": {"TEXT": "Hello"}})
        self.display.display_static_text()
        self.assertEqual(len(self.display.lcd.texts), 1)

    def test_static_text_with_show_true_is_drawn(self):
        self.set_theme(static_text={"title": {"TEXT": "Hello", "SHOW": True}})
        self.display.display_static_text()
        self.assertEqual(len(self.display.lcd.texts), 1)

    def test_static_text_with_show_false_is_not_drawn(self):
        self.set_theme(static_text={"title": {"TEXT": "Hello", "SHOW": False}})
        self.display.display_static_text()
        self.assertEqual(self.display.lcd.texts, [])

    def test_hidden_entry_does_not_block_next_visible_entry(self):
        self.set_theme(
            static_text={
                "hidden": {"TEXT": "Hidden", "SHOW": False},
                "visible": {"TEXT": "Visible"},
            }
        )
        self.display.display_static_text()
        self.assertEqual(len(self.display.lcd.texts), 1)
        self.assertEqual(self.display.lcd.texts[0]["text"], "Visible")

    def test_renderer_does_not_modify_theme_data(self):
        self.set_theme(
            static_images={"logo": {"PATH": "logo.png", "SHOW": False}},
            static_text={"title": {"TEXT": "Hello"}},
        )
        original = copy.deepcopy(config.THEME_DATA)
        self.display.display_static_images()
        self.display.display_static_text()
        self.assertEqual(config.THEME_DATA, original)


if __name__ == "__main__":
    unittest.main()
