# SPDX-License-Identifier: GPL-3.0-or-later
"""Release metadata and source/installation integrity helpers."""

from __future__ import annotations

import json
import locale
import os
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


METADATA_FILENAME = ".installation.json"
VERSION_FILENAME = "VERSION"

# These files define the minimum coherent application tree. Keep this list small
# enough to remain stable, but broad enough to catch stale/incomplete checkouts.
REQUIRED_PROJECT_FILES = (
    "VERSION",
    "main.py",
    "configure-gtk.py",
    "configure_gtk_app.py",
    "gtk-checkup.py",
    "library/i18n.py",
    "library/release_info.py",
    "library/runtime.py",
    "requirements.txt",
    "requirements-gpu-amd.txt",
    "usercustomize.py",
)


@dataclass(frozen=True)
class InstallationMetadata:
    version: str
    source_commit: str
    installed_at: str
    install_mode: str
    source_root: str
    install_root: str
    python_version: str
    platform: str
    language: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def read_version(root: Path) -> str:
    """Read the project version, returning a clear fallback when unavailable."""
    version_file = Path(root) / VERSION_FILENAME
    try:
        value = version_file.read_text(encoding="utf-8").strip()
    except OSError:
        return "0+unknown"
    return value or "0+unknown"


def _run_git(root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def source_commit(root: Path) -> str:
    """Return the checkout commit, including a dirty suffix when appropriate."""
    root = Path(root)
    commit = _run_git(root, "rev-parse", "--short=12", "HEAD")
    if not commit:
        return "unknown"
    dirty = _run_git(root, "status", "--porcelain", "--untracked-files=no")
    return f"{commit}-dirty" if dirty else commit


def active_language() -> str:
    for name in ("TURING_SMART_SCREEN_LANG", "LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    try:
        value, _encoding = locale.getlocale()
    except Exception:
        value = None
    return value or "unknown"


def validate_project_tree(root: Path, required: Iterable[str] = REQUIRED_PROJECT_FILES) -> list[str]:
    """Return required paths missing from a source or installed application tree."""
    root = Path(root)
    return [relative for relative in required if not (root / relative).is_file()]


def build_metadata(*, source_root: Path, install_root: Path, install_mode: str) -> InstallationMetadata:
    source_root = Path(source_root).resolve()
    install_root = Path(install_root).resolve()
    return InstallationMetadata(
        version=read_version(source_root),
        source_commit=source_commit(source_root),
        installed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        install_mode=str(install_mode),
        source_root=str(source_root),
        install_root=str(install_root),
        python_version=platform.python_version(),
        platform=platform.platform(),
        language=active_language(),
    )


def write_metadata(
    *,
    source_root: Path,
    install_root: Path,
    install_mode: str,
) -> Path:
    """Atomically write installation metadata into the installed application."""
    install_root = Path(install_root)
    install_root.mkdir(parents=True, exist_ok=True)
    metadata = build_metadata(
        source_root=source_root,
        install_root=install_root,
        install_mode=install_mode,
    )
    destination = install_root / METADATA_FILENAME
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(metadata.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination


def load_metadata(root: Path) -> InstallationMetadata | None:
    path = Path(root) / METADATA_FILENAME
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return InstallationMetadata(**payload)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def release_summary(root: Path) -> dict[str, object]:
    root = Path(root)
    metadata = load_metadata(root)
    return {
        "version": metadata.version if metadata else read_version(root),
        "source_commit": metadata.source_commit if metadata else source_commit(root),
        "installed_at": metadata.installed_at if metadata else "unknown",
        "install_mode": metadata.install_mode if metadata else "unknown",
        "language": metadata.language if metadata else active_language(),
        "missing_files": validate_project_tree(root),
        "python": sys.version.split()[0],
    }
