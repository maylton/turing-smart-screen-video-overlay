from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from library.theme_property_presets import property_preset_options


class ThemePropertyPresetTests(unittest.TestCase):
    def test_static_stage_one_properties_have_presets(self):
        keys = (
            "DISPLAY_SIZE",
            "DISPLAY_ORIENTATION",
            "ALIGN",
            "ANCHOR",
            "FORMAT",
            "FONT_SIZE",
            "AXIS_FONT_SIZE",
            "X",
            "Y",
            "WIDTH",
            "HEIGHT",
            "RADIUS",
            "INTERVAL",
            "REFRESH_INTERVAL",
            "MIN_VALUE",
            "MAX_VALUE",
            "MIN_SIZE",
            "LINE_WIDTH",
            "HISTORY_SIZE",
            "ANGLE_START",
            "ANGLE_END",
            "ANGLE_STEPS",
            "ANGLE_SEP",
            "BAR_DECORATION",
        )
        for key in keys:
            with self.subTest(key=key):
                self.assertGreater(len(property_preset_options(key, None)), 0)

    def test_numeric_presets_keep_typed_values(self):
        options = property_preset_options("FONT_SIZE", 24)
        values = [value for _label, value in options]
        self.assertIn(24, values)
        self.assertTrue(all(isinstance(value, int) for value in values))

    def test_float_presets_keep_typed_values(self):
        options = property_preset_options("REFRESH_INTERVAL", 0.5)
        values = [value for _label, value in options]
        self.assertIn(0.5, values)
        self.assertTrue(all(isinstance(value, float) for value in values))

    def test_unknown_current_value_is_preserved(self):
        options = property_preset_options("FONT_SIZE", 37)
        self.assertEqual(options[0], ("Current — 37", 37))

    def test_known_current_value_is_not_duplicated(self):
        options = property_preset_options("ALIGN", "center")
        values = [value for _label, value in options]
        self.assertEqual(values.count("center"), 1)

    def test_fonts_are_discovered_recursively(self):
        with tempfile.TemporaryDirectory() as temporary:
            fonts = Path(temporary)
            nested = fonts / "family"
            nested.mkdir()
            (nested / "Example.ttf").write_bytes(b"font")
            (nested / "ignore.txt").write_text("ignore", encoding="utf-8")
            options = property_preset_options(
                "FONT",
                "family/Example.ttf",
                fonts_dir=fonts,
        )
        self.assertIn(("family/Example.ttf", "family/Example.ttf"), options)
        self.assertNotIn(("ignore.txt", "ignore.txt"), options)

    def test_fonts_are_sorted_predictably(self):
        with tempfile.TemporaryDirectory() as temporary:
            fonts = Path(temporary)
            (fonts / "zeta.otf").write_bytes(b"font")
            (fonts / "Alpha.ttc").write_bytes(b"font")
            (fonts / "nested").mkdir()
            (fonts / "nested" / "beta.ttf").write_bytes(b"font")
            options = property_preset_options(
                "AXIS_FONT",
                None,
                fonts_dir=fonts,
            )
        labels = [label for label, _value in options]
        self.assertEqual(labels, ["Alpha.ttc", "nested/beta.ttf", "zeta.otf"])

    def test_theme_images_are_discovered(self):
        with tempfile.TemporaryDirectory() as temporary:
            theme = Path(temporary)
            (theme / "background.png").write_bytes(b"png")
            (theme / "notes.txt").write_text("ignore", encoding="utf-8")
            options = property_preset_options(
                "BACKGROUND_IMAGE",
                "background.png",
                theme_dir=theme,
            )
        self.assertIn(("background.png", "background.png"), options)
        self.assertNotIn(("notes.txt", "notes.txt"), options)

    def test_theme_images_are_sorted_predictably(self):
        with tempfile.TemporaryDirectory() as temporary:
            theme = Path(temporary)
            (theme / "zeta.webp").write_bytes(b"image")
            (theme / "Alpha.JPG").write_bytes(b"image")
            (theme / "nested").mkdir()
            (theme / "nested" / "beta.gif").write_bytes(b"image")
            options = property_preset_options(
                "PREVIEW_BACKGROUND",
                None,
                theme_dir=theme,
            )
        labels = [label for label, _value in options]
        self.assertEqual(labels, ["Alpha.JPG", "nested/beta.gif", "zeta.webp"])

    def test_missing_asset_directories_do_not_raise(self):
        missing = Path("/tmp/this/theme/property/preset/path/does/not/exist")
        self.assertEqual(
            property_preset_options("FONT", None, fonts_dir=missing),
            [],
        )
        self.assertEqual(
            property_preset_options(
                "BACKGROUND_IMAGE",
                None,
                theme_dir=str(missing),
            ),
            [],
        )

    def test_unsupported_property_returns_current_only(self):
        self.assertEqual(
            property_preset_options("UNSUPPORTED", "custom"),
            [("Current — custom", "custom")],
        )
        self.assertEqual(property_preset_options("UNSUPPORTED", None), [])


if __name__ == "__main__":
    unittest.main()
