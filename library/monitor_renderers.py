# SPDX-License-Identifier: GPL-3.0-or-later
"""Concrete monitor runners behind :mod:`renderer_lifecycle`."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable

from library.renderer_lifecycle import RendererSelection


HTML_WORKER_RESTART_DELAYS_SECONDS = (1.0, 2.0, 5.0, 10.0, 30.0)
HTML_WORKER_STABLE_SECONDS = 60.0


class LegacyYamlRunner:
    def __init__(
        self,
        selection: RendererSelection,
        *,
        start_callback: Callable[[], None],
        stop_callback: Callable[[], None],
        wait_callback: Callable[[], int],
    ) -> None:
        self.selection = selection
        self._start = start_callback
        self._stop = stop_callback
        self._wait = wait_callback

    def start(self) -> None:
        self._start()

    def stop(self) -> None:
        self._stop()

    def wait(self) -> int:
        return self._wait()


class HtmlWorkerRunner:
    """Run GTK/WebKit in its own main-thread process.

    The main monitor does not run a GTK loop, while WebKit objects must stay on
    the GTK main thread.  A worker provides that ownership boundary, optional
    dependency isolation and deterministic teardown. Frames remain in memory
    inside the worker; diagnostic PNG output is enabled only by an explicit
    environment variable.
    """

    def __init__(self, selection: RendererSelection, *, root: Path) -> None:
        self.selection = selection
        self.root = Path(root).resolve()
        self.process: subprocess.Popen | None = None
        self._command: list[str] = []
        self._environment: dict[str, str] | None = None
        self._stopping = threading.Event()

    def _spawn(self) -> subprocess.Popen:
        process = subprocess.Popen(
            self._command,
            cwd=self.root,
            env=self._environment,
        )
        self.process = process
        return process

    def start(self) -> None:
        if self.selection.manifest is None:
            raise RuntimeError("HTML worker requires a validated manifest")
        if self.selection.manifest.native_video_overlay is not None:
            from library.html_hybrid import validate_native_video

            validate_native_video(self.selection.manifest)
        env = os.environ.copy()
        env.setdefault("GSK_RENDERER", "gl")
        env.setdefault("WEBKIT_DISABLE_DMABUF_RENDERER", "1")
        self._command = [
            sys.executable,
            "-m",
            "library.html_renderer_worker",
            "--theme",
            str(self.selection.manifest.root),
        ]
        self._environment = env
        self._stopping.clear()
        process = self._spawn()
        # Catch missing optional dependencies and preflight failures without
        # ever opening a second renderer.
        time.sleep(0.15)
        code = process.poll()
        if code is not None:
            if self.process is process:
                self.process = None
            raise RuntimeError(f"HTML renderer worker exited during startup ({code})")

    def stop(self) -> None:
        self._stopping.set()
        process, self.process = self.process, None
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)

    def wait(self) -> int:
        restart_index = 0
        last_code = 0
        while not self._stopping.is_set():
            process = self.process
            if process is None:
                return int(last_code)

            started = time.monotonic()
            last_code = int(process.wait())
            if self._stopping.is_set() or self.process is not process:
                return int(last_code)

            uptime = time.monotonic() - started
            if uptime >= HTML_WORKER_STABLE_SECONDS:
                restart_index = 0
            delay = HTML_WORKER_RESTART_DELAYS_SECONDS[
                min(restart_index, len(HTML_WORKER_RESTART_DELAYS_SECONDS) - 1)
            ]
            restart_index += 1
            print(
                "HTML renderer worker exited unexpectedly "
                f"(status {last_code}); restarting in {delay:.1f}s",
                file=sys.stderr,
                flush=True,
            )
            if self._stopping.wait(delay):
                return int(last_code)

            try:
                self._spawn()
            except Exception as exc:
                # Keep the monitor owner alive while USB/devices settle after
                # resume. The bounded backoff prevents a tight restart loop.
                print(
                    f"Could not restart HTML renderer worker: {exc}",
                    file=sys.stderr,
                    flush=True,
                )

        return int(last_code)
