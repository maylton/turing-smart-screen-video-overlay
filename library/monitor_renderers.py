# SPDX-License-Identifier: GPL-3.0-or-later
"""Concrete monitor runners behind :mod:`renderer_lifecycle`."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

from library.renderer_lifecycle import RendererSelection


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

    def start(self) -> None:
        if self.selection.manifest is None:
            raise RuntimeError("HTML worker requires a validated manifest")
        if self.selection.manifest.native_video_overlay is not None:
            from library.html_hybrid import validate_native_video

            validate_native_video(self.selection.manifest)
        env = os.environ.copy()
        env.setdefault("GSK_RENDERER", "gl")
        env.setdefault("WEBKIT_DISABLE_DMABUF_RENDERER", "1")
        command = [
            sys.executable,
            "-m",
            "library.html_renderer_worker",
            "--theme",
            str(self.selection.manifest.root),
        ]
        self.process = subprocess.Popen(command, cwd=self.root, env=env)
        # Catch missing optional dependencies and preflight failures without
        # ever opening a second renderer.
        time.sleep(0.15)
        code = self.process.poll()
        if code is not None:
            self.process = None
            raise RuntimeError(f"HTML renderer worker exited during startup ({code})")

    def stop(self) -> None:
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
        if self.process is None:
            return 0
        return int(self.process.wait())
