# SPDX-License-Identifier: GPL-3.0-or-later
"""Path helpers for the Theme Gallery import file chooser."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse


_THEME_DEFINITION_NAMES = frozenset({"manifest.json", "theme.yaml", "theme.yml"})
SUPPORTED_PATTERNS = (
    "*.theme",
    "*.THEME",
    "*.zip",
    "*.ZIP",
    "manifest.json",
    "MANIFEST.JSON",
    "theme.yaml",
    "THEME.YAML",
    "theme.yml",
    "THEME.YML",
)


def normalize_theme_import_path(value: str | Path) -> Path:
    """Resolve a selected package or definition file to an import source."""
    text = str(value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1:-1].strip()

    parsed = urlparse(text)
    if parsed.scheme.casefold() == "file":
        text = unquote(parsed.path)

    path = Path(text).expanduser()
    if path.is_file() and path.name.casefold() in _THEME_DEFINITION_NAMES:
        return path.parent
    return path
