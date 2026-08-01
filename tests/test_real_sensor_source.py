from __future__ import annotations

import types
import unittest

from library.real_sensor_source import RealSensorSource
from library.sensor_snapshot import SensorSnapshotCollector


class FakeGpu:
    available_calls = 0

    @classmethod
    def is_available(cls):
        cls.available_calls += 1
        return True

    @staticmethod
    def stats():
        return 72.5, 50.0, 8192.0, 16384.0, 64.2

    @staticmethod
    def frequency():
        return 2450.0

    @staticmethod
    def fan_percent():
        return 38.0

    @staticmethod
    def fps():
        return -1


class FakePsutil:
    def __init__(self):
        self.network_sample = 0

    @staticmethod
    def cpu_percent(interval=None):
        return 37.5

    @staticmethod
    def cpu_freq():
        return types.SimpleNamespace(current=4700.0)

    @staticmethod
    def getloadavg():
        return 1.0, 0.5, 0.25

    @staticmethod
    def cpu_count(logical=True):
        return 16 if logical else 8

    @staticmethod
    def sensors_temperatures():
        return {
            "k10temp": [
                types.SimpleNamespace(current=61.25),
            ],
        }

    @staticmethod
    def virtual_memory():
        gib = 1024 ** 3
        return types.SimpleNamespace(
            total=32 * gib,
            available=12 * gib,
            percent=62.5,
        )

    @staticmethod
    def swap_memory():
        gib = 1024 ** 3
        return types.SimpleNamespace(
            total=8 * gib,
            used=2 * gib,
            percent=25.0,
        )

    @staticmethod
    def disk_usage(_mount):
        gib = 1024 ** 3
        return types.SimpleNamespace(
            total=1000 * gib,
            used=400 * gib,
            free=600 * gib,
            percent=40.0,
        )

    def net_io_counters(self, pernic=True):
        self.network_sample += 1
        return {
            "lo": types.SimpleNamespace(
                bytes_sent=100,
                bytes_recv=100,
            ),
            "enp1s0": types.SimpleNamespace(
                bytes_sent=1000 + self.network_sample * 2 * 1024 ** 2,
                bytes_recv=2000 + self.network_sample * 5 * 1024 ** 2,
            ),
        }

    @staticmethod
    def net_if_stats():
        return {
            "lo": types.SimpleNamespace(isup=True),
            "enp1s0": types.SimpleNamespace(isup=True),
        }

    @staticmethod
    def boot_time():
        return 100.0


class RealSensorSourceTests(unittest.TestCase):
    def setUp(self):
        FakeGpu.available_calls = 0
        self.psutil = FakePsutil()
        self.clock_values = iter((10.0, 11.0, 12.0))
        self.source = RealSensorSource(
            psutil_module=self.psutil,
            gpu_backend_factory=lambda: types.SimpleNamespace(Gpu=FakeGpu),
            gpu_diagnostics_factory=lambda: {
                "available": True,
                "selected_label": "GPU 1 — AMD Radeon RX 9070 XT",
                "selected_index": 1,
                "metrics": {
                    "vram_used_bytes": 8 * 1024 ** 3,
                    "vram_total_bytes": 16 * 1024 ** 3,
                },
            },
            monotonic_clock=lambda: next(self.clock_values),
            wall_clock=lambda: 1000.0,
        )

    def test_readers_produce_theme_friendly_units(self):
        cpu = self.source.read_cpu()
        gpu = self.source.read_gpu()
        memory = self.source.read_memory()
        disk = self.source.read_disk()

        self.assertEqual(cpu["usage"], 37.5)
        self.assertEqual(cpu["temperature"], 61.2)
        self.assertEqual(cpu["frequency"], 4.7)
        self.assertEqual(gpu["usage"], 72.5)
        self.assertEqual(gpu["vramUsed"], 8.0)
        self.assertEqual(gpu["vramTotal"], 16.0)
        self.assertIn("RX 9070 XT", gpu["name"])
        self.assertEqual(memory["used"], 20.0)
        self.assertEqual(disk["free"], 600.0)
        self.assertEqual(FakeGpu.available_calls, 1)

    def test_network_rate_uses_elapsed_time_and_skips_loopback(self):
        first = self.source.read_network()
        second = self.source.read_network()

        self.assertEqual(first["interface"], "enp1s0")
        self.assertEqual(first["upload"], 0.0)
        self.assertEqual(second["upload"], 2.0)
        self.assertEqual(second["download"], 5.0)

    def test_explicit_missing_interface_is_reported_by_collector(self):
        source = RealSensorSource(
            network_interface="missing0",
            psutil_module=self.psutil,
            monotonic_clock=lambda: 1.0,
        )
        collector = SensorSnapshotCollector(
            {"network": source.read_network},
        )

        snapshot = collector.collect()

        self.assertIn("network", snapshot.errors)
        self.assertEqual(snapshot.data["network"], {})

    def test_complete_collector_keeps_sections_json_safe(self):
        collector = SensorSnapshotCollector(self.source.readers())

        snapshot = collector.collect()
        payload = snapshot.as_dict()

        self.assertEqual(payload["data"]["system"]["uptime"], 900)
        self.assertEqual(payload["data"]["gpu"]["selectedIndex"], 1)
        self.assertFalse(payload["errors"])


if __name__ == "__main__":
    unittest.main()
