import threading
import unittest
from unittest import mock

from PIL import Image

from library.lcd.lcd_comm_rev_c import LcdCommRevC


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

    def test_overlay_transaction_retries_transient_empty_status(self):
        lcd = self.bare_lcd()
        lcd.orientation = object()
        lcd._video_overlay_serial_lock = threading.Lock()
        lcd.serial_flush_input = mock.Mock()
        lcd._send_full_video_overlay_transaction = mock.Mock(
            side_effect=[RuntimeError("empty status"), None]
        )
        frame = Image.new("RGBA", (1, 1), (255, 0, 0, 255))

        with (
            mock.patch("library.lcd.lcd_comm_rev_c.time.sleep") as sleeper,
            mock.patch("library.lcd.lcd_comm_rev_c.logger.warning") as warning,
        ):
            lcd._send_full_video_overlay(frame)

        self.assertEqual(lcd._send_full_video_overlay_transaction.call_count, 2)
        lcd.serial_flush_input.assert_called_once()
        sleeper.assert_called_once_with(0.15)
        warning.assert_called_once()

    def test_overlay_transaction_fails_after_bounded_retries(self):
        lcd = self.bare_lcd()
        lcd.orientation = object()
        lcd._video_overlay_serial_lock = threading.Lock()
        lcd.serial_flush_input = mock.Mock()
        lcd._send_full_video_overlay_transaction = mock.Mock(
            side_effect=RuntimeError("status lost")
        )
        frame = Image.new("RGBA", (1, 1), (255, 0, 0, 255))

        with (
            mock.patch("library.lcd.lcd_comm_rev_c.time.sleep"),
            mock.patch("library.lcd.lcd_comm_rev_c.logger.warning"),
        ):
            with self.assertRaisesRegex(RuntimeError, "status lost"):
                lcd._send_full_video_overlay(frame)

        self.assertEqual(lcd._send_full_video_overlay_transaction.call_count, 3)
        self.assertEqual(lcd.serial_flush_input.call_count, 2)

    def test_overlay_retry_continues_when_input_flush_temporarily_fails(self):
        lcd = self.bare_lcd()
        lcd.orientation = object()
        lcd._video_overlay_serial_lock = threading.Lock()
        lcd.serial_flush_input = mock.Mock(
            side_effect=RuntimeError("device is waking")
        )
        lcd._send_full_video_overlay_transaction = mock.Mock(
            side_effect=[RuntimeError("empty status"), None]
        )
        frame = Image.new("RGBA", (1, 1), (255, 0, 0, 255))

        with (
            mock.patch("library.lcd.lcd_comm_rev_c.time.sleep"),
            mock.patch("library.lcd.lcd_comm_rev_c.logger.warning"),
        ):
            lcd._send_full_video_overlay(frame)

        self.assertEqual(lcd._send_full_video_overlay_transaction.call_count, 2)
        lcd.serial_flush_input.assert_called_once()

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
