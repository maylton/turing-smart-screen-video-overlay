#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime-safe launcher for the GTK video manager."""

from __future__ import annotations

import importlib.util
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


def install_runtime_patch(app):
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
            self.busy_status.set_label("Waiting for exclusive display access…")
            self.progress.set_visible(pulse_progress)
            if pulse_progress:
                self.progress.set_fraction(0)
                self.progress.set_text("Uploading…")
            self.content_stack.set_visible_child_name("busy")

        # Never bypass the backend's runtime lease. If main.py is running the
        # operation returns a clear busy error instead of racing for USB.
        command = [app.backend_python(), str(app.BACKEND), *arguments]

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

    app.VideoManagerWindow.run_backend = run_backend


def main() -> int:
    app = load_app_module()
    install_runtime_patch(app)
    return app.VideoManagerApplication().run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
