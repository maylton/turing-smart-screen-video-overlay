from PIL import Image
import unittest

from library.html_native_video_sink import HtmlNativeVideoSink
from library.theme_engine import NativeVideoOverlay, ThemeValidationError


class FakeDriver:
    def __init__(self, fail_start=False, fail_stop=False):
        self.fail_start = fail_start
        self.fail_stop = fail_stop
        self.video_overlay_enabled = False
        self.video_overlay_error = None
        self.events = []
        self.update_queue = object()

    def InitializeComm(self):
        self.events.append("initialize")

    def ScreenOn(self):
        self.events.append("screen-on")

    def SetBrightness(self, value):
        self.events.append(("brightness", value))

    def SetBackplateLedColor(self, *, led_color):
        self.events.append(("led", led_color))

    def SetOrientation(self, _orientation):
        self.events.append("orientation")

    def StartVideoOverlay(self, path, refresh_interval=1.0):
        self.events.append(("start-video", path, refresh_interval))
        if self.fail_start:
            raise RuntimeError("start failed")
        self.video_overlay_enabled = True

    def DisplayPILImageOnVideoOverlay(self, image, **_kwargs):
        self.events.append(("overlay", image.size))

    def StopVideoOverlay(self):
        self.events.append("stop-video")
        if self.fail_stop:
            raise RuntimeError("stop failed")
        self.video_overlay_enabled = False

    def ScreenOff(self):
        if self.video_overlay_enabled:
            self.StopVideoOverlay()
        self.events.append("screen-off")

    def closeSerial(self):
        self.events.append("close")


class HtmlNativeVideoSinkTests(unittest.TestCase):
    def setUp(self):
        self.spec = NativeVideoOverlay(
            local_path="base.mp4",
            device_path="/mnt/SDCARD/video/base.mp4",
            fps=24,
            duration=8,
        )
        self.overlay = Image.new("RGBA", (480, 480), (0, 0, 0, 0))
        self.overlay.putpixel((10, 10), (255, 255, 255, 255))

    def create_sink(self, driver):
        return HtmlNativeVideoSink(
            self.overlay,
            self.spec,
            port="/dev/fake",
            driver_factory=lambda _port: driver,
            sleeper=lambda _seconds: None,
        )

    def test_starts_video_before_submitting_atomic_overlay(self):
        driver = FakeDriver()
        sink = self.create_sink(driver)
        sink.close()
        labels = [event[0] if isinstance(event, tuple) else event for event in driver.events]
        self.assertLess(labels.index("start-video"), labels.index("overlay"))
        self.assertLess(labels.index("stop-video"), labels.index("screen-off"))
        self.assertLess(labels.index("screen-off"), labels.index("close"))
        self.assertIsNone(driver.update_queue)
        sink.close()
        labels_after_second_close = [
            event[0] if isinstance(event, tuple) else event
            for event in driver.events
        ]
        self.assertEqual(labels_after_second_close.count("close"), 1)

    def test_start_failure_powers_off_and_closes_serial(self):
        driver = FakeDriver(fail_start=True)
        with self.assertRaisesRegex(RuntimeError, "start failed"):
            self.create_sink(driver)
        labels = [event[0] if isinstance(event, tuple) else event for event in driver.events]
        self.assertIn("screen-off", labels)
        self.assertEqual(labels[-1], "close")

    def test_fully_opaque_capture_is_refused_before_driver_factory(self):
        calls = []
        with self.assertRaises(ThemeValidationError):
            HtmlNativeVideoSink(
                Image.new("RGBA", (480, 480), (0, 0, 0, 255)),
                self.spec,
                port="/dev/fake",
                driver_factory=lambda _port: calls.append(True),
                sleeper=lambda _seconds: None,
            )
        self.assertEqual(calls, [])

    def test_fully_transparent_capture_is_refused_before_driver_factory(self):
        calls = []
        with self.assertRaises(ThemeValidationError):
            HtmlNativeVideoSink(
                Image.new("RGBA", (480, 480), (0, 0, 0, 0)),
                self.spec,
                port="/dev/fake",
                driver_factory=lambda _port: calls.append(True),
                sleeper=lambda _seconds: None,
            )
        self.assertEqual(calls, [])

    def test_mostly_opaque_capture_is_refused_before_driver_factory(self):
        calls = []
        frame = Image.new("RGBA", (480, 480), (0, 0, 0, 255))
        frame.putpixel((0, 0), (0, 0, 0, 0))
        with self.assertRaises(ThemeValidationError):
            HtmlNativeVideoSink(
                frame,
                self.spec,
                port="/dev/fake",
                driver_factory=lambda _port: calls.append(True),
                sleeper=lambda _seconds: None,
            )
        self.assertEqual(calls, [])

    def test_async_transport_error_is_reported(self):
        driver = FakeDriver()
        sink = self.create_sink(driver)
        driver.video_overlay_error = ValueError("empty status")
        with self.assertRaisesRegex(RuntimeError, "empty status"):
            sink.check_health()
        sink.close()

    def test_stop_failure_uses_brightness_fallback_and_closes_serial(self):
        driver = FakeDriver(fail_stop=True)
        sink = self.create_sink(driver)
        with self.assertRaisesRegex(RuntimeError, "stop failed"):
            sink.close()
        self.assertIn(("brightness", 0), driver.events)
        self.assertEqual(driver.events[-1], "close")


if __name__ == "__main__":
    unittest.main()
