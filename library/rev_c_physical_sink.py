# SPDX-License-Identifier: GPL-3.0-or-later
"""Guarded one-shot physical sink for the Rev. C 480x480 display.

This module deliberately supports only one complete frame. Continuous updates
and partial physical writes remain disabled until the one-shot path has been
validated on real hardware. The caller must provide an explicit device path,
acknowledge that the normal monitor is stopped, and repeat a confirmation token.
"""

from __future__ import annotations

import fcntl
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from PIL import Image


CONFIRMATION_TEXT = "WRITE-REV-C-480X480"
DEFAULT_LOCK_PATH = Path("/tmp/turing-html-theme-rev-c-physical.lock")


class PhysicalWriteRefused(ValueError):
    """Raised before physical I/O when a safety precondition is not met."""


@dataclass(frozen=True)
class PhysicalWriteResult:
    port: str
    width: int
    height: int
    initialized: bool
    frame_written: bool
    serial_closed: bool
    physical_io: bool = True

    def as_dict(self):
        return {
            "port": self.port,
            "width": self.width,
            "height": self.height,
            "initialized": self.initialized,
            "frameWritten": self.frame_written,
            "serialClosed": self.serial_closed,
            "physicalIo": self.physical_io,
        }


def _validate_port(port: str, *, require_device: bool) -> str:
    candidate = str(port or "").strip()
    if not candidate:
        raise PhysicalWriteRefused("an explicit serial device path is required")
    if not os.path.isabs(candidate) or not candidate.startswith("/dev/"):
        raise PhysicalWriteRefused("the serial device must be an absolute /dev path")

    resolved = os.path.realpath(candidate)
    if require_device:
        try:
            metadata = os.stat(resolved)
        except OSError as exc:
            raise PhysicalWriteRefused(
                f"serial device is unavailable: {candidate}"
            ) from exc
        if not stat.S_ISCHR(metadata.st_mode):
            raise PhysicalWriteRefused(
                f"serial device is not a character device: {candidate}"
            )
    return candidate


def _validate_parity(parity) -> None:
    if not bool(getattr(parity, "valid", False)):
        raise PhysicalWriteRefused("production serializer parity is not valid")
    if bool(getattr(parity, "physical_io", False)):
        raise PhysicalWriteRefused("parity input unexpectedly reports physical I/O")
    if str(getattr(parity, "mode", "")) != "full":
        raise PhysicalWriteRefused("the first physical test requires a full frame")
    if getattr(parity, "mismatch_offset", None) is not None:
        raise PhysicalWriteRefused("production serializer bytes do not match")

    expected = bytes(getattr(parity, "expected_wire", b""))
    production = bytes(getattr(parity, "production_wire", b""))
    if not expected or expected != production:
        raise PhysicalWriteRefused("production serializer wire image is incomplete")


def _default_driver_factory(port: str):
    from library.lcd.lcd_comm_rev_c import LcdCommRevC

    return LcdCommRevC(
        com_port=port,
        display_width=480,
        display_height=480,
    )


def write_full_frame_once(
    frame: Image.Image,
    parity,
    *,
    port: str,
    confirmation: str,
    monitor_stopped: bool,
    driver_factory: Optional[Callable[[str], object]] = None,
    lock_path: Path = DEFAULT_LOCK_PATH,
) -> PhysicalWriteResult:
    """Write exactly one validated full frame through the production driver."""
    if str(confirmation or "") != CONFIRMATION_TEXT:
        raise PhysicalWriteRefused(
            f"confirmation must be exactly {CONFIRMATION_TEXT!r}"
        )
    if not monitor_stopped:
        raise PhysicalWriteRefused(
            "the normal monitor must be stopped before opening the display"
        )

    current = frame.convert("RGBA")
    current.load()
    if current.size != (480, 480):
        raise PhysicalWriteRefused(
            f"one-shot Rev. C test requires 480x480; received {current.size}"
        )
    _validate_parity(parity)

    factory = driver_factory or _default_driver_factory
    device = _validate_port(port, require_device=driver_factory is None)
    lock_file_path = Path(lock_path).expanduser().resolve()
    lock_file_path.parent.mkdir(parents=True, exist_ok=True)

    initialized = False
    frame_written = False
    serial_closed = False
    driver = None

    with lock_file_path.open("a+b") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PhysicalWriteRefused(
                "another guarded physical display test is already running"
            ) from exc

        try:
            from library.lcd.lcd_comm import Orientation

            driver = factory(device)
            driver.InitializeComm()
            initialized = True
            driver.SetOrientation(Orientation.LANDSCAPE)
            driver.DisplayPILImage(
                current,
                x=0,
                y=0,
                image_width=480,
                image_height=480,
            )
            frame_written = True
        finally:
            if driver is not None:
                close = getattr(driver, "closeSerial", None)
                if callable(close):
                    close()
                    serial_closed = True
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    return PhysicalWriteResult(
        port=device,
        width=480,
        height=480,
        initialized=initialized,
        frame_written=frame_written,
        serial_closed=serial_closed,
    )
