from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from library.html_theme_visual_editor import load_visual_styles
from library.theme_engine import ThemeManifest
from library.theme_package import PACKAGE_FILENAME
from library.yaml_theme_converter import convert_yaml_theme
from library.yaml_theme_migration import (
    YamlThemeMigrationError,
    analyze_yaml_theme,
    format_migration_report,
)


ROOT = Path(__file__).resolve().parents[1]


class YamlThemeMigrationTests(unittest.TestCase):
    def write_convertible_theme(self, root: Path, *, radial: bool = False) -> Path:
        root.mkdir()
        (root / "background.png").write_bytes(b"png")
        radial_yaml = """
      RADIAL:
        SHOW: true
        X: 150
        Y: 40
        RADIUS: 30
""" if radial else ""
        (root / "theme.yaml").write_text(
            """display:
  DISPLAY_SIZE: 2.1\"
  DISPLAY_ORIENTATION: landscape
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
        X: 20
        Y: 20
        WIDTH: 100
        HEIGHT: 30
        FONT_SIZE: 20
        FONT_COLOR: 255, 255, 255
      GRAPH:
        SHOW: true
        X: 20
        Y: 60
        WIDTH: 120
        HEIGHT: 10
        MIN_VALUE: 0
        MAX_VALUE: 100
""" + radial_yaml,
            encoding="utf-8",
        )
        return root

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

    def test_converter_creates_editable_html_directory_without_touching_yaml(self):
        with tempfile.TemporaryDirectory(prefix="turing-yaml-convert-") as temporary:
            root = Path(temporary)
            source = self.write_convertible_theme(root / "classic")
            original = (source / "theme.yaml").read_bytes()
            destination = root / "classic-html"

            result = convert_yaml_theme(source, destination)

            self.assertFalse(result.packaged)
            self.assertEqual(len(result.converted), 2)
            self.assertEqual((source / "theme.yaml").read_bytes(), original)
            manifest = ThemeManifest.load(destination)
            styles = load_visual_styles(manifest)
            self.assertEqual(
                {style.binding for style in styles},
                {"cpu.usage"},
            )
            self.assertEqual(
                {style.element_kind for style in styles},
                {"text", "bar"},
            )
            self.assertTrue((destination / "source" / "theme.yaml").is_file())
            self.assertTrue((destination / "migration-report.json").is_file())
            migration_report = (destination / "migration-report.json").read_text(
                encoding="utf-8"
            )
            self.assertIn('"source": "source/theme.yaml"', migration_report)
            self.assertNotIn(str(source), migration_report)
            self.assertIn("data-turing-generated-widget", (destination / "index.html").read_text(encoding="utf-8"))

    def test_converter_packages_theme_and_requires_opt_in_for_partial_drafts(self):
        with tempfile.TemporaryDirectory(prefix="turing-yaml-package-") as temporary:
            root = Path(temporary)
            source = self.write_convertible_theme(root / "assisted", radial=True)
            destination = root / "assisted.theme"

            with self.assertRaisesRegex(YamlThemeMigrationError, "allow-partial"):
                convert_yaml_theme(source, destination)

            result = convert_yaml_theme(
                source,
                destination,
                allow_partial=True,
            )
            self.assertTrue(result.packaged)
            self.assertEqual(len(result.converted), 2)
            self.assertEqual(result.skipped, ("STATS.CPU.PERCENTAGE.RADIAL",))
            with zipfile.ZipFile(destination) as archive:
                names = set(archive.namelist())
            self.assertIn(PACKAGE_FILENAME, names)
            self.assertIn("manifest.json", names)
            self.assertIn("overlays.json", names)
            self.assertIn("source/theme.yaml", names)

    def test_batch_command_converts_automatic_and_reports_assisted_theme(self):
        with tempfile.TemporaryDirectory(prefix="turing-yaml-batch-") as temporary:
            root = Path(temporary)
            sources = root / "themes"
            sources.mkdir()
            self.write_convertible_theme(sources / "automatic")
            self.write_convertible_theme(sources / "assisted", radial=True)
            destination = root / "converted"

            completed = subprocess.run(
                [
                    "python3",
                    str(ROOT / "theme-migrate.py"),
                    "batch",
                    str(sources),
                    str(destination),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((destination / "automatic-html.theme").is_file())
            report = json.loads(
                (destination / "batch-report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                report["converted"][0]["output"],
                str(destination / "automatic-html.theme"),
            )
            self.assertEqual(
                report["skipped"],
                [{"theme": "assisted", "readiness": "assisted"}],
            )


if __name__ == "__main__":
    unittest.main()
