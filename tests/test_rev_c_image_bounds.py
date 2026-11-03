from __future__ import annotations

import threading
import unittest
from unittest import mock

from PIL import Image

from library.lcd.lcd_comm import Orientation
from library.lcd.lcd_comm_rev_c import Command, LcdCommRevC, SubRevision


def make_driver(orientation=Orientation.LANDSCAPE) -> LcdCommRevC:
    # Never call __init__: it opens the serial port.
    lcd = LcdCommRevC.__new__(LcdCommRevC)
    lcd.display_width = 480
    lcd.display_height = 480
    lcd.sub_revision = SubRevision.REV_2INCH
    lcd.rom_version = 88
    lcd.orientation = orientation
    lcd.video_overlay_enabled = False
    lcd.update_queue = None
    lcd.update_queue_mutex = threading.Lock()
    lcd._send_command = mock.Mock(return_value=b"")
    return lcd


def row_addresses(image_data: bytearray, width: int) -> list[int]:
    """Decode the 3-byte row addresses from an unpadded update payload."""
    raw = bytes(image_data)[:-2]  # drop the ef69 terminator
    if len(raw) > 249:
        raw = b"".join(raw[i:i + 249] for i in range(0, len(raw), 250))
    row = 3 + 2 + width * 3
    return [int.from_bytes(raw[i:i + 3], "big") for i in range(0, len(raw), row)]


class RevCImageBoundsTests(unittest.TestCase):
    def test_in_bounds_update_keeps_the_original_addressing(self):
        lcd = make_driver()
        image = Image.new("RGB", (4, 3), "red")
        data, header = lcd._generate_update_image(image, 10, 20, 7, Command.UPDATE_BITMAP)
        # Landscape on 2.1": x0 = y, y0 = x, pitch = display height.
        self.assertEqual(row_addresses(data, 4), [(20 + h) * 480 + 10 for h in range(3)])
        self.assertEqual(header[-4:], (7).to_bytes(4, "big"))

    def test_partially_offscreen_image_is_clipped_without_negative_addresses(self):
        lcd = make_driver()
        image = Image.new("RGB", (10, 6), "blue")
        data, _header = lcd._generate_update_image(image, -4, -2, 0, Command.UPDATE_BITMAP)
        addresses = row_addresses(data, 6)
        self.assertEqual(len(addresses), 4)
        self.assertEqual(addresses[0], 0)
        self.assertTrue(all(address >= 0 for address in addresses))

    def test_fully_offscreen_image_produces_no_update(self):
        lcd = make_driver()
        image = Image.new("RGB", (10, 10), "green")
        self.assertIsNone(lcd._generate_update_image(image, 600, 600, 0))
        self.assertIsNone(lcd._generate_update_image(image, -50, 5, 0))

    def test_display_skips_offscreen_bitmaps_without_sending(self):
        lcd = make_driver()
        lcd.DisplayPILImage(Image.new("RGB", (10, 10)), x=-100, y=-100)
        lcd._send_command.assert_not_called()

    def test_oversized_image_is_positioned_before_clipping(self):
        lcd = make_driver()
        sent = []
        lcd._send_command = mock.Mock(side_effect=lambda *a, **k: sent.append(k.get("payload")))
        lcd.DisplayPILImage(Image.new("RGB", (600, 600), "white"), x=-60, y=-60)
        # Header, image and status query: one partial update, not a crash.
        self.assertEqual(lcd._send_command.call_count, 3)
        self.assertEqual(row_addresses(sent[1], 480)[0], 0)


if __name__ == "__main__":
    unittest.main()
