from __future__ import annotations

import multiprocessing
import signal
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from library.runtime import (
    DeviceBusyError,
    DeviceLock,
    _force_terminate_monitor_tree,
    get_runtime_state,
)


def hold_lock(lock_path: str, ready) -> None:
    with DeviceLock("monitor", root=Path.cwd(), lock_path=lock_path):
        ready.set()
        time.sleep(1.5)


class DeviceLockTests(unittest.TestCase):
    def test_force_termination_kills_dedicated_monitor_group(self):
        with (
            mock.patch("library.runtime.os.name", "posix"),
            mock.patch("library.runtime.os.getpgid", return_value=4321),
            mock.patch("library.runtime.os.killpg") as kill_group,
            mock.patch("library.runtime.os.kill") as kill_process,
        ):
            _force_terminate_monitor_tree(4321)

        kill_group.assert_called_once_with(4321, signal.SIGKILL)
        kill_process.assert_not_called()

    def test_second_process_sees_owner_and_cannot_acquire(self):
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "device.lock"
            ready = multiprocessing.Event()
            process = multiprocessing.Process(
                target=hold_lock,
                args=(str(lock_path), ready),
            )
            process.start()
            self.assertTrue(ready.wait(timeout=2))

            state = get_runtime_state(lock_path)
            self.assertTrue(state.busy)
            self.assertEqual(state.owner.role, "monitor")
            self.assertEqual(state.owner.pid, process.pid)

            with self.assertRaises(DeviceBusyError):
                DeviceLock(
                    "video-manager",
                    root=Path.cwd(),
                    lock_path=lock_path,
                ).acquire()

            process.join(timeout=3)
            self.assertFalse(process.is_alive())
            self.assertFalse(get_runtime_state(lock_path).busy)

    def test_release_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = DeviceLock(
                "monitor",
                root=Path.cwd(),
                lock_path=Path(directory) / "device.lock",
            )
            lock.acquire()
            lock.release()
            lock.release()
            self.assertFalse(lock.acquired)


if __name__ == "__main__":
    unittest.main()
