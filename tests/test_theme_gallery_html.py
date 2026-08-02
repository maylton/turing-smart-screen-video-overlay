from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from library.theme_gallery import (
    ThemeRecord,
    is_theme_directory,
    read_current_renderer_theme,
    read_renderer_engine,
    replace_current_theme_name,
    set_current_theme,
)


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


if __name__ == "__main__":
    unittest.main()
