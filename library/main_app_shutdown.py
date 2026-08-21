# SPDX-License-Identifier: GPL-3.0-or-later
"""Coordinated shutdown for the GTK shell and its monitor process group."""

from __future__ import annotations

import os
import signal
import subprocess
from typing import Any

from library.runtime import DeviceBusyError, MonitorController


GRACEFUL_MONITOR_TIMEOUT_SECONDS = 8
FORCE_MONITOR_TIMEOUT_SECONDS = 2


def _monitor_process_group(process: subprocess.Popen) -> int | None:
    """Return a safe dedicated process group, never the caller's own group."""
    if os.name != "posix":
        return None
    try:
        group = os.getpgid(process.pid)
    except OSError:
        return None
    return group if group == process.pid else None


def stop_monitor_process(
    process: subprocess.Popen | None,
    *,
    graceful_timeout: float = GRACEFUL_MONITOR_TIMEOUT_SECONDS,
    force_timeout: float = FORCE_MONITOR_TIMEOUT_SECONDS,
) -> bool:
    """Let main.py stop its worker and LCD; force its group only on timeout."""
    if process is None or process.poll() is not None:
        return False

    group = _monitor_process_group(process)
    try:
        # main.py owns renderer cleanup, so it must receive SIGTERM first.
        process.terminate()
        process.wait(timeout=max(0.0, float(graceful_timeout)))
    except subprocess.TimeoutExpired:
        if group is not None:
            try:
                os.killpg(group, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        try:
            process.wait(timeout=max(0.0, float(force_timeout)))
        except subprocess.TimeoutExpired:
            pass
    except ProcessLookupError:
        pass
    return True


def _monitor_controller(app_module: Any) -> MonitorController:
    """Build the persistent lock-based controller used by the GTK shell."""
    return MonitorController(
        root=app_module.ROOT,
        main_program=app_module.MAIN_PROGRAM,
        python_executable=app_module.project_python(),
    )


def _application_windows(application: Any) -> tuple[Any, ...]:
    get_windows = getattr(application, "get_windows", None)
    windows = tuple(get_windows()) if callable(get_windows) else ()
    if windows:
        return windows
    active = getattr(getattr(application, "props", None), "active_window", None)
    return (active,) if active is not None else ()


def install_main_app_shutdown(app: Any) -> bool:
    """Patch the dynamically loaded GTK application with orderly shutdown."""
    window_class = getattr(app, "SmartScreenWindow", None)
    application_class = getattr(app, "SmartScreenApplication", None)
    if window_class is None or application_class is None:
        return False
    if getattr(application_class, "_turing_shutdown_installed", False):
        return False

    GLib = app.GLib

    def terminate_persistent_monitor() -> tuple[bool, str]:
        controller = _monitor_controller(app)
        state = controller.state()
        if not state.busy:
            return False, "Monitor is not running"
        if not state.monitor_running:
            raise DeviceBusyError(state.owner)
        result = controller.terminate_monitor(
            timeout=GRACEFUL_MONITOR_TIMEOUT_SECONDS,
            kill_timeout=FORCE_MONITOR_TIMEOUT_SECONDS,
        )
        return result.stopped, result.message

    def stop_window_monitor(self, *, notify: bool) -> bool:
        local_process = getattr(self, "monitor_process", None)
        stopped = False
        message = "Monitor is not running"
        try:
            stopped, message = terminate_persistent_monitor()

            # Cover the short interval before a new child acquires its lock.
            if (
                not stopped
                and local_process is not None
                and local_process.poll() is None
            ):
                stopped = stop_monitor_process(local_process)
                message = "Monitor stopped"

            if notify:
                self.toast(
                    "Monitor stopped and display powered off" if stopped else message
                )
            return stopped
        except Exception as exc:
            if notify:
                self.toast(f"Could not stop monitor cleanly: {exc}")
            else:
                print(
                    f"Could not stop monitor during application shutdown: {exc}",
                    file=app.sys.stderr,
                    flush=True,
                )
            return False
        finally:
            self.monitor_process = None
            try:
                self.refresh_overview()
            except Exception:
                pass

    def stop_monitor(self, *_args):
        stop_window_monitor(self, notify=True)

    def stop_all_monitors(self, *, notify: bool = False) -> bool:
        windows = _application_windows(self)
        stopped = False
        for window in windows:
            callback = getattr(window, "_turing_stop_monitor_process", None)
            if callable(callback):
                stopped = bool(callback(notify=notify)) or stopped

        # A detached monitor may outlive a hidden/destroyed GTK window.
        if not windows:
            try:
                stopped, _message = terminate_persistent_monitor()
            except Exception as exc:
                print(
                    f"Could not stop detached monitor during shutdown: {exc}",
                    file=app.sys.stderr,
                    flush=True,
                )
        return stopped

    window_class.stop_monitor = stop_monitor
    window_class._turing_stop_monitor_process = stop_window_monitor
    application_class._turing_stop_all_monitors = stop_all_monitors

    original_startup = application_class.do_startup
    original_shutdown = application_class.do_shutdown

    def request_quit(application) -> bool:
        application.quit()
        return False

    def register_signal_sources(application) -> bool:
        if getattr(application, "_turing_shutdown_signal_sources", None) is not None:
            return False
        sources = []
        unix_signal_add = getattr(GLib, "unix_signal_add", None)
        if callable(unix_signal_add):
            priority = getattr(GLib, "PRIORITY_HIGH", 0)
            registered_signals = set()
            for signum in (
                signal.SIGTERM,
                signal.SIGINT,
                getattr(signal, "SIGHUP", signal.SIGTERM),
                getattr(signal, "SIGQUIT", signal.SIGTERM),
            ):
                if signum in registered_signals:
                    continue
                registered_signals.add(signum)
                callback = lambda current=application: request_quit(current)
                source_id = unix_signal_add(priority, signum, callback)
                sources.append((signum, source_id))
        application._turing_shutdown_signal_sources = sources
        return False

    def do_startup(self):
        original_startup(self)
        register_signal_sources(self)

    def do_shutdown(self):
        self._turing_stop_all_monitors(notify=False)

        for _signum, source_id in tuple(
            getattr(self, "_turing_shutdown_signal_sources", ())
        ):
            try:
                GLib.source_remove(source_id)
            except Exception:
                pass
        self._turing_shutdown_signal_sources = []
        original_shutdown(self)

    application_class.do_startup = do_startup
    application_class.do_shutdown = do_shutdown
    application_class._turing_shutdown_installed = True

    # Ensure the tray exit action performs the same ordered shutdown.
    menu_class = getattr(app, "StatusNotifierMenu", None)
    if menu_class is not None and not getattr(
        menu_class, "_turing_quit_shutdown_installed", False
    ):
        original_activate_item = menu_class.activate_item

        def activate_item(self, item_id: int):
            action = self.action_for_id(item_id)
            if action != "quit":
                return original_activate_item(self, item_id)

            def run_quit():
                try:
                    callback = getattr(self.app, "_turing_stop_all_monitors", None)
                    if callable(callback):
                        callback(notify=False)
                finally:
                    self.app.quit()
                return False

            GLib.idle_add(run_quit)

        menu_class.activate_item = activate_item
        menu_class._turing_quit_shutdown_installed = True

    # Also support installation after GTK startup has already completed.
    gio = getattr(app, "Gio", None)
    application_api = getattr(gio, "Application", None)
    get_default = getattr(application_api, "get_default", None)
    if callable(get_default):
        current = get_default()
        if isinstance(current, application_class):
            GLib.idle_add(register_signal_sources, current)
    return True
