# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from library.rev_c_physical_sink import (
    CONFIRMATION_TEXT,
    PhysicalWriteRefused,
    write_full_frame_once,
)


class FakeDriver:
    def __init__(self, port, *, fail_display=False):
        self.port = port
        self.fail_display = fail_display
        self.calls = []
        self.closed = False

    def InitializeComm(self):
        self.calls.append(("initialize",))

    def SetOrientation(self, orientation):
        self.calls.append(("orientation", int(orientation)))

    def DisplayPILImage(self, image, **kwargs):
        self.calls.append(("display", image.size, kwargs))
        if self.fail_display:
            raise RuntimeError("simulated display failure")

    def closeSerial(self):
        self.calls.append(("close",))
        self.closed = True


class RevCPhysicalSinkTests(unittest.TestCase):
    def setUp(self):
        self.frame = Image.new("RGBA", (480, 480), (20, 30, 40, 255))
        self.parity = SimpleNamespace(
            valid=True,
            physical_io=False,
            mode="full",
            mismatch_offset=None,
            expected_wire=b"identical-wire",
            production_wire=b"identical-wire",
        )

    def write(self, **overrides):
        created = []

        def factory(port):
            driver = FakeDriver(
                port,
                fail_display=bool(overrides.pop("fail_display", False)),
            )
            created.append(driver)
            return driver

        with TemporaryDirectory() as temporary:
            arguments = {
                "frame": self.frame,
                "parity": self.parity,
                "port": "/dev/fake-rev-c",
                "confirmation": CONFIRMATION_TEXT,
                "monitor_stopped": True,
                "driver_factory": factory,
                "lock_path": Path(temporary) / "physical.lock",
            }
            arguments.update(overrides)
            result = write_full_frame_once(**arguments)
        return result, created

    def test_valid_request_writes_one_frame_and_closes(self):
        result, created = self.write()

        self.assertTrue(result.frame_written)
        self.assertTrue(result.serial_closed)
        self.assertTrue(result.physical_io)
        self.assertEqual(len(created), 1)
        self.assertEqual(
            [call[0] for call in created[0].calls],
            ["initialize", "orientation", "display", "close"],
        )
        display_call = created[0].calls[2]
        self.assertEqual(display_call[1], (480, 480))
        self.assertEqual(display_call[2]["image_width"], 480)
        self.assertEqual(display_call[2]["image_height"], 480)

    def test_wrong_confirmation_refuses_before_driver_creation(self):
        with self.assertRaisesRegex(PhysicalWriteRefused, "confirmation"):
            self.write(confirmation="wrong-token")

    def test_monitor_acknowledgement_is_required(self):
        with self.assertRaisesRegex(PhysicalWriteRefused, "monitor"):
            self.write(monitor_stopped=False)

    def test_invalid_parity_is_rejected(self):
        parity = SimpleNamespace(
            valid=False,
            physical_io=False,
            mode="full",
            mismatch_offset=0,
            expected_wire=b"a",
            production_wire=b"b",
        )
        with self.assertRaisesRegex(PhysicalWriteRefused, "parity"):
            self.write(parity=parity)

    def test_non_full_frame_is_rejected(self):
        small = Image.new("RGBA", (320, 480), (0, 0, 0, 255))
        with self.assertRaisesRegex(PhysicalWriteRefused, "480x480"):
            self.write(frame=small)

    def test_serial_is_closed_when_display_raises(self):
        created = []

        def factory(port):
            driver = FakeDriver(port, fail_display=True)
            created.append(driver)
            return driver

        with TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RuntimeError, "simulated display failure"):
                write_full_frame_once(
                    self.frame,
                    self.parity,
                    port="/dev/fake-rev-c",
                    confirmation=CONFIRMATION_TEXT,
                    monitor_stopped=True,
                    driver_factory=factory,
                    lock_path=Path(temporary) / "physical.lock",
                )

        self.assertEqual(len(created), 1)
        self.assertTrue(created[0].closed)
        self.assertEqual(created[0].calls[-1], ("close",))


if __name__ == "__main__":
    unittest.main()
