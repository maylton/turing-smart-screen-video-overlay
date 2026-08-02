# SPDX-License-Identifier: GPL-3.0-or-later
"""Guarded, observable live updates for the Rev. C 480x480 display.

The session sends one validated full frame followed by a small, bounded number
of validated partial frames. Physical writes use the exact protocol blocks that
passed production parity. Every requested status read is retained instead of
being discarded by the production driver's private command helper.
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
from library.rev_c_status_transport import (
    RevCStatusBatch,
    send_protocol_with_status,
)


LIVE_CONFIRMATION_TEXT = "LIVE-REV-C-480X480"
MAX_ALLOWED_PARTIAL_FRAMES = 60
MAX_ALLOWED_DURATION = 120.0
MIN_ALLOWED_INTERVAL = 0.75
MAX_ALLOWED_REGIONS = 32
MAX_ALLOWED_BATCH_REGIONS = 16
MAX_ALLOWED_WIRE_BYTES = 500_000
MIN_ALLOWED_REGION_PACING = 0.05
MAX_ALLOWED_REGION_PACING = 2.0
MIN_ALLOWED_BATCH_PACING = 0.05
MAX_ALLOWED_BATCH_PACING = 3.0
MAX_ALLOWED_MINIMUM_STATUS_BYTES = 1024


class LiveWriteRefused(PhysicalWriteRefused):
    """Raised before or during a live session when a safety limit is violated."""


@dataclass(frozen=True)
class LiveUpdateResult:
    sequence: int
    region_count: int
    wire_bytes: int
    partial_frame_number: int
    status_batch: RevCStatusBatch
    batch_count: int = 1
    physical_io: bool = True


@dataclass(frozen=True)
class LiveSessionSummary:
    port: str
    partial_frames_written: int
    status_responses: int
    serial_closed: bool
    physical_io: bool = True


def _protocol_wire(protocol) -> bytes:
    wire = getattr(protocol, "wire", None)
    if wire is not None:
        return bytes(wire)
    return b"".join(
        bytes(getattr(block, "wire", b""))
        for exchange in tuple(getattr(protocol, "exchanges", ()))
        for block in tuple(getattr(exchange, "blocks", ()))
    )


def _validate_protocol_parity(protocol, parity, expected_mode: str) -> None:
    if not bool(getattr(protocol, "valid", False)):
        raise LiveWriteRefused("Rev. C framing validation failed")
    if str(getattr(protocol, "mode", "")) != expected_mode:
        raise LiveWriteRefused(
            f"Rev. C protocol mode must be {expected_mode!r}"
        )
    parity_mode = str(getattr(parity, "mode", ""))
    if parity_mode != expected_mode:
        raise LiveWriteRefused(
            f"production parity mode must be {expected_mode!r}"
        )
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
    protocol_wire = _protocol_wire(protocol)
    if not expected_wire or expected_wire != production_wire:
        raise LiveWriteRefused("production serializer wire image is incomplete")
    if protocol_wire != expected_wire:
        raise LiveWriteRefused(
            "protocol wire image differs from production serializer parity"
        )


class GuardedRevCLiveSession:
    """Open one Rev. C device and apply a bounded stream of observable updates."""

    def __init__(
        self,
        initial_frame: Image.Image,
        initial_protocol,
        initial_parity,
        *,
        port: str,
        confirmation: str,
        monitor_stopped: bool,
        max_partial_frames: int = 5,
        max_duration: float = 30.0,
        min_interval: float = 2.0,
        max_regions: int = 4,
        batch_regions: Optional[int] = None,
        max_wire_bytes: int = 300_000,
        region_pacing: float = 0.25,
        batch_pacing: Optional[float] = None,
        minimum_status_bytes: int = 1,
        driver_factory: Optional[Callable[[str], object]] = None,
        lock_path: Path = DEFAULT_LOCK_PATH,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
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
        self.batch_regions = int(
            self.max_regions if batch_regions is None else batch_regions
        )
        self.max_wire_bytes = int(max_wire_bytes)
        self.region_pacing = float(region_pacing)
        self.batch_pacing = float(
            self.region_pacing if batch_pacing is None else batch_pacing
        )
        self.minimum_status_bytes = int(minimum_status_bytes)
        self._validate_limits()

        frame = initial_frame.convert("RGBA")
        frame.load()
        if frame.size != (480, 480):
            raise LiveWriteRefused(
                f"live Rev. C test requires 480x480; received {frame.size}"
            )
        _validate_parity(initial_parity)
        _validate_protocol_parity(initial_protocol, initial_parity, "full")

        self._driver_factory = driver_factory or _default_driver_factory
        self._uses_production_driver = driver_factory is None
        self.port = _validate_port(
            port,
            require_device=self._uses_production_driver,
        )
        self._clock = clock
        self._sleeper = sleeper
        self._lock_path = Path(lock_path).expanduser().resolve()
        self._lock_file = None
        self._driver = None
        self._started_at = 0.0
        self._last_write_at = 0.0
        self._partial_frames_written = 0
        self._status_responses = 0
        self._initial_status_batch = None
        self._closed = False
        self._serial_closed = False
        self._last_sequence = int(getattr(initial_parity, "sequence", 0))

        self._open_and_write_initial(initial_protocol)

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
        if not 1 <= self.batch_regions <= MAX_ALLOWED_BATCH_REGIONS:
            raise LiveWriteRefused(
                "batch_regions must be between 1 and "
                f"{MAX_ALLOWED_BATCH_REGIONS}"
            )
        if self.batch_regions > self.max_regions:
            raise LiveWriteRefused(
                "batch_regions must not exceed the total max_regions limit"
            )
        if not 1 <= self.max_wire_bytes <= MAX_ALLOWED_WIRE_BYTES:
            raise LiveWriteRefused(
                f"max_wire_bytes must be between 1 and {MAX_ALLOWED_WIRE_BYTES}"
            )
        if not (
            MIN_ALLOWED_REGION_PACING
            <= self.region_pacing
            <= MAX_ALLOWED_REGION_PACING
        ):
            raise LiveWriteRefused(
                "region_pacing must be between "
                f"{MIN_ALLOWED_REGION_PACING} and "
                f"{MAX_ALLOWED_REGION_PACING} seconds"
            )
        if not (
            MIN_ALLOWED_BATCH_PACING
            <= self.batch_pacing
            <= MAX_ALLOWED_BATCH_PACING
        ):
            raise LiveWriteRefused(
                "batch_pacing must be between "
                f"{MIN_ALLOWED_BATCH_PACING} and "
                f"{MAX_ALLOWED_BATCH_PACING} seconds"
            )
        if not (
            1
            <= self.minimum_status_bytes
            <= MAX_ALLOWED_MINIMUM_STATUS_BYTES
        ):
            raise LiveWriteRefused(
                "minimum_status_bytes must be between 1 and "
                f"{MAX_ALLOWED_MINIMUM_STATUS_BYTES}"
            )

    def _open_and_write_initial(self, protocol) -> None:
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

            driver = self._driver_factory(self.port)
            self._driver = driver
            driver.InitializeComm()
            driver.SetOrientation(Orientation.LANDSCAPE)
            batch = send_protocol_with_status(
                driver,
                protocol,
                minimum_status_bytes=self.minimum_status_bytes,
                inter_exchange_delay=0.0,
                exchange_batch_size=1,
                inter_batch_delay=0.0,
                sleeper=self._sleeper,
                clock=self._clock,
            )
            self._initial_status_batch = batch
            self._status_responses += len(batch.samples)
            now = self._clock()
            self._started_at = now
            self._last_write_at = now
        except Exception:
            self.close()
            raise

    @property
    def initial_status_batch(self) -> RevCStatusBatch:
        if self._initial_status_batch is None:
            raise LiveWriteRefused("initial status batch is unavailable")
        return self._initial_status_batch

    @property
    def partial_frames_written(self) -> int:
        return self._partial_frames_written

    @property
    def status_responses(self) -> int:
        return self._status_responses

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

        packets = tuple(getattr(transport, "packets", ()))
        exchanges = tuple(getattr(protocol, "exchanges", ()))
        mode = "partial" if packets else "noop"
        _validate_protocol_parity(protocol, parity, mode)
        if len(packets) != len(exchanges):
            raise LiveWriteRefused(
                "transport packet count differs from protocol exchanges"
            )
        if len(packets) > self.max_regions:
            raise LiveWriteRefused(
                f"partial update has {len(packets)} total regions; "
                f"limit is {self.max_regions}"
            )

        wire_bytes = int(getattr(protocol, "wire_bytes", 0))
        if wire_bytes > self.max_wire_bytes:
            raise LiveWriteRefused(
                f"partial update requires {wire_bytes} wire bytes; "
                f"limit is {self.max_wire_bytes}"
            )

        sequence = int(getattr(parity, "sequence", 0))
        if sequence <= self._last_sequence:
            raise LiveWriteRefused("partial update sequence did not increase")

        batch = send_protocol_with_status(
            self._driver,
            protocol,
            minimum_status_bytes=self.minimum_status_bytes,
            inter_exchange_delay=self.region_pacing,
            exchange_batch_size=self.batch_regions,
            inter_batch_delay=self.batch_pacing,
            sleeper=self._sleeper,
            clock=self._clock,
        )
        self._status_responses += len(batch.samples)
        self._last_sequence = sequence
        if packets:
            self._partial_frames_written += 1
            self._last_write_at = self._clock()

        return LiveUpdateResult(
            sequence=sequence,
            region_count=len(packets),
            wire_bytes=wire_bytes,
            partial_frame_number=self._partial_frames_written,
            status_batch=batch,
            batch_count=batch.batch_count,
        )

    def close(self) -> LiveSessionSummary:
        if self._closed:
            return LiveSessionSummary(
                port=self.port,
                partial_frames_written=self._partial_frames_written,
                status_responses=self._status_responses,
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
            status_responses=self._status_responses,
            serial_closed=self._serial_closed,
        )

    def __enter__(self) -> "GuardedRevCLiveSession":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        self.close()
        return False
