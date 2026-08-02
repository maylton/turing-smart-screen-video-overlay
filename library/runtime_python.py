# SPDX-License-Identifier: GPL-3.0-or-later
"""Resolve the dependency-complete Python used by project subprocesses."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path


RUNTIME_PYTHON_ENV = "TURING_SMART_SCREEN_PYTHON"
_THEME_IMPORT_ENTRY_POINTS = {
    "configure-gtk.py",
    "theme-gallery-gtk.py",
    "turing-smart-screen-gtk.py",
    "turing-smart-screen-main.py",
}


def _install_html_editor_background_extension() -> None:
    """Schedule the optional background page without altering editor internals."""
    if Path(sys.argv[0]).name != "html-theme-editor-gtk.py":
        return
    try:
        from library.html_theme_background_compat import install_background_editor_hook

        install_background_editor_hook()
    except Exception as exc:
        print(
            f"Não foi possível preparar a aba Fundo do editor HTML: {exc}",
            file=sys.stderr,
        )


def _install_native_theme_import_dialog() -> None:
    """Install the native chooser in GTK entry points that already loaded the gallery."""
    if Path(sys.argv[0]).name not in _THEME_IMPORT_ENTRY_POINTS:
        return
    try:
        from library.theme_import_file_dialog import install

        install()
    except Exception as exc:
        print(
            f"Não foi possível preparar o seletor de arquivos de temas: {exc}",
            file=sys.stderr,
        )


def _executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def resolve_project_python(
    root: Path | str,
    *,
    current: str | None = None,
    environment: Mapping[str, str] | None = None,
    user_data_home: Path | str | None = None,
) -> str:
    """Prefer project or installed venvs before the current Python.

    GTK launchers normally run with the system interpreter so PyGObject is
    available. Monitor and editor subprocesses still need the application's
    pip dependencies, which live in a venv. Source-tree runs may reuse the
    per-user installation venv when no local development venv exists.
    """
    root = Path(root).expanduser()
    environment = os.environ if environment is None else environment
    current = sys.executable if current is None else current

    override = str(environment.get(RUNTIME_PYTHON_ENV, "")).strip()
    if override:
        candidate = Path(override).expanduser()
        if _executable(candidate):
            return str(candidate)

    if user_data_home is None:
        configured_data_home = str(environment.get("XDG_DATA_HOME", "")).strip()
        user_data_home = (
            Path(configured_data_home).expanduser()
            if configured_data_home
            else Path.home() / ".local" / "share"
        )
    else:
        user_data_home = Path(user_data_home).expanduser()

    candidates = (
        root / "venv" / "bin" / "python3",
        root / ".venv" / "bin" / "python3",
        root / "venv" / "Scripts" / "python.exe",
        root / ".venv" / "Scripts" / "python.exe",
        user_data_home / "turing-smart-screen" / "venv" / "bin" / "python3",
    )
    for candidate in candidates:
        if _executable(candidate):
            return str(candidate)
    return current


_install_html_editor_background_extension()
_install_native_theme_import_dialog()
