#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Main GTK/Libadwaita app shell for Turing Smart Screen tools."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# GTK comes from the system Python on Arch/CachyOS, while the project
# dependencies may live in the virtual environment.
for site_dir in (
    ROOT / "venv" / "lib",
    ROOT / ".venv" / "lib",
):
    if site_dir.is_dir():
        for candidate in site_dir.glob("python*/site-packages"):
            sys.path.insert(0, str(candidate))

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from library.theme_gallery import (
    ThemeGalleryPane,
    ThemeRecord,
    launch_theme_editor,
    open_theme_folder,
    set_current_theme,
    show_set_current_theme_dialog,
    show_theme_gallery_diagnostics_dialog,
)

APP_ID = "io.github.turing.SmartScreen"


class TuringSmartScreenWindow(Adw.ApplicationWindow):
    """Primary app shell.

    The shell is intentionally small in this first slice: it establishes a
    single user-facing launcher and embeds the reusable Theme Gallery as the
    home surface. Future roadmap surfaces should be added here instead of as
    separate standalone apps.
    """

    def __init__(self, app: Adw.Application):
        super().__init__(
            application=app,
            title="Turing Smart Screen",
            default_width=1280,
            default_height=800,
        )
        self.set_size_request(920, 600)

        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        toolbar = Adw.ToolbarView()
        self.toast_overlay.set_child(toolbar)

        header = Adw.HeaderBar()
        self.window_title = Adw.WindowTitle(
            title="Turing Smart Screen",
            subtitle="Themes",
        )
        header.set_title_widget(self.window_title)
        toolbar.add_top_bar(header)

        refresh_button = Gtk.Button(
            icon_name="view-refresh-symbolic",
            tooltip_text="Reload the current surface",
        )
        refresh_button.connect("clicked", lambda *_: self.refresh_current_surface())
        header.pack_end(refresh_button)

        self.open_current_button = Gtk.Button(
            label="Open Current",
            tooltip_text="Open the current theme in the GTK Theme Editor",
        )
        self.open_current_button.add_css_class("suggested-action")
        self.open_current_button.connect("clicked", lambda *_: self.open_current_theme())
        header.pack_end(self.open_current_button)

        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        toolbar.set_content(root)

        sidebar = self.build_sidebar()
        root.append(sidebar)

        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        root.append(separator)

        self.stack = Gtk.Stack()
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        root.append(self.stack)

        self.gallery = ThemeGalleryPane(
            on_open_theme=self.open_theme_editor,
            on_open_folder=self.open_folder,
            on_theme_diagnostics=self.show_theme_diagnostics,
            on_set_current_theme=self.confirm_set_current_theme,
            on_records_changed=self.update_theme_state,
        )
        self.stack.add_named(self.gallery, "themes")
        self.stack.set_visible_child_name("themes")

    def build_sidebar(self) -> Gtk.Widget:
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_top=18,
            margin_bottom=18,
            margin_start=18,
            margin_end=18,
        )
        box.set_size_request(240, -1)

        title = Gtk.Label(label="App", xalign=0)
        title.add_css_class("heading")
        box.append(title)

        nav = Gtk.ListBox()
        nav.add_css_class("boxed-list")
        nav.set_selection_mode(Gtk.SelectionMode.SINGLE)
        box.append(nav)

        themes_row = self.nav_row(
            "Themes",
            "Browse and edit theme folders",
            "folder-pictures-symbolic",
        )
        nav.append(themes_row)
        nav.select_row(themes_row)

        device_row = self.nav_row(
            "Device Manager",
            "Coming in a later stack phase",
            "drive-harddisk-symbolic",
        )
        device_row.set_sensitive(False)
        nav.append(device_row)

        diagnostics_row = self.nav_row(
            "Diagnostics",
            "Available per theme from the gallery",
            "dialog-information-symbolic",
        )
        diagnostics_row.set_sensitive(False)
        nav.append(diagnostics_row)

        settings_row = self.nav_row(
            "Settings",
            "Future app preferences",
            "emblem-system-symbolic",
        )
        settings_row.set_sensitive(False)
        nav.append(settings_row)

        note = Gtk.Label(
            label=(
                "This is the new app shell. Standalone scripts remain only "
                "as developer entry points during the transition."
            ),
            xalign=0,
            wrap=True,
            margin_top=8,
        )
        note.add_css_class("dim-label")
        box.append(note)

        return box

    def nav_row(self, title: str, subtitle: str, icon_name: str) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        content = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10,
            margin_top=8,
            margin_bottom=8,
            margin_start=8,
            margin_end=8,
        )
        icon = Gtk.Image.new_from_icon_name(icon_name)
        content.append(icon)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        labels.set_hexpand(True)
        title_label = Gtk.Label(label=title, xalign=0)
        title_label.add_css_class("heading")
        labels.append(title_label)
        subtitle_label = Gtk.Label(label=subtitle, xalign=0, wrap=True)
        subtitle_label.add_css_class("caption")
        subtitle_label.add_css_class("dim-label")
        labels.append(subtitle_label)
        content.append(labels)

        row.set_child(content)
        return row

    def toast(self, message: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast(title=message))

    def error_dialog(self, heading: str, body: str) -> None:
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("ok", "OK")
        dialog.set_close_response("ok")
        dialog.set_default_response("ok")
        dialog.present(self)

    def update_theme_state(self, records: list[ThemeRecord]) -> None:
        self.window_title.set_subtitle(
            f"Themes · {len(records)} installed"
            if records
            else "Themes · none found"
        )
        self.open_current_button.set_sensitive(any(record.current for record in records))

    def refresh_current_surface(self) -> None:
        if self.stack.get_visible_child_name() == "themes":
            self.gallery.reload_themes()
            self.toast("Theme list refreshed")

    def open_current_theme(self) -> None:
        record = self.gallery.current_theme_record()
        if record is None:
            self.error_dialog(
                "No current theme",
                "config.yaml does not point to a theme that exists in res/themes.",
            )
            return
        self.open_theme_editor(record)

    def open_theme_editor(self, record: ThemeRecord) -> None:
        try:
            launch_theme_editor(record)
        except Exception as exc:
            self.error_dialog("Could not open theme editor", str(exc))
            return
        self.toast(f"Opening {record.name}")

    def open_folder(self, record: ThemeRecord) -> None:
        try:
            open_theme_folder(record)
        except Exception as exc:
            self.error_dialog("Could not open theme folder", str(exc))
            return
        self.toast(f"Opening folder for {record.name}")

    def show_theme_diagnostics(self, record: ThemeRecord) -> None:
        show_theme_gallery_diagnostics_dialog(self, record, self.toast)

    def confirm_set_current_theme(self, record: ThemeRecord) -> None:
        show_set_current_theme_dialog(self, record, self.apply_set_current_theme)

    def apply_set_current_theme(self, record: ThemeRecord) -> None:
        try:
            old_theme, new_theme = set_current_theme(record)
        except Exception as exc:
            self.error_dialog("Could not set current theme", str(exc))
            return
        self.gallery.reload_themes()
        if old_theme and old_theme != new_theme:
            self.toast(f"Current theme changed: {old_theme} → {new_theme}")
        else:
            self.toast(f"Current theme set to {new_theme}")


class TuringSmartScreenApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        GLib.set_application_name("Turing Smart Screen")

    def do_activate(self):
        window = self.props.active_window
        if window is None:
            window = TuringSmartScreenWindow(self)
        window.present()


def main(argv: list[str] | None = None) -> int:
    app = TuringSmartScreenApplication()
    return app.run(argv or sys.argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
