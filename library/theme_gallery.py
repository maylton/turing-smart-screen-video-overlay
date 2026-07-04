# SPDX-License-Identifier: GPL-3.0-or-later
"""Reusable GTK theme gallery components.

This module is shared by the temporary gallery developer entry point and the
main GTK configuration application. It intentionally keeps theme discovery,
model logic, and gallery widgets in one place so the project does not grow a
separate app for every feature.
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

    def search_text(self) -> str:
        parts = [self.name, self.status_label]
        try:
            parts.append(os.path.relpath(self.directory, ROOT))
        except ValueError:
            parts.append(str(self.directory))
        if self.yaml_file is not None:
            parts.append(self.yaml_file.name)
        return " ".join(parts).casefold()


def relative_path_label(path: Path) -> str:
    try:
        return os.path.relpath(path, ROOT)
    except ValueError:
        return str(path)


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


def set_current_theme(
    record: ThemeRecord,
    config_file: Path = CONFIG_FILE,
) -> tuple[str | None, str]:
    """Set the active theme in config.yaml and return (old_theme, new_theme)."""
    if not record.editable:
        raise RuntimeError(
            f"{record.name} cannot be set as current because it has no theme.yaml/theme.yml."
        )

    try:
        content = config_file.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Could not find {config_file}") from exc

    old_theme = read_current_theme(config_file)
    pattern = re.compile(r"(?m)^(\s*THEME\s*:\s*)([^#\n]*)(\s*(?:#.*)?)$")
    match = pattern.search(content)
    if match is None:
        raise RuntimeError("Could not find THEME in config.yaml")

    replacement = f"{match.group(1)}{record.name}{match.group(3)}"
    new_content = content[: match.start()] + replacement + content[match.end() :]

    tmp_file = config_file.with_name(f"{config_file.name}.tmp")
    tmp_file.write_text(new_content, encoding="utf-8")
    os.replace(tmp_file, config_file)
    return old_theme, record.name


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


def filter_theme_records(records: list[ThemeRecord], query: str) -> list[ThemeRecord]:
    terms = [term.casefold() for term in query.split() if term.strip()]
    if not terms:
        return list(records)
    return [
        record
        for record in records
        if all(term in record.search_text() for term in terms)
    ]


def build_theme_gallery_diagnostics_report(record: ThemeRecord) -> str:
    lines: list[str] = [
        "Theme Gallery Diagnostics",
        "=========================",
        "",
        f"Theme: {record.name}",
        f"Status: {record.status_label}",
        f"Current theme: {'yes' if record.current else 'no'}",
        f"Theme folder: {relative_path_label(record.directory)}",
    ]

    if record.yaml_file is not None:
        lines.append(f"Theme YAML: {relative_path_label(record.yaml_file)}")
        try:
            stat = record.yaml_file.stat()
            lines.append(f"Theme YAML size: {stat.st_size} bytes")
        except OSError as exc:
            lines.append(f"Theme YAML status: stat failed: {exc}")
        try:
            yaml_text = record.yaml_file.read_text(encoding="utf-8")
            lines.append(f"Theme YAML lines: {len(yaml_text.splitlines())}")
        except OSError as exc:
            lines.append(f"Theme YAML status: read failed: {exc}")
        except UnicodeDecodeError as exc:
            lines.append(f"Theme YAML status: decode failed: {exc}")
    else:
        lines.append("Theme YAML: missing")

    if record.preview_file.is_file():
        lines.append(f"Preview: {relative_path_label(record.preview_file)}")
        try:
            stat = record.preview_file.stat()
            lines.append(f"Preview size: {stat.st_size} bytes")
        except OSError as exc:
            lines.append(f"Preview status: stat failed: {exc}")
    else:
        lines.append("Preview: missing")

    try:
        children = list(record.directory.iterdir())
        file_count = sum(1 for child in children if child.is_file())
        dir_count = sum(1 for child in children if child.is_dir())
        lines.append(f"Top-level files: {file_count}")
        lines.append(f"Top-level folders: {dir_count}")
    except OSError as exc:
        lines.append(f"Theme folder status: list failed: {exc}")

    lines.extend(
        [
            "",
            "Gallery checks:",
            f"- Editable in GTK Theme Editor: {'yes' if record.editable else 'no'}",
            f"- Has preview image: {'yes' if record.preview_file.is_file() else 'no'}",
            f"- Has theme.yaml/theme.yml: {'yes' if record.yaml_file is not None else 'no'}",
        ]
    )

    if record.issue:
        lines.append(f"- Blocking issue: {record.issue}")

    return "\n".join(lines)


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


def show_theme_gallery_diagnostics_dialog(
    parent: Gtk.Widget,
    record: ThemeRecord,
    toast: Callable[[str], None] | None = None,
) -> None:
    report = build_theme_gallery_diagnostics_report(record)

    text_view = Gtk.TextView()
    text_view.set_editable(False)
    text_view.set_cursor_visible(False)
    text_view.set_monospace(True)
    text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
    text_view.get_buffer().set_text(report)

    scrolled = Gtk.ScrolledWindow()
    scrolled.set_min_content_width(520)
    scrolled.set_min_content_height(360)
    scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scrolled.set_child(text_view)

    dialog = Adw.AlertDialog(
        heading=f"Diagnostics — {record.name}",
        body="Review the gallery-level theme report below.",
    )
    dialog.set_extra_child(scrolled)
    dialog.add_response("copy", "Copy Report")
    dialog.add_response("ok", "OK")
    dialog.set_default_response("ok")
    dialog.set_close_response("ok")

    def on_response(_dialog: Adw.AlertDialog, response: str) -> None:
        if response != "copy":
            return
        parent.get_clipboard().set(report)
        if toast is not None:
            toast("Diagnostics report copied")

    dialog.connect("response", on_response)
    dialog.present(parent)


def show_set_current_theme_dialog(
    parent: Gtk.Widget,
    record: ThemeRecord,
    on_confirm: ThemeCallback,
) -> None:
    dialog = Adw.AlertDialog(
        heading=f"Use {record.name}?",
        body=(
            "This will update config.yaml so this theme becomes the current "
            "theme used by the app."
        ),
    )
    dialog.add_response("cancel", "Cancel")
    dialog.add_response("use", "Use Theme")
    dialog.set_response_appearance("use", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("use")
    dialog.set_close_response("cancel")

    def on_response(_dialog: Adw.AlertDialog, response: str) -> None:
        if response == "use":
            on_confirm(record)

    dialog.connect("response", on_response)
    dialog.present(parent)


class ThemeGalleryPane(Gtk.Box):
    """Reusable gallery surface for app shell and developer window."""

    def __init__(
        self,
        *,
        on_open_theme: ThemeCallback,
        on_open_folder: ThemeCallback,
        on_theme_diagnostics: ThemeCallback | None = None,
        on_set_current_theme: ThemeCallback | None = None,
        on_records_changed: Callable[[list[ThemeRecord]], None] | None = None,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.on_open_theme = on_open_theme
        self.on_open_folder = on_open_folder
        self.on_theme_diagnostics = on_theme_diagnostics
        self.on_set_current_theme = on_set_current_theme
        self.on_records_changed = on_records_changed
        self.records: list[ThemeRecord] = []
        self.filtered_records: list[ThemeRecord] = []
        self.filter_query = ""

        controls = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_top=18,
            margin_bottom=6,
            margin_start=24,
            margin_end=24,
        )
        controls.set_hexpand(True)
        self.append(controls)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        self.search_entry.set_placeholder_text("Search themes by name, path, or status")
        self.search_entry.connect("search-changed", self.on_search_changed)
        controls.append(self.search_entry)

        self.result_label = Gtk.Label(label="", xalign=1)
        self.result_label.add_css_class("dim-label")
        controls.append(self.result_label)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_hexpand(True)
        self.scrolled.set_vexpand(True)
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(self.scrolled)

        self.flow_box = Gtk.FlowBox(
            column_spacing=18,
            row_spacing=18,
            margin_top=18,
            margin_bottom=24,
            margin_start=24,
            margin_end=24,
        )
        self.flow_box.set_hexpand(True)
        self.flow_box.set_vexpand(True)
        self.flow_box.set_valign(Gtk.Align.START)
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

    def on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        self.filter_query = entry.get_text().strip()
        self.apply_filter()

    def reload_themes(self, show_toast: bool = True) -> None:
        del show_toast  # handled by the containing window/shell
        self.records = discover_themes()
        self.apply_filter()
        if self.on_records_changed is not None:
            self.on_records_changed(list(self.records))

    def apply_filter(self) -> None:
        self.filtered_records = filter_theme_records(self.records, self.filter_query)
        self.render_records(self.filtered_records)
        self.update_result_label()

    def update_result_label(self) -> None:
        total = len(self.records)
        visible = len(self.filtered_records)
        if not total:
            self.result_label.set_text("No themes")
            return
        if self.filter_query:
            self.result_label.set_text(f"{visible} of {total}")
            return
        self.result_label.set_text(f"{total} theme{'s' if total != 1 else ''}")

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
        box.set_size_request(320, 260)
        icon_name = "edit-find-symbolic" if self.filter_query else "folder-symbolic"
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(64)
        box.append(icon)

        title_text = "No matching themes" if self.filter_query else "No themes found"
        title = Gtk.Label(label=title_text)
        title.add_css_class("title-2")
        box.append(title)

        if self.filter_query:
            subtitle_text = f"No theme matches “{self.filter_query}”."
        else:
            subtitle_text = f"Create or copy themes into {THEMES_DIR}"
        subtitle = Gtk.Label(
            label=subtitle_text,
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
        card.set_size_request(292, 280)
        card.set_valign(Gtk.Align.START)

        preview_frame = Gtk.Frame()
        preview_frame.set_size_request(256, 144)
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

        path = Gtk.Label(label=relative_path_label(record.directory), xalign=0)
        path.set_ellipsize(Pango.EllipsizeMode.END)
        path.add_css_class("caption")
        path.add_css_class("dim-label")
        card.append(path)

        actions = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_top=4,
        )
        if self.on_set_current_theme is not None and not record.current:
            use_button = Gtk.Button(label="Use")
            use_button.set_sensitive(record.editable)
            use_button.set_tooltip_text("Set this theme as current")
            use_button.connect(
                "clicked",
                lambda *_args: self.on_set_current_theme(record),
            )
            actions.append(use_button)

        edit_button = Gtk.Button(label="Edit")
        edit_button.add_css_class("suggested-action")
        edit_button.set_hexpand(True)
        edit_button.set_sensitive(record.editable)
        edit_button.connect("clicked", lambda *_args: self.on_open_theme(record))
        actions.append(edit_button)

        if self.on_theme_diagnostics is not None:
            diagnostics_button = Gtk.Button(icon_name="dialog-information-symbolic")
            diagnostics_button.set_tooltip_text("Show theme diagnostics")
            diagnostics_button.connect(
                "clicked",
                lambda *_args: self.on_theme_diagnostics(record),
            )
            actions.append(diagnostics_button)

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
            on_theme_diagnostics=self.show_theme_diagnostics,
            on_set_current_theme=self.confirm_set_current_theme,
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
