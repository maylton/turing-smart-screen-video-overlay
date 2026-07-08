# SPDX-License-Identifier: GPL-3.0-or-later
"""Inline Theme Editor page for the main GTK configuration app."""

from __future__ import annotations

import importlib.util
import sys
from typing import Any


_MODULE_NAME = "turing_smart_screen_embedded_theme_editor"


def _load_theme_editor_module(app: Any):
    """Load theme-editor-gtk.py without running its standalone application."""

    cached = sys.modules.get(_MODULE_NAME)
    if cached is not None:
        return cached

    editor_file = app.ROOT / "theme-editor-gtk.py"
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, editor_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {editor_file.name}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


def _install_inline_theme_editor_i18n(app_module: Any, editor_class: type) -> None:
    """Install safe ThemeEditorWindow-level i18n wrappers, not GTK monkeypatches."""

    try:
        from library.theme_editor_i18n import install_theme_editor_i18n

        install_theme_editor_i18n(editor_class)
    except Exception:
        pass

    try:
        from library.theme_editor_safe_i18n import install_theme_editor_safe_i18n

        install_theme_editor_safe_i18n(app_module)
    except Exception:
        pass


def build_inline_theme_editor_page(app: Any, window: Any, theme_name: str):
    """Build an embeddable Theme Editor page for ``SmartScreenWindow.stack``."""

    Gtk = app.Gtk

    try:
        from library.theme_editor_widget_i18n import install as install_widget_i18n

        install_widget_i18n()
    except Exception:
        pass

    module = _load_theme_editor_module(app)
    editor_class = getattr(module, "ThemeEditorWindow")
    _install_inline_theme_editor_i18n(module, editor_class)
    application = window.get_application() if hasattr(window, "get_application") else None
    editor = editor_class(application, theme_name)

    page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    page.set_hexpand(True)
    page.set_vexpand(True)

    content = None
    getter = getattr(editor, "get_content", None)
    if callable(getter):
        try:
            content = getter()
        except Exception:
            content = None
    if content is None:
        content = getattr(editor, "toast_overlay", None)
    if content is None:
        raise RuntimeError("Theme Editor did not expose embeddable content")

    try:
        editor.set_content(None)
    except Exception:
        pass

    try:
        content.set_hexpand(True)
        content.set_vexpand(True)
    except Exception:
        pass

    page.append(content)
    editor._embedded_dialog_parent = page
    page._theme_editor_window = editor
    page._theme_name = theme_name

    try:
        from library.theme_editor_i18n import translate_widget_tree

        translate_widget_tree(page)
    except Exception:
        pass

    return page
