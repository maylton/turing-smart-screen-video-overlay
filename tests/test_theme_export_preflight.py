# SPDX-License-Identifier: GPL-3.0-or-later

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from library.theme_export_preflight import ExportAssetStatus, inspect_theme_export
from library.theme_generated_media import GeneratedMediaStatus
from library.theme_media_transform import ImageTransformSettings, prepare_transform_asset


def save_image(path: Path, color=(10, 20, 30, 255)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (4, 3), color).save(path)
    return path


def write_theme(theme_dir: Path, content: str) -> Path:
    theme_dir.mkdir(parents=True, exist_ok=True)
    path = theme_dir / "theme.yaml"
    path.write_text(content, encoding="utf-8")
    return path


class ThemeExportPreflightTests(unittest.TestCase):
    def test_reports_complete_theme_assets_without_warnings(self):
        with tempfile.TemporaryDirectory() as directory:
            theme = Path(directory) / "demo"
            save_image(theme / "assets" / "logo.png")
            save_image(theme / "background.png")
            save_image(theme / "video-preview.png")
            write_theme(
                theme,
                """
static_images:
  hero:
    PATH: assets/logo.png
static_text:
  title:
    BACKGROUND_IMAGE: background.png
video:
  ENABLED: true
  PATH: /mnt/SDCARD/background.mp4
  PREVIEW_BACKGROUND: video-preview.png
""",
            )

            report = inspect_theme_export(theme)
            self.assertTrue(report.yaml_valid)
            self.assertFalse(report.warnings)
            by_key = {item.key_path: item for item in report.asset_references}
            self.assertEqual(by_key["static_images.hero.PATH"].status, ExportAssetStatus.INCLUDED)
            self.assertEqual(
                by_key["static_text.title.BACKGROUND_IMAGE"].status,
                ExportAssetStatus.INCLUDED,
            )
            self.assertEqual(
                by_key["video.PREVIEW_BACKGROUND"].status,
                ExportAssetStatus.INCLUDED,
            )
            self.assertEqual(by_key["video.PATH"].status, ExportAssetStatus.REMOTE_DEVICE)

    def test_warns_about_missing_referenced_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            theme = Path(directory) / "demo"
            write_theme(theme, "static_images:\n  hero:\n    PATH: missing.png\n")

            report = inspect_theme_export(theme)
            self.assertFalse(report.ok)
            [asset] = report.by_reference("missing.png")
            self.assertEqual(asset.status, ExportAssetStatus.MISSING)
            self.assertIn("missing file", asset.warning)
            self.assertEqual(len(report.warnings), 1)

    def test_warns_about_absolute_assets_outside_theme_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            theme = root / "demo"
            external = save_image(root / "external.png")
            write_theme(theme, f"video:\n  LOCAL_PATH: {external}\n")

            report = inspect_theme_export(theme)
            [asset] = report.asset_references
            self.assertEqual(asset.status, ExportAssetStatus.OUTSIDE_THEME)
            self.assertFalse(asset.included_in_archive)
            self.assertIn("outside the theme folder", asset.warning)

    def test_classifies_registered_generated_media_as_managed(self):
        with tempfile.TemporaryDirectory() as directory:
            theme = Path(directory) / "demo"
            save_image(theme / "source.png")
            prepared = prepare_transform_asset(
                theme,
                "source.png",
                ImageTransformSettings(rotation=90),
            )
            write_theme(
                theme,
                f"static_images:\n  hero:\n    PATH: {prepared.output_reference}\n",
            )

            report = inspect_theme_export(theme)
            [asset] = report.by_reference(prepared.output_reference)
            self.assertEqual(asset.status, ExportAssetStatus.GENERATED_MANAGED)
            self.assertTrue(asset.included_in_archive)
            self.assertFalse(report.warnings)

    def test_warns_about_referenced_generated_media_without_manifest_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            theme = Path(directory) / "demo"
            save_image(theme / "generated-media" / "manual.png")
            write_theme(theme, "static_images:\n  hero:\n    PATH: generated-media/manual.png\n")

            report = inspect_theme_export(theme)
            [asset] = report.by_reference("generated-media/manual.png")
            self.assertEqual(asset.status, ExportAssetStatus.GENERATED_UNMANAGED)
            self.assertTrue(asset.included_in_archive)
            self.assertIn("without manifest metadata", asset.warning)

    def test_global_font_references_do_not_warn_when_font_exists_in_res_fonts(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            theme = project / "res" / "themes" / "demo"
            font = project / "res" / "fonts" / "roboto" / "Roboto.ttf"
            font.parent.mkdir(parents=True, exist_ok=True)
            font.write_bytes(b"font")
            write_theme(
                theme,
                "static_text:\n  title:\n    FONT: roboto/Roboto.ttf\n",
            )

            report = inspect_theme_export(theme)
            [asset] = report.by_reference("roboto/Roboto.ttf")
            self.assertEqual(asset.status, ExportAssetStatus.GLOBAL_FONT)
            self.assertFalse(asset.included_in_archive)
            self.assertFalse(report.warnings)

    def test_exposes_unused_generated_media_records_for_ui_reporting(self):
        with tempfile.TemporaryDirectory() as directory:
            theme = Path(directory) / "demo"
            save_image(theme / "source.png")
            prepared = prepare_transform_asset(
                theme,
                "source.png",
                ImageTransformSettings(flip_horizontal=True),
            )
            write_theme(theme, "static_images:\n  hero:\n    PATH: source.png\n")

            report = inspect_theme_export(theme)
            self.assertIsNotNone(report.generated_media)
            record = report.generated_media.by_reference(prepared.output_reference)
            self.assertIsNotNone(record)
            self.assertEqual(record.status, GeneratedMediaStatus.UNUSED)

    def test_reports_missing_theme_yaml_as_error(self):
        with tempfile.TemporaryDirectory() as directory:
            theme = Path(directory) / "demo"
            theme.mkdir()

            report = inspect_theme_export(theme)
            self.assertFalse(report.yaml_valid)
            self.assertTrue(report.blocking)
            self.assertIn("missing", report.errors[0])


if __name__ == "__main__":
    unittest.main()
