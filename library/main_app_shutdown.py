# SPDX-License-Identifier: GPL-3.0-or-later
"""Coordinated shutdown for the GTK shell and its monitor process group."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from typing import Any

from gi.repository import GLib

from library.main_app_base import MAIN_PROGRAM, ROOT, project_python
from library.runtime import DeviceBusyError, MonitorController


GRACEFUL_MONITOR_TIMEOUT_SECONDS = 8
FORCE_MONITOR_TIMEOUT_SECONDS = 2


def _monitor_process_group(process: subprocess.Popen) -> int | None:
    """Return a safe dedicated process group, never the caller's own group."""
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


def _monitor_controller() -> MonitorController:
    """Build the persistent lock-based controller used by the GTK shell."""
    return MonitorController(root=ROOT, main_program=MAIN_PROGRAM, python_executable=project_python())


def _application_windows(application: Any) -> tuple[Any, ...]:
    get_windows = getattr(application, "get_windows", None)
    windows = tuple(get_windows()) if callable(get_windows) else ()
    if windows:
        return windows
    active = getattr(getattr(application, "props", None), "active_window", None)
    return (active,) if active is not None else ()


def terminate_persistent_monitor() -> tuple[bool, str]:
    controller = _monitor_controller()
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


class ShutdownWindowMixin:
    """Stop the monitor through its lock, whoever started it."""

    def stop_window_monitor(self, *, notify: bool) -> bool:
        local_process = getattr(self, "monitor_process", None)
        stopped = False
        message = "Monitor is not running"
        try:
            stopped, message = terminate_persistent_monitor()

            # Cover the short interval before a new child acquires its lock.
            if not stopped and local_process is not None and local_process.poll() is None:
                stopped = stop_monitor_process(local_process)
                message = "Monitor stopped"

            if notify:
                self.toast("Monitor stopped and display powered off" if stopped else message)
            return stopped
        except Exception as exc:
            if notify:
                self.toast(f"Could not stop monitor cleanly: {exc}")
            else:
                print(f"Could not stop monitor during application shutdown: {exc}", file=sys.stderr, flush=True)
            return False
        finally:
            self.monitor_process = None
            try:
                self.refresh_overview()
            except Exception:
                pass

    def stop_monitor(self, *_args):
        self.stop_window_monitor(notify=True)


class ShutdownApplicationMixin:
    def stop_all_monitors(self, *, notify: bool = False) -> bool:
        windows = _application_windows(self)
        stopped = False
        for window in windows:
            callback = getattr(window, "stop_window_monitor", None)
            if callable(callback):
                stopped = bool(callback(notify=notify)) or stopped

        # A detached monitor may outlive a hidden/destroyed GTK window.
        if not windows:
            try:
                stopped, _message = terminate_persistent_monitor()
            except Exception as exc:
                print(f"Could not stop detached monitor during shutdown: {exc}", file=sys.stderr, flush=True)
        return stopped


class ShutdownTrayMenuMixin:
    """The tray Quit action stops the monitor before quitting."""

    def activate_item(self, item_id: int):
        if self.action_for_id(item_id) != "quit":
            return super().activate_item(item_id)

        def run_quit():
            try:
                stop_all = getattr(self.app, "stop_all_monitors", None)
                if callable(stop_all):
                    stop_all(notify=False)
            finally:
                self.app.quit()
            return False

        GLib.idle_add(run_quit)
