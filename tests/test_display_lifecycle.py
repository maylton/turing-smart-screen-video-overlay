from __future__ import annotations

import unittest
from unittest import mock

from library.display_lifecycle import (
    DisplayLifecycleState,
    inspect_display_lifecycle,
)
from library.runtime import LockOwner, RuntimeState


REAL_PORT = {
    "device": "/dev/ttyACM0",
    "is_tty_acm": True,
    "is_usb_monitor": False,
}
USBMONITOR_PORT = {
    "device": "/dev/ttyACM1",
    "is_tty_acm": True,
    "is_usb_monitor": True,
}


class DisplayLifecycleTests(unittest.TestCase):
    def test_running_runtime_has_highest_priority(self):
        state = RuntimeState(
            busy=True,
            owner=LockOwner(pid=123, role="monitor", root="/project"),
        )
        snapshot = inspect_display_lifecycle([USBMONITOR_PORT], state)
        self.assertEqual(snapshot.state, DisplayLifecycleState.RUNNING)
        self.assertEqual(snapshot.owner_pids, (123,))

    def test_busy_runtime_precedes_ready_tty(self):
        state = RuntimeState(
            busy=True,
            owner=LockOwner(pid=456, role="video-manager"),
        )
        snapshot = inspect_display_lifecycle([REAL_PORT], state)
        self.assertEqual(snapshot.state, DisplayLifecycleState.BUSY)
        self.assertEqual(snapshot.owner_pids, (456,))

    def test_monitor_pid_is_fallback_when_lock_metadata_is_missing(self):
        snapshot = inspect_display_lifecycle(
            [REAL_PORT],
            RuntimeState(busy=False),
            monitor_pids=[99],
        )
        self.assertEqual(snapshot.state, DisplayLifecycleState.RUNNING)
        self.assertIn("lock metadata", snapshot.warning)

    @mock.patch("library.display_lifecycle.device_owner_pids", return_value=(777,))
    def test_external_serial_owner_marks_device_busy(self, _owner_pids):
        snapshot = inspect_display_lifecycle([REAL_PORT], RuntimeState(busy=False))
        self.assertEqual(snapshot.state, DisplayLifecycleState.BUSY)
        self.assertEqual(snapshot.owner_pids, (777,))
        self.assertIn("fuser", snapshot.warning)

    @mock.patch("library.display_lifecycle.device_owner_pids", return_value=())
    def test_unowned_tty_is_ready(self, _owner_pids):
        snapshot = inspect_display_lifecycle([REAL_PORT], RuntimeState(busy=False))
        self.assertEqual(snapshot.state, DisplayLifecycleState.TTY_READY)
        self.assertEqual(snapshot.devices, ("/dev/ttyACM0",))

    def test_usbmonitor_without_real_tty_is_waking(self):
        snapshot = inspect_display_lifecycle(
            [USBMONITOR_PORT],
            RuntimeState(busy=False),
        )
        self.assertEqual(snapshot.state, DisplayLifecycleState.USBMONITOR_WAKING)

    def test_no_relevant_ports_is_disconnected(self):
        snapshot = inspect_display_lifecycle([], RuntimeState(busy=False))
        self.assertEqual(snapshot.state, DisplayLifecycleState.DISCONNECTED)

    def test_serial_enumeration_error_is_unknown(self):
        snapshot = inspect_display_lifecycle(
            [{"error": "pyserial unavailable"}],
            RuntimeState(busy=False),
        )
        self.assertEqual(snapshot.state, DisplayLifecycleState.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
