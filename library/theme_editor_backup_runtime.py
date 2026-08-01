# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime bridge between atomic Theme Editor saves and versioned backups."""

from __future__ import annotations

import os
from pathlib import Path

from library.theme_editor_backups import BACKUP_DIRECTORY, THEME_FILENAMES, create_backup


_INSTALLED = False
_ORIGINAL_REPLACE = os.replace


def _is_validated_theme_save(source: Path, destination: Path) -> bool:
    return (
        destination.name in THEME_FILENAMES
        and source.parent == destination.parent
        and source.name == destination.name + ".tmp"
        and BACKUP_DIRECTORY not in destination.parts
    )


def install() -> None:
    """Install a narrowly scoped replacement guard for the Theme Editor process."""
    global _INSTALLED
    if _INSTALLED:
        return

    def replace_after_backup(source, destination, *args, **kwargs):
        source_path = Path(source)
        destination_path = Path(destination)
        if _is_validated_theme_save(source_path, destination_path):
            create_backup(destination_path)
        return _ORIGINAL_REPLACE(source, destination, *args, **kwargs)

    os.replace = replace_after_backup
    _INSTALLED = True
