# SPDX-License-Identifier: GPL-3.0-or-later
"""Guarded, bounded live updates for the Rev. C 480x480 display.

The session sends one validated full frame, followed by a limited number of
validated partial frames. It never discovers a port automatically and refuses
updates that exceed conservative region or wire-size budgets.
"""

from __future__ import annotations

import fcntl
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from PIL import Image

from library.rev_c_physical_sink import (
    DEFAULT_LOCK_PATH,
    PhysicalWriteRefused,
    _default_driver_factory,
    _validate_parity,
    _validate_port,
)


LIVE_CONFIRMATION_TEXT = "LIVE-REV-C-480X480"
MAX_ALLOWED_PARTIAL_FRAMES = 60
MAX_ALLOWED_DURATION = 120.0
MIN_ALLOWED_INTERVAL = 0.75
MAX_ALLOWED_REGIONS = 32
MAX_ALLOWED_WIRE_BYTES = 500_000


class LiveWriteRefused(PhysicalWriteRefused):
    """Raised before or during a live session when a safety limit is violated."""


@dataclass(frozen=True)
class LiveUpdateResult:
    sequence: int
    region_count: int
    wire_bytes: int
    partial_frame_number: int
    physical_io: bool = True


@dataclass(frozen=True)
class LiveSessionSummary:
    port: str
    partial_frames_written: int
    serial_closed: bool
    physical_io: bool = True


