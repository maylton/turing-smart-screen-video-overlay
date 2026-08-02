from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from library.html_theme_components import SUPPORTED_WIDGET_FORMATTERS
from library.html_theme_visual_editor import (
    discover_overlay_candidates,
    load_visual_styles,
)
from library.theme_engine import ThemeManifest
from library.theme_package import (
    load_theme_package_descriptor,
    validate_archive_members,
)


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = ROOT / "res" / "theme-templates" / "html-ide-starter"
TEMPLATE_PACKAGE = ROOT / "res" / "theme-templates" / "html-ide-starter.theme"


class HtmlThemeTemplateTests(unittest.TestCase):
    def test_source_template_is_a_complete_editable_html_theme(self):
        manifest = ThemeManifest.load(TEMPLATE_ROOT)
        styles = load_visual_styles(manifest)
        candidates = discover_overlay_candidates(manifest)

        self.assertEqual((manifest.width, manifest.height), (480, 480))
        self.assertEqual(len(styles), 4)
        self.assertEqual(
            {style.element_id for style in styles},
            {candidate.element_id for candidate in candidates if candidate.marked},
        )
        self.assertEqual(
            {style.element_kind for style in styles},
            {"text", "bar"},
        )
        self.assertTrue((TEMPLATE_ROOT / "theme-editor-widgets.js").is_file())
        html = manifest.entrypoint_path.read_text(encoding="utf-8")
        self.assertIn("Content-Security-Policy", html)
        self.assertIn("data-turing-overlay", html)

    def test_packaged_template_matches_the_validated_source(self):
        with tempfile.TemporaryDirectory(prefix="turing-template-package-") as temporary:
            extracted = Path(temporary)
            with zipfile.ZipFile(TEMPLATE_PACKAGE) as archive:
                validate_archive_members(archive)
                names = set(archive.namelist())
                archive.extractall(extracted)

            descriptor = load_theme_package_descriptor(extracted)
            self.assertEqual(descriptor.name, "html-ide-starter")
            self.assertEqual(descriptor.engine, "html")
            packaged_manifest = ThemeManifest.load(extracted)
            packaged_styles = load_visual_styles(packaged_manifest)
            self.assertEqual(len(packaged_styles), 4)
            for source_file in TEMPLATE_ROOT.rglob("*"):
                if source_file.is_file():
                    relative = source_file.relative_to(TEMPLATE_ROOT).as_posix()
                    self.assertIn(relative, names)
                    self.assertEqual(
                        (extracted / relative).read_bytes(),
                        source_file.read_bytes(),
                    )

    def test_authoring_guide_covers_every_runtime_formatter(self):
        guide = (ROOT / "docs" / "HTML_THEME_AUTHORING_GUIDE.md").read_text(
            encoding="utf-8"
        )
        for formatter in SUPPORTED_WIDGET_FORMATTERS:
            with self.subTest(formatter=formatter):
                self.assertIn(f"`{formatter}`", guide)
        for token in (
            "window.TuringTheme",
            "turing-snapshot",
            "nativeVideoOverlay",
            "overlays.json",
            "theme-migrate.py batch",
            "git push",
        ):
            with self.subTest(token=token):
                self.assertIn(token, guide)


if __name__ == "__main__":
    unittest.main()
