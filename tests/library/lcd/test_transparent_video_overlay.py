from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from library.lcd.lcd_comm import LcdComm, Orientation


class DummyLcd(LcdComm):
    def InitializeComm(self):
        pass

    def Reset(self):
        pass

    def Clear(self):
        pass

    def ScreenOff(self):
        pass

    def ScreenOn(self):
        pass

    def SetBrightness(self, level: int):
        pass

    def SetOrientation(self, orientation: Orientation):
        self.orientation = orientation

    def DisplayPILImage(
        self,
        image: Image.Image,
        x: int = 0,
        y: int = 0,
        image_width: int = 0,
        image_height: int = 0,
    ):
        self.last_image = image
        self.last_position = (x, y)


class TransparentVideoOverlayTests(unittest.TestCase):
    def setUp(self):
        self.lcd = DummyLcd(
            com_port="TEST",
            display_width=480,
            display_height=480,
            update_queue=None,
        )

    def test_video_overlay_canvas_is_fully_transparent(self):
        self.lcd.video_overlay_enabled = True
        canvas = self.lcd._make_widget_canvas((40, 20), (255, 0, 0))
        self.assertEqual(canvas.mode, "RGBA")
        self.assertEqual(canvas.getchannel("A").getextrema(), (0, 0))

    def test_video_overlay_ignores_captured_background_image(self):
        with tempfile.TemporaryDirectory() as directory:
            background = Path(directory) / "frame.png"
            Image.new("RGB", (100, 100), (12, 34, 56)).save(background)
            self.lcd.video_overlay_enabled = True
            canvas = self.lcd._make_widget_canvas(
                (20, 10),
                (255, 255, 255),
                str(background),
                crop_box=(5, 5, 25, 15),
            )
        self.assertEqual(canvas.mode, "RGBA")
        self.assertEqual(canvas.getchannel("A").getextrema(), (0, 0))

    def test_non_video_mode_keeps_legacy_solid_background(self):
        self.lcd.video_overlay_enabled = False
        canvas = self.lcd._make_widget_canvas((10, 5), (1, 2, 3))
        self.assertEqual(canvas.mode, "RGB")
        self.assertEqual(canvas.getpixel((0, 0)), (1, 2, 3))

    def test_non_video_mode_keeps_alpha_background(self):
        self.lcd.video_overlay_enabled = False
        canvas = self.lcd._make_widget_canvas((10, 5), (100, 20, 40, 128))
        self.assertEqual(canvas.mode, "RGBA")
        self.assertEqual(canvas.getpixel((0, 0)), (100, 20, 40, 128))

    def test_non_video_mode_keeps_legacy_background_crop(self):
        with tempfile.TemporaryDirectory() as directory:
            background = Path(directory) / "frame.png"
            Image.new("RGB", (30, 30), (10, 20, 30)).save(background)
            self.lcd.video_overlay_enabled = False
            canvas = self.lcd._make_widget_canvas(
                (10, 8),
                (255, 255, 255),
                str(background),
                crop_box=(5, 6, 15, 14),
            )
        self.assertEqual(canvas.mode, "RGB")
        self.assertEqual(canvas.size, (10, 8))
        self.assertEqual(canvas.getpixel((0, 0)), (10, 20, 30))


if __name__ == "__main__":
    unittest.main()
