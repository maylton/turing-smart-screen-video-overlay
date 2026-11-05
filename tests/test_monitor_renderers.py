from __future__ import annotations

import subprocess
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from library.monitor_renderers import HtmlWorkerRunner
from library.renderer_lifecycle import RendererSelection


class FakeProcess:
    def __init__(self, code=0):
        self.code = code
        self.terminated = False
        self.killed = False

    def poll(self):
        return None

    def wait(self, timeout=None):
        return self.code

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


class BlockingProcess(FakeProcess):
    def __init__(self):
        super().__init__(code=0)
        self.wait_started = threading.Event()
        self.exited = threading.Event()

    def poll(self):
        return self.code if self.exited.is_set() else None

    def wait(self, timeout=None):
        self.wait_started.set()
        if not self.exited.wait(timeout):
            raise subprocess.TimeoutExpired("worker", timeout)
        return self.code

    def terminate(self):
        super().terminate()
        self.exited.set()

    def kill(self):
        super().kill()
        self.exited.set()


def selection() -> RendererSelection:
    manifest = SimpleNamespace(
        root=Path("/tmp/html-theme"),
        native_video_overlay=None,
    )
    return RendererSelection("html", "html-theme", manifest)


class HtmlWorkerRunnerTests(unittest.TestCase):
    def test_stop_powers_display_off_when_worker_already_died(self):
        # At system shutdown the compositor goes away first and GTK ends the
        # worker at once, so the monitor must turn the display off itself.
        power_off = mock.Mock()
        runner = HtmlWorkerRunner(selection(), root=Path("/tmp"), power_off=power_off)
        dead = mock.Mock()
        dead.poll.return_value = 1
        runner.process = dead
        runner._started = True
        runner.stop()
        dead.terminate.assert_not_called()
        power_off.assert_called_once_with(Path("/tmp").resolve())

    def test_stop_powers_display_off_while_waiting_for_a_restart(self):
        power_off = mock.Mock()
        runner = HtmlWorkerRunner(selection(), root=Path("/tmp"), power_off=power_off)
        runner.process = None
        runner._started = True
        runner.stop()
        power_off.assert_called_once()

    def test_clean_worker_stop_leaves_power_off_to_the_worker(self):
        power_off = mock.Mock()
        runner = HtmlWorkerRunner(selection(), root=Path("/tmp"), power_off=power_off)
        process = mock.Mock()
        process.poll.return_value = None
        runner.process = process
        runner._started = True
        runner.stop()
        process.terminate.assert_called_once_with()
        power_off.assert_not_called()

    def test_killed_worker_gets_a_monitor_power_off(self):
        power_off = mock.Mock()
        runner = HtmlWorkerRunner(selection(), root=Path("/tmp"), power_off=power_off)
        process = mock.Mock()
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired("worker", 5), 0]
        runner.process = process
        runner._started = True
        runner.stop()
        process.kill.assert_called_once_with()
        power_off.assert_called_once()

    def test_never_started_runner_does_not_touch_the_display(self):
        power_off = mock.Mock()
        runner = HtmlWorkerRunner(selection(), root=Path("/tmp"), power_off=power_off)
        runner.stop()
        power_off.assert_not_called()

    def test_power_off_errors_do_not_escape_stop(self):
        runner = HtmlWorkerRunner(selection(), root=Path("/tmp"), power_off=mock.Mock(side_effect=OSError("no port")))
        runner._started = True
        with mock.patch("library.monitor_renderers.logger") as logger:
            runner.stop()
        logger.warning.assert_called_once()

    def test_refresh_kills_a_running_worker(self):
        runner = HtmlWorkerRunner(selection(), root=Path("/tmp"))
        process = mock.Mock()
        process.poll.return_value = None
        runner.process = process
        self.assertTrue(runner.refresh())
        process.kill.assert_called_once_with()
        process.terminate.assert_not_called()

    def test_requested_reload_restarts_without_a_failure_warning(self):
        runner = HtmlWorkerRunner(selection(), root=Path("/tmp"))
        first = FakeProcess(code=-9)
        second = FakeProcess(code=0)
        runner.process = first
        runner._reload_requested.set()
        spawned = []

        def spawn():
            spawned.append(second)
            runner.process = second
            runner._stopping.set()
            return second

        runner._spawn = spawn
        with (
            mock.patch("library.monitor_renderers.HTML_WORKER_RELOAD_DELAY_SECONDS", 0.0),
            mock.patch("library.monitor_renderers.logger") as logger,
        ):
            runner.wait()

        self.assertEqual(spawned, [second])
        self.assertFalse(runner._reload_requested.is_set())
        logger.warning.assert_not_called()
        logger.info.assert_called_once()

    def test_refresh_without_a_live_worker(self):
        runner = HtmlWorkerRunner(selection(), root=Path("/tmp"))
        self.assertFalse(runner.refresh())
        exited = mock.Mock()
        exited.poll.return_value = 1
        runner.process = exited
        self.assertFalse(runner.refresh())
        exited.kill.assert_not_called()

    def test_unexpected_worker_exit_is_restarted(self):
        runner = HtmlWorkerRunner(selection(), root=Path("/tmp"))
        first = FakeProcess(code=1)
        second = FakeProcess(code=0)
        runner.process = first
        runner._command = ["python", "worker"]
        runner._environment = {}
        spawned = []

        def spawn():
            spawned.append(second)
            runner.process = second
            runner._stopping.set()
            return second

        runner._spawn = spawn
        with (
            mock.patch(
                "library.monitor_renderers.HTML_WORKER_RESTART_DELAYS_SECONDS",
                (0.0,),
            ),
            mock.patch("library.monitor_renderers.time.monotonic", side_effect=[0.0, 1.0]),
            mock.patch("library.monitor_renderers.logger") as logger,
        ):
            result = runner.wait()

        self.assertEqual(result, 1)
        self.assertEqual(spawned, [second])
        # Logged (not only printed) so the failure reaches log.log.
        logger.warning.assert_called_once()
        self.assertIn("exited unexpectedly", logger.warning.call_args.args[0])
        self.assertEqual(logger.warning.call_args.args[1], 1)

    def test_explicit_stop_does_not_restart_worker(self):
        runner = HtmlWorkerRunner(selection(), root=Path("/tmp"))
        process = BlockingProcess()
        runner.process = process
        runner._command = ["python", "worker"]
        runner._environment = {}
        spawned = mock.Mock()
        runner._spawn = spawned

        waiter_result = []
        waiter = threading.Thread(target=lambda: waiter_result.append(runner.wait()))
        waiter.start()
        self.assertTrue(process.wait_started.wait(timeout=1))
        runner.stop()
        waiter.join(timeout=1)

        self.assertEqual(waiter_result, [0])
        self.assertTrue(process.terminated)
        spawned.assert_not_called()


if __name__ == "__main__":
    unittest.main()
