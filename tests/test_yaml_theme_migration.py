from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from library.yaml_theme_migration import (
    YamlThemeMigrationError,
    analyze_yaml_theme,
    format_migration_report,
)


ROOT = Path(__file__).resolve().parents[1]


class YamlThemeMigrationTests(unittest.TestCase):
    def test_analyzer_is_read_only_and_classifies_migration_gaps(self):
        with tempfile.TemporaryDirectory(prefix="turing-yaml-analysis-") as temporary:
            theme = Path(temporary) / "legacy"
            theme.mkdir()
            (theme / "background.png").write_bytes(b"png")
            source = theme / "theme.yaml"
            source.write_text(
                """display:
  DISPLAY_SIZE: 2.1\"
  DISPLAY_ORIENTATION: landscape
video:
  ENABLED: true
  MODE: native
  PATH: /mnt/SDCARD/video/background.mp4
static_images:
  BACKGROUND:
    PATH: background.png
    X: 0
    Y: 0
    WIDTH: 480
    HEIGHT: 480
STATS:
  CPU:
    PERCENTAGE:
      TEXT:
        SHOW: true
        X: 10
        Y: 10
        FONT_SIZE: 20
      GRAPH:
        SHOW: true
        X: 10
        Y: 40
        WIDTH: 100
        HEIGHT: 10
        MIN_VALUE: 0
        MAX_VALUE: 100
      RADIAL:
        SHOW: true
        X: 120
        Y: 40
        RADIUS: 30
  PING:
    TEXT:
      SHOW: true
      X: 10
      Y: 100
      FONT_SIZE: 16
""",
                encoding="utf-8",
            )
            original = source.read_bytes()

            report = analyze_yaml_theme(theme)

            self.assertEqual(source.read_bytes(), original)
            self.assertEqual((report.width, report.height), (480, 480))
            self.assertTrue(report.native_video)
            self.assertEqual(report.static_images, 1)
            self.assertEqual(report.readiness, "assisted")
            statuses = {".".join(item.path): item.status for item in report.overlays}
            self.assertEqual(statuses["STATS.CPU.PERCENTAGE.TEXT"], "ready")
            self.assertEqual(statuses["STATS.CPU.PERCENTAGE.GRAPH"], "ready")
            self.assertEqual(statuses["STATS.CPU.PERCENTAGE.RADIAL"], "needs-component")
            self.assertEqual(statuses["STATS.PING.TEXT"], "needs-binding")
            self.assertIn("Readiness: assisted", format_migration_report(report))

    def test_custom_data_requires_manual_migration(self):
        report = analyze_yaml_theme(ROOT / "res" / "themes" / "CustomDataExample")
        self.assertEqual(report.readiness, "manual")
        self.assertEqual(report.display_source, "geometry")
        self.assertTrue(
            any(
                overlay.status == "needs-binding"
                and "CUSTOM" in overlay.path
                for overlay in report.visible_overlays
            )
        )

    def test_native_video_text_and_bar_theme_is_automatic(self):
        report = analyze_yaml_theme(ROOT / "res" / "themes" / "24")
        self.assertEqual(report.readiness, "automatic")
        self.assertTrue(report.native_video)
        self.assertEqual(len(report.ready_overlays), len(report.visible_overlays))

    def test_invalid_yaml_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "theme.yaml"
            source.write_text("STATS: [", encoding="utf-8")
            with self.assertRaises(YamlThemeMigrationError):
                analyze_yaml_theme(source)


if __name__ == "__main__":
    unittest.main()
