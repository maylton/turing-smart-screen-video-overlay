import json
import re
import unittest
from pathlib import Path

from library.html_theme_round_mask import (
    OUTSIDE_TOLERANCE_PX,
    is_probably_round,
    round_mask_script,
)

ROOT = Path(__file__).resolve().parents[1]


class RoundMaskTests(unittest.TestCase):
    def test_square_displays_are_treated_as_round(self):
        self.assertTrue(is_probably_round(480, 480))
        self.assertFalse(is_probably_round(320, 480))

    def test_script_embeds_display_geometry(self):
        script = round_mask_script(480, 480)
        config = json.loads(re.search(r"const config = (\{.*?\});", script).group(1))
        self.assertEqual(
            config,
            {"width": 480, "height": 480, "tolerance": OUTSIDE_TOLERANCE_PX},
        )

    def test_script_is_idempotent_and_never_restyles_theme_elements(self):
        script = round_mask_script(480, 480)
        self.assertIn("if (window.__turingEditorSetRoundMask) return;", script)
        self.assertIn("[data-turing-overlay]", script)
        self.assertNotIn("element.style", script)

    def test_editor_wires_round_mask(self):
        source = (ROOT / "html-theme-editor-gtk.py").read_text(encoding="utf-8")
        self.assertIn("Mostrar a área visível da tela redonda", source)
        self.assertIn("round_mask_script(self.manifest.width, self.manifest.height)", source)
        self.assertIn("__turingEditorSetRoundMask", source)


if __name__ == "__main__":
    unittest.main()
