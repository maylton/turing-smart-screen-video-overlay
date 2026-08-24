#!/usr/bin/env python3
"""Flatpak launcher and writable-payload synchronizer.

The upstream application intentionally keeps config.yaml, themes and generated
media beside the Python sources. Flatpak mounts /app read-only, so the packaged
payload is seeded into XDG_DATA_HOME and refreshed on Flatpak updates while
preserving user-owned mutable data.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

SOURCE = Path("/app/share/turing-smart-screen")
RELEASE_FILE = SOURCE / ".flatpak-release"
PRESERVE_TOP_LEVEL = {"config.yaml"}
PRESERVE_RES_DIRS = {"themes", "video", "videos"}


def _copy_replace(source: Path, target: Path) -> None:
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.is_dir():
        shutil.rmtree(target)
    if source.is_dir():
        shutil.copytree(source, target, symlinks=True)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target, follow_symlinks=False)


def _merge_missing(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        destination = target / item.name
        if destination.exists() or destination.is_symlink():
            continue
        _copy_replace(item, destination)


def _sync_res(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        destination = target / item.name
        if item.name in PRESERVE_RES_DIRS and item.is_dir():
            _merge_missing(item, destination)
        else:
            _copy_replace(item, destination)


def _sync_payload(workdir: Path, release: str) -> None:
    applied_file = workdir / ".flatpak-applied-release"
    applied = applied_file.read_text(encoding="utf-8").strip() if applied_file.is_file() else ""
    if applied == release:
        return

    workdir.mkdir(parents=True, exist_ok=True)
    for item in SOURCE.iterdir():
        if item.name == ".flatpak-applied-release":
            continue
        destination = workdir / item.name
        if item.name in PRESERVE_TOP_LEVEL:
            if not destination.exists():
                _copy_replace(item, destination)
            continue
        if item.name == "res" and item.is_dir():
            _sync_res(item, destination)
            continue
        _copy_replace(item, destination)

    applied_file.write_text(release + "\n", encoding="utf-8")


def main() -> int:
    if not SOURCE.is_dir() or not RELEASE_FILE.is_file():
        print("Flatpak payload is incomplete.", file=sys.stderr)
        return 1

    release = RELEASE_FILE.read_text(encoding="utf-8").strip()
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    workdir = data_home / "turing-smart-screen"

    try:
        _sync_payload(workdir, release)
    except Exception as exc:
        print(f"Could not prepare writable Flatpak payload: {exc}", file=sys.stderr)
        return 1

    # Keep code that uses Path.home() inside the app-private Flatpak data tree.
    # XDG_* variables remain untouched, so GTK/portal integration still uses
    # Flatpak's normal per-app directories.
    private_home = data_home / "turing-home"
    private_home.mkdir(parents=True, exist_ok=True)

    if os.environ.get("TURING_FLATPAK_BOOTSTRAP_ONLY") == "1":
        print(workdir)
        return 0

    env = os.environ.copy()
    env["HOME"] = str(private_home)
    env["TURING_SMART_SCREEN_FLATPAK"] = "1"
    env["TURING_SMART_SCREEN_PYTHON"] = sys.executable
    env["TURING_DISABLE_PYSTRAY"] = "1"

    entrypoint = workdir / "configure-gtk.py"
    if not entrypoint.is_file():
        print(f"Flatpak entry point is missing: {entrypoint}", file=sys.stderr)
        return 1

    os.chdir(workdir)
    os.execvpe(sys.executable, [sys.executable, str(entrypoint)], env)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
