#!/usr/bin/env python3
"""Run a safe two-pass installation/update test under an isolated HOME."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class InstallTestError(RuntimeError):
    pass


def run(args: list[str], *, cwd: Path, env: dict[str, str], capture: bool = False):
    print("$", " ".join(args))
    result = subprocess.run(
        args,
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=capture,
        check=False,
    )
    if capture:
        if result.stdout:
            print(result.stdout.rstrip())
        if result.stderr:
            print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode != 0:
        raise InstallTestError(
            f"Command failed with status {result.returncode}: " + " ".join(args)
        )
    return result


def require(condition: bool, message: str) -> None:
    if not condition:
        raise InstallTestError(message)


def safe_reset(path: Path) -> None:
    resolved = path.resolve()
    forbidden = {Path("/").resolve(), Path.home().resolve(), ROOT.resolve(), ROOT.parent.resolve()}
    if resolved in forbidden or len(resolved.parts) < 4:
        raise InstallTestError(f"Refusing to remove unsafe path: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def prepare_env(home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "PATH": f"{home / '.local' / 'bin'}:{env.get('PATH', '')}",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    for relative in (".config", ".cache", ".local/share"):
        (home / relative).mkdir(parents=True, exist_ok=True)
    return env


def validate_install(home: Path, env: dict[str, str]) -> Path:
    prefix = home / ".local" / "share" / "turing-smart-screen"
    launcher = home / ".local" / "bin" / "turing-smart-screen"
    desktop = home / ".local" / "share" / "applications" / "io.github.turing.SmartScreen.desktop"
    python = prefix / "venv" / "bin" / "python3"

    for path in (
        prefix / "main.py",
        prefix / "configure-gtk.py",
        prefix / "video_manager.py",
        prefix / "library" / "runtime.py",
        prefix / "library" / "video_media.py",
        launcher,
        desktop,
        python,
    ):
        require(path.is_file(), f"Installed file missing: {path}")

    run(
        [
            str(python),
            "-c",
            (
                "import gi; "
                "gi.require_version('Gtk', '4.0'); "
                "gi.require_version('Adw', '1'); "
                "from gi.repository import Adw, Gtk; "
                "import PIL, ruamel.yaml; "
                "print('isolated install imports OK')"
            ),
        ],
        cwd=prefix,
        env=env,
    )
    require(str(prefix) in launcher.read_text(encoding="utf-8"), "Launcher does not target test prefix.")
    require(
        "io.github.turing.SmartScreen" in desktop.read_text(encoding="utf-8"),
        "Desktop identity is inconsistent.",
    )
    return prefix


def add_preservation_fixtures(prefix: Path):
    marker = "# packaging-preservation-marker"
    config = prefix / "config.yaml"
    text = config.read_text(encoding="utf-8")
    if marker not in text:
        config.write_text(text.rstrip() + "\n" + marker + "\n", encoding="utf-8")

    themes = prefix / "res" / "themes"
    source_theme = next(
        (path for path in themes.iterdir() if path.is_dir() and (path / "theme.yaml").is_file()),
        None,
    )
    require(source_theme is not None, "No installed theme available for fixture.")
    custom_theme = themes / "packaging-preserved-theme"
    if custom_theme.exists():
        shutil.rmtree(custom_theme)
    shutil.copytree(source_theme, custom_theme)

    custom_video = prefix / "res" / "videos" / "packaging-preserved-video.bin"
    custom_video.parent.mkdir(parents=True, exist_ok=True)
    custom_video.write_bytes(b"packaging-preservation-fixture\n")
    return marker, custom_theme, custom_video


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    home = args.root.expanduser().resolve()
    if args.reset:
        safe_reset(home)
    elif home.exists() and any(home.iterdir()):
        raise InstallTestError(f"Test HOME is not empty: {home}. Use --reset explicitly.")

    env = prepare_env(home)
    install = ["bash", str(ROOT / "install.sh"), "--no-deps"]

    print("\n=== First isolated installation ===")
    run(install, cwd=ROOT, env=env)
    prefix = validate_install(home, env)

    print("\n=== Creating user-data preservation fixtures ===")
    marker, custom_theme, custom_video = add_preservation_fixtures(prefix)

    print("\n=== Second isolated installation (upgrade path) ===")
    run(install, cwd=ROOT, env=env)
    prefix = validate_install(home, env)

    require(marker in (prefix / "config.yaml").read_text(encoding="utf-8"), "config.yaml was not preserved across update.")
    require(custom_theme.is_dir(), "Custom theme was not preserved.")
    require(custom_video.is_file(), "Custom media was not preserved.")

    print("\n=== Final installed checkup ===")
    run(
        ["/usr/bin/python3", str(prefix / "gtk-checkup.py"), str(prefix)],
        cwd=prefix,
        env=env,
    )

    print("\nPackaging installation test passed.")
    print(f"Isolated HOME kept at: {home}")
    print(f"Launcher: {home / '.local' / 'bin' / 'turing-smart-screen'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InstallTestError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
