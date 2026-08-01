from __future__ import annotations

import math
import unittest

from library.diagnostic_gpu_backend import DiagnosticGpuProvider


class DiagnosticGpuProviderTests(unittest.TestCase):
    def test_exposes_amd_metrics_without_nvidia_backend(self):
        calls = []

        def collect():
            calls.append(True)
            return {
                "available": True,
                "selected_index": 1,
                "selected_label": "GPU 1 — AMD Radeon RX 9070 XT",
                "metrics": {
                    "load_percent": 72.5,
                    "temperature_c": 64.2,
                    "vram_percent": 50.0,
                    "vram_used_bytes": 8 * 1024 ** 3,
                    "vram_total_bytes": 16 * 1024 ** 3,
                    "clock_mhz": 2450.0,
                },
            }

        provider = DiagnosticGpuProvider(
            collect,
            clock=lambda: 1.0,
        )

        self.assertTrue(provider.backend.Gpu.is_available())
        stats = provider.backend.Gpu.stats()
        self.assertEqual(stats[0], 72.5)
        self.assertEqual(stats[1], 50.0)
        self.assertEqual(stats[2], 8192.0)
        self.assertEqual(stats[3], 16384.0)
        self.assertEqual(stats[4], 64.2)
        self.assertEqual(provider.backend.Gpu.frequency(), 2450.0)
        self.assertEqual(len(calls), 1)

    def test_unavailable_adapter_is_reported_without_exception(self):
        provider = DiagnosticGpuProvider(
            lambda: {
                "available": True,
                "selected_index": -1,
                "metrics": {},
            },
            clock=lambda: 1.0,
        )

        self.assertFalse(provider.backend.Gpu.is_available())
        self.assertTrue(math.isnan(provider.backend.Gpu.stats()[0]))
        self.assertEqual(provider.backend.Gpu.fps(), -1)

    def test_cache_refreshes_after_interval(self):
        clock_values = iter((1.0, 1.1, 1.4))
        calls = []

        def collect():
            calls.append(len(calls) + 1)
            return {
                "available": True,
                "selected_index": 0,
                "metrics": {"load_percent": calls[-1]},
            }

        provider = DiagnosticGpuProvider(
            collect,
            clock=lambda: next(clock_values),
            cache_seconds=0.2,
        )

        self.assertEqual(provider.backend.Gpu.stats()[0], 1.0)
        self.assertEqual(provider.backend.Gpu.stats()[0], 1.0)
        self.assertEqual(provider.backend.Gpu.stats()[0], 2.0)
        self.assertEqual(calls, [1, 2])


if __name__ == "__main__":
    unittest.main()
