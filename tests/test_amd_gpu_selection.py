from __future__ import annotations

import unittest
from unittest import mock

from library.sensors import sensors_python


class FakeGpu:
    def __init__(self, vram_size=None):
        self.memory_info = {}
        if vram_size is not None:
            self.memory_info["vram_size"] = vram_size


class FakeAmdGpuInfo:
    def __init__(self, vram_sizes):
        self.gpus = [FakeGpu(size) for size in vram_sizes]

    def detect_gpus(self):
        return len(self.gpus)

    def get_gpu(self, index):
        return self.gpus[index]


class AmdGpuSelectionTests(unittest.TestCase):
    def setUp(self):
        self.original_index = sensors_python.GpuAmd.selected_index

    def tearDown(self):
        sensors_python.GpuAmd.selected_index = self.original_index

    def test_prefers_gpu_with_largest_dedicated_vram(self):
        fake = FakeAmdGpuInfo((512 * 1024**2, 16 * 1024**3))
        with mock.patch.object(sensors_python, "pyamdgpuinfo", fake):
            index = sensors_python.GpuAmd.preferred_linux_gpu_index()
        self.assertEqual(index, 1)

    def test_falls_back_to_first_gpu_when_vram_is_unknown(self):
        fake = FakeAmdGpuInfo((None, None))
        with mock.patch.object(sensors_python, "pyamdgpuinfo", fake):
            index = sensors_python.GpuAmd.preferred_linux_gpu_index()
        self.assertEqual(index, 0)

    def test_returns_minus_one_when_no_amd_gpu_is_available(self):
        fake = FakeAmdGpuInfo(())
        with mock.patch.object(sensors_python, "pyamdgpuinfo", fake):
            index = sensors_python.GpuAmd.preferred_linux_gpu_index()
        self.assertEqual(index, -1)

    def test_is_available_caches_the_preferred_gpu(self):
        fake = FakeAmdGpuInfo((256 * 1024**2, 8 * 1024**3))
        sensors_python.GpuAmd.selected_index = -1
        with mock.patch.object(sensors_python, "pyamdgpuinfo", fake):
            self.assertTrue(sensors_python.GpuAmd.is_available())
            self.assertEqual(sensors_python.GpuAmd.selected_index, 1)
            self.assertIs(sensors_python.GpuAmd.linux_gpu(), fake.gpus[1])


if __name__ == "__main__":
    unittest.main()
