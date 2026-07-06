# SPDX-License-Identifier: GPL-3.0-or-later
"""Overview display lifecycle status for the main GTK app.

The helpers in this module are passive: they enumerate serial descriptors and
read the runtime controller state, but they do not open the display serial port
or send commands to the display.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class DisplayLifecycleSummary:
    state: str
    title: str
    subtitle: str


def _owner_description(state: Any) -> str:
    owner = getattr(state, "owner", None)
    if owner is None:
        return "unknown owner"
    describe = getattr(owner, "describe", None)
    if callable(describe):
        try:
            return str(describe())
        except Exception:
            pass
    pid = getattr(owner, "pid", None)
    role = getattr(owner, "role", None)
    if pid and role:
        return f"{role} (PID {pid})"
    if pid:
        return f"PID {pid}"
    return str(owner)


def _port_haystack(port: Any) -> str:
    return " ".join(
        str(getattr(port, attr, "") or "")
        for attr in ("description", "manufacturer", "product", "interface")
    ).casefold()


def _classify_ports(ports: Sequence[Any]) -> tuple[list[str], list[str]]:
    real_tty_acm: list[str] = []
    usb_monitor: list[str] = []

    for port in ports:
        device = str(getattr(port, "device", "") or "")
        if not device:
            continue

        haystack = _port_haystack(port)
        if "usbmonitor" in haystack:
            usb_monitor.append(device)
        elif device.startswith("/dev/ttyACM"):
            real_tty_acm.append(device)

    return sorted(set(real_tty_acm)), sorted(set(usb_monitor))


def _serial_ports() -> tuple[list[Any], str]:
    try:
        from serial.tools import list_ports
    except Exception as exc:
        return [], f"pyserial unavailable: {exc}"

    try:
        return list(list_ports.comports()), ""
    except Exception as exc:
        return [], f"serial scan failed: {exc}"


def read_display_lifecycle(window: Any) -> DisplayLifecycleSummary:
    """Return a passive lifecycle summary for the Overview status row."""

    runtime_state = None
    controller = getattr(window, "runtime_controller", None)
    if controller is not None:
        try:
            runtime_state = controller.state()
        except Exception as exc:
            return DisplayLifecycleSummary(
                "unknown",
                "Unknown",
                f"Could not read runtime state: {exc}",
            )

    ports, serial_error = _serial_ports()
    real_tty_acm, usb_monitor = _classify_ports(ports)

    if runtime_state is not None and getattr(runtime_state, "monitor_running", False):
        owner = getattr(runtime_state, "owner", None)
        pid = getattr(owner, "pid", None)
        detail = f"Monitor running (PID {pid})" if pid else "Monitor running"
        if real_tty_acm:
            detail += f" · {', '.join(real_tty_acm)}"
        return DisplayLifecycleSummary("running", "Running", detail)

    if runtime_state is not None and getattr(runtime_state, "busy", False):
        return DisplayLifecycleSummary(
            "busy",
            "Busy",
            "Display is in use by " + _owner_description(runtime_state),
        )

    if real_tty_acm:
        return DisplayLifecycleSummary(
            "tty_ready",
            "Ready",
            f"Real display port ready: {', '.join(real_tty_acm)}",
        )

    if usb_monitor:
        return DisplayLifecycleSummary(
            "usbmonitor_waking",
            "Waking",
            f"UsbMonitor visible ({', '.join(usb_monitor)}); waiting for ttyACM",
        )

    if serial_error:
        return DisplayLifecycleSummary("unknown", "Unknown", serial_error)

    return DisplayLifecycleSummary(
        "disconnected",
        "Disconnected",
        "No real ttyACM display or UsbMonitor endpoint detected",
    )


def install_main_app_display_lifecycle(app: Any) -> None:
    """Patch SmartScreenWindow so Overview displays the passive display state."""

    window_class = getattr(app, "SmartScreenWindow", None)
    if window_class is None or getattr(window_class, "_display_lifecycle_installed", False):
        return

    original_init = window_class.__init__
    original_refresh_overview = window_class.refresh_overview

    def update_display_lifecycle_status(self) -> DisplayLifecycleSummary | None:
        row = getattr(self, "detection_status_row", None)
        if row is None or getattr(self, "detection_running", False):
            return None

        summary = read_display_lifecycle(self)

        try:
            row.set_title("Display state")
        except Exception:
            pass

        try:
            row.set_subtitle(f"{summary.title} · {summary.subtitle}")
        except Exception:
            pass

        return summary

    def refresh_display_lifecycle_status(self) -> bool:
        update_display_lifecycle_status(self)
        return True

    def patched_refresh_overview(self):
        result = original_refresh_overview(self)
        update_display_lifecycle_status(self)
        return result

    def patched_init(self, application):
        original_init(self, application)
        update_display_lifecycle_status(self)
        try:
            app.GLib.timeout_add_seconds(2, self.refresh_display_lifecycle_status)
        except Exception:
            pass

    window_class.update_display_lifecycle_status = update_display_lifecycle_status
    window_class.refresh_display_lifecycle_status = refresh_display_lifecycle_status
    window_class.refresh_overview = patched_refresh_overview
    window_class.__init__ = patched_init
    window_class._display_lifecycle_installed = True