class GuardedRevCLiveSession:
    """Open one Rev. C device and apply a bounded stream of partial updates."""

    def __init__(
        self,
        initial_frame: Image.Image,
        initial_parity,
        *,
        port: str,
        confirmation: str,
        monitor_stopped: bool,
        max_partial_frames: int = 15,
        max_duration: float = 30.0,
        min_interval: float = 1.0,
        max_regions: int = 16,
        max_wire_bytes: int = 300_000,
        driver_factory: Optional[Callable[[str], object]] = None,
        lock_path: Path = DEFAULT_LOCK_PATH,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if str(confirmation or "") != LIVE_CONFIRMATION_TEXT:
            raise LiveWriteRefused(
                f"confirmation must be exactly {LIVE_CONFIRMATION_TEXT!r}"
            )
        if not monitor_stopped:
            raise LiveWriteRefused(
                "the normal monitor must be stopped before opening the display"
            )

        self.max_partial_frames = int(max_partial_frames)
        self.max_duration = float(max_duration)
        self.min_interval = float(min_interval)
        self.max_regions = int(max_regions)
        self.max_wire_bytes = int(max_wire_bytes)
        self._validate_limits()

        frame = initial_frame.convert("RGBA")
        frame.load()
        if frame.size != (480, 480):
            raise LiveWriteRefused(
                f"live Rev. C test requires 480x480; received {frame.size}"
            )
        _validate_parity(initial_parity)
        if str(getattr(initial_parity, "mode", "")) != "full":
            raise LiveWriteRefused("the live session must start with a full frame")

        self._driver_factory = driver_factory or _default_driver_factory
        self._uses_production_driver = driver_factory is None
        self.port = _validate_port(
            port,
            require_device=self._uses_production_driver,
        )
        self._clock = clock
        self._lock_path = Path(lock_path).expanduser().resolve()
        self._lock_file = None
        self._driver = None
        self._started_at = 0.0
        self._last_write_at = 0.0
        self._partial_frames_written = 0
        self._closed = False
        self._serial_closed = False
        self._last_sequence = int(getattr(initial_parity, "sequence", 0))

        self._open_and_write_initial(frame)

    def _validate_limits(self) -> None:
        if not 1 <= self.max_partial_frames <= MAX_ALLOWED_PARTIAL_FRAMES:
            raise LiveWriteRefused(
                f"max_partial_frames must be between 1 and "
                f"{MAX_ALLOWED_PARTIAL_FRAMES}"
            )
        if not 1.0 <= self.max_duration <= MAX_ALLOWED_DURATION:
            raise LiveWriteRefused(
                f"max_duration must be between 1 and {MAX_ALLOWED_DURATION} seconds"
            )
        if self.min_interval < MIN_ALLOWED_INTERVAL:
            raise LiveWriteRefused(
                f"min_interval must be at least {MIN_ALLOWED_INTERVAL} seconds"
            )
        if not 1 <= self.max_regions <= MAX_ALLOWED_REGIONS:
            raise LiveWriteRefused(
                f"max_regions must be between 1 and {MAX_ALLOWED_REGIONS}"
            )
        if not 1 <= self.max_wire_bytes <= MAX_ALLOWED_WIRE_BYTES:
            raise LiveWriteRefused(
                f"max_wire_bytes must be between 1 and {MAX_ALLOWED_WIRE_BYTES}"
            )

    def _open_and_write_initial(self, frame: Image.Image) -> None:
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = self._lock_path.open("a+b")
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            lock_file.close()
            raise LiveWriteRefused(
                "another guarded physical display test is already running"
            ) from exc

        self._lock_file = lock_file
        try:
            from library.lcd.lcd_comm import Orientation
            from library.lcd.lcd_comm_rev_c import Count

            Count.Start = 0
            driver = self._driver_factory(self.port)
            self._driver = driver
            driver.InitializeComm()
            driver.SetOrientation(Orientation.LANDSCAPE)
            driver.DisplayPILImage(
                frame,
                x=0,
                y=0,
                image_width=480,
                image_height=480,
            )
            now = self._clock()
            self._started_at = now
            self._last_write_at = now
        except Exception:
            self.close()
            raise

    @property
    def partial_frames_written(self) -> int:
        return self._partial_frames_written

    @property
    def elapsed(self) -> float:
        if not self._started_at:
            return 0.0
        return max(0.0, self._clock() - self._started_at)

    @property
    def seconds_until_next_write(self) -> float:
        if not self._last_write_at:
            return 0.0
        return max(
            0.0,
            self.min_interval - (self._clock() - self._last_write_at),
        )

    @property
    def can_continue(self) -> bool:
        return (
            not self._closed
            and self._partial_frames_written < self.max_partial_frames
            and self.elapsed < self.max_duration
        )

    def submit_partial(
        self,
        frame: Image.Image,
        transport,
        protocol,
        parity,
    ) -> LiveUpdateResult:
        if self._closed or self._driver is None:
            raise LiveWriteRefused("the live session is already closed")
        if not self.can_continue:
            raise LiveWriteRefused("the live session safety budget is exhausted")
        if self.seconds_until_next_write > 0:
            raise LiveWriteRefused("the live update interval has not elapsed")

        current = frame.convert("RGBA")
        current.load()
        if current.size != (480, 480):
            raise LiveWriteRefused(
                f"partial Rev. C frame must be 480x480; received {current.size}"
            )
        if bool(getattr(transport, "full_refresh", True)):
            raise LiveWriteRefused(
                "an unexpected full refresh was requested after session start"
            )
        if not bool(getattr(transport, "roundtrip_matches", False)):
            raise LiveWriteRefused("transport roundtrip validation failed")
        if not bool(getattr(protocol, "valid", False)):
            raise LiveWriteRefused("Rev. C framing validation failed")
        parity_mode = str(getattr(parity, "mode", ""))
        if parity_mode not in {"partial", "noop"}:
            raise LiveWriteRefused("production parity is not a partial update")
        if not bool(getattr(parity, "valid", False)):
            raise LiveWriteRefused("production serializer parity is not valid")
        if bool(getattr(parity, "physical_io", False)):
            raise LiveWriteRefused(
                "production parity unexpectedly reports physical I/O"
            )
        if getattr(parity, "mismatch_offset", None) is not None:
            raise LiveWriteRefused("production serializer bytes do not match")
        expected_wire = bytes(getattr(parity, "expected_wire", b""))
        production_wire = bytes(getattr(parity, "production_wire", b""))
        if expected_wire != production_wire:
            raise LiveWriteRefused("production serializer wire images differ")
        if parity_mode == "partial" and not expected_wire:
            raise LiveWriteRefused(
                "production serializer partial wire image is incomplete"
            )

        sequence = int(getattr(parity, "sequence", 0))
        if sequence <= self._last_sequence:
            raise LiveWriteRefused("partial update sequence did not increase")

        packets = tuple(getattr(transport, "packets", ()))
        exchanges = tuple(getattr(protocol, "exchanges", ()))
        if len(packets) != len(exchanges):
            raise LiveWriteRefused(
                "transport packet count differs from protocol exchanges"
            )
        if len(packets) > self.max_regions:
            raise LiveWriteRefused(
                f"partial update has {len(packets)} regions; "
                f"limit is {self.max_regions}"
            )

        wire_bytes = int(getattr(protocol, "wire_bytes", 0))
        if wire_bytes > self.max_wire_bytes:
            raise LiveWriteRefused(
                f"partial update requires {wire_bytes} wire bytes; "
                f"limit is {self.max_wire_bytes}"
            )

        if self._uses_production_driver and packets:
            from library.lcd.lcd_comm_rev_c import Count

            expected_count = getattr(exchanges[0], "update_count", None)
            if expected_count is None or int(expected_count) != int(Count.Start):
                raise LiveWriteRefused(
                    "production update counter is not aligned with parity"
                )

        for packet in packets:
            region = packet.region
            crop = current.crop(
                (region.x, region.y, region.right, region.bottom)
            )
            self._driver.DisplayPILImage(
                crop,
                x=region.x,
                y=region.y,
                image_width=region.width,
                image_height=region.height,
            )

        self._last_sequence = sequence
        if packets:
            self._partial_frames_written += 1
            self._last_write_at = self._clock()

        return LiveUpdateResult(
            sequence=sequence,
            region_count=len(packets),
            wire_bytes=wire_bytes,
            partial_frame_number=self._partial_frames_written,
        )

    def close(self) -> LiveSessionSummary:
        if self._closed:
            return LiveSessionSummary(
                port=self.port,
                partial_frames_written=self._partial_frames_written,
                serial_closed=self._serial_closed,
            )

        self._closed = True
        driver = self._driver
        self._driver = None
        lock_file = self._lock_file
        self._lock_file = None
        try:
            if driver is not None:
                close = getattr(driver, "closeSerial", None)
                if callable(close):
                    try:
                        close()
                    finally:
                        self._serial_closed = True
        finally:
            if lock_file is not None:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                finally:
                    lock_file.close()

        return LiveSessionSummary(
            port=self.port,
            partial_frames_written=self._partial_frames_written,
            serial_closed=self._serial_closed,
        )

    def __enter__(self) -> "GuardedRevCLiveSession":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        self.close()
        return False
