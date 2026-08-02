from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from library.html_hybrid import validate_native_video
from library.html_theme_authoring import (
    discover_overlay_candidates,
    inspect_native_video_artifact,
)
from library.theme_engine import ThemeManifest


class HtmlElvenReverieThemeTests(unittest.TestCase):
    def setUp(self):
        self.root = (
            Path(__file__).resolve().parents[1]
            / "res"
            / "themes"
            / "html-elven-reverie"
        )

    def test_package_is_local_safe_and_uses_snapshot_bridge(self):
        manifest = ThemeManifest.load(self.root)
        html = (self.root / "index.html").read_text(encoding="utf-8")
        css = (self.root / "style.css").read_text(encoding="utf-8")
        javascript = (self.root / "theme.js").read_text(encoding="utf-8")
        combined = "\n".join((html, css, javascript)).lower()

        self.assertEqual(manifest.engine, "html")
        self.assertEqual((manifest.width, manifest.height), (480, 480))
        self.assertFalse(manifest.network)
        self.assertEqual(manifest.permissions, ("sensors",))
        self.assertIn("content-security-policy", html.lower())
        self.assertIn("window.TuringTheme", javascript)
        self.assertIn("snapshot.data", javascript)
        self.assertNotIn("https://", combined)
        self.assertNotIn("http://", "\n".join((html, javascript)).lower())
        self.assertNotIn("url(\"http", css.lower())
        self.assertNotIn("Math.random", javascript)
        self.assertNotIn("setInterval", javascript)
        self.assertNotIn("updateThemeMetrics", javascript)

    def test_live_values_are_explicit_overlays(self):
        manifest = ThemeManifest.load(self.root)
        marked = {
            candidate.element_id
            for candidate in discover_overlay_candidates(manifest)
            if candidate.marked
        }
        self.assertEqual(
            marked,
            {
                "time-display",
                "cpu-value",
                "gpu-value",
                "ram-value",
            },
        )

    def test_generated_video_matches_current_sources(self):
        state = inspect_native_video_artifact(ThemeManifest.load(self.root))
        self.assertEqual(state.status, "ready", state.message)

    @unittest.skipUnless(shutil.which("ffprobe"), "ffprobe is unavailable")
    def test_generated_video_matches_physical_profile(self):
        probe = validate_native_video(ThemeManifest.load(self.root))
        self.assertEqual((probe.width, probe.height), (480, 480))
        self.assertEqual(probe.profile, "Constrained Baseline")
        self.assertEqual(probe.has_b_frames, 0)
        self.assertFalse(probe.has_audio)
        self.assertAlmostEqual(probe.duration, 8.0, places=2)


if __name__ == "__main__":
    unittest.main()
