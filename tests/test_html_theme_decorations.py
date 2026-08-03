from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from library.html_theme_components import (
    generated_widget_markup,
    get_html_widget_component,
    html_widget_components,
    render_widget_runtime_script,
)
from library.html_theme_decorations import (
    apply_date_format,
    apply_shape_type,
    date_format_options,
    install_decorative_shape_renderer,
    is_date_style,
    is_shape_style,
    shape_css,
    shape_options,
)
from library.html_theme_visual_editor import HtmlVisualElementStyle
from library.theme_engine import ThemeManifest


class HtmlThemeDecorationsTests(unittest.TestCase):
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
                    "name": "Decorations",
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

    def date_style(self, manifest: ThemeManifest) -> HtmlVisualElementStyle:
        return HtmlVisualElementStyle(
            element_id="turing-date-1",
            x=20,
            y=20,
            width=220,
            height=40,
            font_size=22,
            color="#ffffff",
            font_weight=600,
            text_align="center",
            component_type="date",
            generated_widget=True,
            binding="$timestamp",
            formatter="date",
            sample="02/08/2026",
            element_kind="text",
        ).validated(manifest)

    def shape_style(self, manifest: ThemeManifest) -> HtmlVisualElementStyle:
        return HtmlVisualElementStyle(
            element_id="turing-shape-squircle-1",
            x=40,
            y=50,
            width=120,
            height=120,
            font_size=6,
            color="#b388ff",
            component_type="shape-squircle",
            generated_widget=True,
            binding="$timestamp",
            formatter="shape",
            sample="shape",
            element_kind="text",
            effects_managed=True,
            gradient_enabled=True,
            gradient_start_color="#ff8bd7",
            gradient_end_color="#8c7dff",
            outline_width=2,
            outline_color="#120818",
            glow_radius=8,
            glow_color="#c77dff",
        ).validated(manifest)

    def test_catalog_exposes_one_generic_shape_entry(self):
        addable = [component.key for component in html_widget_components()]
        self.assertIn("shape-squircle", addable)
        self.assertNotIn("shape-circle", addable)
        self.assertEqual(
            get_html_widget_component("shape-circle").label,
            "Círculo",
        )

    def test_date_catalog_has_common_formats(self):
        keys = [option.key for option in date_format_options()]
        self.assertEqual(keys[0], "date")
        self.assertIn("date-full", keys)
        self.assertIn("date-iso", keys)
        self.assertIn("date-weekday", keys)

    def test_date_format_is_persisted_in_widget_metadata(self):
        with TemporaryDirectory() as temporary:
            manifest = self.make_manifest(Path(temporary) / "theme")
            updated = apply_date_format(
                self.date_style(manifest),
                "date-full",
                manifest,
            )
            self.assertTrue(is_date_style(updated))
            self.assertEqual(updated.formatter, "date-full")
            self.assertEqual(updated.sample, "domingo, 2 de agosto de 2026")
            self.assertEqual(updated.widget_definition().formatter, "date-full")

    def test_shape_type_changes_component_and_default_geometry(self):
        with TemporaryDirectory() as temporary:
            manifest = self.make_manifest(Path(temporary) / "theme")
            updated = apply_shape_type(
                self.shape_style(manifest),
                "line-horizontal",
                manifest,
            )
            self.assertTrue(is_shape_style(updated))
            self.assertEqual(updated.component_type, "shape-line-horizontal")
            self.assertEqual((updated.width, updated.height), (180, 4))
            self.assertEqual(updated.formatter, "shape")

    def test_shape_css_uses_fill_border_glow_and_radius(self):
        with TemporaryDirectory() as temporary:
            manifest = self.make_manifest(Path(temporary) / "theme")
            css = shape_css(self.shape_style(manifest))
            self.assertIn("border-radius: 30%", css)
            self.assertIn("linear-gradient(90deg", css)
            self.assertIn("border: 2px solid #120818", css)
            self.assertIn("box-shadow: 0 0 8px #c77dff", css)
            self.assertIn("font-size: 0", css)

    def test_renderer_appends_shape_rules(self):
        with TemporaryDirectory() as temporary:
            manifest = self.make_manifest(Path(temporary) / "theme")
            install_decorative_shape_renderer()
            from library import html_theme_visual_editor as visual

            css = visual.render_visual_stylesheet((self.shape_style(manifest),))
            self.assertIn("Decorative shapes generated", css)
            self.assertIn("border-radius: 30%", css)

    def test_shape_markup_is_hidden_from_accessibility_and_runtime_text(self):
        markup = generated_widget_markup(
            "turing-shape-squircle-1",
            "shape-squircle",
        )
        self.assertIn('data-turing-format="shape"', markup)
        self.assertIn('aria-hidden="true"', markup)
        runtime = render_widget_runtime_script()
        self.assertIn("format === 'shape'", runtime)
        self.assertIn("date-full", runtime)
        self.assertIn("date-iso", runtime)

    def test_shape_catalog_contains_requested_geometries(self):
        keys = {option.key for option in shape_options()}
        self.assertTrue(
            {
                "squircle",
                "circle",
                "square",
                "rounded-rectangle",
                "pill",
                "line-horizontal",
                "line-vertical",
            }.issubset(keys)
        )


if __name__ == "__main__":
    unittest.main()
