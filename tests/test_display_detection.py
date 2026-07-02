from __future__ import annotations
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from library.display_detection import auto_configure, detect_serial, detect_usb, select

@dataclass
class Port:
    device: str
    vid: int | None = None
    pid: int | None = None
    serial_number: str | None = None

@dataclass
class Usb:
    idVendor: int
    idProduct: int

class DisplayDetectionTests(unittest.TestCase):
    def project(self, root: Path, revision: str = "A", theme: str = "small", auto: bool = True):
        for name, size in (("small", '2.1"'), ("wide", '5.2"'), ("tiny", '0.96"')):
            directory = root / "res" / "themes" / name
            directory.mkdir(parents=True)
            (directory / "theme.yaml").write_text(
                f"display:\n  DISPLAY_SIZE: '{size}'\n  DISPLAY_ORIENTATION: portrait\n",
                encoding="utf-8",
            )
        (root / "config.yaml").write_text(
            f"config:\n  COM_PORT: AUTO\n  THEME: {theme}\n"
            f"display:\n  AUTO_DETECT: {'true' if auto else 'false'}\n  REVISION: {revision}\n",
            encoding="utf-8",
        )

    def test_ct21_exact(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.project(root)
            item = detect_serial([Port("/dev/ttyACM0", serial_number="CT21INCH")], root)[0]
        self.assertEqual((item.revision, item.display_size), ("C", '2.1"'))
        self.assertTrue(item.complete)

    def test_shared_ch340_is_ambiguous(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.project(root)
            items = detect_serial([Port("/dev/ttyUSB0", 0x1A86, 0x5722)], root)
        self.assertFalse(items[0].safe)
        self.assertIsNone(select(items))

    def test_weact_prefixes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.project(root)
            large = detect_serial([Port("a", serial_number="AB123")], root)[0]
            tiny = detect_serial([Port("b", serial_number="AD123")], root)[0]
        self.assertEqual((large.revision, tiny.revision), ("WEACT_A", "WEACT_B"))

    def test_turing_usb_updates_revision_and_theme(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.project(root)
            report = auto_configure(root, ports=[], usb_devices=[Usb(0x1CBE, 0x0050)])
            text = (root / "config.yaml").read_text(encoding="utf-8")
        self.assertEqual((report.current_revision, report.current_theme), ("TUR_USB", "wide"))
        self.assertIn("REVISION: TUR_USB", text)

    def test_rev_c_awake_keeps_theme_hint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.project(root, revision="C")
            report = auto_configure(root, ports=[Port("/dev/ttyACM0", 0x0525, 0xA4A7, "20080411")], usb_devices=[])
        self.assertEqual(report.current_theme, "small")
        self.assertFalse(report.selected.complete)

    def test_disabled_does_nothing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.project(root, auto=False)
            report = auto_configure(root, ports=[Port("x", serial_number="CT21INCH")], usb_devices=[])
        self.assertFalse(report.enabled)
        self.assertFalse(report.applied)

    def test_two_equal_usb_matches_require_manual_choice(self):
        items = detect_usb([Usb(0x1CBE, 0x0046), Usb(0x1CBE, 0x0050)])
        self.assertIsNone(select(items))

    def test_complete_rev_c_groups_awake_and_sleep_endpoints(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.project(root, revision="C")

            import library.display_detection as detection

            public = getattr(
                detection,
                "detect",
                getattr(detection, "detect_supported_displays", None),
            )
            self.assertIsNotNone(public)

            items = public(
                root,
                ports=[
                    Port("/dev/ttyACM1", 0x1A86, 0xCA21, "CT21INCH"),
                    Port("/dev/ttyACM0", 0x1D6B, 0x0121, "20080411"),
                ],
                usb_devices=[],
            )

        self.assertEqual(len(items), 1)
        selected = items[0]
        self.assertEqual(getattr(selected, "device", None), "/dev/ttyACM1")
        self.assertTrue(
            getattr(
                selected,
                "complete",
                getattr(selected, "configuration_complete", False),
            )
        )

if __name__ == "__main__":
    unittest.main()
