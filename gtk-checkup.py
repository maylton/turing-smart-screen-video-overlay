#!/usr/bin/env python3
"""Final installation checkup for the GTK Turing Smart Screen interface."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def result(ok: bool, label: str, details: str = "") -> tuple[bool, str]:
    prefix = "✓" if ok else "✗"
    suffix = f" — {details}" if details else ""
    return ok, f"{prefix} {label}{suffix}"


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
        "media-preparation.py",
        "media-preparation-gtk.py",
        "media_preparation_gtk_app.py",
        "tests/test_runtime_lock.py",
        "tests/test_video_media.py",
        "tests/test_packaging.py",
        "tests/test_media_preparation.py",
        "scripts/test-media-preparation.py",
        "docs/MEDIA_PREPARATION.md",
        "scripts/test-install.py",
        "docs/INSTALLATION.md",
        "docs/ROADMAP.md",
        "theme-editor.py",
        "main.py",
        "config.yaml",
        "res/editor-templates/default.yaml",
        "res/editor-templates/theme_example.yaml",
    )
    for relative in required_files:
        path = root / relative
        checks.append(result(path.is_file(), relative))

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
        ],
        cwd=str(root),
        text=True,
        capture_output=True,
        check=False,
    )
    checks.append(result(
        automated_tests.returncode == 0,
        "Runtime and video safety tests",
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
