from __future__ import annotations

import unittest

from library.display_shutdown import (
    DISPLAY_MEDIA_STOP_SETTLE_SECONDS,
    DISPLAY_POWER_OFF_SETTLE_SECONDS,
    power_off_and_close_display,
)


class FakeDriver:
    def __init__(self, *, fail_power=False, screen_off=True):
        self.fail_power = fail_power
        self.events = []
        self.update_queue = object()
        self.video_overlay_enabled = True
        if not screen_off:
            self.ScreenOff = None

    def ScreenOff(self):
        self.events.append("screen-off")
        if self.fail_power:
            raise RuntimeError("power command failed")
        self.video_overlay_enabled = False

    def StopVideoOverlay(self):
        self.events.append("stop-video")
        self.video_overlay_enabled = False

    def SetBrightness(self, value):
        self.events.append(("brightness", value))

    def SetBackplateLedColor(self, *, led_color):
        self.events.append(("led", led_color))

    def closeSerial(self):
        self.events.append("close")


class DisplayShutdownTests(unittest.TestCase):
    def test_native_video_stops_before_power_command_and_serial_close(self):
        driver = FakeDriver()
        sleeps = []

        power_off_and_close_display(driver, sleeper=sleeps.append)

        self.assertIsNone(driver.update_queue)
        self.assertLess(
            driver.events.index("stop-video"),
            driver.events.index(("brightness", 0)),
        )
        self.assertLess(
            driver.events.index(("brightness", 0)),
            driver.events.index("screen-off"),
        )
        self.assertLess(
            driver.events.index("screen-off"),
            driver.events.index("close"),
        )
        self.assertIn(("led", (0, 0, 0)), driver.events)
        self.assertEqual(
            sleeps,
            [
                DISPLAY_MEDIA_STOP_SETTLE_SECONDS,
                DISPLAY_POWER_OFF_SETTLE_SECONDS,
            ],
        )

    def test_power_failure_still_blanks_and_closes(self):
        driver = FakeDriver(fail_power=True)

        with self.assertRaisesRegex(RuntimeError, "power command failed"):
            power_off_and_close_display(driver, sleeper=lambda _seconds: None)

        self.assertIn(("brightness", 0), driver.events)
        self.assertEqual(driver.events[-1], "close")

    def test_legacy_fallback_stops_video_and_blanks_before_close(self):
        driver = FakeDriver(screen_off=False)

        power_off_and_close_display(driver, sleeper=lambda _seconds: None)

        self.assertLess(
            driver.events.index("stop-video"),
            driver.events.index(("brightness", 0)),
        )
        self.assertLess(
            driver.events.index(("brightness", 0)),
            driver.events.index("close"),
        )


if __name__ == "__main__":
    unittest.main()
