import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from library.html_theme_creator import (
    STARTER_ELEMENT_ID,
    create_blank_html_theme,
    sanitize_theme_folder_name,
)
from library.html_theme_visual_editor import load_visual_styles
from library.theme_engine import ThemeManifest


class HtmlThemeCreatorTests(unittest.TestCase):
    def test_sanitizes_folder_name(self):
        self.assertEqual(
            sanitize_theme_folder_name("  Meu Tema DBZ!  "),
            "meu-tema-dbz",
        )

    def test_creates_valid_blank_html_theme(self):
        with TemporaryDirectory() as temporary:
            themes = Path(temporary) / "themes"
            folder_name = create_blank_html_theme("Meu Tema", themes)
            self.assertEqual(folder_name, "meu-tema")

            root = themes / folder_name
            manifest = ThemeManifest.load(root)
            self.assertEqual(manifest.engine, "html")
            self.assertEqual((manifest.width, manifest.height), (480, 480))
            self.assertEqual(manifest.refresh_rate, 2)
            self.assertEqual(manifest.overlay_document, "overlays.json")
            self.assertFalse(manifest.network)
            self.assertIn("sensors", manifest.permissions)

            expected_files = {
                "manifest.json",
                "index.html",
                "style.css",
                "theme.js",
                "overlays.json",
                "theme-editor-overrides.css",
                "theme-editor-widgets.js",
            }
            self.assertTrue(expected_files.issubset({path.name for path in root.iterdir()}))
            self.assertTrue((root / "assets").is_dir())

            html = (root / "index.html").read_text(encoding="utf-8")
            self.assertIn("Content-Security-Policy", html)
            self.assertIn(f'id="{STARTER_ELEMENT_ID}"', html)
            self.assertIn("data-turing-overlay", html)
            self.assertIn("theme-editor-widgets.js", html)

            styles = load_visual_styles(manifest)
            self.assertEqual(len(styles), 1)
            self.assertEqual(styles[0].element_id, STARTER_ELEMENT_ID)
            self.assertTrue(styles[0].is_generated)
            self.assertFalse(styles[0].visible)
            self.assertEqual(styles[0].opacity, 0)

            payload = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["atomicRegions"], [])
            self.assertFalse(list(root.glob("*.visual.editor-backup")))

    def test_does_not_overwrite_existing_theme(self):
        with TemporaryDirectory() as temporary:
            themes = Path(temporary) / "themes"
            create_blank_html_theme("Repeated", themes)
            with self.assertRaises(FileExistsError):
                create_blank_html_theme("Repeated", themes)

    def test_rejects_empty_name_without_leaving_staging_directory(self):
        with TemporaryDirectory() as temporary:
            themes = Path(temporary) / "themes"
            with self.assertRaises(ValueError):
                create_blank_html_theme("   ", themes)
            self.assertFalse(themes.exists())


if __name__ == "__main__":
    unittest.main()
