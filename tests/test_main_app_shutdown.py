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


class FakeController:
    def __init__(self, *, busy=True, monitor_running=True):
        self.runtime_state = SimpleNamespace(
            busy=busy,
            monitor_running=monitor_running,
            owner=SimpleNamespace(role="monitor", describe=lambda: "monitor"),
        )
        self.terminate_calls = []

    def state(self):
        return self.runtime_state

    def terminate_monitor(self, timeout, kill_timeout):
        self.terminate_calls.append((timeout, kill_timeout))
        self.runtime_state = SimpleNamespace(
            busy=False,
            monitor_running=False,
            owner=SimpleNamespace(role="unknown", describe=lambda: "unknown"),
        )
        return SimpleNamespace(stopped=True, message="Monitor stopped")


def build_fake_module(events):
    class Window:
        def __init__(self, process=None):
            self.monitor_process = process
            self.messages = []

        def toast(self, message):
            self.messages.append(message)

        def refresh_overview(self):
            pass

    class Application:
        def __init__(self, selected_window=None):
            self.props = SimpleNamespace(active_window=None)
            self.window = selected_window
            self.quit_calls = 0

        def get_windows(self):
            return [self.window] if self.window is not None else []

        def do_startup(self):
            events.append("startup")

        def do_shutdown(self):
            events.append("shutdown")

        def quit(self):
            events.append("quit")
            self.quit_calls += 1

    class Menu:
        def __init__(self, application):
            self.app = application

        def action_for_id(self, item_id):
            return "quit" if item_id == 6 else "other"

        def activate_item(self, item_id):
            events.append(("original-menu", item_id))

    module = SimpleNamespace(
        SmartScreenWindow=Window,
        SmartScreenApplication=Application,
        StatusNotifierMenu=Menu,
        GLib=FakeGLib,
        Gio=SimpleNamespace(Application=FakeGioApplicationAPI),
        ROOT="/tmp/turing",
        MAIN_PROGRAM="/tmp/turing/main.py",
        project_python=lambda: "/usr/bin/python3",
        sys=SimpleNamespace(stderr=None),
    )
    return module, Window, Application, Menu


class MainAppShutdownTests(unittest.TestCase):
    def setUp(self):
        FakeGLib.registered = []
        FakeGLib.removed = []
        FakeGioApplicationAPI.current = None

    def test_parent_gets_graceful_signal_before_process_group(self):
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

        self.assertEqual(process.events, ["terminate"])
        self.assertEqual(signals, [])

    def test_timeout_force_kills_dedicated_group(self):
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

        self.assertEqual(process.events, ["terminate"])
        self.assertEqual(signals, [(process.pid, signal.SIGKILL)])

    def test_shutdown_stops_persistent_monitor_and_removes_signals(self):
        events = []
        module, Window, Application, _Menu = build_fake_module(events)
        window = Window()
        application = Application(window)
        controller = FakeController()
        FakeGioApplicationAPI.current = application

        with patch(
            "library.main_app_shutdown._monitor_controller",
            return_value=controller,
        ):
            self.assertTrue(install_main_app_shutdown(module))
            application.do_startup()
            application.do_shutdown()

        self.assertEqual(controller.terminate_calls, [(8, 2)])
        self.assertIsNone(window.monitor_process)
        self.assertGreaterEqual(len(FakeGLib.registered), 2)
        self.assertEqual(
            sorted(FakeGLib.removed),
            sorted(item[-1] for item in FakeGLib.registered),
        )
        self.assertEqual(events, ["startup", "shutdown"])

    def test_tray_quit_stops_monitor_before_quitting(self):
        events = []
        module, Window, Application, Menu = build_fake_module(events)
        window = Window()
        application = Application(window)
        controller = FakeController()
        FakeGioApplicationAPI.current = application

        def terminate(timeout, kill_timeout):
            events.append("stop-monitor")
            controller.terminate_calls.append((timeout, kill_timeout))
            controller.runtime_state = SimpleNamespace(
                busy=False,
                monitor_running=False,
                owner=SimpleNamespace(role="unknown", describe=lambda: "unknown"),
            )
            return SimpleNamespace(stopped=True, message="Monitor stopped")

        controller.terminate_monitor = terminate

        with patch(
            "library.main_app_shutdown._monitor_controller",
            return_value=controller,
        ):
            self.assertTrue(install_main_app_shutdown(module))
            Menu(application).activate_item(6)

        self.assertEqual(events, ["stop-monitor", "quit"])
        self.assertEqual(controller.terminate_calls, [(8, 2)])

    def test_non_quit_tray_action_uses_original_handler(self):
        events = []
        module, _Window, Application, Menu = build_fake_module(events)
        application = Application()

        with patch(
            "library.main_app_shutdown._monitor_controller",
            return_value=FakeController(busy=False, monitor_running=False),
        ):
            self.assertTrue(install_main_app_shutdown(module))
            Menu(application).activate_item(2)

        self.assertEqual(events, [("original-menu", 2)])


if __name__ == "__main__":
    unittest.main()
