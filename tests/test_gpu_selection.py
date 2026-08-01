from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from library import gpu_selection_runtime
from library.gpu_diagnostics import collect_gpu_diagnostics
from library.gpu_selection import (
    GpuPreference,
    enumerate_amd_gpus,
    load_preference,
    preference_for_candidate,
    save_preference,
    select_amd_gpu_index,
)


class FakeGpu:
    def __init__(self, name: str, vram: int, load: float = 0.5):
        self.name = name
        self.memory_info = {"vram_size": vram}
        self._load = load

    def query_load(self):
        return self._load

    def query_temperature(self):
        return 62.5

    def query_vram_usage(self):
        return self.memory_info["vram_size"] // 2

    def query_sclk(self):
        return 2_500_000_000


class FakeApi:
    def __init__(self, gpus):
        self.gpus = list(gpus)

    def detect_gpus(self):
        return len(self.gpus)

    def get_gpu(self, index):
        return self.gpus[index]


class GpuSelectionTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeApi(
            [
                FakeGpu("Ryzen integrated graphics", 512 * 1024 ** 2),
                FakeGpu("Radeon discrete graphics", 16 * 1024 ** 3),
            ]
        )

    def test_enumeration_exposes_index_name_vram_and_fingerprint(self):
        candidates = enumerate_amd_gpus(self.api)
        self.assertEqual([item.index for item in candidates], [0, 1])
        self.assertEqual(candidates[1].name, "Radeon discrete graphics")
        self.assertIn("16.0 GiB", candidates[1].label)
        self.assertEqual(len(candidates[1].fingerprint), 16)

    def test_auto_prefers_largest_vram(self):
        self.assertEqual(
            select_amd_gpu_index(self.api, GpuPreference()),
            1,
        )

    def test_explicit_index_overrides_auto(self):
        preference = GpuPreference(mode="index", amd_index=0)
        self.assertEqual(select_amd_gpu_index(self.api, preference), 0)

    def test_missing_explicit_index_falls_back_to_auto(self):
        preference = GpuPreference(mode="index", amd_index=9)
        self.assertEqual(select_amd_gpu_index(self.api, preference), 1)

    def test_fingerprint_survives_adapter_index_reordering(self):
        candidates = enumerate_amd_gpus(self.api)
        preference = preference_for_candidate(candidates[1])
        reordered = FakeApi(
            [
                FakeGpu("Radeon discrete graphics", 16 * 1024 ** 3),
                FakeGpu("Ryzen integrated graphics", 512 * 1024 ** 2),
            ]
        )
        self.assertEqual(select_amd_gpu_index(reordered, preference), 0)

    def test_preference_round_trip_is_atomic(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "hardware.json"
            candidate = enumerate_amd_gpus(self.api)[1]
            preference = preference_for_candidate(candidate)
            save_preference(preference, path)
            self.assertFalse(path.with_suffix(".json.tmp").exists())
            self.assertEqual(load_preference(path), preference)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["amd_gpu_index"], 1)
            self.assertEqual(
                payload["amd_gpu_fingerprint"],
                candidate.fingerprint,
            )

    def test_environment_override_has_priority(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "hardware.json"
            candidate = enumerate_amd_gpus(self.api)[1]
            save_preference(preference_for_candidate(candidate), path)
            with mock.patch.dict(os.environ, {"TURING_AMD_GPU_INDEX": "0"}):
                self.assertEqual(
                    load_preference(path),
                    GpuPreference(mode="index", amd_index=0),
                )

    def test_diagnostics_use_selected_adapter(self):
        with mock.patch(
            "library.gpu_diagnostics.selection_summary",
            return_value={
                "selected_index": 1,
                "selected_label": "GPU 1",
                "selected_fingerprint": "abc",
                "preference": {
                    "mode": "auto",
                    "amd_index": None,
                    "amd_fingerprint": None,
                },
                "candidates": [],
                "configuration_path": "/tmp/hardware.json",
            },
        ):
            payload = collect_gpu_diagnostics(self.api)

        self.assertEqual(payload["selected_index"], 1)
        metrics = payload["metrics"]
        self.assertEqual(metrics["load_percent"], 50.0)
        self.assertEqual(metrics["temperature_c"], 62.5)
        self.assertEqual(metrics["vram_percent"], 50.0)
        self.assertEqual(metrics["clock_mhz"], 2500.0)

    def test_runtime_hook_applies_persistent_index(self):
        from library.sensors import sensors_python

        original_selector = sensors_python.GpuAmd.preferred_linux_gpu_index
        original_api = sensors_python.pyamdgpuinfo
        original_index = sensors_python.GpuAmd.selected_index
        original_installed = gpu_selection_runtime._INSTALLED
        try:
            sensors_python.pyamdgpuinfo = self.api
            sensors_python.GpuAmd.selected_index = 1
            gpu_selection_runtime._INSTALLED = False
            with mock.patch(
                "library.gpu_selection_runtime.load_preference",
                return_value=GpuPreference(mode="index", amd_index=0),
            ):
                gpu_selection_runtime.install()
                self.assertEqual(
                    sensors_python.GpuAmd.preferred_linux_gpu_index(),
                    0,
                )
                self.assertEqual(sensors_python.GpuAmd.selected_index, -1)
        finally:
            sensors_python.GpuAmd.preferred_linux_gpu_index = staticmethod(
                original_selector
            )
            sensors_python.GpuAmd.selected_index = original_index
            sensors_python.pyamdgpuinfo = original_api
            gpu_selection_runtime._INSTALLED = original_installed


if __name__ == "__main__":
    unittest.main()
