# SPDX-License-Identifier: GPL-3.0-or-later
"""Passive, shared display lifecycle classification.

This module never opens or writes to the display serial port. It combines the
existing advisory runtime lock, serial descriptors and best-effort process
ownership information into one state used by diagnostics and UI surfaces.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from library.runtime import LockOwner, RuntimeState


class DisplayLifecycleState(str, Enum):
    DISCONNECTED = "disconnected"
    USBMONITOR_WAKING = "usbmonitor_waking"
    TTY_READY = "tty_ready"
    BUSY = "busy"
    RUNNING = "running"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DisplayLifecycleSnapshot:
    state: DisplayLifecycleState
    detail: str
    devices: Tuple[str, ...] = ()
    owner_pids: Tuple[int, ...] = ()
    runtime_owner: LockOwner = LockOwner()
    warning: str = ""

    def to_dict(self) -> Dict[str, Union[str, List[str], List[int], Dict[str, object]]]:
        payload = asdict(self)
        payload["state"] = self.state.value
        payload["devices"] = list(self.devices)
        payload["owner_pids"] = list(self.owner_pids)
        return payload


def _port_device(port: Mapping[str, object]) -> str:
    return str(port.get("device") or "")


def _unique_devices(ports: Iterable[Mapping[str, object]]) -> Tuple[str, ...]:
    return tuple(sorted({_port_device(port) for port in ports if _port_device(port)}))


def _parse_pids(text: str) -> Tuple[int, ...]:
    pids = set()
    for token in re.findall(r"(?<!\d)\d+(?!\d)", str(text or "")):
        try:
            pid = int(token)
        except ValueError:
            continue
        if pid > 0:
            pids.add(pid)
    return tuple(sorted(pids))


def _normalized_pids(values: Sequence[int]) -> Tuple[int, ...]:
    normalized = set()
    for value in values:
        try:
            pid = int(value)
        except (TypeError, ValueError):
            continue
        if pid > 0:
            normalized.add(pid)
    return tuple(sorted(normalized))


def device_owner_pids(device: str) -> Tuple[int, ...]:
    """Return best-effort fuser ownership without elevation or side effects."""
    if os.name != "posix" or not device or shutil.which("fuser") is None:
        return ()
    try:
        completed = subprocess.run(
            ["fuser", "-a", str(Path(device))],
            text=True,
            capture_output=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ()

    # GNU fuser writes the device label to stderr and numeric owners to stdout.
    # Parsing stderr can mistake the trailing number in /dev/ttyACM1 for PID 1.
    return _parse_pids(completed.stdout)


def inspect_display_lifecycle(
    serial_ports: Sequence[Mapping[str, object]],
    runtime_state: Optional[RuntimeState] = None,
    monitor_pids: Sequence[int] = (),
) -> DisplayLifecycleSnapshot:
    """Classify the passive display lifecycle with deterministic priorities."""
    runtime_state = runtime_state or RuntimeState(busy=False)
    fallback_monitor_pids = _normalized_pids(monitor_pids)

    real_ports = [
        port
        for port in serial_ports
        if bool(port.get("is_tty_acm")) and not bool(port.get("is_usb_monitor"))
    ]
    waking_ports = [port for port in serial_ports if bool(port.get("is_usb_monitor"))]
    real_devices = _unique_devices(real_ports)
    waking_devices = _unique_devices(waking_ports)

    if runtime_state.monitor_running:
        owner_pid = runtime_state.owner.pid
        pids = (owner_pid,) if owner_pid else fallback_monitor_pids
        return DisplayLifecycleSnapshot(
            state=DisplayLifecycleState.RUNNING,
            detail="The monitor owns the display channel.",
            devices=real_devices or waking_devices,
            owner_pids=pids,
            runtime_owner=runtime_state.owner,
        )

    if runtime_state.busy:
        owner_pid = runtime_state.owner.pid
        return DisplayLifecycleSnapshot(
            state=DisplayLifecycleState.BUSY,
            detail="The display channel is owned by another application operation.",
            devices=real_devices or waking_devices,
            owner_pids=(owner_pid,) if owner_pid else (),
            runtime_owner=runtime_state.owner,
        )

    if fallback_monitor_pids:
        return DisplayLifecycleSnapshot(
            state=DisplayLifecycleState.RUNNING,
            detail="A monitor process was found without current lock metadata.",
            devices=real_devices or waking_devices,
            owner_pids=fallback_monitor_pids,
            warning="Runtime lock metadata is missing or stale.",
        )

    if real_devices:
        owner_pids = tuple(
            sorted(
                {
                    pid
                    for device in real_devices
                    for pid in device_owner_pids(device)
                    if pid != os.getpid()
                }
            )
        )
        if owner_pids:
            return DisplayLifecycleSnapshot(
                state=DisplayLifecycleState.BUSY,
                detail="The serial device is open outside the application runtime lock.",
                devices=real_devices,
                owner_pids=owner_pids,
                warning="External serial ownership was detected with fuser.",
            )
        return DisplayLifecycleSnapshot(
            state=DisplayLifecycleState.TTY_READY,
            detail="The display serial device is ready.",
            devices=real_devices,
        )

    if waking_devices:
        return DisplayLifecycleSnapshot(
            state=DisplayLifecycleState.USBMONITOR_WAKING,
            detail="UsbMonitor is present while the ttyACM display device is still appearing.",
            devices=waking_devices,
        )

    if any("error" in port for port in serial_ports):
        return DisplayLifecycleSnapshot(
            state=DisplayLifecycleState.UNKNOWN,
            detail="Serial enumeration failed, so the display state is unknown.",
            warning="Review the serial diagnostics error.",
        )

    return DisplayLifecycleSnapshot(
        state=DisplayLifecycleState.DISCONNECTED,
        detail="No supported display serial descriptor was found.",
    )
