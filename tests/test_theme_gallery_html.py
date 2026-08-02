from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import yaml

from library.theme_gallery import (
    ThemeRecord,
    default_export_path,
    export_theme,
    import_theme,
    is_theme_directory,
    read_current_renderer_theme,
    read_renderer_engine,
    replace_current_theme_name,
    set_current_theme,
)
from library.theme_package import PACKAGE_FILENAME, ThemePackageError


class HtmlThemeGalleryTests(unittest.TestCase):
    def record(self, root: Path, name: str, engine: str) -> ThemeRecord:
        directory = root / name
        directory.mkdir()
        yaml_file = None
        if engine == "yaml":
            yaml_file = directory / "theme.yaml"
            yaml_file.write_text("DISPLAY_SIZE: 2.1\n", encoding="utf-8")
        return ThemeRecord(
            name=name,
            directory=directory,
            yaml_file=yaml_file,
            preview_file=directory / "preview.png",
            engine=engine,
        )

    def write_html_package(self, root: Path, *, network=False, permissions=None, csp=True):
        root.mkdir()
        meta = (
            '<meta http-equiv="Content-Security-Policy" content="default-src self">'
            if csp
            else ""
        )
        (root / "index.html").write_text(meta + "<main></main>", encoding="utf-8")
        (root / "manifest.json").write_text(
            json.dumps({
                "engine": "html",
                "name": "Imported HTML",
                "version": 1,
                "display": {"width": 480, "height": 480},
                "entrypoint": "index.html",
                "permissions": permissions if permissions is not None else ["sensors"],
                "network": network,
            }),
            encoding="utf-8",
        )

    def test_switches_between_html_and_yaml_renderer_without_losing_legacy_theme(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config.yaml"
            config.write_text(
                "config:\n  THEME: legacy\n  DISPLAY_SIZE: 2.1\n\n"
                "renderer:\n  engine: yaml\n\n"
                "display:\n  BRIGHTNESS: 40\n",
                encoding="utf-8",
            )
            html = self.record(root, "html-theme", "html")
            legacy = self.record(root, "next-yaml", "yaml")

            old, new = set_current_theme(html, config)
            html_payload = yaml.safe_load(config.read_text(encoding="utf-8"))
            self.assertEqual((old, new), ("legacy", "html-theme"))
            self.assertEqual(html_payload["config"]["THEME"], "legacy")
            self.assertEqual(html_payload["renderer"], {
                "engine": "html",
                "theme": "html-theme",
            })
            self.assertEqual(html_payload["display"]["BRIGHTNESS"], 40)
            self.assertEqual(read_current_renderer_theme(config), "html-theme")

            old, new = set_current_theme(legacy, config)
            yaml_payload = yaml.safe_load(config.read_text(encoding="utf-8"))
            self.assertEqual((old, new), ("html-theme", "next-yaml"))
            self.assertEqual(yaml_payload["config"]["THEME"], "next-yaml")
            self.assertEqual(yaml_payload["renderer"], {"engine": "yaml"})
            self.assertEqual(read_renderer_engine(config), "yaml")

    def test_renames_active_html_renderer_theme(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "config.yaml"
            config.write_text(
                "config:\n  THEME: legacy\n"
                "renderer:\n  renderer:\n  engine: html\n  theme: old-html\n",
                encoding="utf-8",
            )

            replace_current_theme_name("old-html", "new-html", config)
            payload = yaml.safe_load(config.read_text(encoding="utf-8"))
            self.assertEqual(payload["renderer"], {
                "engine": "html",
                "theme": "new-html",
            })
            self.assertEqual(payload["config"]["THEME"], "legacy")

    def test_import_policy_accepts_only_local_sensor_html_packages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            safe = root / "safe"
            networked = root / "networked"
            unknown = root / "unknown"
            no_csp = root / "no-csp"
            self.write_html_package(safe)
            self.write_html_package(networked, network=True, permissions=["sensors", "network"])
            self.write_html_package(unknown, permissions=["sensors", "shell"])
            self.write_html_package(no_csp, csp=False)

            self.assertTrue(is_theme_directory(safe))
            self.assertFalse(is_theme_directory(networked))
            self.assertFalse(is_theme_directory(unknown))
            self.assertFalse(is_theme_directory(no_csp))

    def test_html_theme_round_trips_as_canonical_theme_package(self):
        with tempfile.TemporaryDirectory(prefix="turing-theme-roundtrip-") as temporary:
            root = Path(temporary)
            themes = root / "themes"
            themes.mkdir()
            source = themes / "portable-html"
            self.write_html_package(source)
            record = ThemeRecord(
                name=source.name,
                directory=source,
                yaml_file=None,
                preview_file=source / "preview.png",
                engine="html",
            )

            with mock.patch("library.theme_gallery.THEMES_DIR", themes):
                destination = export_theme(record, str(root / "exported"))
                self.assertEqual(destination.suffix, ".theme")
                with zipfile.ZipFile(destination) as archive:
                    names = set(archive.namelist())
                    descriptor = json.loads(archive.read(PACKAGE_FILENAME))
                self.assertIn(PACKAGE_FILENAME, names)
                self.assertIn("manifest.json", names)
                self.assertIn("index.html", names)
                self.assertNotIn("portable-html/manifest.json", names)
                self.assertEqual(descriptor["formatVersion"], 1)
                self.assertEqual(descriptor["engine"], "html")

                shutil.rmtree(source)
                imported_name = import_theme(str(destination))

            self.assertEqual(imported_name, "portable-html")
            self.assertTrue((themes / imported_name / "manifest.json").is_file())
            self.assertTrue((themes / imported_name / PACKAGE_FILENAME).is_file())

    def test_yaml_theme_round_trips_as_theme_package(self):
        with tempfile.TemporaryDirectory(prefix="turing-yaml-package-") as temporary:
            root = Path(temporary)
            themes = root / "themes"
            source = themes / "portable-yaml"
            source.mkdir(parents=True)
            yaml_file = source / "theme.yaml"
            yaml_file.write_text("DISPLAY_SIZE: 2.1\n", encoding="utf-8")
            record = ThemeRecord(
                name=source.name,
                directory=source,
                yaml_file=yaml_file,
                preview_file=source / "preview.png",
                engine="yaml",
            )

            with mock.patch("library.theme_gallery.THEMES_DIR", themes):
                destination = export_theme(record, str(root / "yaml.theme"))
                shutil.rmtree(source)
                imported_name = import_theme(str(destination))

            self.assertEqual(imported_name, "portable-yaml")
            self.assertEqual(
                (themes / imported_name / "theme.yaml").read_text(encoding="utf-8"),
                "DISPLAY_SIZE: 2.1\n",
            )

    def test_legacy_zip_export_and_import_remain_supported(self):
        with tempfile.TemporaryDirectory(prefix="turing-legacy-zip-") as temporary:
            root = Path(temporary)
            themes = root / "themes"
            source = themes / "legacy-yaml"
            source.mkdir(parents=True)
            yaml_file = source / "theme.yaml"
            yaml_file.write_text("DISPLAY_SIZE: 2.1\n", encoding="utf-8")
            record = ThemeRecord(
                name=source.name,
                directory=source,
                yaml_file=yaml_file,
                preview_file=source / "preview.png",
                engine="yaml",
            )

            with mock.patch("library.theme_gallery.THEMES_DIR", themes):
                destination = export_theme(record, str(root / "legacy.zip"))
                with zipfile.ZipFile(destination) as archive:
                    self.assertIn("legacy-yaml/theme.yaml", archive.namelist())
                    self.assertNotIn(PACKAGE_FILENAME, archive.namelist())
                shutil.rmtree(source)
                imported_name = import_theme(str(destination))

            self.assertEqual(imported_name, "legacy-yaml")

    def test_theme_extension_requires_versioned_root_descriptor(self):
        with tempfile.TemporaryDirectory(prefix="turing-invalid-theme-") as temporary:
            root = Path(temporary)
            themes = root / "themes"
            themes.mkdir()
            archive_path = root / "invalid.theme"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("theme.yaml", "DISPLAY_SIZE: 2.1\n")

            with mock.patch("library.theme_gallery.THEMES_DIR", themes):
                with self.assertRaisesRegex(ThemePackageError, PACKAGE_FILENAME):
                    import_theme(str(archive_path))

    def test_default_export_extension_is_theme(self):
        self.assertEqual(default_export_path("example").suffix, ".theme")


if __name__ == "__main__":
    unittest.main()
