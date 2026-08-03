# SPDX-License-Identifier: GPL-3.0-or-later
"""Resolve the dependency-complete Python used by project subprocesses."""

from __future__ import annotations

import os
import sys
import threading
import time
from collections.abc import Mapping
from pathlib import Path


RUNTIME_PYTHON_ENV = "TURING_SMART_SCREEN_PYTHON"
_THEME_IMPORT_ENTRY_POINTS = {
    "configure-gtk.py",
    "theme-gallery-gtk.py",
    "turing-smart-screen-gtk.py",
    "turing-smart-screen-main.py",
}
_MAIN_APP_THEME_CREATOR_ENTRY_POINTS = {
    "configure-gtk.py",
    "turing-smart-screen",
    "turing-smart-screen-gtk.py",
    "turing-smart-screen-main.py",
}
_THEME_CREATOR_WATCH_STARTED = False


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


def _install_html_editor_style_extension() -> None:
    """Add outer text outlines and curated presets after editor initialization."""
    if Path(sys.argv[0]).name != "html-theme-editor-gtk.py":
        return
    try:
        from library.html_theme_style_presets import install_style_preset_editor_hook

        install_style_preset_editor_hook()
    except Exception as exc:
        print(
            f"Não foi possível preparar os presets visuais do editor HTML: {exc}",
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


def _main_app_module():
    for module in tuple(sys.modules.values()):
        module_file = str(getattr(module, "__file__", "") or "")
        if not module_file:
            continue
        try:
            if Path(module_file).name != "configure_gtk_app.py":
                continue
        except (OSError, TypeError, ValueError):
            continue
        if getattr(module, "SmartScreenWindow", None) is not None:
            return module
    return None


def _install_main_app_theme_creator_extension() -> None:
    """Install the HTML theme creator after the dynamically loaded GTK app exists."""
    global _THEME_CREATOR_WATCH_STARTED
    if Path(sys.argv[0]).name not in _MAIN_APP_THEME_CREATOR_ENTRY_POINTS:
        return
    if _THEME_CREATOR_WATCH_STARTED:
        return
    _THEME_CREATOR_WATCH_STARTED = True

    def wait_for_main_app() -> None:
        for _attempt in range(400):
            app_module = _main_app_module()
            if app_module is None:
                time.sleep(0.025)
                continue

            def install() -> bool:
                try:
                    from library.html_theme_creator import (
                        install_main_app_theme_creator,
                    )

                    install_main_app_theme_creator(app_module)
                except Exception as exc:
                    print(
                        f"Não foi possível preparar a criação de temas HTML: {exc}",
                        file=sys.stderr,
                    )
                return False

            glib = getattr(app_module, "GLib", None)
            idle_add = getattr(glib, "idle_add", None)
            if callable(idle_add):
                idle_add(install)
            else:
                install()
            return

        print(
            "Não foi possível localizar a janela GTK para instalar a criação de temas HTML.",
            file=sys.stderr,
        )

    threading.Thread(
        target=wait_for_main_app,
        name="turing-html-theme-creator",
        daemon=True,
    ).start()


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
_install_html_editor_style_extension()
_install_native_theme_import_dialog()
_install_main_app_theme_creator_extension()
