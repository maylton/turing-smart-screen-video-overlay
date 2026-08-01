from __future__ import annotations

import json
import math
import unittest
from pathlib import Path

from library.sensor_snapshot import (
    SCHEMA_VERSION,
    SensorSnapshotCollector,
    StaticSnapshotSource,
)


class SensorSnapshotTests(unittest.TestCase):
    def test_collects_stable_json_shape(self):
        source = StaticSnapshotSource(
            {
                "cpu": {"usage": 42.5, "temperature": 61},
                "gpu": {"name": "Radeon", "usage": 73},
            }
        )
        collector = SensorSnapshotCollector(
            source.readers(),
            clock=lambda: 1234.5,
        )

        payload = collector.collect().as_dict()

        self.assertEqual(payload["schemaVersion"], SCHEMA_VERSION)
        self.assertEqual(payload["timestamp"], 1234.5)
        self.assertEqual(payload["sequence"], 1)
        self.assertEqual(payload["data"]["cpu"]["usage"], 42.5)
        self.assertIn("memory", payload["data"])
        self.assertEqual(payload["errors"], {})

    def test_reader_failure_is_isolated(self):
        collector = SensorSnapshotCollector(
            {
                "cpu": lambda: {"usage": 20},
                "gpu": lambda: (_ for _ in ()).throw(RuntimeError("offline")),
            },
            clock=lambda: 1,
        )

        payload = collector.collect().as_dict()

        self.assertEqual(payload["data"]["cpu"]["usage"], 20)
        self.assertEqual(payload["data"]["gpu"], {})
        self.assertIn("RuntimeError: offline", payload["errors"]["gpu"])

    def test_non_json_values_are_normalized(self):
        collector = SensorSnapshotCollector(
            {
                "custom": lambda: {
                    "nan": math.nan,
                    "infinity": math.inf,
                    "path": Path("asset.png"),
                    "tuple": (1, 2),
                }
            },
            clock=lambda: 1,
        )

        serialized = collector.collect().to_json()
        payload = json.loads(serialized)

        self.assertIsNone(payload["data"]["custom"]["nan"])
        self.assertIsNone(payload["data"]["custom"]["infinity"])
        self.assertEqual(payload["data"]["custom"]["path"], "asset.png")
        self.assertEqual(payload["data"]["custom"]["tuple"], [1, 2])

    def test_sequence_increments(self):
        collector = SensorSnapshotCollector(clock=lambda: 1)
        self.assertEqual(collector.collect().sequence, 1)
        self.assertEqual(collector.collect().sequence, 2)

    def test_register_rejects_invalid_reader(self):
        collector = SensorSnapshotCollector()
        with self.assertRaises(ValueError):
            collector.register("", lambda: {})
        with self.assertRaises(TypeError):
            collector.register("cpu", None)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
