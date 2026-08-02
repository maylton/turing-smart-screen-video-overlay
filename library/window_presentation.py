"""Best-effort presentation of child application windows.

GTK's activation hand-off is not always enough when a child application is
started from a window living on another Hyprland workspace.  Keep the generic
launcher compositor-neutral and apply the small Hyprland workaround only when
that compositor is actually in use.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Mapping
from typing import Any


_HYPRLAND_ADDRESS = re.compile(r"^0x[0-9a-fA-F]+$")


def is_hyprland_session(environment: Mapping[str, str] | None = None) -> bool:
    environment = os.environ if environment is None else environment
    desktops = ":".join(
        (
            environment.get("XDG_CURRENT_DESKTOP", ""),
            environment.get("XDG_SESSION_DESKTOP", ""),
        )
    )
    return "hyprland" in desktops.lower()


def _hyprctl(
    *arguments: str,
    timeout: float = 2.0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["hyprctl", *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def active_hyprland_workspace() -> int | None:
    """Return the active numeric workspace, or ``None`` when unavailable."""

    if not is_hyprland_session() or shutil.which("hyprctl") is None:
        return None
    try:
        result = _hyprctl("activeworkspace", "-j")
        payload = json.loads(result.stdout) if result.returncode == 0 else {}
        workspace_id = int(payload.get("id", 0))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    return workspace_id if workspace_id > 0 else None


def _window_address_for_pid(payload: Any, pid: int) -> str | None:
    if not isinstance(payload, list):
        return None
    for client in payload:
        if not isinstance(client, dict):
            continue
        try:
            client_pid = int(client.get("pid", -1))
        except (TypeError, ValueError):
            continue
        address = str(client.get("address", ""))
        if client_pid == pid and _HYPRLAND_ADDRESS.fullmatch(address):
            return address
    return None


def _move_window_expression(address: str, workspace_id: int) -> str:
    target = json.dumps(f"address:{address}")
    return (
        "return hl.dispatch(hl.dsp.window.move({ "
        f"window = {target}, workspace = {int(workspace_id)}, follow = true "
        "}))"
    )


def _present_hyprland_window(
    pid: int,
    workspace_id: int,
    *,
    timeout: float = 6.0,
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = _hyprctl("clients", "-j")
            payload = json.loads(result.stdout) if result.returncode == 0 else []
            address = _window_address_for_pid(payload, pid)
            if address is not None:
                moved = _hyprctl(
                    "eval",
                    _move_window_expression(address, workspace_id),
                )
                return moved.returncode == 0
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            return False
        time.sleep(0.1)
    return False


def present_child_window(
    process: Any,
    *,
    workspace_id: int | None = None,
) -> bool:
    """Move/focus a launched child window on Hyprland, asynchronously.

    Other desktop environments are deliberately left to their native window
    activation handling.  The boolean only indicates whether presentation was
    scheduled; the operation itself remains best effort.
    """

    if process is None or not is_hyprland_session():
        return False
    if shutil.which("hyprctl") is None:
        return False
    target_workspace = workspace_id or active_hyprland_workspace()
    try:
        pid = int(process.pid)
    except (AttributeError, TypeError, ValueError):
        return False
    if pid <= 0 or target_workspace is None:
        return False

    threading.Thread(
        target=_present_hyprland_window,
        args=(pid, target_workspace),
        daemon=True,
        name="present-child-window",
    ).start()
    return True
