from __future__ import annotations

import multiprocessing
import tempfile
import time
import unittest
from pathlib import Path

from library.runtime import DeviceBusyError, DeviceLock, get_runtime_state


def hold_lock(lock_path: str, ready) -> None:
    with DeviceLock("monitor", root=Path.cwd(), lock_path=lock_path):
        ready.set()
        time.sleep(1.5)


class DeviceLockTests(unittest.TestCase):
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
