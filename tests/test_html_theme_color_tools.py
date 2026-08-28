from __future__ import annotations

import unittest
from pathlib import Path

from library.html_theme_color_tools import (
    PICK_TITLE_PREFIX,
    color_distance,
    normalize_hex,
    preview_palette_script,
    preview_picker_script,
    relative_luminance,
    smart_palette,
)


class HtmlThemeColorToolsTests(unittest.TestCase):
    def test_normalizes_only_full_hex_colors(self):
        self.assertEqual(normalize_hex(" #Aa22FF "), "#aa22ff")
        self.assertEqual(normalize_hex("red"), "#ffffff")
        self.assertEqual(normalize_hex("#fff"), "#ffffff")

    def test_smart_palette_uses_contrast_and_two_accents(self):
        result = smart_palette(
            ["#120818", "#f8f4ff", "#ff4fa3", "#6fe7ff", "#584080"]
        )
        self.assertEqual(result["main"], "#f8f4ff")
        self.assertEqual(result["outline"], "#120818")
        self.assertNotEqual(result["gradient_start"], result["gradient_end"])
        self.assertGreater(
            color_distance(result["gradient_start"], result["gradient_end"]),
            0,
        )
        self.assertLess(relative_luminance(result["outline"]), relative_luminance(result["main"]))

    def test_picker_script_is_one_shot_and_uses_preview_image(self):
        script = preview_picker_script()
        self.assertIn(PICK_TITLE_PREFIX, script)
        self.assertIn("__turing-background-preview", script)
        self.assertIn("getImageData", script)
        self.assertIn("crosshair", script)
        self.assertIn("stopImmediatePropagation", script)

    def test_palette_script_returns_diverse_preview_colors(self):
        script = preview_palette_script()
        self.assertIn("__turing-background-preview", script)
        self.assertIn("colors.length >= 8", script)
        self.assertIn("30 ** 2", script)
        self.assertIn("getComputedStyle", script)

    def test_color_tools_do_not_create_an_inspector_tab(self):
        source = Path("library/html_theme_color_tools.py").read_text(encoding="utf-8")
        self.assertNotIn("add_titled", source)
        self.assertIn('Gtk.Expander(label="Cores do tema")', source)
        self.assertIn('"style"', source)
        self.assertIn('"effects"', source)

    def test_runtime_bootstrap_keeps_linux_virtualenv_candidates(self):
        source = Path("library/runtime_python.py").read_text(encoding="utf-8")
        self.assertIn('root / "venv" / "bin" / "python3"', source)
        self.assertIn('root / ".venv" / "bin" / "python3"', source)
        self.assertIn("install_color_tools_hook", source)


if __name__ == "__main__":
    unittest.main()
