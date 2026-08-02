# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from library.html_theme_engine import HtmlThemeEngine
from library.sensor_snapshot import SensorSnapshot
from library.sensor_update_scheduler import (
    SensorUpdatePolicy,
    SensorUpdateScheduler,
)
from library.theme_engine import ThemeManifest, ThemeValidationError


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class FakeBackend:
    def __init__(self, manifest):
        self.manifest = manifest
        self.view = object()
        self.scripts = []
        self.loaded = False
        self.closed = False

    def load(self):
        self.loaded = True

    def evaluate(self, script):
        self.scripts.append(script)

    def close(self):
        self.closed = True


def snapshot(sequence, timestamp, *, usage, temperature, frequency):
    return SensorSnapshot(
        schema_version=1,
        timestamp=float(timestamp),
        sequence=int(sequence),
        data={
            "cpu": {
                "usage": usage,
                "temperature": temperature,
                "frequency": frequency,
            },
            "system": {"time": f"12:00:0{sequence}"},
        },
        errors={},
    )


class SensorUpdateSchedulerTests(unittest.TestCase):
    def test_exact_paths_override_wildcards_and_default(self):
        policy = SensorUpdatePolicy(
            default_interval=10.0,
            overrides=(
                ("cpu.*", 2.0),
                ("cpu.temperature", 5.0),
                ("$sequence", 3.0),
            ),
        )
        self.assertEqual(policy.interval_for("cpu.usage"), 2.0)
        self.assertEqual(policy.interval_for("cpu.temperature"), 5.0)
        self.assertEqual(policy.interval_for("gpu.usage"), 10.0)
        self.assertEqual(policy.interval_for("$sequence"), 3.0)

    def test_first_snapshot_is_complete_and_fields_release_independently(self):
        clock = FakeClock()
        policy = SensorUpdatePolicy(
            default_interval=10.0,
            overrides=(
                ("cpu.usage", 2.0),
                ("cpu.temperature", 5.0),
                ("cpu.frequency", 5.0),
                ("system.time", 1.0),
                ("$sequence", 2.0),
                ("$timestamp", 1.0),
            ),
        )
        scheduler = SensorUpdateScheduler(policy, clock=clock)

        first = scheduler.apply(
            snapshot(1, 1000, usage=10, temperature=50, frequency=4.0)
        )
        self.assertEqual(first.data["cpu"]["usage"], 10)
        self.assertEqual(first.data["cpu"]["temperature"], 50)
        self.assertEqual(first.sequence, 1)

        clock.advance(1.0)
        second = scheduler.apply(
            snapshot(2, 1001, usage=20, temperature=60, frequency=4.5)
        )
        self.assertEqual(second.data["cpu"]["usage"], 10)
        self.assertEqual(second.data["cpu"]["temperature"], 50)
        self.assertEqual(second.data["system"]["time"], "12:00:02")
        self.assertEqual(second.sequence, 1)
        self.assertEqual(second.timestamp, 1001.0)

        clock.advance(1.0)
        third = scheduler.apply(
            snapshot(3, 1002, usage=30, temperature=70, frequency=5.0)
        )
        self.assertEqual(third.data["cpu"]["usage"], 30)
        self.assertEqual(third.data["cpu"]["temperature"], 50)
        self.assertEqual(third.data["cpu"]["frequency"], 4.0)
        self.assertEqual(third.sequence, 3)

        clock.advance(3.0)
        fourth = scheduler.apply(
            snapshot(4, 1005, usage=40, temperature=80, frequency=5.5)
        )
        self.assertEqual(fourth.data["cpu"]["temperature"], 80)
        self.assertEqual(fourth.data["cpu"]["frequency"], 5.5)

    def test_missing_fields_do_not_erase_retained_values(self):
        clock = FakeClock()
        scheduler = SensorUpdateScheduler(
            SensorUpdatePolicy(default_interval=1.0),
            clock=clock,
        )
        first = scheduler.apply(
            snapshot(1, 1000, usage=10, temperature=50, frequency=4.0)
        )
        self.assertEqual(first.data["cpu"]["temperature"], 50)

        clock.advance(1.0)
        partial = SensorSnapshot(
            schema_version=1,
            timestamp=1001,
            sequence=2,
            data={"cpu": {"usage": 20}},
            errors={},
        )
        second = scheduler.apply(partial)
        self.assertEqual(second.data["cpu"]["usage"], 20)
        self.assertEqual(second.data["cpu"]["temperature"], 50)

    def test_manifest_parses_intervals_and_old_themes_keep_global_cadence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "theme"
            root.mkdir()
            (root / "index.html").write_text("<!doctype html>", encoding="utf-8")
            payload = {
                "engine": "html",
                "display": {"width": 480, "height": 480},
                "refreshRate": 2,
                "entrypoint": "index.html",
                "permissions": ["sensors"],
                "dataUpdateIntervals": {
                    "default": 5,
                    "cpu.usage": 2,
                    "cpu.temperature": 5,
                },
            }
            (root / "manifest.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            manifest = ThemeManifest.load(root)
            self.assertEqual(manifest.data_update_policy.default_interval, 5.0)
            self.assertEqual(
                manifest.data_update_policy.interval_for("cpu.usage"), 2.0
            )

            payload.pop("dataUpdateIntervals")
            (root / "manifest.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            legacy = ThemeManifest.load(root)
            self.assertEqual(legacy.data_update_policy.default_interval, 0.5)

    def test_manifest_rejects_invalid_paths_and_intervals(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "theme"
            root.mkdir()
            (root / "index.html").write_text("<!doctype html>", encoding="utf-8")
            payload = {
                "engine": "html",
                "entrypoint": "index.html",
                "permissions": ["sensors"],
                "dataUpdateIntervals": {"cpu usage": 0},
            }
            (root / "manifest.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            with self.assertRaises(ThemeValidationError):
                ThemeManifest.load(root)

    def test_html_engine_sends_retained_snapshot_to_javascript(self):
        clock = FakeClock()
        backends = []

        def factory(manifest):
            backend = FakeBackend(manifest)
            backends.append(backend)
            return backend

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "theme"
            root.mkdir()
            (root / "index.html").write_text("<!doctype html>", encoding="utf-8")
            (root / "manifest.json").write_text(
                json.dumps(
                    {
                        "engine": "html",
                        "entrypoint": "index.html",
                        "permissions": ["sensors"],
                        "refreshRate": 2,
                        "dataUpdateIntervals": {
                            "default": 5,
                            "cpu.usage": 2,
                        },
                    }
                ),
                encoding="utf-8",
            )
            manifest = ThemeManifest.load(root)
            engine = HtmlThemeEngine(factory, clock=clock)
            engine.load(manifest)
            engine.update(
                snapshot(1, 1000, usage=10, temperature=50, frequency=4.0)
            )
            clock.advance(1.0)
            engine.update(
                snapshot(2, 1001, usage=20, temperature=60, frequency=4.5)
            )
            engine.close()

        self.assertEqual(len(backends[0].scripts), 2)
        self.assertIn('"usage":10', backends[0].scripts[1])
        self.assertIn('"temperature":50', backends[0].scripts[1])
        self.assertTrue(backends[0].closed)


if __name__ == "__main__":
    unittest.main()
