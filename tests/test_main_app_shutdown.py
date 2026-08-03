from __future__ import annotations

import signal
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from library.main_app_shutdown import (
    install_main_app_shutdown,
    stop_monitor_process,
)


class FakeProcess:
    def __init__(self, pid=4321, *, time_out=False):
        self.pid = pid
        self.time_out = time_out
        self.wait_calls = []
        self.events = []
        self.running = True

    def poll(self):
        return None if self.running else 0

    def terminate(self):
        self.events.append("terminate")

    def kill(self):
        self.events.append("kill")
        self.running = False

    def wait(self, timeout):
        self.wait_calls.append(timeout)
        if self.time_out and len(self.wait_calls) == 1:
            raise subprocess.TimeoutExpired("monitor", timeout)
        self.running = False
        return 0


class FakeGLib:
    PRIORITY_HIGH = -100
    registered = []
    removed = []

    @classmethod
    def unix_signal_add(cls, priority, signum, callback):
        source_id = len(cls.registered) + 1
        cls.registered.append((priority, signum, callback, source_id))
        return source_id

    @classmethod
    def source_remove(cls, source_id):
        cls.removed.append(source_id)

    @classmethod
    def idle_add(cls, callback, *args):
        callback(*args)
        return 1


class FakeGioApplicationAPI:
    current = None

    @classmethod
    def get_default(cls):
        return cls.current


class FakeWindow:
    def __init__(self, process=None):
        self.monitor_process = process
        self.messages = []
        self.refreshes = 0

    def toast(self, message):
        self.messages.append(message)

    def refresh_overview(self):
        self.refreshes += 1


class FakeApplication:
    startup_calls = 0
    shutdown_calls = 0

    def __init__(self, window=None):
        self.props = SimpleNamespace(active_window=None)
        self.window = window
        self.quit_calls = 0

    def get_windows(self):
        return [self.window] if self.window is not None else []

    def do_startup(self):
        type(self).startup_calls += 1

    def do_shutdown(self):
        type(self).shutdown_calls += 1

    def quit(self):
        self.quit_calls += 1


class MainAppShutdownTests(unittest.TestCase):
    def setUp(self):
        FakeGLib.registered = []
        FakeGLib.removed = []
        FakeApplication.startup_calls = 0
        FakeApplication.shutdown_calls = 0
        for attribute in (
            "_turing_shutdown_installed",
            "_turing_shutdown_signal_sources",
        ):
            if hasattr(FakeApplication, attribute):
                delattr(FakeApplication, attribute)
        FakeGioApplicationAPI.current = None

    def test_dedicated_process_group_receives_sigterm(self):
        process = FakeProcess()
        signals = []
        with (
            patch("library.main_app_shutdown.os.name", "posix"),
            patch("library.main_app_shutdown.os.getpgid", return_value=process.pid),
            patch(
                "library.main_app_shutdown.os.killpg",
                side_effect=lambda group, signum: signals.append((group, signum)),
            ),
        ):
            self.assertTrue(stop_monitor_process(process))

        self.assertEqual(signals, [(process.pid, signal.SIGTERM)])
        self.assertNotIn("terminate", process.events)

    def test_timeout_force_kills_whole_group(self):
        process = FakeProcess(time_out=True)
        signals = []
        with (
            patch("library.main_app_shutdown.os.name", "posix"),
            patch("library.main_app_shutdown.os.getpgid", return_value=process.pid),
            patch(
                "library.main_app_shutdown.os.killpg",
                side_effect=lambda group, signum: signals.append((group, signum)),
            ),
        ):
            stop_monitor_process(process, graceful_timeout=0, force_timeout=0)

        self.assertEqual(
            signals,
            [
                (process.pid, signal.SIGTERM),
                (process.pid, signal.SIGKILL),
            ],
        )

    def test_shared_process_group_only_terminates_child(self):
        process = FakeProcess()
        with (
            patch("library.main_app_shutdown.os.name", "posix"),
            patch("library.main_app_shutdown.os.getpgid", return_value=9999),
            patch("library.main_app_shutdown.os.killpg") as kill_group,
        ):
            stop_monitor_process(process)

        kill_group.assert_not_called()
        self.assertIn("terminate", process.events)

    def test_hidden_application_window_still_stops_monitor_on_shutdown(self):
        module = SimpleNamespace(
            SmartScreenWindow=FakeWindow,
            SmartScreenApplication=FakeApplication,
            GLib=FakeGLib,
            Gio=SimpleNamespace(Application=FakeGioApplicationAPI),
            sys=SimpleNamespace(stderr=None),
        )
        process = FakeProcess()
        window = FakeWindow(process)
        application = FakeApplication(window)
        FakeGioApplicationAPI.current = application

        with patch(
            "library.main_app_shutdown.stop_monitor_process",
            side_effect=lambda item: setattr(item, "running", False),
        ) as stop:
            self.assertTrue(install_main_app_shutdown(module))
            application.do_startup()
            application.do_shutdown()

        stop.assert_called_once_with(process)
        self.assertIsNone(window.monitor_process)
        self.assertGreaterEqual(len(FakeGLib.registered), 2)
        self.assertEqual(
            sorted(FakeGLib.removed),
            sorted(item[-1] for item in FakeGLib.registered),
        )
        self.assertEqual(FakeApplication.startup_calls, 1)
        self.assertEqual(FakeApplication.shutdown_calls, 1)


if __name__ == "__main__":
    unittest.main()
