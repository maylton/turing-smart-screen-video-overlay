from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest import mock

from library.shutdown_inhibitor import ShutdownInhibitor


def signal_args(starting: bool):
    return (None, "org.freedesktop.login1", "/org/freedesktop/login1",
            "org.freedesktop.login1.Manager", "PrepareForShutdown",
            SimpleNamespace(unpack=lambda: (starting,)))


class ShutdownInhibitorTests(unittest.TestCase):
    def make(self, callback):
        inhibitor = ShutdownInhibitor(callback)
        read_end, write_end = os.pipe()
        self.addCleanup(lambda: os.close(read_end))
        inhibitor._fd = write_end
        return inhibitor, write_end

    def assertClosed(self, fd: int) -> None:
        with self.assertRaises(OSError):
            os.fstat(fd)

    def test_shutdown_runs_cleanup_then_releases_the_lock(self):
        calls = []
        inhibitor, fd = self.make(lambda: calls.append("cleanup"))
        inhibitor._on_signal(*signal_args(True))
        self.assertEqual(calls, ["cleanup"])
        self.assertIsNone(inhibitor._fd)
        self.assertClosed(fd)

    def test_shutdown_cancelled_or_finished_signal_is_ignored(self):
        callback = mock.Mock()
        inhibitor, fd = self.make(callback)
        inhibitor._on_signal(*signal_args(False))
        callback.assert_not_called()
        self.assertEqual(inhibitor._fd, fd)
        inhibitor.release()

    def test_cleanup_runs_once_and_errors_still_release(self):
        callback = mock.Mock(side_effect=RuntimeError("serial gone"))
        inhibitor, fd = self.make(callback)
        with mock.patch("library.shutdown_inhibitor.logger") as logger:
            inhibitor._on_signal(*signal_args(True))
            inhibitor._on_signal(*signal_args(True))
        callback.assert_called_once_with()
        logger.warning.assert_called_once()
        self.assertClosed(fd)

    def test_release_is_idempotent(self):
        inhibitor, _fd = self.make(mock.Mock())
        inhibitor.release()
        inhibitor.release()
        self.assertIsNone(inhibitor._fd)


if __name__ == "__main__":
    unittest.main()
