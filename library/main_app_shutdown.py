# SPDX-License-Identifier: GPL-3.0-or-later
"""Coordinated shutdown for the GTK shell and its monitor process group."""

from __future__ import annotations

import os
import signal
import subprocess
from typing import Any


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
    # configure_gtk_app.py launches main.py with start_new_session=True, making
    # its PID the group ID. Refuse to signal an inherited/shared process group.
    return group if group == process.pid else None


def stop_monitor_process(
    process: subprocess.Popen | None,
    *,
    graceful_timeout: float = GRACEFUL_MONITOR_TIMEOUT_SECONDS,
    force_timeout: float = FORCE_MONITOR_TIMEOUT_SECONDS,
) -> bool:
    """Let main.py stop its worker and LCD; force the group only on timeout.

    Sending SIGTERM to the complete process group races the parent cleanup
    against the HTML worker cleanup. The worker can stop its live overlays
    while the parent simultaneously tears it down, leaving native video frozen
    in the firmware. Signal only main.py first: its registered handler owns the
    renderer controller and waits for the worker to power the display off.
    """
    if process is None or process.poll() is not None:
        return False

    group = _monitor_process_group(process)
    try:
        process.terminate()
        process.wait(timeout=max(0.0, float(graceful_timeout)))
    except subprocess.TimeoutExpired:
        # The orderly parent-owned path did not finish. At this point force the
        # dedicated group so neither main.py nor an orphan worker survives.
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


def install_main_app_shutdown(app: Any) -> bool:
    """Patch the dynamically loaded GTK application with orderly shutdown."""
    window_class = getattr(app, "SmartScreenWindow", None)
    application_class = getattr(app, "SmartScreenApplication", None)
    if window_class is None or application_class is None:
        return False
    if getattr(application_class, "_turing_shutdown_installed", False):
        return False

    GLib = app.GLib

    def stop_window_monitor(self, *, notify: bool) -> bool:
        process = getattr(self, "monitor_process", None)
        if process is None or process.poll() is not None:
            self.monitor_process = None
            if notify:
                self.toast("No monitor process started from this window")
            return False
        try:
            stop_monitor_process(process)
            if notify:
                self.toast("Monitor stopped and display powered off")
            return True
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

    window_class.stop_monitor = stop_monitor
    window_class._turing_stop_monitor_process = stop_window_monitor

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
        get_windows = getattr(self, "get_windows", None)
        windows = tuple(get_windows()) if callable(get_windows) else ()
        if not windows:
            active = getattr(self.props, "active_window", None)
            windows = (active,) if active is not None else ()

        for window in windows:
            callback = getattr(window, "_turing_stop_monitor_process", None)
            if callable(callback):
                callback(notify=False)

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

    # The extension is installed by a watcher because configure_gtk_app.py is
    # loaded dynamically. If GTK startup already ran, register the signals on
    # the current application during the next main-loop turn.
    gio = getattr(app, "Gio", None)
    application_api = getattr(gio, "Application", None)
    get_default = getattr(application_api, "get_default", None)
    if callable(get_default):
        current = get_default()
        if isinstance(current, application_class):
            GLib.idle_add(register_signal_sources, current)
    return True
