from __future__ import annotations

import unittest
import shutil
from pathlib import Path

from library.theme_engine import ThemeManifest
from library.html_hybrid import validate_native_video


class HtmlAioMaterialThemeTests(unittest.TestCase):
    def setUp(self):
        self.root = (
            Path(__file__).resolve().parents[1]
            / "res"
            / "themes"
            / "html-aio-material-expressive"
        )

    def test_theme_package_is_local_and_valid(self):
        manifest = ThemeManifest.load(self.root)
        html = (self.root / "index.html").read_text(encoding="utf-8")
        css = (self.root / "style.css").read_text(encoding="utf-8")
        javascript = (self.root / "theme.js").read_text(encoding="utf-8")
        combined = "\n".join((html, css, javascript)).lower()

        self.assertEqual(manifest.engine, "html")
        self.assertEqual((manifest.width, manifest.height), (480, 480))
        self.assertFalse(manifest.network)
        self.assertEqual(len(manifest.atomic_regions), 5)
        self.assertNotIn("https://", combined)
        self.assertNotIn("http://", combined)
        self.assertNotIn("tailwind", combined)
        self.assertNotIn("fonts.googleapis.com", combined)
        self.assertIn("content-security-policy", html.lower())

    def test_theme_uses_real_snapshot_contract_without_mock_loop(self):
        javascript = (self.root / "theme.js").read_text(encoding="utf-8")

        self.assertIn("window.TuringTheme", javascript)
        self.assertIn("snapshot.data", javascript)
        self.assertIn("cooling.liquidTemperature", javascript)
        self.assertIn("gpu.fan", javascript)
        self.assertNotIn("Math.random", javascript)
        self.assertNotIn("setInterval", javascript)
        self.assertIn("value === null", javascript)
        self.assertIn("turingRenderMode === 'overlay'", javascript)

    def test_theme_declares_native_video_and_explicit_live_layer(self):
        manifest = ThemeManifest.load(self.root)
        spec = manifest.native_video_overlay
        self.assertIsNotNone(spec)
        self.assertEqual((spec.fps, spec.duration), (24, 8.0))
        html = (self.root / "index.html").read_text(encoding="utf-8")
        for fragment in (
            'id="cpu-load" data-turing-overlay',
            'class="temperature-row" data-turing-overlay',
            'id="cpu-bar" data-turing-overlay',
            'id="gpu-load" data-turing-overlay',
            'id="gpu-bar" data-turing-overlay',
            'class="liquid-value-row" data-turing-overlay',
            'id="liquid-label" data-turing-overlay',
            'id="liquid-status" data-turing-overlay',
            'id="ram-usage" data-turing-overlay',
            'id="cooling-label" data-turing-overlay',
            'id="pump-value" data-turing-overlay',
            'id="pump-unit" data-turing-overlay',
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, html)

    def test_manifest_controls_each_metric_cadence(self):
        manifest = ThemeManifest.load(self.root)
        policy = manifest.data_update_policy

        self.assertEqual(policy.interval_for("cpu.usage"), 2.0)
        self.assertEqual(policy.interval_for("cpu.temperature"), 5.0)
        self.assertEqual(policy.interval_for("gpu.usage"), 2.0)
        self.assertEqual(policy.interval_for("memory.total"), 30.0)
        self.assertEqual(policy.interval_for("cooling.pumpRpm"), 5.0)

    @unittest.skipUnless(shutil.which("ffprobe"), "ffprobe is unavailable")
    def test_built_native_video_matches_physical_profile(self):
        manifest = ThemeManifest.load(self.root)
        probe = validate_native_video(manifest)
        self.assertEqual((probe.width, probe.height), (480, 480))
        self.assertEqual(probe.profile, "Constrained Baseline")
        self.assertEqual(probe.has_b_frames, 0)
        self.assertFalse(probe.has_audio)
        self.assertAlmostEqual(probe.duration, 8.0, places=2)


if __name__ == "__main__":
    unittest.main()
