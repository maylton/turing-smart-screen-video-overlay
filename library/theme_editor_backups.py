# SPDX-License-Identifier: GPL-3.0-or-later
"""Versioned backup storage for Theme Editor YAML files."""

from __future__ import annotations

import hashlib
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


BACKUP_DIRECTORY = ".theme-editor-backups"
DEFAULT_RETENTION = 20
THEME_FILENAMES = {"theme.yaml", "theme.yml"}


def retention_limit() -> int:
    value = os.environ.get("TURING_THEME_BACKUP_RETENTION", "").strip()
    try:
        parsed = int(value)
    except ValueError:
        parsed = DEFAULT_RETENTION
    return max(1, min(parsed, 200))


def backup_directory(theme_file: Path) -> Path:
    return Path(theme_file).parent / BACKUP_DIRECTORY


def backup_files(theme_file: Path) -> List[Path]:
    directory = backup_directory(theme_file)
    if not directory.is_dir():
        return []
    paths = [path for path in directory.iterdir() if path.is_file()]
    return sorted(
        paths,
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )


def _backup_name(theme_file: Path, content: bytes) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    digest = hashlib.sha256(content).hexdigest()[:10]
    return f"{theme_file.stem}-{timestamp}-{digest}{theme_file.suffix}"


def prune_backups(theme_file: Path, keep: Optional[int] = None) -> List[Path]:
    keep = retention_limit() if keep is None else max(1, int(keep))
    removed = []
    for path in backup_files(theme_file)[keep:]:
        try:
            path.unlink()
            removed.append(path)
        except OSError:
            continue
    return removed


def create_backup(theme_file: Path) -> Optional[Path]:
    """Copy the current valid theme YAML before it is replaced."""
    theme_file = Path(theme_file)
    if not theme_file.is_file() or theme_file.name not in THEME_FILENAMES:
        return None

    content = theme_file.read_bytes()
    directory = backup_directory(theme_file)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / _backup_name(theme_file, content)
    destination.write_bytes(content)
    shutil.copystat(theme_file, destination, follow_symlinks=True)
    prune_backups(theme_file)
    return destination


def restore_backup(backup: Path, theme_file: Path) -> Path:
    """Restore a selected backup atomically and retain the current version."""
    backup = Path(backup)
    theme_file = Path(theme_file)
    if not backup.is_file():
        raise FileNotFoundError(backup)
    if theme_file.name not in THEME_FILENAMES:
        raise ValueError(f"Unsupported theme file: {theme_file}")
    if backup.parent != backup_directory(theme_file):
        raise ValueError("Backup does not belong to the selected theme")

    create_backup(theme_file)
    temporary = theme_file.with_suffix(theme_file.suffix + ".restore.tmp")
    shutil.copy2(backup, temporary)
    os.replace(temporary, theme_file)
    return theme_file
