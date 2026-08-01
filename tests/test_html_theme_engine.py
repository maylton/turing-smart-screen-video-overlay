from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from library.html_theme_engine import (
    HtmlThemeEngine,
    build_snapshot_script,
    is_allowed_theme_uri,
)
from library.sensor_snapshot import SensorSnapshotCollector
from library.theme_engine import ThemeManifest, ThemeValidationError


class FakeBackend:
    def __init__(self, manifest):
        self.manifest = manifest
        self.view = object()
        self.loaded = False
        self.scripts = []
        self.closed = False
        self.snapshots = []

    def load(self):
        self.loaded = True

    def evaluate(self, script):
        self.scripts.append(script)

    def snapshot_png(self, destination, callback=None):
        self.snapshots.append(Path(destination))
        if callback:
            callback(None)

    def close(self):
        self.closed = True


class HtmlThemeEngineTests(unittest.TestCase):
    def create_theme(self, root: Path, *, network=False):
        root.mkdir(parents=True)
        (root / "index.html").write_text("<!doctype html>", encoding="utf-8")
        permissions = '["sensors", "network"]' if network else '["sensors"]'
        (root / "manifest.json").write_text(
            "{"
            '"engine":"html",'
            '"name":"Demo",'
            '"version":1,'
            '"display":{"width":480,"height":480},'
            '"refreshRate":2,'
            '"entrypoint":"index.html",'
            f'"permissions":{permissions},'
            f'"network":{str(network).lower()}'
            "}",
            encoding="utf-8",
        )
        return ThemeManifest.load(root)

    def test_uri_policy_confines_files_to_theme(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "theme"
            root.mkdir()
            asset = root / "asset.png"
            asset.touch()
            outside = Path(temporary) / "outside.png"
            outside.touch()
            self.assertTrue(is_allowed_theme_uri(asset.as_uri(), root))
            self.assertFalse(is_allowed_theme_uri(outside.as_uri(), root))
            self.assertFalse(is_allowed_theme_uri("https://example.com/a.js", root))
            self.assertFalse(is_allowed_theme_uri("javascript:alert(1)", root))
            self.assertTrue(is_allowed_theme_uri("data:image/png;base64,AA==", root))

    def test_snapshot_script_contains_only_serialized_payload(self):
        snapshot = SensorSnapshotCollector(
            {"cpu": lambda: {"usage": 42, "label": "</script>"}},
            clock=lambda: 1,
        ).collect()
        script = build_snapshot_script(snapshot)
        self.assertIn("window.TuringTheme.update(snapshot)", script)
        self.assertIn('"usage":42', script)
        self.assertNotIn("nan", script.lower())

    def test_engine_lifecycle_uses_injected_backend(self):
        backends = []

        def factory(manifest):
            backend = FakeBackend(manifest)
            backends.append(backend)
            return backend

        with tempfile.TemporaryDirectory() as temporary:
            manifest = self.create_theme(Path(temporary) / "theme")
            engine = HtmlThemeEngine(factory)
            engine.load(manifest)
            snapshot = SensorSnapshotCollector(clock=lambda: 1).collect()
            engine.update(snapshot)
            self.assertIs(engine.render(), backends[0].view)
            engine.snapshot_png(Path(temporary) / "preview.png")
            engine.close()

        self.assertTrue(backends[0].loaded)
        self.assertEqual(len(backends[0].scripts), 1)
        self.assertTrue(backends[0].closed)

    def test_safe_prototype_rejects_network_theme(self):
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self.create_theme(Path(temporary) / "theme", network=True)
            engine = HtmlThemeEngine(FakeBackend)
            with self.assertRaises(ThemeValidationError):
                engine.load(manifest)

    def test_repository_demo_theme_is_valid_and_has_csp(self):
        root = Path(__file__).resolve().parents[1]
        theme = root / "res" / "themes" / "html-demo"
        manifest = ThemeManifest.load(theme)
        html = (theme / "index.html").read_text(encoding="utf-8")
        self.assertEqual(manifest.engine, "html")
        self.assertFalse(manifest.network)
        self.assertIn("Content-Security-Policy", html)
        self.assertIn("connect-src 'none'", html)


if __name__ == "__main__":
    unittest.main()
