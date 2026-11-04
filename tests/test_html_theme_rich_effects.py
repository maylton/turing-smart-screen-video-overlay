from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from library import html_theme_rich_effects as rich
from library.html_theme_style_presets import apply_visual_style_preset, visual_style_presets
from library.html_theme_visual_editor import (
    EDITOR_SCHEMA_VERSION,
    HtmlVisualElementStyle,
    load_visual_styles,
    render_visual_stylesheet,
    save_visual_styles,
    visual_style_from_dict,
)
from library.theme_engine import ThemeManifest, ThemeValidationError


def make_theme(root: Path) -> ThemeManifest:
    root.mkdir()
    (root / "index.html").write_text(
        "<!doctype html><html><head></head><body>"
        '<span id="cpu" data-turing-overlay>--%</span>'
        '<div id="bar" data-turing-overlay></div>'
        "</body></html>",
        encoding="utf-8",
    )
    (root / "manifest.json").write_text(json.dumps({
        "engine": "html", "name": "Rich", "version": 1,
        "display": {"width": 480, "height": 480}, "entrypoint": "index.html",
        "permissions": ["sensors"], "network": False,
    }), encoding="utf-8")
    return ThemeManifest.load(root)


def text_style(**overrides) -> HtmlVisualElementStyle:
    values = dict(element_id="cpu", x=20, y=30, width=200, height=60, font_size=32, color="#ffffff", effects_managed=True)
    values.update(overrides)
    return HtmlVisualElementStyle(**values)


def bar_style(**overrides) -> HtmlVisualElementStyle:
    values = dict(element_id="bar", x=20, y=200, width=300, height=14, font_size=16, color="#22d3ee",
                  element_kind="bar", effects_managed=True)
    values.update(overrides)
    return HtmlVisualElementStyle(**values)


class FontCatalogTests(unittest.TestCase):
    def test_every_font_has_files_and_an_ofl_license(self):
        self.assertGreaterEqual(len(rich.theme_fonts()), 10)
        for font in rich.theme_fonts():
            with self.subTest(font=font.key):
                self.assertTrue(font.faces)
                for face in font.faces:
                    self.assertTrue((rich.FONTS_DIR / face.file).is_file())
                license_text = (rich.FONTS_DIR / font.license).read_text(encoding="utf-8")
                self.assertIn("SIL OPEN FONT LICENSE", license_text.upper())

    def test_font_face_css_uses_theme_relative_urls(self):
        css = rich.font_face_css(["orbitron"])
        self.assertIn('font-family: "Orbitron";', css)
        self.assertIn('url("fonts/orbitron/', css)


