import unittest

from PIL import Image

from library.lcd.lcd_simulated import LcdSimulated, _clip_image_to_screen


class SimulatedLcdClippingTests(unittest.TestCase):
    def test_negative_x_keeps_visible_center_slice(self):
        source = Image.new("RGB", (768, 480), (0, 0, 0))
        source.putpixel((144, 0), (255, 0, 0))
        source.putpixel((623, 479), (0, 255, 0))

        image, x, y, width, height = _clip_image_to_screen(source, -144, 0, 480, 480)

        self.assertIsNotNone(image)
        self.assertEqual((x, y), (0, 0))
        self.assertEqual((width, height), (480, 480))
        self.assertEqual(image.getpixel((0, 0)), (255, 0, 0))
        self.assertEqual(image.getpixel((479, 479)), (0, 255, 0))

    def test_negative_y_keeps_visible_lower_slice(self):
        source = Image.new("RGB", (480, 768), (0, 0, 0))
        source.putpixel((0, 144), (255, 0, 0))
        source.putpixel((479, 623), (0, 255, 0))

        image, x, y, width, height = _clip_image_to_screen(source, 0, -144, 480, 480)

        self.assertIsNotNone(image)
        self.assertEqual((x, y), (0, 0))
        self.assertEqual((width, height), (480, 480))
        self.assertEqual(image.getpixel((0, 0)), (255, 0, 0))
        self.assertEqual(image.getpixel((479, 479)), (0, 255, 0))

    def test_fully_offscreen_returns_no_image(self):
        source = Image.new("RGB", (120, 120), (255, 0, 0))

        image, x, y, width, height = _clip_image_to_screen(source, -120, 0, 480, 480)

        self.assertIsNone(image)
        self.assertEqual((x, y, width, height), (-120, 0, 0, 0))

    def test_close_without_webserver_is_safe(self):
        lcd = LcdSimulated.__new__(LcdSimulated)

        lcd.closeSerial()


if __name__ == "__main__":
    unittest.main()
