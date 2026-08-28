import threading
import unittest
from types import SimpleNamespace
from unittest import mock

import serial
from PIL import Image

from library.lcd.lcd_comm import LcdComm
from library.lcd.lcd_comm_rev_c import (
    LcdCommRevC,
    SERIAL_WRITE_TIMEOUT_SECONDS,
)


class RevCNativeVideoHealthTests(unittest.TestCase):
    @staticmethod
    def bare_lcd():
        lcd = LcdCommRevC.__new__(LcdCommRevC)
        lcd.lcd_serial = None
        lcd._video_overlay_thread = None
        return lcd

    def test_empty_overlay_status_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "empty status"):
            LcdCommRevC._require_video_overlay_status(b"", "bitmap payload")
        LcdCommRevC._require_video_overlay_status(b"ok", "bitmap payload")

    def test_d0_and_cf_allow_empty_optional_acknowledgements(self):
        lcd = self.bare_lcd()
        lcd.display_height = 480
        lcd._send_command = mock.Mock(return_value=b"")
        image = Image.new("RGBA", (1, 1), (255, 255, 255, 255))

        lcd._send_video_visible_pixels(image)
        lcd._apply_video_overlay()

        self.assertEqual(lcd._send_command.call_count, 2)

    def test_every_serial_open_installs_bounded_write_timeout(self):
        lcd = self.bare_lcd()
        lcd.lcd_serial = SimpleNamespace(write_timeout=None, close=mock.Mock())

        with mock.patch.object(LcdComm, "openSerial", return_value=None):
            lcd.openSerial()

        self.assertEqual(
            lcd.lcd_serial.write_timeout,
            SERIAL_WRITE_TIMEOUT_SECONDS,
        )

    def test_rev_c_write_timeout_is_not_swallowed(self):
        lcd = self.bare_lcd()
        lcd.serial_write = mock.Mock(
            side_effect=serial.SerialTimeoutException("firmware stopped reading")
        )

        with self.assertRaises(serial.SerialTimeoutException):
            lcd.WriteData(bytearray(b"frame"))

    def test_hello_uses_usb_recovery_after_bounded_attempts(self):
        lcd = self.bare_lcd()
        lcd._try_hello = mock.Mock(
            side_effect=["", "chs_5inch.dev1_rom1.88"]
        )
        lcd._usb_reset_and_reopen = mock.Mock()
        lcd._finish_hello = mock.Mock()

        lcd._hello()

        lcd._usb_reset_and_reopen.assert_called_once_with()
        lcd._finish_hello.assert_called_once_with("chs_5inch.dev1_rom1.88")

    def test_overlay_transaction_fails_fast_on_empty_status(self):
        lcd = self.bare_lcd()
        lcd.orientation = object()
        lcd._video_overlay_serial_lock = threading.Lock()
        lcd._send_full_video_overlay_transaction = mock.Mock(
            side_effect=RuntimeError("empty status")
        )
        frame = Image.new("RGBA", (1, 1), (255, 0, 0, 255))

        with self.assertRaisesRegex(RuntimeError, "empty status"):
            lcd._send_full_video_overlay(frame)

        lcd._send_full_video_overlay_transaction.assert_called_once_with(frame)

    def test_overlay_worker_records_first_transport_error_and_stops(self):
        lcd = self.bare_lcd()
        lcd._video_overlay_stop = threading.Event()
        lcd._video_overlay_event = threading.Event()
        lcd._video_overlay_event.set()
        lcd._video_overlay_lock = threading.Lock()
        lcd._video_overlay_debounce = 0.0
        lcd._video_overlay_min_interval = 0.0
        lcd._video_overlay_last_sent = 0.0
        lcd.video_overlay_enabled = True
        lcd.video_overlay_image = Image.new("RGBA", (1, 1), (255, 0, 0, 255))
        lcd._video_overlay_dirty = True
        lcd.video_overlay_error = None

        def fail(_frame):
            raise RuntimeError("status lost")

        lcd._send_full_video_overlay = fail
        with mock.patch("library.lcd.lcd_comm_rev_c.logger.exception") as logged:
            lcd._video_overlay_worker()

        logged.assert_called_once()
        self.assertIsInstance(lcd.video_overlay_error, RuntimeError)
        self.assertIn("status lost", str(lcd.video_overlay_error))
        self.assertTrue(lcd._video_overlay_stop.is_set())

    def test_future_overlay_updates_surface_worker_error(self):
        lcd = self.bare_lcd()
        lcd.video_overlay_error = RuntimeError("status lost")
        lcd.video_overlay_enabled = True
        with self.assertRaisesRegex(RuntimeError, "status lost"):
            lcd.DisplayPILImageOnVideoOverlay(
                Image.new("RGBA", (1, 1), (255, 255, 255, 255))
            )


if __name__ == "__main__":
    unittest.main()