class RichStyleTests(unittest.TestCase):
    def test_schema_6_round_trip(self):
        style = text_style(font_family="orbitron", letter_spacing=3, text_transform="uppercase",
                           glow_style="neon", glow_radius=12, shadow_x=2, shadow_y=-1, shadow_blur=4,
                           shadow_color="#112233", gradient_enabled=True, gradient_mid_color="#ff00ff")
        self.assertEqual(EDITOR_SCHEMA_VERSION, 6)
        self.assertEqual(visual_style_from_dict(style.as_dict()), style)

    def test_schema_5_documents_get_neutral_defaults(self):
        legacy = {k: v for k, v in text_style().as_dict().items()
                  if k not in {"fontFamily", "letterSpacing", "textTransform", "glowStyle", "shadowX",
                               "shadowY", "shadowBlur", "shadowColor", "gradientMidColor", "barStyle"}}
        style = visual_style_from_dict(legacy)
        self.assertEqual((style.font_family, style.glow_style, style.bar_style, style.shadow_blur), ("", "soft", "solid", 0))

    def test_validation_rejects_unknown_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = make_theme(Path(tmp) / "t")
            for bad in (dict(font_family="comic-sans"), dict(glow_style="laser"), dict(letter_spacing=99),
                        dict(shadow_x=50), dict(gradient_mid_color="red"), dict(text_transform="lowercase")):
                with self.subTest(bad=bad):
                    with self.assertRaises(ThemeValidationError):
                        text_style(**bad).validated(manifest)
            with self.assertRaises(ThemeValidationError):
                bar_style(bar_style="zigzag").validated(manifest)

    def test_neon_glow_has_a_white_core_and_widening_halos(self):
        shadow = rich.rich_effect_properties(text_style(glow_radius=24, glow_color="#ff3dbb", glow_style="neon"))["text"]["text-shadow"]
        self.assertEqual(shadow, "0 0 4px #ffffff, 0 0 8px #ff3dbb, 0 0 16px #ff3dbb, 0 0 24px #ff3dbb")

    def test_shadow_comes_before_glow(self):
        shadow = rich.rich_effect_properties(text_style(shadow_x=3, shadow_y=3, shadow_color="#140026", glow_radius=10))["text"]["text-shadow"]
        self.assertTrue(shadow.startswith("3px 3px 0px #140026, 0 0 10px"))

    def test_three_stop_gradient(self):
        props = rich.rich_effect_properties(text_style(gradient_enabled=True, gradient_direction="vertical",
                                                       gradient_start_color="#ffffff", gradient_mid_color="#ff00ff",
                                                       gradient_end_color="#0000ff"))
        self.assertEqual(props["text"]["background-image"], "linear-gradient(180deg, #ffffff, #ff00ff, #0000ff)")

    def test_gradient_text_uses_drop_shadow_instead_of_text_shadow(self):
        props = rich.rich_effect_properties(text_style(gradient_enabled=True, shadow_x=3, shadow_y=3,
                                                       shadow_color="#140026", glow_radius=10, glow_color="#ff4fd8"))
        self.assertEqual(props["text"]["text-shadow"], "none")
        self.assertEqual(props["element"]["filter"], "drop-shadow(3px 3px 0px #140026) drop-shadow(0 0 10px #ff4fd8)")

    def test_bar_styles(self):
        segmented = rich.rich_effect_properties(bar_style(bar_style="segmented"))["fill"]
        self.assertIn("repeating-linear-gradient(90deg", segmented["mask-image"])
        striped = rich.rich_effect_properties(bar_style(bar_style="striped"))["fill"]
        self.assertTrue(striped["background"].startswith("repeating-linear-gradient(45deg"))
        self.assertTrue(striped["background"].endswith("#22d3ee"))
        self.assertEqual(rich.rich_effect_properties(bar_style())["fill"]["mask-image"], "none")

    def test_unmanaged_styles_get_no_rich_css(self):
        self.assertEqual(rich.rich_effect_properties(text_style(effects_managed=False, glow_radius=10)), {})

    def test_stylesheet_declares_used_fonts_and_rich_rules(self):
        css = render_visual_stylesheet([text_style(font_family="vt323", letter_spacing=2), bar_style(bar_style="glossy")])
        self.assertIn('font-family: "VT323";', css)
        self.assertIn('font-family: "VT323", monospace !important;', css)
        self.assertIn("letter-spacing: 2px !important;", css)
        self.assertIn("rgba(255, 255, 255, 0.5)", css)

    def test_save_copies_used_fonts_into_the_theme(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = make_theme(Path(tmp) / "t")
            styles = [text_style(font_family="press-start-2p"), bar_style()]
            manifest = save_visual_styles(manifest, styles)
            fonts = sorted(p.relative_to(manifest.root).as_posix() for p in (manifest.root / "fonts").rglob("*") if p.is_file())
            self.assertIn("fonts/press-start-2p/OFL.txt", fonts)
            self.assertTrue(any(f.endswith(".woff2") for f in fonts))
            loaded = {s.element_id: s for s in load_visual_styles(manifest)}
            self.assertEqual(loaded["cpu"].font_family, "press-start-2p")


class RichPresetTests(unittest.TestCase):
    def test_every_preset_applies_and_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = make_theme(Path(tmp) / "t")
            for preset in visual_style_presets():
                base = text_style() if preset.kind == "text" else bar_style()
                with self.subTest(preset=preset.key):
                    applied = apply_visual_style_preset(base, preset, manifest)
                    self.assertTrue(applied.effects_managed)
                    if preset.font_family:
                        self.assertIsNotNone(rich.get_theme_font(applied.font_family))

    def test_new_presets_exist_for_text_and_bars(self):
        keys = {p.key for p in visual_style_presets()}
        for key in ("text-neon-tube", "text-synthwave-chrome", "text-pixel-arcade", "bar-led-segments", "bar-candy-gloss"):
            self.assertIn(key, keys)
        self.assertGreaterEqual(len(visual_style_presets("text")), 20)
        self.assertGreaterEqual(len(visual_style_presets("bar")), 15)


if __name__ == "__main__":
    unittest.main()
