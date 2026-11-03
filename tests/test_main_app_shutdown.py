from __future__ import annotations

import signal
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from library.main_app_shutdown import (
    ShutdownApplicationMixin,
    ShutdownTrayMenuMixin,
    ShutdownWindowMixin,
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


def build_fake_classes(events):
    class WindowBase:
        def __init__(self, process=None):
            self.monitor_process = process
            self.messages = []

        def toast(self, message):
            self.messages.append(message)

        def refresh_overview(self):
            pass

    class ApplicationBase:
        def __init__(self, selected_window=None):
            self.props = SimpleNamespace(active_window=None)
            self.window = selected_window

        def get_windows(self):
            return [self.window] if self.window is not None else []

        def quit(self):
            events.append("quit")

    class MenuBase:
        def __init__(self, application):
            self.app = application

        def action_for_id(self, item_id):
            return "quit" if item_id == 6 else "other"

        def activate_item(self, item_id):
            events.append(("original-menu", item_id))

    class Window(ShutdownWindowMixin, WindowBase):
        pass

    class Application(ShutdownApplicationMixin, ApplicationBase):
        pass

    class Menu(ShutdownTrayMenuMixin, MenuBase):
        pass

    return Window, Application, Menu


class MainAppShutdownTests(unittest.TestCase):
    def test_parent_gets_graceful_signal_before_process_group(self):
        process = FakeProcess()
        signals = []
        with (
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
            patch("library.main_app_shutdown.os.getpgid", return_value=process.pid),
            patch(
                "library.main_app_shutdown.os.killpg",
                side_effect=lambda group, signum: signals.append((group, signum)),
            ),
        ):
            stop_monitor_process(process, graceful_timeout=0, force_timeout=0)

        self.assertEqual(process.events, ["terminate"])
        self.assertEqual(signals, [(process.pid, signal.SIGKILL)])

    def test_stop_all_monitors_stops_each_window_monitor(self):
        Window, Application, _Menu = build_fake_classes([])
        window = Window()
        application = Application(window)
        controller = FakeController()

        with patch("library.main_app_shutdown._monitor_controller", return_value=controller):
            self.assertTrue(application.stop_all_monitors(notify=False))

        self.assertEqual(controller.terminate_calls, [(8, 2)])
        self.assertIsNone(window.monitor_process)

    def test_tray_quit_stops_monitor_before_quitting(self):
        events = []
        Window, Application, Menu = build_fake_classes(events)
        window = Window()
        application = Application(window)
        controller = FakeController()

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

        with (
            patch("library.main_app_shutdown._monitor_controller", return_value=controller),
            patch("library.main_app_shutdown.GLib", FakeGLib),
        ):
            Menu(application).activate_item(6)

        self.assertEqual(events, ["stop-monitor", "quit"])
        self.assertEqual(controller.terminate_calls, [(8, 2)])

    def test_non_quit_tray_action_uses_original_handler(self):
        events = []
        _Window, Application, Menu = build_fake_classes(events)
        application = Application()

        with patch(
            "library.main_app_shutdown._monitor_controller",
            return_value=FakeController(busy=False, monitor_running=False),
        ):
            Menu(application).activate_item(2)

        self.assertEqual(events, [("original-menu", 2)])


if __name__ == "__main__":
    unittest.main()
