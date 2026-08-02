from __future__ import annotations

import unittest
from pathlib import Path

from library.theme_engine import ThemeManifest


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

    def test_manifest_controls_each_metric_cadence(self):
        manifest = ThemeManifest.load(self.root)
        policy = manifest.data_update_policy

        self.assertEqual(policy.interval_for("cpu.usage"), 2.0)
        self.assertEqual(policy.interval_for("cpu.temperature"), 5.0)
        self.assertEqual(policy.interval_for("gpu.usage"), 2.0)
        self.assertEqual(policy.interval_for("memory.total"), 30.0)
        self.assertEqual(policy.interval_for("cooling.pumpRpm"), 5.0)


if __name__ == "__main__":
    unittest.main()
