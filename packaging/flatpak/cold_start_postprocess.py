#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Flatpak cold-start readiness fixes for the staged application payload."""

from __future__ import annotations

import sys
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    source = path.read_text(encoding="utf-8")
    if old not in source:
        raise AssertionError(f"Flatpak cold-start hook not found: {label}")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: cold_start_postprocess.py PAYLOAD_ROOT")

    root = Path(sys.argv[1]).resolve()

    runners = root / "library/monitor_renderers.py"
    replace_once(
        runners,
        "HTML_WORKER_STABLE_SECONDS = 60.0\n",
        "HTML_WORKER_STABLE_SECONDS = 60.0\n"
        "HTML_WORKER_STARTUP_ATTEMPTS = 2\n"
        "HTML_WORKER_READY_TIMEOUT_SECONDS = 24.0\n"
        "HTML_WORKER_STARTUP_RETRY_DELAY_SECONDS = 2.0\n",
        "HTML startup constants",
    )
    replace_once(
        runners,
        '''    def start(self) -> None:
        if self.selection.manifest is None:
            raise RuntimeError("HTML worker requires a validated manifest")
''',
        '''    def _ready_file(self) -> Path | None:
        raw = str((self._environment or {}).get("TURING_MONITOR_READY_FILE") or "").strip()
        return Path(raw) if raw else None

    def _clear_ready_file(self) -> None:
        path = self._ready_file()
        if path is None:
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    def _wait_for_ready(self, process: subprocess.Popen, timeout: float) -> bool:
        path = self._ready_file()
        if path is None:
            time.sleep(0.15)
            return process.poll() is None
        deadline = time.monotonic() + max(0.0, float(timeout))
        while time.monotonic() < deadline and not self._stopping.is_set():
            if process.poll() is not None:
                return False
            if path.is_file():
                return True
            time.sleep(0.10)
        return process.poll() is None and path.is_file()

    def _abort_startup_process(self, process: subprocess.Popen) -> None:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2.0)
        if self.process is process:
            self.process = None

    def start(self) -> None:
        if self.selection.manifest is None:
            raise RuntimeError("HTML worker requires a validated manifest")
''',
        "HTML readiness helpers",
    )
    replace_once(
        runners,
        '''        self._environment = env
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
''',
        '''        self._environment = env
        self._stopping.clear()
        last_reason = "HTML renderer did not become ready"

        for attempt in range(1, HTML_WORKER_STARTUP_ATTEMPTS + 1):
            self._clear_ready_file()
            process = self._spawn()
            if self._wait_for_ready(process, HTML_WORKER_READY_TIMEOUT_SECONDS):
                return

            code = process.poll()
            if code is None:
                last_reason = (
                    "HTML renderer worker stayed alive but did not initialize "
                    f"the display within {HTML_WORKER_READY_TIMEOUT_SECONDS:.0f}s"
                )
            else:
                last_reason = f"HTML renderer worker exited during startup ({code})"

            self._abort_startup_process(process)
            if attempt < HTML_WORKER_STARTUP_ATTEMPTS:
                print(
                    f"{last_reason}; retrying cold start in "
                    f"{HTML_WORKER_STARTUP_RETRY_DELAY_SECONDS:.1f}s",
                    file=sys.stderr,
                    flush=True,
                )
                if self._stopping.wait(HTML_WORKER_STARTUP_RETRY_DELAY_SECONDS):
                    raise RuntimeError("HTML renderer startup was cancelled")

        raise RuntimeError(last_reason)
''',
        "HTML readiness startup loop",
    )

    worker = root / "library/html_renderer_worker.py"
    replace_once(
        worker,
        "SUPPORTED_NATIVE_VIDEO_SIZES = {'2.1\"', '2.8\"'}\n",
        "SUPPORTED_NATIVE_VIDEO_SIZES = {'2.1\"', '2.8\"'}\n\n"
        "def _signal_monitor_ready() -> None:\n"
        "    raw = os.environ.get(\"TURING_MONITOR_READY_FILE\", \"\").strip()\n"
        "    if not raw:\n"
        "        return\n"
        "    path = Path(raw)\n"
        "    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)\n"
        "    path.write_text(f\"{os.getpid()}\\n\", encoding=\"utf-8\")\n\n",
        "HTML worker readiness signal",
    )
    replace_once(
        worker,
        '''                            self.sink = HtmlNativeVideoSink(
                                frame,
                                hybrid_spec,
                                port=port,
                                brightness=brightness,
                                refresh_interval=1.0 / manifest.refresh_rate,
                            )
''',
        '''                            self.sink = HtmlNativeVideoSink(
                                frame,
                                hybrid_spec,
                                port=port,
                                brightness=brightness,
                                refresh_interval=1.0 / manifest.refresh_rate,
                            )
                            _signal_monitor_ready()
''',
        "native HTML sink readiness",
    )
    replace_once(
        worker,
        '''                        self.sink = IntegratedRevCSink(frame, protocol, parity, port=port)
                        self.planner = BudgetedFramePlanner(
''',
        '''                        self.sink = IntegratedRevCSink(frame, protocol, parity, port=port)
                        _signal_monitor_ready()
                        self.planner = BudgetedFramePlanner(
''',
        "integrated HTML sink readiness",
    )

    configure = root / "configure-gtk.py"
    replace_once(
        configure,
        '''        monitor_env = os.environ.copy()
        monitor_env["TURING_DISABLE_PYSTRAY"] = "1"
        try:
''',
        '''        monitor_env = os.environ.copy()
        monitor_env["TURING_DISABLE_PYSTRAY"] = "1"
        ready_file = self.runtime_controller.lock_path.with_name("monitor.ready")
        try:
            ready_file.unlink(missing_ok=True)
        except OSError:
            pass
        self.monitor_ready_file = ready_file
        monitor_env["TURING_MONITOR_READY_FILE"] = str(ready_file)
        try:
''',
        "GTK readiness environment",
    )
    replace_once(
        configure,
        "        self.monitor_start_deadline = time.monotonic() + 10.0\n",
        "        self.monitor_start_deadline = time.monotonic() + 55.0\n",
        "GTK cold-start deadline",
    )
    replace_once(
        configure,
        '''        if state.monitor_running:
            self.refresh_overview()
            return False
''',
        '''        ready_file = getattr(self, "monitor_ready_file", None)
        if ready_file is None:
            ready_file = self.runtime_controller.lock_path.with_name("monitor.ready")
        ready = ready_file.is_file()

        if state.monitor_running and ready:
            self.refresh_overview()
            return False
''',
        "GTK readiness completion",
    )
    replace_once(
        configure,
        '''            self.toast("Monitor startup timed out; try Start Monitor again")
''',
        '''            self.toast("Monitor did not become ready; startup process was stopped")
''',
        "GTK readiness timeout message",
    )

    dashboard = root / "library/main_app_dashboard_polish.py"
    replace_once(
        dashboard,
        '''        if state is not None and getattr(state, "monitor_running", False):
            owner = getattr(state, "owner", None)
            pid = getattr(owner, "pid", None)
            monitor_value = "Running"
            monitor_detail = f"PID {pid}" if pid else "Monitor owns the display"
        elif state is not None and getattr(state, "busy", False):
''',
        '''        process = getattr(self, "monitor_process", None)
        ready_file = getattr(self, "monitor_ready_file", None)
        if ready_file is None and controller is not None:
            ready_file = controller.lock_path.with_name("monitor.ready")
        starting = (
            process is not None
            and process.poll() is None
            and ready_file is not None
            and not ready_file.is_file()
        )

        if starting:
            monitor_value = "Starting"
            monitor_detail = f"PID {process.pid} · waiting for display readiness"
        elif state is not None and getattr(state, "monitor_running", False):
            owner = getattr(state, "owner", None)
            pid = getattr(owner, "pid", None)
            monitor_value = "Running"
            monitor_detail = f"PID {pid}" if pid else "Monitor owns the display"
        elif state is not None and getattr(state, "busy", False):
''',
        "dashboard cold-start status",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
