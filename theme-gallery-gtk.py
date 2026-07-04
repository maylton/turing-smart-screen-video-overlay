#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""GTK4 + Libadwaita theme gallery for Turing Smart Screen themes."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
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

APP_ID = "io.github.turing.SmartScreen.ThemeGallery"
CONFIG_FILE = ROOT / "config.yaml"
THEMES_DIR = ROOT / "res" / "themes"
THEME_EDITOR = ROOT / "theme-editor-gtk.py"


@dataclass(frozen=True)
class ThemeRecord:
    name: str
    directory: Path
    yaml_file: Path | None
    preview_file: Path
    current: bool = False
    issue: str | None = None

    @property
    def editable(self) -> bool:
        return self.yaml_file is not None and self.issue is None

    @property
    def status_label(self) -> str:
        if self.issue:
            return self.issue
        if self.current:
            return "Current theme"
        return "Ready"


def find_theme_file(theme_dir: Path) -> Path | None:
    for file_name in ("theme.yaml", "theme.yml"):
        candidate = theme_dir / file_name
        if candidate.is_file():
            return candidate
    return None


def read_current_theme() -> str | None:
    try:
        content = CONFIG_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None

    match = re.search(r"(?m)^\s*THEME\s*:\s*['\"]?([^'\"\n#]+)", content)
    if match is None:
        return None
    return match.group(1).strip()


def discover_themes() -> list[ThemeRecord]:
    current_theme = read_current_theme()
    records: list[ThemeRecord] = []

    if not THEMES_DIR.is_dir():
        return records

    for theme_dir in sorted(
        (path for path in THEMES_DIR.iterdir() if path.is_dir()),
        key=lambda path: path.name.casefold(),
    ):
        yaml_file = find_theme_file(theme_dir)
        issue = None
        if yaml_file is None:
            issue = "Missing theme.yaml"

        records.append(
            ThemeRecord(
                name=theme_dir.name,
                directory=theme_dir,
                yaml_file=yaml_file,
                preview_file=theme_dir / "preview.png",
                current=theme_dir.name == current_theme,
                issue=issue,
            )
        )

    return sorted(records, key=lambda record: (not record.current, record.name.casefold()))


class ThemeGalleryWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(
            application=app,
            title="Theme Gallery",
            default_width=1180,
            default_height=760,
        )
        self.set_size_request(860, 560)

        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        toolbar = Adw.ToolbarView()
        self.toast_overlay.set_child(toolbar)

        header = Adw.HeaderBar()
        self.window_title = Adw.WindowTitle(
            title="Theme Gallery",
            subtitle="Browse and open installed themes",
        )
        header.set_title_widget(self.window_title)
        toolbar.add_top_bar(header)

        refresh_button = Gtk.Button(
            icon_name="view-refresh-symbolic",
            tooltip_text="Reload the theme list",
        )
        refresh_button.connect("clicked", lambda *_: self.reload_themes())
        header.pack_end(refresh_button)

        open_current_button = Gtk.Button(
            label="Open Current",
            tooltip_text="Open the current theme in the GTK Theme Editor",
        )
        open_current_button.add_css_class("suggested-action")
        open_current_button.connect("clicked", lambda *_: self.open_current_theme())
        header.pack_end(open_current_button)
        self.open_current_button = open_current_button

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        toolbar.set_content(scrolled)

        self.flow_box = Gtk.FlowBox(
            column_spacing=18,
            row_spacing=18,
            margin_top=24,
            margin_bottom=24,
            margin_start=24,
            margin_end=24,
        )
        self.flow_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flow_box.set_homogeneous(False)
        self.flow_box.set_min_children_per_line(2)
        self.flow_box.set_max_children_per_line(4)
        scrolled.set_child(self.flow_box)

        self.records: list[ThemeRecord] = []
        self.reload_themes()

    def toast(self, message: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast(title=message))

    def error_dialog(self, heading: str, body: str) -> None:
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("ok", "OK")
        dialog.set_close_response("ok")
        dialog.set_default_response("ok")
        dialog.present(self)

    def clear_flow_box(self) -> None:
        child = self.flow_box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.flow_box.remove(child)
            child = next_child

    def reload_themes(self) -> None:
        self.records = discover_themes()
        self.clear_flow_box()

        if not self.records:
            self.flow_box.append(self.empty_state())
            self.window_title.set_subtitle("No themes found")
            self.open_current_button.set_sensitive(False)
            return

        for record in self.records:
            self.flow_box.append(self.theme_card(record))

        current_count = sum(1 for record in self.records if record.current)
        self.window_title.set_subtitle(
            f"{len(self.records)} theme{'s' if len(self.records) != 1 else ''}"
        )
        self.open_current_button.set_sensitive(current_count > 0)
        self.toast("Theme list refreshed")

    def empty_state(self) -> Gtk.Widget:
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            margin_top=80,
            margin_bottom=80,
            margin_start=80,
            margin_end=80,
        )
        icon = Gtk.Image.new_from_icon_name("folder-symbolic")
        icon.set_pixel_size(64)
        box.append(icon)
        title = Gtk.Label(label="No themes found")
        title.add_css_class("title-2")
        box.append(title)
        subtitle = Gtk.Label(
            label=f"Create or copy themes into {THEMES_DIR}",
            wrap=True,
            justify=Gtk.Justification.CENTER,
        )
        subtitle.add_css_class("dim-label")
        box.append(subtitle)
        return box

    def preview_widget(self, record: ThemeRecord) -> Gtk.Widget:
        if record.preview_file.is_file():
            picture = Gtk.Picture.new_for_filename(str(record.preview_file))
            picture.set_size_request(256, 144)
            picture.set_can_shrink(True)
            if hasattr(picture, "set_content_fit"):
                picture.set_content_fit(Gtk.ContentFit.CONTAIN)
            return picture

        placeholder = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
        )
        placeholder.set_size_request(256, 144)
        icon = Gtk.Image.new_from_icon_name("image-missing-symbolic")
        icon.set_pixel_size(48)
        placeholder.append(icon)
        label = Gtk.Label(label="No preview")
        label.add_css_class("dim-label")
        placeholder.append(label)
        return placeholder

    def theme_card(self, record: ThemeRecord) -> Gtk.Widget:
        card = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
        )
        card.add_css_class("card")
        card.set_size_request(292, -1)

        preview_frame = Gtk.Frame()
        preview_frame.set_child(self.preview_widget(record))
        card.append(preview_frame)

        name_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )
        name = Gtk.Label(label=record.name, xalign=0, ellipsize=3)
        name.add_css_class("heading")
        name.set_hexpand(True)
        name_row.append(name)
        if record.current:
            badge = Gtk.Label(label="Current")
            badge.add_css_class("accent")
            name_row.append(badge)
        card.append(name_row)

        status = Gtk.Label(label=record.status_label, xalign=0, wrap=True)
        status.add_css_class("dim-label")
        card.append(status)

        path = Gtk.Label(
            label=os.path.relpath(record.directory, ROOT),
            xalign=0,
            ellipsize=3,
        )
        path.add_css_class("caption")
        path.add_css_class("dim-label")
        card.append(path)

        actions = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_top=4,
        )
        edit_button = Gtk.Button(label="Edit")
        edit_button.add_css_class("suggested-action")
        edit_button.set_hexpand(True)
        edit_button.set_sensitive(record.editable)
        edit_button.connect("clicked", lambda *_args, theme=record: self.open_theme_editor(theme))
        actions.append(edit_button)

        folder_button = Gtk.Button(icon_name="folder-open-symbolic")
        folder_button.set_tooltip_text("Open theme folder")
        folder_button.connect("clicked", lambda *_args, theme=record: self.open_theme_folder(theme))
        actions.append(folder_button)
        card.append(actions)

        return card

    def current_theme_record(self) -> ThemeRecord | None:
        return next((record for record in self.records if record.current), None)

    def open_current_theme(self) -> None:
        record = self.current_theme_record()
        if record is None:
            self.error_dialog(
                "No current theme",
                "config.yaml does not point to a theme that exists in res/themes.",
            )
            return
        self.open_theme_editor(record)

    def open_theme_editor(self, record: ThemeRecord) -> None:
        if not record.editable:
            self.error_dialog(
                "Theme cannot be opened",
                f"{record.name} cannot be opened because it has no theme.yaml/theme.yml.",
            )
            return

        if not THEME_EDITOR.is_file():
            self.error_dialog(
                "GTK Theme Editor not found",
                f"Could not find {THEME_EDITOR}",
            )
            return

        try:
            subprocess.Popen(
                [sys.executable, str(THEME_EDITOR), record.name],
                cwd=str(ROOT),
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            self.error_dialog("Could not open theme editor", str(exc))
            return

        self.toast(f"Opening {record.name}")

    def open_theme_folder(self, record: ThemeRecord) -> None:
        try:
            subprocess.Popen(
                ["gio", "open", str(record.directory)],
                cwd=str(ROOT),
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            self.error_dialog("Could not open theme folder", str(exc))
            return

        self.toast(f"Opening folder for {record.name}")


class ThemeGalleryApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        GLib.set_application_name("Theme Gallery")

    def do_activate(self):
        window = self.props.active_window
        if window is None:
            window = ThemeGalleryWindow(self)
        window.present()


def main() -> int:
    app = ThemeGalleryApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
