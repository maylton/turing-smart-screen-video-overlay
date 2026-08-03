from __future__ import annotations

import unittest

from library.display_shutdown import (
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
    def test_screen_is_powered_off_before_serial_closes(self):
        driver = FakeDriver()
        sleeps = []

        power_off_and_close_display(driver, sleeper=sleeps.append)

        self.assertIsNone(driver.update_queue)
        self.assertLess(
            driver.events.index("screen-off"),
            driver.events.index("close"),
        )
        self.assertIn(("led", (0, 0, 0)), driver.events)
        self.assertEqual(sleeps, [DISPLAY_POWER_OFF_SETTLE_SECONDS])

    def test_power_failure_uses_brightness_zero_and_still_closes(self):
        driver = FakeDriver(fail_power=True)

        with self.assertRaisesRegex(RuntimeError, "power command failed"):
            power_off_and_close_display(driver, sleeper=lambda _seconds: None)

        self.assertIn(("brightness", 0), driver.events)
        self.assertEqual(driver.events[-1], "close")

    def test_legacy_fallback_stops_video_before_close(self):
        driver = FakeDriver(screen_off=False)

        power_off_and_close_display(driver, sleeper=lambda _seconds: None)

        self.assertLess(
            driver.events.index("stop-video"),
            driver.events.index("close"),
        )


if __name__ == "__main__":
    unittest.main()
