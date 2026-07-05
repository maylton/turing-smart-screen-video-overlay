#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Structured/runtime-safe launcher for the GTK video manager."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_MODULE = ROOT / "video_manager_gtk_app.py"


def load_app_module():
    spec = importlib.util.spec_from_file_location(
        "turing_video_manager_gtk_app", APP_MODULE
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {APP_MODULE.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def install_structured_backend(app):
    def populate_from_list_output(self, data):
        self.clear_video_list()
        files = data.get("files") if isinstance(data, dict) else []
        if not isinstance(files, list):
            files = []

        for filename in files:
            self.video_list.append(app.VideoRow(str(filename)))

        self.count_label.set_label(f"{len(files)} video(s)")
        self.content_stack.set_visible_child_name("main")
        if not files:
            self.selected_title.set_label("No videos found")
            self.selected_subtitle.set_label(
                "Upload a compatible MP4 video to start native playback."
            )
            self.size_row.set_subtitle("—")

    def update_size(self, data):
        if isinstance(data, dict):
            self.size_row.set_subtitle(data.get("human") or "Unknown")
        else:
            self.size_row.set_subtitle("Unknown")
        self.content_stack.set_visible_child_name("main")

    def start_upload(self, path):
        args = [
            "upload",
            str(path),
            "--remote",
            self.remote_path(path.name),
            "--overwrite",
        ]
        self.run_backend(
            args,
            title=f"Validating and uploading {path.name}",
            on_success=lambda _data: self.after_upload(path.name),
            pulse_progress=True,
        )

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
        if not app.BACKEND.is_file():
            self.toast("video_manager.py was not found")
            return

        if not quiet:
            self.busy = True
            self.busy_title.set_label(title)
            self.busy_status.set_label("Communicating with the display…")
            self.progress.set_visible(pulse_progress)
            if pulse_progress:
                self.progress.set_fraction(0)
                self.progress.set_text("Working…")
            self.content_stack.set_visible_child_name("busy")

        command = [
            app.backend_python(),
            str(app.BACKEND),
            "--json",
            *arguments,
        ]

        def worker():
            try:
                result = subprocess.run(
                    command,
                    cwd=str(app.ROOT),
                    text=True,
                    capture_output=True,
                    check=False,
                )
                app.GLib.idle_add(
                    self.finish_backend,
                    result.returncode,
                    result.stdout,
                    result.stderr,
                    on_success,
                    quiet,
                )
            except Exception as exc:
                app.GLib.idle_add(
                    self.finish_backend,
                    1,
                    "",
                    str(exc),
                    on_success,
                    quiet,
                )

        threading.Thread(target=worker, daemon=True).start()
        if pulse_progress and not quiet:
            app.GLib.timeout_add(120, self.pulse_upload)

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

        payload = None
        try:
            payload = json.loads((stdout or "").strip())
        except (json.JSONDecodeError, TypeError):
            pass

        if returncode != 0 or not isinstance(payload, dict) or not payload.get("ok"):
            if isinstance(payload, dict):
                error = payload.get("error") or {}
                message = error.get("message") or "Unknown error"
                probe = error.get("probe")
                if isinstance(probe, dict) and probe.get("issues"):
                    message += "\n\nRequired changes:\n• " + "\n• ".join(
                        str(issue) for issue in probe["issues"]
                    )
            else:
                message = (stderr or stdout or "Unknown error").strip()

            if quiet:
                self.size_row.set_subtitle("Unavailable")
                return False

            dialog = app.Adw.AlertDialog(
                heading="Operation failed",
                body=message[-2400:],
            )
            dialog.add_response("close", "Close")
            dialog.present(self.dialog_parent() if hasattr(self, 'dialog_parent') else self)
            self.content_stack.set_visible_child_name("main")
            return False

        on_success(payload.get("data") or {})
        return False

    app.VideoManagerWindow.populate_from_list_output = populate_from_list_output
    app.VideoManagerWindow.update_size = update_size
    app.VideoManagerWindow.start_upload = start_upload
    app.VideoManagerWindow.run_backend = run_backend
    app.VideoManagerWindow.finish_backend = finish_backend


def main() -> int:
    app = load_app_module()
    install_structured_backend(app)
    return app.VideoManagerApplication().run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
