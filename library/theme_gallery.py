# SPDX-License-Identifier: GPL-3.0-or-later
"""Reusable GTK theme gallery components.

This module is shared by the temporary gallery developer entry point and the
future main GTK app shell. It intentionally keeps theme discovery/model logic in
one place so the project does not grow a separate app for every feature.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk, Pango

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "config.yaml"
THEMES_DIR = ROOT / "res" / "themes"
THEME_EDITOR = ROOT / "theme-editor-gtk.py"

ThemeCallback = Callable[["ThemeRecord"], None]


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


def read_current_theme(config_file: Path = CONFIG_FILE) -> str | None:
    try:
        content = config_file.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None

    match = re.search(r"(?m)^\s*THEME\s*:\s*['\"]?([^'\"\n#]+)", content)
    if match is None:
        return None
    return match.group(1).strip()


def discover_themes(
    themes_dir: Path = THEMES_DIR,
    config_file: Path = CONFIG_FILE,
) -> list[ThemeRecord]:
    current_theme = read_current_theme(config_file)
    records: list[ThemeRecord] = []

    if not themes_dir.is_dir():
        return records

    for theme_dir in sorted(
        (path for path in themes_dir.iterdir() if path.is_dir()),
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


def launch_theme_editor(record: ThemeRecord, theme_editor: Path = THEME_EDITOR) -> None:
    if not record.editable:
        raise RuntimeError(
            f"{record.name} cannot be opened because it has no theme.yaml/theme.yml."
        )
    if not theme_editor.is_file():
        raise FileNotFoundError(f"Could not find {theme_editor}")

    subprocess.Popen(
        [sys.executable, str(theme_editor), record.name],
        cwd=str(ROOT),
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def open_theme_folder(record: ThemeRecord) -> None:
    subprocess.Popen(
        ["gio", "open", str(record.directory)],
        cwd=str(ROOT),
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class ThemeGalleryPane(Gtk.Box):
    """Reusable gallery surface for app shell and developer window."""

    def __init__(
        self,
        *,
        on_open_theme: ThemeCallback,
        on_open_folder: ThemeCallback,
        on_records_changed: Callable[[list[ThemeRecord]], None] | None = None,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.on_open_theme = on_open_theme
        self.on_open_folder = on_open_folder
        self.on_records_changed = on_records_changed
        self.records: list[ThemeRecord] = []

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(self.scrolled)

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
        self.scrolled.set_child(self.flow_box)

        self.reload_themes(show_toast=False)

    def clear_flow_box(self) -> None:
        child = self.flow_box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.flow_box.remove(child)
            child = next_child

    def reload_themes(self, show_toast: bool = True) -> None:
        del show_toast  # handled by the containing window/shell
        self.records = discover_themes()
        self.render_records(self.records)
        if self.on_records_changed is not None:
            self.on_records_changed(list(self.records))

    def render_records(self, records: list[ThemeRecord]) -> None:
        self.clear_flow_box()

        if not records:
            self.flow_box.append(self.empty_state())
            return

        for record in records:
            self.flow_box.append(self.theme_card(record))

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

        name_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        name = Gtk.Label(label=record.name, xalign=0)
        name.set_ellipsize(Pango.EllipsizeMode.END)
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

        path = Gtk.Label(label=os.path.relpath(record.directory, ROOT), xalign=0)
        path.set_ellipsize(Pango.EllipsizeMode.END)
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
        edit_button.connect("clicked", lambda *_args: self.on_open_theme(record))
        actions.append(edit_button)

        folder_button = Gtk.Button(icon_name="folder-open-symbolic")
        folder_button.set_tooltip_text("Open theme folder")
        folder_button.connect("clicked", lambda *_args: self.on_open_folder(record))
        actions.append(folder_button)
        card.append(actions)

        return card

    def current_theme_record(self) -> ThemeRecord | None:
        return next((record for record in self.records if record.current), None)


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

        self.open_current_button = Gtk.Button(
            label="Open Current",
            tooltip_text="Open the current theme in the GTK Theme Editor",
        )
        self.open_current_button.add_css_class("suggested-action")
        self.open_current_button.connect("clicked", lambda *_: self.open_current_theme())
        header.pack_end(self.open_current_button)

        self.gallery = ThemeGalleryPane(
            on_open_theme=self.open_theme_editor,
            on_open_folder=self.open_theme_folder,
            on_records_changed=self.update_records_state,
        )
        toolbar.set_content(self.gallery)

    def toast(self, message: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast(title=message))

    def error_dialog(self, heading: str, body: str) -> None:
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("ok", "OK")
        dialog.set_close_response("ok")
        dialog.set_default_response("ok")
        dialog.present(self)

    def update_records_state(self, records: list[ThemeRecord]) -> None:
        self.window_title.set_subtitle(
            f"{len(records)} theme{'s' if len(records) != 1 else ''}"
            if records
            else "No themes found"
        )
        self.open_current_button.set_sensitive(any(record.current for record in records))

    def reload_themes(self) -> None:
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

    def open_theme_folder(self, record: ThemeRecord) -> None:
        try:
            open_theme_folder(record)
        except Exception as exc:
            self.error_dialog("Could not open theme folder", str(exc))
            return
        self.toast(f"Opening folder for {record.name}")


class ThemeGalleryApplication(Adw.Application):
    def __init__(self, application_id: str = "io.github.turing.SmartScreen.ThemeGallery"):
        super().__init__(application_id=application_id)
        GLib.set_application_name("Theme Gallery")

    def do_activate(self):
        window = self.props.active_window
        if window is None:
            window = ThemeGalleryWindow(self)
        window.present()


def main(argv: list[str] | None = None) -> int:
    app = ThemeGalleryApplication()
    return app.run(argv or sys.argv)
