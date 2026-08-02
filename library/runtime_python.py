# SPDX-License-Identifier: GPL-3.0-or-later
"""Resolve the dependency-complete Python used by project subprocesses."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from types import MethodType


RUNTIME_PYTHON_ENV = "TURING_SMART_SCREEN_PYTHON"


def _javascript_json_script(script: str) -> str:
    """Wrap a JavaScript expression so WebKit only returns a string value."""
    expression = str(script or "").strip()
    if expression.endswith(";"):
        expression = expression[:-1].rstrip()
    if not expression:
        raise ValueError("JavaScript expression cannot be empty")
    return f"JSON.stringify(({expression}))"


def _decode_javascript_json(value):
    """Decode a JSON string returned as a JSC.Value-like object."""
    if value is None:
        raise RuntimeError("WebKit returned no JavaScript result")
    text = value.to_string()
    if text is None:
        raise RuntimeError("WebKit returned an empty JavaScript string")
    return json.loads(str(text))


def _install_html_editor_json_bridge(window) -> None:
    """Avoid unsupported structured return values in older WebKitGTK builds."""
    if getattr(window, "_turing_json_bridge_installed", False):
        return

    def evaluate_json(self, script: str, callback) -> None:
        wrapped_script = _javascript_json_script(script)

        def finished(view, result, _user_data=None):
            try:
                value = view.evaluate_javascript_finish(result)
                callback(_decode_javascript_json(value), None)
            except Exception as exc:
                callback(None, exc)

        self.backend.view.evaluate_javascript(
            wrapped_script,
            -1,
            None,
            None,
            None,
            finished,
            None,
        )

    window._evaluate_json = MethodType(evaluate_json, window)
    window._turing_json_bridge_installed = True


def _install_html_editor_extensions() -> None:
    """Attach editor extensions after the HTML editor window is fully built."""
    if Path(sys.argv[0]).name != "html-theme-editor-gtk.py":
        return
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gio, GLib, Gtk
        from library.html_theme_background_editor import _attach_background_page
    except Exception as exc:
        print(f"Erro ao preparar a aba Fundo: {exc}", file=sys.stderr)
        return

    attempts = 0

    def attach_when_ready() -> bool:
        nonlocal attempts
        attempts += 1
        try:
            application = Gtk.Application.get_default()
            if application is None:
                return attempts < 150
            for window in application.get_windows():
                if window.__class__.__name__ != "HtmlThemeEditorWindow":
                    continue
                if getattr(window, "inspector_stack", None) is None:
                    return attempts < 150
                _install_html_editor_json_bridge(window)
                _attach_background_page(window, Gtk, Gio)
                if not getattr(window, "_turing_background_page_attached", False):
                    raise RuntimeError("a página Fundo não foi anexada ao inspector_stack")
                return False
        except Exception as exc:
            print(f"Erro ao carregar extensões do editor HTML: {exc}", file=sys.stderr)
            return False
        return attempts < 150

    GLib.timeout_add(100, attach_when_ready)


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


_install_html_editor_extensions()
