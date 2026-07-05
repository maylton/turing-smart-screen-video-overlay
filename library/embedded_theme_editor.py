# SPDX-License-Identifier: GPL-3.0-or-later
"""Embedded Theme Editor surface for the main GTK application."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk


class EmbeddedThemeEditorPage(Gtk.Box):
    """Host the existing ThemeEditorWindow content inside the main app stack.

    This is an integration bridge: the standalone editor remains available, but
    the main app can now display the editor content in-process instead of
    opening a separate window for the normal gallery -> edit flow.
    """

    def __init__(
        self,
        *,
        root: Path,
        application: Adw.Application,
        on_back: Callable[[], None],
        on_open_external: Callable[[str], None],
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.root = root
        self.application = application
        self.on_back = on_back
        self.on_open_external = on_open_external
        self._editor_module = None
        self._editor_window = None
        self.current_theme_name = ""

        header = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_top=12,
            margin_bottom=12,
            margin_start=18,
            margin_end=18,
        )
        header.add_css_class("toolbar")
        self.append(header)

        back_button = Gtk.Button(
            label="Themes",
            icon_name="go-previous-symbolic",
            tooltip_text="Back to Theme Gallery",
            valign=Gtk.Align.CENTER,
        )
        back_button.connect("clicked", lambda *_: self.on_back())
        header.append(back_button)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title_box.set_hexpand(True)
        self.title_label = Gtk.Label(label="Theme Editor", xalign=0)
        self.title_label.add_css_class("title-2")
        self.subtitle_label = Gtk.Label(
            label="Choose a theme from the gallery to start editing.",
            xalign=0,
        )
        self.subtitle_label.add_css_class("dim-label")
        title_box.append(self.title_label)
        title_box.append(self.subtitle_label)
        header.append(title_box)

        self.open_external_button = Gtk.Button(
            label="Open separate window",
            icon_name="window-new-symbolic",
            tooltip_text="Open this theme in the standalone GTK Theme Editor",
            valign=Gtk.Align.CENTER,
        )
        self.open_external_button.set_sensitive(False)
        self.open_external_button.connect("clicked", self.open_external)
        header.append(self.open_external_button)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.append(separator)

        self.editor_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.editor_container.set_hexpand(True)
        self.editor_container.set_vexpand(True)
        self.append(self.editor_container)
        self.show_empty_state()

    def clear_editor_container(self) -> None:
        child = self.editor_container.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.editor_container.remove(child)
            child = next_child

    def show_empty_state(self, message: str | None = None) -> None:
        self.clear_editor_container()
        empty = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            margin_top=80,
            margin_bottom=80,
            margin_start=80,
            margin_end=80,
        )
        empty.set_vexpand(True)
        icon = Gtk.Image.new_from_icon_name("applications-graphics-symbolic")
        icon.set_pixel_size(64)
        empty.append(icon)

        title = Gtk.Label(label="No theme open")
        title.add_css_class("title-2")
        empty.append(title)

        subtitle = Gtk.Label(
            label=message or "Go back to Themes and choose Edit on a theme card.",
            wrap=True,
            justify=Gtk.Justification.CENTER,
        )
        subtitle.add_css_class("dim-label")
        empty.append(subtitle)
        self.editor_container.append(empty)

    def load_editor_module(self):
        if self._editor_module is not None:
            return self._editor_module

        editor_file = self.root / "theme-editor-gtk.py"
        spec = importlib.util.spec_from_file_location(
            "turing_smart_screen_embedded_theme_editor",
            editor_file,
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not load {editor_file.name}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        self._editor_module = module
        return module

    def open_theme(self, theme_name: str) -> None:
        theme_name = str(theme_name or "").strip()
        if not theme_name:
            raise ValueError("No theme selected.")
        if self._editor_window is not None and self.current_theme_name == theme_name:
            return

        module = self.load_editor_module()
        editor_window = module.ThemeEditorWindow(self.application, theme_name)
        editor_window._embedded_dialog_parent = self

        if hasattr(editor_window, "get_content"):
            content = editor_window.get_content()
            editor_window.set_content(None)
        else:
            content = editor_window.get_child()
            editor_window.set_child(None)

        if content is None:
            raise RuntimeError("Theme Editor did not expose embeddable content.")

        self.clear_editor_container()
        self._editor_window = editor_window
        self.current_theme_name = theme_name
        self.title_label.set_label(f"Theme Editor — {theme_name}")
        self.subtitle_label.set_label("Embedded editor in the main app")
        self.open_external_button.set_sensitive(True)
        self.editor_container.append(content)

    def open_external(self, *_args) -> None:
        if self.current_theme_name:
            self.on_open_external(self.current_theme_name)
