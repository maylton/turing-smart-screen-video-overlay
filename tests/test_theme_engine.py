from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from library.sensor_snapshot import SensorSnapshotCollector
from library.theme_engine import (
    LegacyYamlThemeEngine,
    ThemeEngine,
    ThemeEngineError,
    ThemeEngineRegistry,
    ThemeManifest,
    ThemeValidationError,
)


class FakeEngine(ThemeEngine):
    def __init__(self):
        self.manifest = None
        self.snapshot = None
        self.closed = False

    def load(self, manifest):
        self.manifest = manifest

    def update(self, snapshot):
        self.snapshot = snapshot

    def render(self):
        return {"ok": True}

    def close(self):
        self.closed = True


class ThemeEngineTests(unittest.TestCase):
    def write_html_theme(self, root: Path, **overrides):
        root.mkdir(parents=True)
        (root / "index.html").write_text("<html></html>", encoding="utf-8")
        payload = {
            "engine": "html",
            "name": "HTML demo",
            "version": 1,
            "display": {"width": 480, "height": 480},
            "refreshRate": 2,
            "entrypoint": "index.html",
            "permissions": ["sensors"],
            "network": False,
        }
        payload.update(overrides)
        (root / "manifest.json").write_text(
            json.dumps(payload),
            encoding="utf-8",
        )

    def test_discovers_legacy_yaml_without_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "theme.yaml").write_text("display: {}", encoding="utf-8")
            manifest = ThemeManifest.load(root)

        self.assertEqual(manifest.engine, "yaml")
        self.assertEqual(manifest.entrypoint, "theme.yaml")

    def test_loads_html_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "theme"
            self.write_html_theme(root)
            manifest = ThemeManifest.load(root)

        self.assertEqual(manifest.engine, "html")
        self.assertEqual((manifest.width, manifest.height), (480, 480))
        self.assertEqual(manifest.refresh_rate, 2.0)
        self.assertFalse(manifest.network)

    def test_rejects_entrypoint_outside_theme(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "theme"
            self.write_html_theme(root, entrypoint="../outside.html")
            with self.assertRaises(ThemeValidationError):
                ThemeManifest.load(root)

    def test_network_requires_permission(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "theme"
            self.write_html_theme(root, permissions=["sensors"], network=True)
            with self.assertRaises(ThemeValidationError):
                ThemeManifest.load(root)

    def test_registry_loads_created_engine(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "theme"
            self.write_html_theme(root)
            manifest = ThemeManifest.load(root)
            registry = ThemeEngineRegistry()
            registry.register("html", FakeEngine)
            engine = registry.create(manifest)

        self.assertIsInstance(engine, FakeEngine)
        self.assertEqual(engine.manifest, manifest)

    def test_registry_rejects_unregistered_engine(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "theme.yaml").write_text("display: {}", encoding="utf-8")
            manifest = ThemeManifest.load(root)
            with self.assertRaises(ThemeEngineError):
                ThemeEngineRegistry().create(manifest)

    def test_yaml_adapter_preserves_callback_lifecycle(self):
        events = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "theme.yaml").write_text("display: {}", encoding="utf-8")
            manifest = ThemeManifest.load(root)
            snapshot = SensorSnapshotCollector(clock=lambda: 1).collect()
            engine = LegacyYamlThemeEngine(
                load_callback=lambda item: events.append(("load", item.engine)),
                update_callback=lambda item: events.append(("update", item.sequence)),
                render_callback=lambda: events.append(("render", None)) or "frame",
                close_callback=lambda: events.append(("close", None)),
            )
            engine.load(manifest)
            engine.update(snapshot)
            self.assertEqual(engine.render(), "frame")
            engine.close()

        self.assertEqual(
            events,
            [("load", "yaml"), ("update", 1), ("render", None), ("close", None)],
        )


if __name__ == "__main__":
    unittest.main()
