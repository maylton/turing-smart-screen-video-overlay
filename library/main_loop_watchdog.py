# SPDX-License-Identifier: GPL-3.0-or-later
"""Exit a renderer whose GTK main loop stopped completing captures.

A blocked main loop cannot notice its own stall, so the check runs on a
separate thread. Exiting without touching the serial port lets the
supervisor restart the worker the same way as after a crash, which keeps
the display connected; a clean stop would power the display off.
"""

from __future__ import annotations

import faulthandler
import os
import sys
import threading
import time
from typing import Callable, Optional


def _dump_and_exit(stalled_for: float) -> None:
    print(
        f"HTML renderer main loop stalled for {stalled_for:.0f}s; exiting so it is restarted",
        file=sys.stderr,
        flush=True,
    )
    faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
    sys.stderr.flush()
    os._exit(1)


class MainLoopWatchdog:
    def __init__(
        self,
        stall_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        on_stall: Callable[[float], None] = _dump_and_exit,
        poll_seconds: float = 1.0,
    ) -> None:
        self.stall_seconds = float(stall_seconds)
        self._clock = clock
        self._on_stall = on_stall
        self._poll_seconds = poll_seconds
        self._last_beat: Optional[float] = None
        self._lock = threading.Lock()
        self._stopped = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def arm(self) -> None:
        """Start counting from now; beats before arming are ignored."""
        self.beat()

    def beat(self) -> None:
        with self._lock:
            self._last_beat = self._clock()

    def disarm(self) -> None:
        with self._lock:
            self._last_beat = None

    def check(self) -> bool:
        """Run one check; True when the stall handler was called."""
        with self._lock:
            last = self._last_beat
        if last is None:
            return False
        stalled_for = self._clock() - last
        if stalled_for <= self.stall_seconds:
            return False
        self._on_stall(stalled_for)
        return True

    def start(self) -> None:
        if self._thread is not None:
            return

        def run() -> None:
            while not self._stopped.wait(self._poll_seconds):
                if self.check():
                    return

        self._thread = threading.Thread(target=run, name="main-loop-watchdog", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopped.set()
