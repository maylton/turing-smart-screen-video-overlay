import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from library.html_theme_style_presets import (
    apply_visual_style_preset,
    get_visual_style_preset,
    install_outer_text_outline_renderer,
    outer_outline_css,
    visual_style_presets,
)
from library.html_theme_visual_editor import (
    HtmlVisualElementStyle,
    render_visual_stylesheet,
)
from library.theme_engine import ThemeManifest, ThemeValidationError


class HtmlThemeStylePresetTests(unittest.TestCase):
    def make_manifest(self, root: Path) -> ThemeManifest:
        root.mkdir(parents=True)
        (root / "index.html").write_text(
            "<!doctype html><html><head></head><body></body></html>",
            encoding="utf-8",
        )
        (root / "manifest.json").write_text(
            json.dumps(
                {
                    "engine": "html",
                    "name": "Preset Test",
                    "version": 1,
                    "display": {"width": 480, "height": 480},
                    "refreshRate": 2,
                    "entrypoint": "index.html",
                    "permissions": ["sensors"],
                    "network": False,
                    "atomicRegions": [],
                }
            ),
            encoding="utf-8",
        )
        return ThemeManifest.load(root)

    def text_style(self, manifest: ThemeManifest) -> HtmlVisualElementStyle:
        return HtmlVisualElementStyle(
            element_id="clock-value",
            x=40,
            y=40,
            width=240,
            height=80,
            font_size=48,
            color="#ffffff",
            font_weight=700,
            text_align="center",
            opacity=100,
            z_index=1000,
            visible=True,
            element_kind="text",
            effects_managed=True,
            outline_width=2,
            outline_color="#000000",
        ).validated(manifest)

    def bar_style(self, manifest: ThemeManifest) -> HtmlVisualElementStyle:
        return HtmlVisualElementStyle(
            element_id="cpu-bar",
            x=420,
            y=450,
            width=60,
            height=12,
            font_size=12,
            color="#ffffff",
            opacity=100,
            z_index=1000,
            visible=True,
            element_kind="bar",
            effects_managed=True,
        ).validated(manifest)

    def test_outer_outline_is_painted_behind_fill_at_double_width(self):
        with TemporaryDirectory() as temporary:
            manifest = self.make_manifest(Path(temporary) / "theme")
            css = outer_outline_css(self.text_style(manifest))
            self.assertIn("paint-order: stroke fill", css)
            self.assertIn("-webkit-text-stroke-width: 4px", css)
            self.assertIn("stroke-linejoin: round", css)

    def test_installed_renderer_appends_outer_outline_override(self):
        with TemporaryDirectory() as temporary:
            manifest = self.make_manifest(Path(temporary) / "theme")
            style = self.text_style(manifest)
            install_outer_text_outline_renderer()
            from library import html_theme_visual_editor as visual

            css = visual.render_visual_stylesheet((style,))
            self.assertIn("Outer-only text outlines", css)
            self.assertIn("paint-order: stroke fill", css)
            self.assertIn("-webkit-text-stroke-width: 4px", css)

    def test_catalog_has_curated_text_and_bar_presets(self):
        text = visual_style_presets("text")
        bars = visual_style_presets("bar")
        self.assertGreaterEqual(len(text), 8)
        self.assertGreaterEqual(len(bars), 7)
        self.assertTrue(all(item.kind == "text" for item in text))
        self.assertTrue(all(item.kind == "bar" for item in bars))

    def test_text_preset_updates_typography_and_effects(self):
        with TemporaryDirectory() as temporary:
            manifest = self.make_manifest(Path(temporary) / "theme")
            updated = apply_visual_style_preset(
                self.text_style(manifest),
                "text-arcade",
                manifest,
            )
            self.assertEqual(updated.font_size, 52)
            self.assertEqual(updated.font_weight, 900)
            self.assertEqual(updated.color, "#ffe45e")
            self.assertEqual(updated.outline_width, 3)
            self.assertTrue(updated.effects_managed)

    def test_bar_preset_is_clamped_to_remaining_canvas(self):
        with TemporaryDirectory() as temporary:
            manifest = self.make_manifest(Path(temporary) / "theme")
            updated = apply_visual_style_preset(
                self.bar_style(manifest),
                get_visual_style_preset("bar-expressive"),
                manifest,
            )
            self.assertEqual(updated.width, 60)
            self.assertEqual(updated.height, 18)
            self.assertTrue(updated.gradient_enabled)

    def test_rejects_preset_for_wrong_element_kind(self):
        with TemporaryDirectory() as temporary:
            manifest = self.make_manifest(Path(temporary) / "theme")
            with self.assertRaises(ThemeValidationError):
                apply_visual_style_preset(
                    self.text_style(manifest),
                    "bar-minimal",
                    manifest,
                )


if __name__ == "__main__":
    unittest.main()
