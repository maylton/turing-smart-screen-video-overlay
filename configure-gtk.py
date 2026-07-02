#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime-stable launcher for the GTK4 configuration application.

The visual application remains in ``configure_gtk_app.py``. This launcher
adds process discovery, explicit autostart, and non-blocking stop operations
without duplicating the large GTK interface.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import threading
from pathlib import Path

from library.runtime import DeviceBusyError, MonitorController

ROOT = Path(__file__).resolve().parent
APP_MODULE = ROOT / "configure_gtk_app.py"
START_MONITOR_FILE = (
    Path.home()
    / ".config"
    / "turing-smart-screen"
    / "start-monitor.conf"
)


def load_boolean(path: Path, default: bool = False) -> bool:
    try:
        value = path.read_text(encoding="utf-8").strip().lower()
    except OSError:
        return default
    return value in {"1", "true", "yes", "on"}


def save_boolean(path: Path, enabled: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("true\n" if enabled else "false\n", encoding="utf-8")
    os.replace(temporary, path)


def load_app_module():
    spec = importlib.util.spec_from_file_location(
        "turing_smart_screen_gtk_app", APP_MODULE
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {APP_MODULE.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def install_runtime_patches(app):
    original_init = app.SmartScreenWindow.__init__
    original_refresh_overview = app.SmartScreenWindow.refresh_overview

    def reap_monitor_child(self, timeout=2.0):
        """Collect a monitor process started by this GTK application."""
        process = (
            self.monitor_process
            if self.monitor_process is not None
            else self.runtime_controller.child
        )
        if process is None:
            return False

        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return False
        except (ChildProcessError, OSError):
            if process.poll() is None:
                return False

        if self.runtime_controller.child is process:
            self.runtime_controller.child = None
        return True

    def patched_init(self, application):
        self.runtime_controller = MonitorController(
            root=app.ROOT,
            main_program=app.MAIN_PROGRAM,
            python_executable=app.project_python(),
        )
        self.runtime_stop_in_progress = False
        original_init(self, application)
        app.GLib.timeout_add_seconds(2, self.refresh_runtime_status)

    def update_runtime_status(self):
        state = self.runtime_controller.state()
        if state.monitor_running:
            owner = state.owner
            subtitle = (
                f"Running (PID {owner.pid})" if owner.pid else "Running"
            )
        elif state.busy:
            subtitle = "Device busy: " + state.owner.describe()
        else:
            subtitle = "Stopped"
        self.process_status_row.set_subtitle(subtitle)
        return state

    def refresh_runtime_status(self):
        update_runtime_status(self)
        return True

    def patched_refresh_overview(self):
        original_refresh_overview(self)
        if self.current_theme:
            self.theme_path_label.set_label(
                str(app.THEMES_DIR / self.current_theme)
            )
        else:
            self.theme_path_label.set_label("")
        update_runtime_status(self)

    def build_settings_page(self):
        clamp = app.Adw.Clamp(maximum_size=760)
        scrolled = app.Gtk.ScrolledWindow()
        scrolled.set_child(clamp)

        box = app.Gtk.Box(
            orientation=app.Gtk.Orientation.VERTICAL,
            spacing=18,
            margin_top=28,
            margin_bottom=28,
            margin_start=24,
            margin_end=24,
        )
        clamp.set_child(box)

        title = app.Gtk.Label(label="Settings", xalign=0)
        title.add_css_class("title-1")
        box.append(title)

        appearance = app.Adw.PreferencesGroup(
            title="Appearance",
            description=(
                "Choose the application appearance. The selection is saved "
                "for the next session."
            ),
        )
        self.style_row = app.Adw.ComboRow(title="Color scheme")
        self.style_row.set_model(
            app.Gtk.StringList.new(["Follow system", "Light", "Dark"])
        )
        self.style_row.set_selected(
            {"system": 0, "light": 1, "dark": 2}.get(
                self.saved_color_scheme, 0
            )
        )
        self.style_row.connect(
            "notify::selected", self.on_color_scheme_changed
        )
        appearance.add(self.style_row)

        self.start_minimized_row = app.Adw.SwitchRow(
            title="Start application minimized to tray",
            subtitle=(
                "Controls only the GTK window. It does not start the display "
                "monitor."
            ),
        )
        self.start_minimized_row.set_active(app.load_start_minimized())
        self.start_minimized_row.connect(
            "notify::active", self.on_start_minimized_changed
        )
        appearance.add(self.start_minimized_row)
        box.append(appearance)

        runtime_group = app.Adw.PreferencesGroup(
            title="Runtime",
            description=(
                "The monitor owns the display connection exclusively while it "
                "is running."
            ),
        )
        self.start_monitor_row = app.Adw.SwitchRow(
            title="Start monitor automatically",
            subtitle=(
                "Start main.py when this application opens. Keep this disabled "
                "to start the monitor manually."
            ),
        )
        self.start_monitor_row.set_active(
            load_boolean(START_MONITOR_FILE, default=False)
        )
        self.start_monitor_row.connect(
            "notify::active", self.on_start_monitor_changed
        )
        runtime_group.add(self.start_monitor_row)
        box.append(runtime_group)

        maintenance = app.Adw.PreferencesGroup(
            title="Maintenance",
            description=(
                "Verify GTK, Python dependencies, project files, and theme "
                "YAML files."
            ),
        )
        checkup_row = app.Adw.ActionRow(
            title="Program check",
            subtitle=(
                "Verify dependencies, project files, themes, and Python syntax"
            ),
            icon_name="emblem-ok-symbolic",
            activatable=True,
        )
        checkup_row.connect("activated", lambda *_: self.run_checkup())
        checkup_row.add_suffix(
            app.Gtk.Image.new_from_icon_name("go-next-symbolic")
        )
        maintenance.add(checkup_row)
        box.append(maintenance)
        return scrolled

    def on_start_monitor_changed(self, row, _param):
        enabled = row.get_active()
        try:
            save_boolean(START_MONITOR_FILE, enabled)
        except Exception as exc:
            self.toast(f"Could not save monitor startup preference: {exc}")
            return
        self.toast(
            "Monitor will start with the application"
            if enabled
            else "Monitor will be started manually"
        )

    def auto_apply_last_theme(self):
        if not load_boolean(START_MONITOR_FILE, default=False):
            return False
        if not app.read_current_theme():
            self.toast("No saved theme to start automatically")
            return False
        start_monitor(self)
        return False

    def start_monitor(self, *_args):
        state = self.runtime_controller.state()
        if state.busy:
            if state.monitor_running:
                self.toast("Monitor is already running")
            else:
                self.toast("Display is busy: " + state.owner.describe())
            update_runtime_status(self)
            return

        monitor_env = os.environ.copy()
        monitor_env["TURING_DISABLE_PYSTRAY"] = "1"
        try:
            self.monitor_process = self.runtime_controller.start(
                env=monitor_env
            )
        except DeviceBusyError as exc:
            self.toast("Display is busy: " + exc.owner.describe())
            return
        except Exception as exc:
            self.toast(f"Could not start monitor: {exc}")
            return

        self.toast("Monitor is starting")
        app.GLib.timeout_add(350, self.finish_monitor_start)

    def finish_monitor_start(self):
        process = self.monitor_process
        if process is not None and process.poll() is not None:
            self.toast(f"Monitor exited with status {process.returncode}")
            reap_monitor_child(self, timeout=0.0)
            self.monitor_process = None
        self.refresh_overview()
        return False

    def stop_monitor(self, *_args):
        if self.runtime_stop_in_progress:
            self.toast("Monitor stop is already in progress")
            return

        state = self.runtime_controller.state()
        if not state.busy:
            self.toast("Monitor is not running")
            return
        if not state.monitor_running:
            self.toast("Display is busy: " + state.owner.describe())
            return

        self.runtime_stop_in_progress = True
        self.toast("Stopping monitor…")

        def worker():
            try:
                result = self.runtime_controller.terminate_monitor()
                reap_monitor_child(self)
                error = ""
            except Exception as exc:
                result = None
                error = str(exc)
            app.GLib.idle_add(self.finish_monitor_stop, result, error)

        threading.Thread(target=worker, daemon=True).start()

    def finish_monitor_stop(self, result, error):
        self.runtime_stop_in_progress = False
        self.monitor_process = None
        self.refresh_overview()
        if error:
            self.toast(f"Could not stop monitor: {error}")
        elif result is not None:
            self.toast(result.message or "Monitor stopped")
        return False

    def turn_off_display(self, *_args):
        if not app.SCREEN_CONTROL.is_file():
            self.toast("screen-control.py was not found")
            return
        if self.runtime_stop_in_progress:
            self.toast("Another runtime operation is already in progress")
            return

        self.runtime_stop_in_progress = True
        self.toast("Turning off display…")

        def worker():
            try:
                state = self.runtime_controller.state()
                if state.monitor_running:
                    self.runtime_controller.terminate_monitor()
                    reap_monitor_child(self)
                elif state.busy:
                    raise DeviceBusyError(state.owner)

                result = subprocess.run(
                    [app.project_python(), str(app.SCREEN_CONTROL), "off"],
                    cwd=str(app.ROOT),
                    text=True,
                    capture_output=True,
                    check=False,
                )
                returncode = result.returncode
                stdout = result.stdout
                stderr = result.stderr
            except Exception as exc:
                returncode = 1
                stdout = ""
                stderr = str(exc)
            app.GLib.idle_add(
                self.finish_turn_off_display,
                returncode,
                stdout,
                stderr,
            )

        threading.Thread(target=worker, daemon=True).start()

    original_finish_turn_off = app.SmartScreenWindow.finish_turn_off_display

    def finish_turn_off_display(self, returncode, stdout, stderr):
        self.runtime_stop_in_progress = False
        self.monitor_process = None
        return original_finish_turn_off(self, returncode, stdout, stderr)

    app.SmartScreenWindow.__init__ = patched_init
    app.SmartScreenWindow.update_runtime_status = update_runtime_status
    app.SmartScreenWindow.refresh_runtime_status = refresh_runtime_status
    app.SmartScreenWindow.refresh_overview = patched_refresh_overview
    app.SmartScreenWindow.build_settings_page = build_settings_page
    app.SmartScreenWindow.on_start_monitor_changed = on_start_monitor_changed
    app.SmartScreenWindow.auto_apply_last_theme = auto_apply_last_theme
    app.SmartScreenWindow.start_monitor = start_monitor
    app.SmartScreenWindow.finish_monitor_start = finish_monitor_start
    app.SmartScreenWindow.stop_monitor = stop_monitor
    app.SmartScreenWindow.finish_monitor_stop = finish_monitor_stop
    app.SmartScreenWindow.turn_off_display = turn_off_display
    app.SmartScreenWindow.finish_turn_off_display = finish_turn_off_display


def main() -> int:
    app = load_app_module()
    install_runtime_patches(app)
    return app.main()


if __name__ == "__main__":
    raise SystemExit(main())
