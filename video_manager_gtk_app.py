#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""GTK4 + Libadwaita video manager for Turing Smart Screen Rev. C."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

APP_ID = "io.github.turing.SmartScreen.VideoManager"
ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "video_manager.py"
MEDIA_PREPARATION = ROOT / "media-preparation-gtk.py"


def backend_python() -> str:
    for candidate in (
        ROOT / "venv" / "bin" / "python3",
        ROOT / ".venv" / "bin" / "python3",
    ):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return sys.executable


class VideoRow(Gtk.ListBoxRow):
    def __init__(self, filename: str, size_text: str = ""):
        super().__init__()
        self.filename = filename
        row = Adw.ActionRow(
            title=filename,
            subtitle=size_text,
            icon_name="video-x-generic-symbolic",
        )
        row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
        self.set_child(row)


class VideoManagerWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(
            application=app,
            title="Turing Video Manager",
            default_width=1120,
            default_height=720,
        )
        self.set_size_request(900, 600)

        self.selected_file: str | None = None
        self.storage_internal = False
        self.busy = False

        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        toolbar = Adw.ToolbarView()
        self.toast_overlay.set_child(toolbar)

        header = Adw.HeaderBar()
        header.set_title_widget(
            Adw.WindowTitle(
                title="Video Manager",
                subtitle="Turing Smart Screen Rev. C",
            )
        )
        toolbar.add_top_bar(header)

        refresh_button = Gtk.Button(
            icon_name="view-refresh-symbolic",
            tooltip_text="Refresh video list",
        )
        refresh_button.connect("clicked", lambda *_: self.refresh_videos())
        header.pack_start(refresh_button)

        stop_button = Gtk.Button(
            icon_name="media-playback-stop-symbolic",
            tooltip_text="Stop current video",
        )
        stop_button.connect("clicked", lambda *_: self.stop_video())
        header.pack_end(stop_button)

        self.content_stack = Gtk.Stack()
        self.content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        toolbar.set_content(self.content_stack)

        self.main_page = self.build_main_page()
        self.content_stack.add_named(self.main_page, "main")

        self.busy_page = self.build_busy_page()
        self.content_stack.add_named(self.busy_page, "busy")

        self.refresh_videos()

    def dialog_parent(self):
        """Return the visible parent for dialogs.

        In standalone mode, dialogs can be parented to the VideoManagerWindow.
        In embedded mode, the window object is only used as an integration
        shell while its content lives inside the main app. Dialogs and file
        choosers must then be parented to the visible main window/root.
        """
        embedded_parent = getattr(self, "_embedded_dialog_parent", None)
        if embedded_parent is not None:
            root = embedded_parent.get_root()
            if root is not None:
                return root
            return embedded_parent
        return self

    def build_main_page(self):
        split = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        split.set_position(500)
        split.set_shrink_start_child(False)
        split.set_shrink_end_child(False)

        left_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
            margin_top=18,
            margin_bottom=18,
            margin_start=18,
            margin_end=18,
        )
        left_box.set_size_request(460, -1)

        storage_row = Adw.ComboRow(title="Storage")
        storage_row.set_model(
            Gtk.StringList.new(["SD card", "Internal storage"])
        )
        storage_row.set_selected(0)
        storage_row.connect("notify::selected", self.on_storage_changed)
        left_box.append(storage_row)

        list_heading = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )
        title = Gtk.Label(label="Videos on display", xalign=0)
        title.add_css_class("heading")
        title.set_hexpand(True)
        list_heading.append(title)

        self.count_label = Gtk.Label(label="")
        self.count_label.add_css_class("dim-label")
        list_heading.append(self.count_label)
        left_box.append(list_heading)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)

        self.video_list = Gtk.ListBox(
            selection_mode=Gtk.SelectionMode.SINGLE,
        )
        self.video_list.add_css_class("boxed-list")
        self.video_list.connect("row-selected", self.on_video_selected)
        scrolled.set_child(self.video_list)
        left_box.append(scrolled)

        prepare_button = Gtk.Button(
            label="Import and prepare media…",
            icon_name="applications-multimedia-symbolic",
        )
        prepare_button.add_css_class("suggested-action")
        prepare_button.connect("clicked", self.open_media_preparation)
        left_box.append(prepare_button)

        upload_button = Gtk.Button(
            label="Upload compatible MP4…",
            icon_name="document-send-symbolic",
        )
        upload_button.connect("clicked", self.choose_upload)
        left_box.append(upload_button)

        split.set_start_child(left_box)

        right_clamp = Adw.Clamp(maximum_size=640)
        right_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=18,
            margin_top=32,
            margin_bottom=32,
            margin_start=28,
            margin_end=28,
        )
        right_clamp.set_child(right_box)

        icon = Gtk.Image.new_from_icon_name("video-x-generic-symbolic")
        icon.set_pixel_size(96)
        right_box.append(icon)

        self.selected_title = Gtk.Label(
            label="Select a video",
            xalign=0.5,
            wrap=True,
        )
        self.selected_title.add_css_class("title-2")
        right_box.append(self.selected_title)

        self.selected_subtitle = Gtk.Label(
            label="Choose a file from the list to play or remove it.",
            xalign=0.5,
            wrap=True,
            justify=Gtk.Justification.CENTER,
        )
        self.selected_subtitle.add_css_class("dim-label")
        right_box.append(self.selected_subtitle)

        action_group = Adw.PreferencesGroup(title="Actions")
        play_row = Adw.ActionRow(
            title="Play video",
            subtitle="Start playback on the display",
            icon_name="media-playback-start-symbolic",
            activatable=True,
        )
        play_row.connect("activated", lambda *_: self.play_selected())
        play_row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
        action_group.add(play_row)

        delete_row = Adw.ActionRow(
            title="Delete video",
            subtitle="Remove the selected file from storage",
            icon_name="user-trash-symbolic",
            activatable=True,
        )
        delete_row.connect("activated", lambda *_: self.delete_selected())
        delete_row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
        action_group.add(delete_row)

        self.size_row = Adw.ActionRow(
            title="File size",
            subtitle="Select a video",
            icon_name="document-properties-symbolic",
        )
        action_group.add(self.size_row)

        right_box.append(action_group)

        note = Adw.Banner(
            title="Stop main.py before uploads to avoid two processes using the display."
        )
        note.set_revealed(True)
        right_box.append(note)

        split.set_end_child(right_clamp)
        return split

    def build_busy_page(self):
        clamp = Adw.Clamp(maximum_size=520)
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=18,
            valign=Gtk.Align.CENTER,
            margin_top=40,
            margin_bottom=40,
            margin_start=30,
            margin_end=30,
        )
        clamp.set_child(box)

        self.busy_spinner = Gtk.Spinner(spinning=True)
        self.busy_spinner.set_size_request(64, 64)
        box.append(self.busy_spinner)

        self.busy_title = Gtk.Label(label="Working…")
        self.busy_title.add_css_class("title-2")
        box.append(self.busy_title)

        self.busy_status = Gtk.Label(
            label="Please wait",
            wrap=True,
            justify=Gtk.Justification.CENTER,
        )
        self.busy_status.add_css_class("dim-label")
        box.append(self.busy_status)

        self.progress = Gtk.ProgressBar(show_text=True)
        self.progress.set_visible(False)
        box.append(self.progress)

        cancel = Gtk.Button(label="Return to video list")
        cancel.connect(
            "clicked",
            lambda *_: self.content_stack.set_visible_child_name("main"),
        )
        box.append(cancel)
        return clamp

    def remote_directory(self):
        return "/root/video/" if self.storage_internal else "/mnt/SDCARD/video/"

    def remote_path(self, filename):
        return self.remote_directory() + filename

    def on_storage_changed(self, row, _param):
        self.storage_internal = row.get_selected() == 1
        self.selected_file = None
        self.refresh_videos()

    def clear_video_list(self):
        while True:
            row = self.video_list.get_row_at_index(0)
            if row is None:
                break
            self.video_list.remove(row)

    def refresh_videos(self):
        args = ["list"]
        if self.storage_internal:
            args.append("--internal")

        self.run_backend(
            args,
            title="Loading videos",
            on_success=self.populate_from_list_output,
        )

    def populate_from_list_output(self, output):
        self.clear_video_list()

        match = re.search(r"Arquivos:\s*(.*)", output)
        raw = match.group(1).strip() if match else ""
        if raw in ("", "(nenhum)"):
            files = []
        else:
            try:
                # CLI prints Python list representation.
                import ast
                files = ast.literal_eval(raw)
            except Exception:
                files = [part.strip() for part in raw.split("/") if part.strip()]

        for filename in files:
            self.video_list.append(VideoRow(str(filename)))

        self.count_label.set_label(f"{len(files)} video(s)")
        self.content_stack.set_visible_child_name("main")

        if not files:
            self.selected_title.set_label("No videos found")
            self.selected_subtitle.set_label(
                "Upload an MP4 video to start using native playback."
            )
            self.size_row.set_subtitle("—")

    def on_video_selected(self, _listbox, row):
        if row is None or not hasattr(row, "filename"):
            self.selected_file = None
            return

        self.selected_file = row.filename
        self.selected_title.set_label(row.filename)
        self.selected_subtitle.set_label(self.remote_path(row.filename))
        self.query_selected_size()

    def query_selected_size(self):
        if not self.selected_file:
            return
        self.run_backend(
            ["size", self.remote_path(self.selected_file)],
            title="Reading file information",
            on_success=self.update_size,
            quiet=True,
        )

    def update_size(self, output):
        self.size_row.set_subtitle(output.strip() or "Unknown")
        self.content_stack.set_visible_child_name("main")

    def play_selected(self):
        if not self.selected_file:
            self.toast("Select a video first")
            return
        self.run_backend(
            ["play", self.remote_path(self.selected_file)],
            title="Starting video",
            on_success=lambda _out: self.finish_action(
                f"Playing {self.selected_file}"
            ),
        )

    def stop_video(self):
        self.run_backend(
            ["stop"],
            title="Stopping video",
            on_success=lambda _out: self.finish_action("Video stopped"),
        )

    def delete_selected(self):
        if not self.selected_file:
            self.toast("Select a video first")
            return

        dialog = Adw.AlertDialog(
            heading="Delete video?",
            body=f"{self.selected_file} will be permanently removed from the display.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance(
            "delete",
            Adw.ResponseAppearance.DESTRUCTIVE,
        )
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self.on_delete_response)
        dialog.present(self.dialog_parent())

    def on_delete_response(self, _dialog, response):
        if response != "delete" or not self.selected_file:
            return

        filename = self.selected_file
        self.run_backend(
            ["delete", self.remote_path(filename)],
            title="Deleting video",
            on_success=lambda _out: self.after_delete(filename),
        )

    def after_delete(self, filename):
        self.toast(f"Deleted {filename}")
        self.selected_file = None
        self.refresh_videos()

    def open_media_preparation(self, _button):
        if not MEDIA_PREPARATION.is_file():
            self.toast("Media preparation editor was not found")
            return
        try:
            subprocess.Popen(
                [sys.executable, str(MEDIA_PREPARATION)],
                cwd=str(ROOT),
                start_new_session=True,
            )
        except Exception as exc:
            dialog = Adw.AlertDialog(
                heading="Could not open media preparation",
                body=str(exc),
            )
            dialog.add_response("close", "Close")
            dialog.present(self.dialog_parent())

    def choose_upload(self, _button):
        dialog = Gtk.FileDialog(
            title="Choose a video",
            modal=True,
        )
        video_filter = Gtk.FileFilter()
        video_filter.set_name("Video files")
        for mime in (
            "video/mp4",
            "video/x-matroska",
            "video/webm",
            "video/quicktime",
        ):
            video_filter.add_mime_type(mime)

        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(video_filter)
        dialog.set_filters(filters)
        dialog.open(self.dialog_parent(), None, self.on_upload_file_chosen)

    def on_upload_file_chosen(self, dialog, result):
        try:
            file = dialog.open_finish(result)
        except GLib.Error:
            return

        path = Path(file.get_path())
        if not path.is_file():
            self.toast("The selected file is not available locally")
            return

        confirm = Adw.AlertDialog(
            heading="Upload video?",
            body=(
                f"{path.name}\n\n"
                f"Destination: {self.remote_path(path.name)}\n\n"
                "An existing file with the same name will be replaced."
            ),
        )
        confirm.add_response("cancel", "Cancel")
        confirm.add_response("upload", "Upload")
        confirm.set_response_appearance(
            "upload",
            Adw.ResponseAppearance.SUGGESTED,
        )
        confirm.set_default_response("upload")
        confirm.set_close_response("cancel")
        confirm.connect(
            "response",
            lambda _dialog, response: self.start_upload(path)
            if response == "upload"
            else None,
        )
        confirm.present(self.dialog_parent())

    def start_upload(self, path):
        args = [
            "upload",
            str(path),
            "--remote",
            self.remote_path(path.name),
            "--overwrite",
            "--skip-probe",
        ]
        self.run_backend(
            args,
            title=f"Uploading {path.name}",
            on_success=lambda _out: self.after_upload(path.name),
            pulse_progress=True,
        )

    def after_upload(self, filename):
        self.toast(f"Upload complete: {filename}")
        self.refresh_videos()

    def finish_action(self, message):
        self.toast(message)
        self.content_stack.set_visible_child_name("main")

    def run_backend(
        self,
        arguments,
        title,
        on_success,
        quiet=False,
        pulse_progress=False,
    ):
        if self.busy and not quiet:
            self.toast("Another operation is already running")
            return

        if not BACKEND.is_file():
            self.toast("video_manager.py was not found")
            return

        if not quiet:
            self.busy = True
            self.busy_title.set_label(title)
            self.busy_status.set_label("Communicating with the display…")
            self.progress.set_visible(pulse_progress)
            if pulse_progress:
                self.progress.set_fraction(0)
                self.progress.set_text("Uploading…")
            self.content_stack.set_visible_child_name("busy")

        command = [backend_python(), str(BACKEND), "--force", *arguments]

        def worker():
            try:
                result = subprocess.run(
                    command,
                    cwd=str(ROOT),
                    text=True,
                    capture_output=True,
                    check=False,
                )
                GLib.idle_add(
                    self.finish_backend,
                    result.returncode,
                    result.stdout,
                    result.stderr,
                    on_success,
                    quiet,
                )
            except Exception as exc:
                GLib.idle_add(
                    self.finish_backend,
                    1,
                    "",
                    str(exc),
                    on_success,
                    quiet,
                )

        import threading
        threading.Thread(target=worker, daemon=True).start()

        if pulse_progress and not quiet:
            GLib.timeout_add(120, self.pulse_upload)

    def pulse_upload(self):
        if not self.busy or not self.progress.get_visible():
            return False
        self.progress.pulse()
        return True

    def finish_backend(
        self,
        returncode,
        stdout,
        stderr,
        on_success,
        quiet,
    ):
        if not quiet:
            self.busy = False
            self.progress.set_visible(False)

        if returncode != 0:
            message = (stderr or stdout or "Unknown error").strip()
            dialog = Adw.AlertDialog(
                heading="Operation failed",
                body=message[-1800:],
            )
            dialog.add_response("close", "Close")
            dialog.present(self.dialog_parent())
            if not quiet:
                self.content_stack.set_visible_child_name("main")
            return False

        on_success(stdout)
        return False

    def toast(self, text):
        self.toast_overlay.add_toast(
            Adw.Toast(title=text, timeout=3)
        )


class VideoManagerApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

    def do_activate(self):
        window = self.props.active_window
        if window is None:
            window = VideoManagerWindow(self)
        window.present()


if __name__ == "__main__":
    raise SystemExit(VideoManagerApplication().run(sys.argv))
