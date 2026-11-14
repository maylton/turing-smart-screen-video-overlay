import unittest
from unittest import mock

from PIL import Image

from library.lcd import lcd_comm
from library.lcd.lcd_comm import LcdComm, SERIAL_OPEN_ATTEMPTS


class RecordingLcd(LcdComm):
    """Minimal concrete LcdComm that records the images it would send."""

    def __init__(self, com_port="AUTO"):
        super().__init__(com_port=com_port, display_width=100, display_height=60)
        self.sent = []

    def InitializeComm(self): pass
    def Reset(self): pass
    def Clear(self): pass
    def ScreenOff(self): pass
    def ScreenOn(self): pass
    def SetBrightness(self, level: int): pass
    def SetOrientation(self, orientation): self.orientation = orientation

    def DisplayPILImage(self, image: Image.Image, x: int = 0, y: int = 0, image_width: int = 0,
                        image_height: int = 0):
        self.sent.append((x, y, image.width, image.height))


class OpenSerialRetryTests(unittest.TestCase):
    def setUp(self):
        patches = [
            mock.patch.object(lcd_comm.time, "sleep"),
            mock.patch.object(lcd_comm, "logger"),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_auto_detection_is_retried_while_the_display_re_enumerates(self):
        lcd = RecordingLcd("AUTO")
        port = object()
        with (
            mock.patch.object(RecordingLcd, "auto_detect_com_port", side_effect=[None, None, "/dev/ttyACM0"]),
            mock.patch.object(lcd_comm.serial, "Serial", return_value=port) as serial_class,
        ):
            lcd.openSerial()
        self.assertIs(lcd.lcd_serial, port)
        self.assertEqual(lcd.com_port, "/dev/ttyACM0")
        serial_class.assert_called_once_with("/dev/ttyACM0", 115200, timeout=1, rtscts=True)

    def test_open_errors_are_retried(self):
        lcd = RecordingLcd("/dev/ttyACM0")
        port = object()
        with (
            mock.patch.object(lcd_comm.os.path, "exists", return_value=True),
            mock.patch.object(lcd_comm.serial, "Serial", side_effect=[OSError("busy"), port]),
        ):
            lcd.openSerial()
        self.assertIs(lcd.lcd_serial, port)

    def test_static_port_that_disappeared_falls_back_to_auto(self):
        lcd = RecordingLcd("/dev/ttyACM9")
        with (
            mock.patch.object(lcd_comm.os.path, "exists", side_effect=lambda path: path != "/dev/ttyACM9"),
            mock.patch.object(RecordingLcd, "auto_detect_com_port", return_value="/dev/ttyACM1"),
            mock.patch.object(lcd_comm.serial, "Serial", return_value=object()) as serial_class,
        ):
            lcd.openSerial()
        serial_class.assert_called_once_with("/dev/ttyACM1", 115200, timeout=1, rtscts=True)
        self.assertEqual(lcd.com_port, "/dev/ttyACM1")

    def test_gives_up_after_the_bounded_number_of_attempts(self):
        lcd = RecordingLcd("AUTO")
        with (
            mock.patch.object(RecordingLcd, "auto_detect_com_port", return_value=None) as detect,
            # The bare except around sys.exit() ends in os._exit(); keep the test process alive.
            mock.patch.object(lcd_comm.os, "_exit", side_effect=SystemExit(0)),
            self.assertRaises(SystemExit),
        ):
            lcd.openSerial()
        self.assertEqual(detect.call_count, SERIAL_OPEN_ATTEMPTS)
        self.assertEqual(lcd_comm.time.sleep.call_count, SERIAL_OPEN_ATTEMPTS - 1)


class TextGhostingTests(unittest.TestCase):
    FONT = "./res/fonts/roboto-mono/RobotoMono-Regular.ttf"

    def test_shorter_text_repaints_the_area_of_the_previous_one(self):
        lcd = RecordingLcd()
        lcd.DisplayText("100%", x=5, y=5, font=self.FONT, font_size=20)
        first = lcd.sent[-1]
        lcd.DisplayText("9%", x=5, y=5, font=self.FONT, font_size=20)
        second = lcd.sent[-1]
        # The second update still covers the full width of "100%".
        self.assertEqual(second[0], first[0])
        self.assertGreaterEqual(second[2], first[2])

    def test_texts_at_other_origins_are_independent(self):
        lcd = RecordingLcd()
        lcd.DisplayText("100%", x=5, y=5, font=self.FONT, font_size=20)
        lcd.DisplayText("9%", x=5, y=35, font=self.FONT, font_size=20)
        lone = RecordingLcd()
        lone.DisplayText("9%", x=5, y=35, font=self.FONT, font_size=20)
        self.assertEqual(lcd.sent[-1], lone.sent[-1])


if __name__ == "__main__":
    unittest.main()
