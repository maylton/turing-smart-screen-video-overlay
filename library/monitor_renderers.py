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

from library.log import logger
from library.renderer_lifecycle import RendererSelection


HTML_WORKER_RESTART_DELAYS_SECONDS = (1.0, 2.0, 5.0, 10.0, 30.0)
# A requested reload restarts the worker without counting as a failure.
HTML_WORKER_RELOAD_DELAY_SECONDS = 0.5
HTML_WORKER_STABLE_SECONDS = 60.0
HTML_WORKER_GRACEFUL_STOP_SECONDS = 5.0
HTML_WORKER_FORCE_STOP_SECONDS = 2.0
# Upper bound for the monitor's own power-off when the worker cannot do it.
HTML_WORKER_POWER_OFF_TIMEOUT_SECONDS = 4.0


def power_off_display_directly(root: Path) -> None:
    """Power the Rev. C display off from the monitor process.

    Used when the HTML worker died before it could do so itself, e.g. at
    system shutdown, when the compositor goes away and GTK ends the worker
    at once. Without this the display keeps showing its last frame.
    """
    import yaml

    from library.display_shutdown import power_off_and_close_display
    from library.lcd.lcd_comm_rev_c import LcdCommRevC

    config = yaml.safe_load((Path(root) / "config.yaml").read_text(encoding="utf-8")) or {}
    port = str(config.get("config", {}).get("COM_PORT") or "AUTO")
    driver = LcdCommRevC(com_port=port, display_width=480, display_height=480)
    driver.update_queue = None
    driver.InitializeComm()
    power_off_and_close_display(driver)


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

    def __init__(
        self,
        selection: RendererSelection,
        *,
        root: Path,
        power_off: Callable[[Path], None] | None = None,
    ) -> None:
        self.selection = selection
        self.root = Path(root).resolve()
        self.process: subprocess.Popen | None = None
        self._power_off = power_off or power_off_display_directly
        self._started = False
        self._command: list[str] = []
        self._environment: dict[str, str] | None = None
        self._stopping = threading.Event()
        self._reload_requested = threading.Event()

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
        self._started = True

    def refresh(self) -> bool:
        """Restart the worker so it renders the theme saved on disk.

        The worker is killed rather than stopped: a clean stop powers the
        display off, and the new worker would then race the display's USB
        re-enumeration. Killed, it leaves the native video playing and the
        restart takes about 6 s with the display staying connected.
        Reloading the page inside the running worker is not used because
        WebKit then stops delivering snapshots.
        """
        process = self.process
        if process is None or process.poll() is not None:
            return False
        self._reload_requested.set()
        process.kill()
        return True

    def stop(self) -> None:
        """Stop the worker; it powers the display off on SIGTERM.

        When the worker is already gone (crashed, or waiting for a restart)
        or had to be killed, nobody turned the display off, so the monitor
        does it itself.
        """
        self._stopping.set()
        process, self.process = self.process, None
        # Only a worker started by this runner can have opened the display.
        display_opened, self._started = self._started, False
        worker_powered_off = False
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=HTML_WORKER_GRACEFUL_STOP_SECONDS)
                worker_powered_off = True
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=HTML_WORKER_FORCE_STOP_SECONDS)
        if display_opened and not worker_powered_off:
            self._power_off_without_worker()

    def _power_off_without_worker(self) -> None:
        logger.info("HTML renderer worker is not running; turning the display off directly")
        errors: list[BaseException] = []

        def run() -> None:
            try:
                self._power_off(self.root)
            except BaseException as exc:  # noqa: BLE001 - reported below
                errors.append(exc)

        thread = threading.Thread(target=run, name="display-power-off", daemon=True)
        thread.start()
        thread.join(HTML_WORKER_POWER_OFF_TIMEOUT_SECONDS)
        if thread.is_alive():
            logger.warning("Turning the display off timed out")
        elif errors:
            logger.warning("Could not turn the display off: %s", errors[0])

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

            if self._reload_requested.is_set():
                self._reload_requested.clear()
                logger.info("Restarting HTML renderer worker to show the saved theme")
                if self._stopping.wait(HTML_WORKER_RELOAD_DELAY_SECONDS):
                    return int(last_code)
                try:
                    self._spawn()
                except Exception as exc:
                    logger.error("Could not restart HTML renderer worker: %s", exc)
                continue

            uptime = time.monotonic() - started
            if uptime >= HTML_WORKER_STABLE_SECONDS:
                restart_index = 0
            delay = HTML_WORKER_RESTART_DELAYS_SECONDS[
                min(restart_index, len(HTML_WORKER_RESTART_DELAYS_SECONDS) - 1)
            ]
            restart_index += 1
            logger.warning(
                "HTML renderer worker exited unexpectedly "
                "(status %d); restarting in %.1fs",
                last_code,
                delay,
            )
            if self._stopping.wait(delay):
                return int(last_code)

            try:
                self._spawn()
            except Exception as exc:
                # Keep the monitor owner alive while USB/devices settle after
                # resume. The bounded backoff prevents a tight restart loop.
                logger.error("Could not restart HTML renderer worker: %s", exc)

        return int(last_code)
