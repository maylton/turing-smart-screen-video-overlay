#!/usr/bin/env python3
"""GTK4/Libadwaita media preparation workflow for native display video."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from library.media_preparation import cache_directory, safe_output_name

APP_ID = "io.github.turing.SmartScreen.MediaPreparation"
ROOT = Path(__file__).resolve().parent
MEDIA_BACKEND = ROOT / "media-preparation.py"
VIDEO_BACKEND = ROOT / "video_manager.py"


def backend_python() -> str:
    for candidate in (
        ROOT / "venv" / "bin" / "python3",
        ROOT / ".venv" / "bin" / "python3",
    ):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return sys.executable


def spin_row(title: str, lower: float, upper: float, step: float, digits: int = 0):
    row = Adw.ActionRow(title=title)
    adjustment = Gtk.Adjustment(
        value=0,
        lower=lower,
        upper=upper,
        step_increment=step,
        page_increment=step * 10,
    )
    spin = Gtk.SpinButton(adjustment=adjustment, digits=digits, numeric=True)
    spin.set_valign(Gtk.Align.CENTER)
    row.add_suffix(spin)
    row.set_activatable_widget(spin)
    return row, spin


class MediaPreparationWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(
            application=app,
            title="Prepare media",
            default_width=1180,
            default_height=760,
        )
        self.set_size_request(900, 620)
        self.source_path: Path | None = None
        self.source_duration = 0.0
        self.converted_path: Path | None = None
        self.preview_generation = 0
        self.preview_timeout = 0
        self.busy = False
        self.drag_origin = (0, 0)

        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)
        toolbar = Adw.ToolbarView()
        self.toast_overlay.set_child(toolbar)
        header = Adw.HeaderBar()
        header.set_title_widget(
            Adw.WindowTitle(
                title="Media preparation",
                subtitle="GIF and video → H.264 480×480 MP4",
            )
        )
        toolbar.add_top_bar(header)

        split = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        split.set_position(500)
        toolbar.set_content(split)
        split.set_start_child(self.build_controls())
        split.set_end_child(self.build_preview())

    def build_controls(self):
        scrolled = Gtk.ScrolledWindow(vexpand=True)
        clamp = Adw.Clamp(maximum_size=560)
        scrolled.set_child(clamp)
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=18,
            margin_top=18,
            margin_bottom=18,
            margin_start=18,
            margin_end=18,
        )
        clamp.set_child(box)

        source_group = Adw.PreferencesGroup(title="Source")
        self.source_row = Adw.ActionRow(
            title="GIF or video",
            subtitle="Choose GIF, MP4, MKV, WebM, MOV, or AVI",
            icon_name="video-x-generic-symbolic",
        )
        choose = Gtk.Button(label="Choose…", valign=Gtk.Align.CENTER)
        choose.connect("clicked", self.choose_source)
        self.source_row.add_suffix(choose)
        source_group.add(self.source_row)
        box.append(source_group)

        metadata = Adw.PreferencesGroup(title="Source information")
        self.codec_row = Adw.ActionRow(title="Codec", subtitle="—")
        self.dimensions_row = Adw.ActionRow(title="Dimensions", subtitle="—")
        self.duration_row = Adw.ActionRow(title="Duration", subtitle="—")
        self.framerate_row = Adw.ActionRow(title="Frame rate", subtitle="—")
        self.audio_row = Adw.ActionRow(title="Audio", subtitle="—")
        for row in (
            self.codec_row,
            self.dimensions_row,
            self.duration_row,
            self.framerate_row,
            self.audio_row,
        ):
            metadata.add(row)
        box.append(metadata)

        framing = Adw.PreferencesGroup(title="Framing")
        self.mode_row = Adw.ComboRow(title="Mode")
        self.mode_row.set_model(Gtk.StringList.new(["Fit", "Fill / Cover", "Stretch"]))
        self.mode_row.set_selected(0)
        self.mode_row.connect("notify::selected", lambda *_: self.schedule_preview())
        framing.add(self.mode_row)

        zoom_row, self.zoom = spin_row("Zoom", 0.25, 4.0, 0.05, 2)
        self.zoom.set_value(1.0)
        self.zoom.connect("value-changed", lambda *_: self.schedule_preview())
        framing.add(zoom_row)

        x_row, self.offset_x = spin_row("Horizontal position", -960, 960, 1)
        y_row, self.offset_y = spin_row("Vertical position", -960, 960, 1)
        self.offset_x.connect("value-changed", lambda *_: self.schedule_preview())
        self.offset_y.connect("value-changed", lambda *_: self.schedule_preview())
        framing.add(x_row)
        framing.add(y_row)

        center = Gtk.Button(label="Center media", icon_name="object-select-symbolic")
        center.connect("clicked", self.center_media)
        framing.add(center)
        box.append(framing)

        timing = Adw.PreferencesGroup(title="Timing and output")
        start_row, self.trim_start = spin_row("Trim start (seconds)", 0, 86400, 0.1, 2)
        end_row, self.trim_end = spin_row("Trim end (seconds)", 0, 86400, 0.1, 2)
        self.trim_start.connect("value-changed", lambda *_: self.schedule_preview())
        self.trim_end.connect("value-changed", lambda *_: self.schedule_preview())
        timing.add(start_row)
        timing.add(end_row)

        self.fps_row = Adw.ComboRow(title="Output frame rate")
        self.fps_row.set_model(Gtk.StringList.new(["24 FPS", "30 FPS"]))
        self.fps_row.set_selected(1)
        self.fps_row.connect("notify::selected", lambda *_: self.schedule_preview())
        timing.add(self.fps_row)

        output_row = Adw.ActionRow(title="Output filename")
        self.output_name = Gtk.Entry(hexpand=True, valign=Gtk.Align.CENTER)
        self.output_name.set_placeholder_text("prepared-video.mp4")
        output_row.add_suffix(self.output_name)
        timing.add(output_row)

        self.storage_row = Adw.ComboRow(title="Upload destination")
        self.storage_row.set_model(Gtk.StringList.new(["SD card", "Internal storage"]))
        self.storage_row.set_selected(0)
        timing.add(self.storage_row)
        box.append(timing)
        return scrolled

    def build_preview(self):
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=14,
            margin_top=22,
            margin_bottom=22,
            margin_start=22,
            margin_end=22,
        )
        title = Gtk.Label(label="Framing preview", xalign=0)
        title.add_css_class("title-2")
        box.append(title)

        self.preview_frame = Gtk.Frame(hexpand=True, vexpand=True)
        self.preview_frame.set_size_request(480, 480)
        self.preview_picture = Gtk.Picture(can_shrink=True)
        self.preview_picture.set_size_request(480, 480)
        self.preview_frame.set_child(self.preview_picture)
        box.append(self.preview_frame)

        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self.on_drag_begin)
        drag.connect("drag-update", self.on_drag_update)
        drag.connect("drag-end", lambda *_: self.schedule_preview())
        self.preview_picture.add_controller(drag)

        self.status = Gtk.Label(
            label="Choose media to begin.",
            wrap=True,
            justify=Gtk.Justification.CENTER,
        )
        self.status.add_css_class("dim-label")
        box.append(self.status)

        self.progress = Gtk.ProgressBar(show_text=True)
        self.progress.set_visible(False)
        box.append(self.progress)

        actions = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10,
            homogeneous=True,
        )
        self.convert_button = Gtk.Button(
            label="Convert",
            icon_name="media-record-symbolic",
            sensitive=False,
        )
        self.convert_button.add_css_class("suggested-action")
        self.convert_button.connect("clicked", self.convert_source)
        actions.append(self.convert_button)

        self.preview_button = Gtk.Button(
            label="Preview output",
            icon_name="media-playback-start-symbolic",
            sensitive=False,
        )
        self.preview_button.connect("clicked", self.preview_output)
        actions.append(self.preview_button)

        self.upload_button = Gtk.Button(
            label="Upload",
            icon_name="document-send-symbolic",
            sensitive=False,
        )
        self.upload_button.connect("clicked", self.upload_output)
        actions.append(self.upload_button)
        box.append(actions)
        return box

    def choose_source(self, _button):
        dialog = Gtk.FileDialog(title="Choose GIF or video", modal=True)
        media_filter = Gtk.FileFilter()
        media_filter.set_name("GIF and video files")
        for pattern in ("*.gif", "*.mp4", "*.mkv", "*.webm", "*.mov", "*.avi"):
            media_filter.add_pattern(pattern)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(media_filter)
        dialog.set_filters(filters)
        dialog.open(self, None, self.on_source_chosen)

    def on_source_chosen(self, dialog, result):
        try:
            file = dialog.open_finish(result)
        except GLib.Error:
            return
        path = Path(file.get_path())
        if not path.is_file():
            self.toast("The selected file is not available locally")
            return
        self.source_path = path
        self.converted_path = None
        self.preview_button.set_sensitive(False)
        self.upload_button.set_sensitive(False)
        self.source_row.set_subtitle(path.name)
        self.output_name.set_text(safe_output_name(path.name))
        self.run_json(
            MEDIA_BACKEND,
            ["probe", str(path)],
            "Analyzing source…",
            self.on_probe_complete,
        )

    def on_probe_complete(self, data):
        self.source_duration = float(data.get("duration") or 0)
        self.codec_row.set_subtitle(str(data.get("codec") or "Unknown"))
        self.dimensions_row.set_subtitle(
            f"{data.get('width', 0)} × {data.get('height', 0)}"
        )
        self.duration_row.set_subtitle(f"{self.source_duration:.2f} seconds")
        fps = data.get("fps")
        self.framerate_row.set_subtitle(f"{fps:.2f} FPS" if fps else "Unknown")
        self.audio_row.set_subtitle("Present" if data.get("has_audio") else "None")
        self.trim_start.set_range(0, max(0.0, self.source_duration - 0.01))
        self.trim_end.set_range(0.01, max(0.01, self.source_duration))
        self.trim_start.set_value(0)
        self.trim_end.set_value(self.source_duration)
        self.convert_button.set_sensitive(True)
        self.status.set_label("Adjust framing or drag the preview to reposition media.")
        self.schedule_preview()

    def selected_mode(self) -> str:
        return ("fit", "fill", "stretch")[self.mode_row.get_selected()]

    def selected_fps(self) -> int:
        return (24, 30)[self.fps_row.get_selected()]

    def settings_args(self) -> list[str]:
        args = [
            "--mode", self.selected_mode(),
            "--zoom", f"{self.zoom.get_value():.3f}",
            "--x", str(int(self.offset_x.get_value())),
            "--y", str(int(self.offset_y.get_value())),
            "--start", f"{self.trim_start.get_value():.3f}",
            "--fps", str(self.selected_fps()),
            "--background", "000000",
        ]
        end = self.trim_end.get_value()
        if end > self.trim_start.get_value():
            args.extend(["--end", f"{end:.3f}"])
        return args

    def center_media(self, _button):
        self.offset_x.set_value(0)
        self.offset_y.set_value(0)
        self.schedule_preview()

    def on_drag_begin(self, _gesture, _x, _y):
        self.drag_origin = (
            int(self.offset_x.get_value()),
            int(self.offset_y.get_value()),
        )

    def on_drag_update(self, _gesture, delta_x, delta_y):
        width = max(1, self.preview_picture.get_allocated_width())
        height = max(1, self.preview_picture.get_allocated_height())
        scale_x = 480 / width
        scale_y = 480 / height
        self.offset_x.set_value(self.drag_origin[0] + delta_x * scale_x)
        self.offset_y.set_value(self.drag_origin[1] + delta_y * scale_y)

    def schedule_preview(self):
        if not self.source_path:
            return
        if self.preview_timeout:
            GLib.source_remove(self.preview_timeout)
        self.preview_timeout = GLib.timeout_add(320, self.start_preview)

    def start_preview(self):
        self.preview_timeout = 0
        if not self.source_path:
            return False
        self.preview_generation += 1
        generation = self.preview_generation
        output = cache_directory() / f"preview-{os.getpid()}.png"
        self.run_json(
            MEDIA_BACKEND,
            [
                "preview",
                str(self.source_path),
                "--output",
                str(output),
                *self.settings_args(),
            ],
            "Rendering preview…",
            lambda data: self.on_preview_complete(data, generation),
            quiet=True,
        )
        return False

    def on_preview_complete(self, data, generation):
        if generation != self.preview_generation:
            return
        output = Path(data["output"])
        if output.is_file():
            self.preview_picture.set_filename(str(output))

    def convert_source(self, _button):
        if not self.source_path:
            return
        name = safe_output_name(self.output_name.get_text() or self.source_path.name)
        self.output_name.set_text(name)
        output = cache_directory() / name
        self.run_json(
            MEDIA_BACKEND,
            [
                "convert",
                str(self.source_path),
                "--output",
                str(output),
                *self.settings_args(),
            ],
            "Converting media…",
            self.on_conversion_complete,
            pulse=True,
        )

    def on_conversion_complete(self, data):
        self.converted_path = Path(data["path"])
        self.preview_button.set_sensitive(True)
        self.upload_button.set_sensitive(True)
        output = data.get("output") or {}
        size = int(output.get("size_bytes") or 0)
        self.status.set_label(
            f"Prepared {self.converted_path.name} — {size / 1024:.1f} KiB"
        )
        self.toast("Conversion completed")

    def preview_output(self, _button):
        if not self.converted_path or not self.converted_path.is_file():
            self.toast("Convert the media first")
            return
        window = Gtk.Window(
            title=f"Preview — {self.converted_path.name}",
            transient_for=self,
            modal=True,
            default_width=560,
            default_height=620,
        )
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
        )
        video = Gtk.Video.new_for_filename(str(self.converted_path))
        video.set_autoplay(True)
        video.set_loop(True)
        video.set_vexpand(True)
        box.append(video)
        close = Gtk.Button(label="Close")
        close.connect("clicked", lambda *_: window.close())
        box.append(close)
        window.set_child(box)
        window.present()

    def upload_output(self, _button):
        if not self.converted_path or not self.converted_path.is_file():
            self.toast("Convert the media first")
            return
        root = "/root/video/" if self.storage_row.get_selected() == 1 else "/mnt/SDCARD/video/"
        remote = root + safe_output_name(self.converted_path.name)
        self.run_json(
            VIDEO_BACKEND,
            [
                "upload",
                str(self.converted_path),
                "--remote",
                remote,
                "--overwrite",
            ],
            "Uploading prepared video…",
            lambda _data: self.on_upload_complete(remote),
            pulse=True,
        )

    def on_upload_complete(self, remote):
        self.status.set_label(f"Upload complete: {remote}")
        self.toast("Prepared video uploaded")

    def run_json(self, program, arguments, title, on_success, quiet=False, pulse=False):
        if self.busy and not quiet:
            self.toast("Another operation is already running")
            return
        if not Path(program).is_file():
            self.show_error(f"Required backend was not found: {program}")
            return
        if not quiet:
            self.busy = True
            self.status.set_label(title)
            self.progress.set_visible(pulse)
            if pulse:
                self.progress.set_text("Working…")
                self.progress.pulse()
        command = [backend_python(), str(program), "--json", *arguments]

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
                    self.finish_json,
                    result.returncode,
                    result.stdout,
                    result.stderr,
                    on_success,
                    quiet,
                )
            except Exception as exc:
                GLib.idle_add(
                    self.finish_json,
                    1,
                    "",
                    str(exc),
                    on_success,
                    quiet,
                )

        threading.Thread(target=worker, daemon=True).start()
        if pulse and not quiet:
            GLib.timeout_add(120, self.pulse_progress)

    def pulse_progress(self):
        if not self.busy or not self.progress.get_visible():
            return False
        self.progress.pulse()
        return True

    def finish_json(self, returncode, stdout, stderr, on_success, quiet):
        if not quiet:
            self.busy = False
            self.progress.set_visible(False)
        try:
            payload = json.loads((stdout or "").strip())
        except (json.JSONDecodeError, TypeError):
            payload = None
        if returncode != 0 or not isinstance(payload, dict) or not payload.get("ok"):
            if quiet:
                return False
            if isinstance(payload, dict):
                error = payload.get("error") or {}
                message = error.get("message") or "Unknown media error"
                details = error.get("stderr")
                if details:
                    message += "\n\n" + str(details)[-1800:]
            else:
                message = (stderr or stdout or "Unknown media error").strip()
            self.show_error(message)
            return False
        on_success(payload.get("data") or {})
        return False

    def show_error(self, message):
        dialog = Adw.AlertDialog(heading="Operation failed", body=str(message)[-2400:])
        dialog.add_response("close", "Close")
        dialog.present(self)

    def toast(self, text):
        self.toast_overlay.add_toast(Adw.Toast(title=text, timeout=3))


class MediaPreparationApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_activate(self):
        window = self.props.active_window
        if window is None:
            window = MediaPreparationWindow(self)
        window.present()
