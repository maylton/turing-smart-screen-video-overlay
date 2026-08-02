from __future__ import annotations

import json
import unittest
from pathlib import Path

from library.html_theme_authoring import discover_overlay_candidates
from library.html_theme_visual_editor import load_visual_styles
from library.theme_engine import ThemeManifest


ROOT = Path(__file__).resolve().parents[1]
THEME_ROOT = ROOT / "res" / "themes" / "html-cosmic-portal-clock"


class CosmicPortalThemeTests(unittest.TestCase):
    def test_composite_overlays_use_canonical_blank_widget_metadata(self):
        manifest = ThemeManifest.load(THEME_ROOT)
        candidates = discover_overlay_candidates(manifest)
        marked_ids = tuple(item.element_id for item in candidates if item.marked)
        self.assertEqual(marked_ids, ("date-card", "clock", "cpu-card"))

        styles = load_visual_styles(manifest)
        self.assertEqual(
            tuple(style.element_id for style in styles),
            ("date-card", "clock", "cpu-card"),
        )
        for style in styles:
            self.assertFalse(style.generated_widget)
            self.assertEqual(style.component_type, "")
            self.assertEqual(style.binding, "")
            self.assertEqual(style.formatter, "")
            self.assertEqual(style.sample, "")

    def test_atomic_regions_match_composite_overlay_ids(self):
        payload = json.loads(
            (THEME_ROOT / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            [region["name"] for region in payload["atomicRegions"]],
            ["date-card", "clock", "cpu-card"],
        )


if __name__ == "__main__":
    unittest.main()
