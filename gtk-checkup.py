#!/usr/bin/env python3
"""Final installation checkup and hardware-specific dependency bootstrap."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

import yaml


GPU_VENDOR_NAMES = {
    "0x1002": "AMD",
    "0x10de": "NVIDIA",
    "0x8086": "Intel",
}
PCI_GPU_CLASS_CODES = {"0300", "0302", "0380"}


def result(ok: bool, label: str, details: str = "") -> tuple[bool, str]:
    prefix = "✓" if ok else "✗"
    suffix = f" — {details}" if details else ""
    return ok, f"{prefix} {label}{suffix}"


def parse_lspci_gpu_vendors(output: str) -> set[str]:
    """Return GPU vendors from locale-independent ``lspci -Dn`` output."""
    vendors: set[str] = set()

    for line in str(output or "").splitlines():
        match = re.search(
            r"\b([0-9a-fA-F]{4}):\s+([0-9a-fA-F]{4}):[0-9a-fA-F]{4}\b",
            line,
        )
        if match is None:
            continue

        class_code = match.group(1).lower()
        vendor_id = "0x" + match.group(2).lower()
        if class_code not in PCI_GPU_CLASS_CODES:
            continue

        vendor_name = GPU_VENDOR_NAMES.get(vendor_id)
        if vendor_name:
            vendors.add(vendor_name)

    return vendors


def detect_linux_gpu_vendors(sysfs_root: Optional[Path] = None) -> set[str]:
    """Detect Linux GPU vendors without requiring an extra package.

    DRM sysfs is the primary source. ``lspci -Dn`` is also consulted when
    available so hybrid systems are not misidentified when sysfs exposes only
    one adapter during installation.
    """
    if not sys.platform.startswith("linux"):
        return set()

    root = sysfs_root or Path(
        os.environ.get("TURING_SYSFS_DRM_ROOT", "/sys/class/drm")
    )
    vendors: set[str] = set()

    try:
        for vendor_file in root.glob("card*/device/vendor"):
            try:
                vendor_id = vendor_file.read_text(encoding="utf-8").strip().lower()
            except OSError:
                continue
            vendor_name = GPU_VENDOR_NAMES.get(vendor_id)
            if vendor_name:
                vendors.add(vendor_name)
    except OSError:
        pass

    try:
        completed = subprocess.run(
            ["lspci", "-Dn"],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return vendors

    if completed.returncode == 0:
        vendors.update(parse_lspci_gpu_vendors(completed.stdout))

    return vendors


def probe_amd_gpu() -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import pyamdgpuinfo; "
                "count=pyamdgpuinfo.detect_gpus(); "
                "print(f'{count} AMD GPU(s) detected by pyamdgpuinfo'); "
                "raise SystemExit(0 if count > 0 else 2)"
            ),
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def ensure_amd_gpu_support(root: Path, checks: list[tuple[bool, str]]) -> None:
    vendors = detect_linux_gpu_vendors()
    vendor_details = ", ".join(sorted(vendors)) if vendors else "none detected"
    checks.append(result(True, "GPU vendor detection", vendor_details))

    if "AMD" not in vendors:
        return

    requirements_file = root / "requirements-gpu-amd.txt"
    if not requirements_file.is_file():
        checks.append(result(
            False,
            "AMD GPU dependency profile",
            "requirements-gpu-amd.txt not found",
        ))
        return

    probe = probe_amd_gpu()
    if probe.returncode != 0:
        print("AMD GPU detected; installing the matching monitoring dependency...")
        install = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-r",
                str(requirements_file),
            ],
            cwd=str(root),
            text=True,
            capture_output=True,
            check=False,
        )
        if install.returncode != 0:
            details = (install.stderr or install.stdout).strip()[-1500:]
            checks.append(result(False, "AMD GPU dependency installation", details))
            return

        install_details = (install.stdout or install.stderr).strip()[-1000:]
        checks.append(result(True, "AMD GPU dependency installation", install_details))
        probe = probe_amd_gpu()
    else:
        checks.append(result(True, "AMD GPU dependency installation", "already installed"))

    probe_details = (probe.stdout or probe.stderr).strip()[-1000:]
    if probe.returncode != 0:
        probe_details = (
            probe_details
            + " | Verify that the Linux amdgpu driver is active and that the "
            "current user can read /sys/class/drm and /sys/class/hwmon."
        ).strip(" |")
    checks.append(result(
        probe.returncode == 0,
        "AMD GPU monitoring probe",
        probe_details,
    ))


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    checks: list[tuple[bool, str]] = []

    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw, Gtk
        checks.append(result(True, "GTK4 and Libadwaita imports"))
    except Exception as exc:
        checks.append(result(False, "GTK4 and Libadwaita imports", str(exc)))

    # WebKit is optional for existing YAML installations. It becomes a hard
    # check only when the experimental HTML renderer is explicitly enabled.
    try:
        configured = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8")) or {}
        renderer = configured.get("renderer", {})
        html_enabled = isinstance(renderer, dict) and str(renderer.get("engine", "")).lower() == "html"
    except Exception:
        html_enabled = False
    if html_enabled:
        try:
            import gi
            gi.require_version("WebKit", "6.0")
            from gi.repository import WebKit  # noqa: F401
            from PIL import Image  # noqa: F401
            checks.append(result(True, "Experimental HTML renderer dependencies"))
        except Exception as exc:
            checks.append(result(False, "Experimental HTML renderer dependencies", str(exc)))

    required_files = (
        "configure-gtk.py",
        "configure_gtk_app.py",
        "theme-editor-gtk.py",
        "video-manager-gtk.py",
        "video_manager_gtk_app.py",
        "video_manager.py",
        "video_manager_backend.py",
        "screen-control.py",
        "library/runtime.py",
        "library/video_media.py",
        "library/media_preparation.py",
        "library/html_hybrid.py",
        "library/html_native_video_sink.py",
        "library/html_theme_video_builder.py",
        "html-theme-build-video.py",
        "media-preparation.py",
        "media-preparation-gtk.py",
        "media_preparation_gtk_app.py",
        "tests/test_runtime_lock.py",
        "tests/test_video_media.py",
        "tests/test_packaging.py",
        "tests/test_media_preparation.py",
        "tests/test_gpu_dependency_detection.py",
        "scripts/test-media-preparation.py",
        "docs/MEDIA_PREPARATION.md",
        "scripts/test-install.py",
        "docs/INSTALLATION.md",
        "docs/ROADMAP.md",
        "theme-editor.py",
        "main.py",
        "config.yaml",
        "requirements-gpu-amd.txt",
        "res/editor-templates/default.yaml",
        "res/editor-templates/theme_example.yaml",
    )
    for relative in required_files:
        path = root / relative
        checks.append(result(path.is_file(), relative))

    ensure_amd_gpu_support(root, checks)

    for command in ("ffmpeg", "ffprobe", "xdg-open"):
        completed = subprocess.run(
            ["sh", "-lc", f"command -v {command}"],
            text=True,
            capture_output=True,
            check=False,
        )
        checks.append(result(
            completed.returncode == 0,
            f"Command: {command}",
            completed.stdout.strip() if completed.returncode == 0 else "not found",
        ))

    scripts = (
        root / "configure-gtk.py",
        root / "configure_gtk_app.py",
        root / "theme-editor-gtk.py",
        root / "video-manager-gtk.py",
        root / "video_manager_gtk_app.py",
        root / "video_manager.py",
        root / "video_manager_backend.py",
        root / "screen-control.py",
        root / "library" / "runtime.py",
        root / "library" / "video_media.py",
        root / "library" / "media_preparation.py",
        root / "media-preparation.py",
        root / "media-preparation-gtk.py",
        root / "media_preparation_gtk_app.py",
        root / "main.py",
    )
    syntax_ok = True
    syntax_errors = []
    for script in scripts:
        if not script.is_file():
            continue
        try:
            compile(script.read_text(encoding="utf-8"), str(script), "exec")
        except Exception as exc:
            syntax_ok = False
            syntax_errors.append(f"{script.name}: {exc}")
    checks.append(result(
        syntax_ok,
        "Python syntax",
        "; ".join(syntax_errors),
    ))

    automated_tests = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "-q",
            "tests.test_runtime_lock",
            "tests.test_video_media",
            "tests.test_packaging",
            "tests.test_media_preparation",
            "tests.test_gpu_dependency_detection",
        ],
        cwd=str(root),
        text=True,
        capture_output=True,
        check=False,
    )
    checks.append(result(
        automated_tests.returncode == 0,
        "Runtime, packaging, GPU and video safety tests",
        (automated_tests.stdout or automated_tests.stderr).strip()[-1000:],
    ))

    venv_python = root / "venv" / "bin" / "python3"
    if venv_python.is_file():
        probe = subprocess.run(
            [
                str(venv_python),
                "-c",
                (
                    "import gi; "
                    "gi.require_version('Gtk', '4.0'); "
                    "gi.require_version('Adw', '1'); "
                    "from gi.repository import Adw, Gtk; "
                    "import PIL, ruamel.yaml; "
                    "print('GTK, Pillow and ruamel.yaml OK')"
                ),
            ],
            cwd=str(root),
            text=True,
            capture_output=True,
            check=False,
        )
        checks.append(result(
            probe.returncode == 0,
            "Project virtual environment imports (GTK, Pillow, ruamel.yaml)",
            (probe.stdout or probe.stderr).strip(),
        ))

        yaml_probe = subprocess.run(
            [
                str(venv_python),
                "-c",
                (
                    "from pathlib import Path; import ruamel.yaml; "
                    "y=ruamel.yaml.YAML(); "
                    "files=list(Path('res/themes').glob('*/theme.yaml')); "
                    "[y.load(p.read_text(encoding='utf-8')) for p in files]; "
                    "print(f'{len(files)} theme YAML file(s) valid')"
                ),
            ],
            cwd=str(root),
            text=True,
            capture_output=True,
            check=False,
        )
        checks.append(result(
            yaml_probe.returncode == 0,
            "Theme YAML validation",
            (yaml_probe.stdout or yaml_probe.stderr).strip()[-1000:],
        ))
    else:
        checks.append(result(
            False,
            "Project virtual environment",
            "venv/bin/python3 not found",
        ))

    temp_files = list((root / "res" / "themes").glob("*/theme.yaml.tmp"))
    checks.append(result(
        not temp_files,
        "No stale theme.yaml.tmp files",
        ", ".join(str(path.relative_to(root)) for path in temp_files),
    ))

    print("\n".join(line for _ok, line in checks))
    failures = sum(1 for ok, _line in checks if not ok)
    print()
    print(f"Result: {len(checks) - failures} passed, {failures} problem(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
