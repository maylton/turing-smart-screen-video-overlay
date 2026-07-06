# SPDX-License-Identifier: GPL-3.0-or-later
"""Passive display lifecycle state model for the GTK app.

This module intentionally does not open the display serial port.  It only reads
serial descriptors, process state, and optional passive device-owner data so the
UI can explain what the app thinks the display is doing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]

STATE_DISCONNECTED = "disconnected"
STATE_USBMONITOR_WAKING = "usbmonitor_waking"
STATE_TTY_READY = "tty_ready"
STATE_BUSY = "busy"
STATE_RUNNING = "running"
STATE_UNKNOWN = "unknown"


@dataclass(frozen=True)
class DisplayLifecycleState:
    """A small, UI-friendly snapshot of the passive display state."""

    state: str
    label: str
    details: str
    severity: str
    real_tty_acm: tuple[str, ...] = ()
    usb_monitor: tuple[str, ...] = ()
    monitor_pids: tuple[int, ...] = ()
    busy_pids: tuple[int, ...] = ()
    selected_detection: dict[str, Any] | None = None
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _get(obj: Any, name: str, default: Any = None) -> Any:
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


def _port_device(port: Any) -> str:
    return str(_get(port, "device", _get(port, "name", "")) or "")


def _port_haystack(port: Any) -> str:
    if isinstance(port, dict) and "error" in port:
        return str(port.get("error") or "").casefold()
    return " ".join(
        str(_get(port, attr, "") or "")
        for attr in ("description", "manufacturer", "product", "interface")
    ).casefold()


def _is_tty_acm(port: Any) -> bool:
    explicit = _get(port, "is_tty_acm")
    if explicit is not None:
        return bool(explicit)
    return _port_device(port).startswith("/dev/ttyACM")


def _is_usb_monitor(port: Any) -> bool:
    explicit = _get(port, "is_usb_monitor")
    if explicit is not None:
        return bool(explicit)
    return "usbmonitor" in _port_haystack(port)


def system_serial_ports() -> tuple[list[Any], tuple[str, ...]]:
    """Return serial port descriptors without opening any port."""

    try:
        from serial.tools.list_ports import comports
    except Exception as exc:
        return [], (f"pyserial unavailable: {exc}",)

    try:
        return list(comports()), ()
    except Exception as exc:
        return [], (f"could not enumerate serial ports: {exc}",)


def classify_serial_ports(ports: Sequence[Any]) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Split descriptors into real ttyACM candidates, UsbMonitor endpoints, and warnings."""

    real: list[str] = []
    usb_monitor: list[str] = []
    warnings: list[str] = []

    for port in ports:
        if isinstance(port, dict) and "error" in port:
            warnings.append(str(port.get("error") or "serial enumeration failed"))
            continue

        device = _port_device(port)
        if not device:
            continue
        if _is_usb_monitor(port):
            usb_monitor.append(device)
        elif _is_tty_acm(port):
            real.append(device)

    return tuple(sorted(set(real))), tuple(sorted(set(usb_monitor))), tuple(warnings)


def monitor_pids(root: str | os.PathLike[str] = ROOT) -> tuple[int, ...]:
    """Find the backend display monitor process without touching the serial port."""

    root = Path(root)
    patterns = [
        str(root / "main.py"),
        r"[m]ain.py",
    ]
    pids: set[int] = set()
    current_pid = os.getpid()

    for pattern in patterns:
        try:
            result = subprocess.run(
                ["pgrep", "-f", pattern],
                cwd=str(root),
                text=True,
                capture_output=True,
                timeout=3,
                check=False,
            )
        except Exception:
            continue

        for line in result.stdout.splitlines():
            try:
                pid = int(line.strip())
            except ValueError:
                continue
            if pid != current_pid:
                pids.add(pid)

    return tuple(sorted(pids))


def _device_owner_pids(devices: Sequence[str]) -> tuple[tuple[int, ...], tuple[str, ...]]:
    """Best-effort passive ownership check using fuser when available."""

    existing = [device for device in devices if device and Path(device).exists()]
    if not existing:
        return (), ()
    if shutil.which("fuser") is None:
        return (), ("fuser unavailable; serial ownership could not be inspected",)

    try:
        result = subprocess.run(
            ["fuser", *existing],
            text=True,
            capture_output=True,
            timeout=3,
            check=False,
        )
    except Exception as exc:
        return (), (f"serial ownership check failed: {exc}",)

    pids: set[int] = set()
    for token in (result.stdout + "\n" + result.stderr).replace(":", " ").split():
        try:
            pid = int(token)
        except ValueError:
            continue
        if pid != os.getpid():
            pids.add(pid)

    return tuple(sorted(pids)), ()


