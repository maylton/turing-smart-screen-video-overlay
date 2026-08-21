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
            mock.patch("builtins.print") as printed,
        ):
            result = runner.wait()

        self.assertEqual(result, 1)
        self.assertEqual(spawned, [second])
        printed.assert_called_once()

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
