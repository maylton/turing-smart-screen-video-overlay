# SPDX-License-Identifier: GPL-3.0-or-later
"""Ask a running monitor to show a freshly saved HTML theme.

The theme editor saves the layout, then signals the monitor process that
owns the display. main.py forwards the request to the HTML worker, which
reloads the theme page in place; the serial session and the native video
keep running. No serial access happens here.
"""

from __future__ import annotations

import os
import re
import signal
from pathlib import Path

from library.runtime import get_runtime_state

LIVE_RELOAD_SIGNAL = signal.SIGUSR1


def active_html_theme(config_path: Path) -> str:
    """Name of the HTML theme selected in config.yaml, or ``""``."""
    try:
        content = Path(config_path).read_text(encoding="utf-8")
    except OSError:
        return ""
    try:
        import yaml

        renderer = (yaml.safe_load(content) or {}).get("renderer", {})
        if isinstance(renderer, dict):
            engine = str(renderer.get("engine") or "yaml").strip().lower()
            theme = str(renderer.get("theme") or "").strip()
            return theme if engine == "html" else ""
    except Exception:
        pass
    match = re.search(r"(?m)^\s*theme\s*:\s*[\"']?([^\"'\n#]+)", content)
    return match.group(1).strip() if match else ""


def running_monitor_pid(lock_path: Path | None = None) -> int | None:
    state = get_runtime_state(lock_path)
    if state.monitor_running and state.owner.pid:
        return int(state.owner.pid)
    return None


def catches_signal(pid: int, signum: int, proc_root: Path = Path("/proc")) -> bool:
    """True when ``pid`` installed a handler for ``signum`` (Linux SigCgt).

    SIGUSR1 terminates a process without a handler, so a monitor started
    before this feature must never receive it.
    """
    try:
        status = (Path(proc_root) / str(pid) / "status").read_text(encoding="ascii")
    except OSError:
        return False
    match = re.search(r"(?m)^SigCgt:\s*([0-9a-fA-F]+)$", status)
    return bool(match) and bool(int(match.group(1), 16) >> (int(signum) - 1) & 1)


def request_monitor_reload(lock_path: Path | None = None) -> bool:
    """Signal the monitor to reload its renderer.

    False when no monitor runs or the running one predates the reload
    handler (it would exit on SIGUSR1).
    """
    pid = running_monitor_pid(lock_path)
    if pid is None or not catches_signal(pid, LIVE_RELOAD_SIGNAL):
        return False
    try:
        os.kill(pid, LIVE_RELOAD_SIGNAL)
    except (ProcessLookupError, PermissionError):
        return False
    return True
