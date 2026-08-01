from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CHECKUP_FILE = ROOT / "gtk-checkup.py"


def load_checkup_module():
    spec = importlib.util.spec_from_file_location(
        "turing_gtk_checkup_gpu_tests",
        CHECKUP_FILE,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {CHECKUP_FILE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checkup = load_checkup_module()


class GpuDependencyDetectionTests(unittest.TestCase):
    def write_vendor(self, root: Path, card: str, vendor_id: str) -> None:
        vendor_file = root / card / "device" / "vendor"
        vendor_file.parent.mkdir(parents=True)
        vendor_file.write_text(vendor_id + "\n", encoding="utf-8")

    def test_detects_amd_from_drm_sysfs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_vendor(root, "card0", "0x1002")

            with mock.patch.object(
                checkup.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(
                    ["lspci", "-Dn"],
                    0,
                    stdout="",
                    stderr="",
                ),
            ):
                vendors = checkup.detect_linux_gpu_vendors(root)

        self.assertEqual(vendors, {"AMD"})

    def test_unions_sysfs_and_lspci_for_hybrid_systems(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_vendor(root, "card0", "0x8086")
            lspci = (
                "0000:00:02.0 0300: 8086:46a6 (rev 0c)\n"
                "0000:03:00.0 0302: 1002:744c (rev c8)\n"
            )

            with mock.patch.object(
                checkup.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(
                    ["lspci", "-Dn"],
                    0,
                    stdout=lspci,
                    stderr="",
                ),
            ):
                vendors = checkup.detect_linux_gpu_vendors(root)

        self.assertEqual(vendors, {"AMD", "Intel"})

    def test_lspci_parser_ignores_non_display_devices(self):
        output = (
            "0000:01:00.0 0200: 1002:1641 (rev 01)\n"
            "0000:03:00.0 0300: 10de:2684 (rev a1)\n"
        )
        self.assertEqual(checkup.parse_lspci_gpu_vendors(output), {"NVIDIA"})

    def test_missing_lspci_keeps_sysfs_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_vendor(root, "card0", "0x1002")

            with mock.patch.object(
                checkup.subprocess,
                "run",
                side_effect=FileNotFoundError("lspci"),
            ):
                vendors = checkup.detect_linux_gpu_vendors(root)

        self.assertEqual(vendors, {"AMD"})

    def test_dependency_profile_covers_supported_python_versions(self):
        text = (ROOT / "requirements-gpu-amd.txt").read_text(encoding="utf-8")
        self.assertIn('pyamdgpuinfo~=2.1.7', text)
        self.assertIn('python_version < "3.10"', text)
        self.assertIn('pyamdgpuinfo~=2.1.8', text)
        self.assertIn('python_version >= "3.10"', text)


if __name__ == "__main__":
    unittest.main()
