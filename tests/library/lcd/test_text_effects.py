from __future__ import annotations

import unittest
from PIL import Image, ImageFont
from library.lcd.lcd_comm import LcdComm, Orientation


class DummyLcd(LcdComm):
    def InitializeComm(self): pass
    def Reset(self): pass
    def Clear(self): pass
    def ScreenOff(self): pass
    def ScreenOn(self): pass
    def SetBrightness(self, level: int): pass
    def SetOrientation(self, orientation: Orientation):
        self.orientation = orientation
    def DisplayPILImage(self, image, x=0, y=0, image_width=0, image_height=0):
        self.last_image = image


class TextEffectsTests(unittest.TestCase):
    def setUp(self):
        self.lcd = DummyLcd(
            com_port="TEST",
            display_width=240,
            display_height=240,
            update_queue=None,
        )

    def test_effect_padding(self):
        self.assertGreaterEqual(
            self.lcd._text_effect_padding({
                "GLOW": {"ENABLED": True, "BLUR_RADIUS": 8}
            }),
            16,
        )

    def test_glow_keeps_rgba(self):
        image = Image.new("RGBA", (240, 240), (0, 0, 0, 0))
        font = ImageFont.load_default()
        rendered = self.lcd._draw_text_effects(
            image,
            (120, 120),
            "Glow",
            font,
            (255, 255, 255),
            "center",
            "mm",
            {
                "GLOW": {
                    "ENABLED": True,
                    "COLOR": [80, 140, 255, 180],
                    "BLUR_RADIUS": 8,
                    "INTENSITY": 2,
                }
            },
        )
        self.assertEqual(rendered.mode, "RGBA")
        self.assertIsNotNone(rendered.getchannel("A").getbbox())


if __name__ == "__main__":
    unittest.main()