def _selected_detection(root: str | os.PathLike[str], ports: Sequence[Any]) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    """Run the existing passive detector and return the selected display, if any."""

    try:
        from library import display_detection
    except Exception as exc:
        return None, (f"display detection unavailable: {exc}",)

    try:
        detections = display_detection.detect(root, ports=ports)
        selected = display_detection.select(detections)
    except Exception as exc:
        return None, (f"display detection failed: {exc}",)

    if selected is None:
        return None, ()
    try:
        return selected.to_dict(), ()
    except Exception:
        return {"label": str(getattr(selected, "label", "detected display"))}, ()


def _state(
    state: str,
    label: str,
    details: str,
    severity: str,
    *,
    real_tty_acm: Sequence[str] = (),
    usb_monitor: Sequence[str] = (),
    monitor_pids: Sequence[int] = (),
    busy_pids: Sequence[int] = (),
    selected_detection: dict[str, Any] | None = None,
    warnings: Sequence[str] = (),
) -> DisplayLifecycleState:
    return DisplayLifecycleState(
        state=state,
        label=label,
        details=details,
        severity=severity,
        real_tty_acm=tuple(real_tty_acm),
        usb_monitor=tuple(usb_monitor),
        monitor_pids=tuple(monitor_pids),
        busy_pids=tuple(busy_pids),
        selected_detection=selected_detection,
        warnings=tuple(warnings),
    )


def get_display_lifecycle_state(
    root: str | os.PathLike[str] = ROOT,
    *,
    serial_ports: Sequence[Any] | None = None,
    monitor_processes: Sequence[int] | None = None,
) -> DisplayLifecycleState:
    """Return the current passive display lifecycle state.

    The priority order is intentionally user-facing:
    running monitor process → serial busy → real ttyACM ready → UsbMonitor waking
    → disconnected/unknown.
    """

    root = Path(root)
    warnings: list[str] = []

    if serial_ports is None:
        ports, port_warnings = system_serial_ports()
        warnings.extend(port_warnings)
    else:
        ports = list(serial_ports)

    real_tty_acm, usb_monitor, classify_warnings = classify_serial_ports(ports)
    warnings.extend(classify_warnings)

    selected_detection, detection_warnings = _selected_detection(root, ports)
    warnings.extend(detection_warnings)

    pids = tuple(sorted(int(pid) for pid in (monitor_processes if monitor_processes is not None else monitor_pids(root))))
    busy_pids, owner_warnings = _device_owner_pids(real_tty_acm)
    warnings.extend(owner_warnings)

    devices_text = ", ".join(real_tty_acm) if real_tty_acm else "no real ttyACM device"
    usb_text = ", ".join(usb_monitor) if usb_monitor else "none"

    if warnings and not ports and not real_tty_acm and not usb_monitor:
        return _state(
            STATE_UNKNOWN,
            "Display: unknown",
            warnings[0],
            "warning",
            real_tty_acm=real_tty_acm,
            usb_monitor=usb_monitor,
            monitor_pids=pids,
            busy_pids=busy_pids,
            selected_detection=selected_detection,
            warnings=warnings,
        )

    if pids:
        return _state(
            STATE_RUNNING,
            "Display: running",
            f"Monitor PID(s) {', '.join(map(str, pids))}; {devices_text}",
            "success",
            real_tty_acm=real_tty_acm,
            usb_monitor=usb_monitor,
            monitor_pids=pids,
            busy_pids=busy_pids,
            selected_detection=selected_detection,
            warnings=warnings,
        )

    if busy_pids:
        return _state(
            STATE_BUSY,
            "Display: busy",
            f"{devices_text} is in use by PID(s) {', '.join(map(str, busy_pids))}",
            "warning",
            real_tty_acm=real_tty_acm,
            usb_monitor=usb_monitor,
            monitor_pids=pids,
            busy_pids=busy_pids,
            selected_detection=selected_detection,
            warnings=warnings,
        )

    if real_tty_acm:
        detection_label = ""
        if selected_detection:
            detection_label = str(selected_detection.get("label") or "").strip()
        suffix = f" · {detection_label}" if detection_label else ""
        return _state(
            STATE_TTY_READY,
            "Display: ready",
            f"{devices_text}; no monitor process detected{suffix}",
            "success",
            real_tty_acm=real_tty_acm,
            usb_monitor=usb_monitor,
            monitor_pids=pids,
            busy_pids=busy_pids,
            selected_detection=selected_detection,
            warnings=warnings,
        )

    if usb_monitor:
        return _state(
            STATE_USBMONITOR_WAKING,
            "Display: waking",
            f"UsbMonitor endpoint(s): {usb_text}; waiting for a real ttyACM display",
            "warning",
            real_tty_acm=real_tty_acm,
            usb_monitor=usb_monitor,
            monitor_pids=pids,
            busy_pids=busy_pids,
            selected_detection=selected_detection,
            warnings=warnings,
        )

    return _state(
        STATE_DISCONNECTED,
        "Display: disconnected",
        "No real ttyACM display or UsbMonitor endpoint detected",
        "error",
        real_tty_acm=real_tty_acm,
        usb_monitor=usb_monitor,
        monitor_pids=pids,
        busy_pids=busy_pids,
        selected_detection=selected_detection,
        warnings=warnings,
    )
