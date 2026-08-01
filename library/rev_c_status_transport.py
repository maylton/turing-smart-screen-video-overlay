# SPDX-License-Identifier: GPL-3.0-or-later
"""Observable physical transport for validated Revision C protocol blocks.

The caller supplies an already validated ``RevCProtocolAnalysis``. Every wire
block is written exactly as produced by the simulator/production parity path.
Unlike ``LcdCommRevC._send_command``, status reads are retained and returned to
the caller instead of being discarded.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

from library.frame_pipeline import FrameRegion


class RevCStatusError(RuntimeError):
    """Raised when an expected hardware status response is missing or invalid."""


@dataclass(frozen=True)
class RevCStatusSample:
    exchange_index: int
    exchange_name: str
    region: Optional[FrameRegion]
    block_name: str
    requested_bytes: int
    response: bytes
    elapsed_ms: float

    @property
    def received_bytes(self) -> int:
        return len(self.response)

    @property
    def nonzero_bytes(self) -> int:
        return sum(1 for value in self.response if value)

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.response).hexdigest()[:16]

    @property
    def prefix_hex(self) -> str:
        return self.response[:16].hex(" ")

    @property
    def suffix_hex(self) -> str:
        return self.response[-16:].hex(" ")

    def as_dict(self) -> Dict[str, object]:
        return {
            "exchangeIndex": self.exchange_index,
            "exchangeName": self.exchange_name,
            "region": self.region.as_dict() if self.region is not None else None,
            "blockName": self.block_name,
            "requestedBytes": self.requested_bytes,
            "receivedBytes": self.received_bytes,
            "nonzeroBytes": self.nonzero_bytes,
            "elapsedMs": round(self.elapsed_ms, 3),
            "checksum": self.checksum,
            "prefixHex": self.prefix_hex,
            "suffixHex": self.suffix_hex,
            "responseHex": self.response.hex(" "),
        }


@dataclass(frozen=True)
class RevCStatusBatch:
    mode: str
    exchange_count: int
    wire_bytes: int
    elapsed_ms: float
    samples: Tuple[RevCStatusSample, ...]
    physical_io: bool = True

    @property
    def minimum_received_bytes(self) -> int:
        if not self.samples:
            return 0
        return min(sample.received_bytes for sample in self.samples)

    @property
    def maximum_received_bytes(self) -> int:
        if not self.samples:
            return 0
        return max(sample.received_bytes for sample in self.samples)

    @property
    def total_nonzero_bytes(self) -> int:
        return sum(sample.nonzero_bytes for sample in self.samples)

    @property
    def fingerprint(self) -> str:
        digest = hashlib.sha256()
        for sample in self.samples:
            digest.update(sample.response)
        return digest.hexdigest()[:16]

    def as_dict(self) -> Dict[str, object]:
        return {
            "mode": self.mode,
            "exchangeCount": self.exchange_count,
            "wireBytes": self.wire_bytes,
            "elapsedMs": round(self.elapsed_ms, 3),
            "statusCount": len(self.samples),
            "minimumReceivedBytes": self.minimum_received_bytes,
            "maximumReceivedBytes": self.maximum_received_bytes,
            "totalNonzeroBytes": self.total_nonzero_bytes,
            "fingerprint": self.fingerprint,
            "physicalIo": self.physical_io,
            "samples": [sample.as_dict() for sample in self.samples],
        }


def _response_bytes(response) -> bytes:
    if response is None:
        return b""
    if isinstance(response, bytes):
        return response
    if isinstance(response, (bytearray, memoryview)):
        return bytes(response)
    try:
        return bytes(response)
    except Exception as exc:
        raise RevCStatusError(
            f"status response is not bytes-like: {type(response).__name__}"
        ) from exc


def send_protocol_with_status(
    driver,
    protocol,
    *,
    minimum_status_bytes: int = 1,
    inter_exchange_delay: float = 0.25,
    sleeper: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> RevCStatusBatch:
    """Write validated protocol blocks and retain every requested status read."""
    minimum = int(minimum_status_bytes)
    delay = float(inter_exchange_delay)
    if minimum <= 0:
        raise ValueError("minimum_status_bytes must be greater than zero")
    if delay < 0:
        raise ValueError("inter_exchange_delay must not be negative")
    if not bool(getattr(protocol, "valid", False)):
        raise RevCStatusError("protocol framing is not valid")

    exchanges = tuple(getattr(protocol, "exchanges", ()))
    mode = str(getattr(protocol, "mode", ""))
    if mode not in {"full", "partial", "noop"}:
        raise RevCStatusError(f"unsupported protocol mode: {mode!r}")
    if mode != "noop" and not exchanges:
        raise RevCStatusError("protocol contains no exchanges")

    write = getattr(driver, "WriteData", None)
    read = getattr(driver, "ReadData", None)
    if not callable(write) or not callable(read):
        raise RevCStatusError("driver does not expose WriteData and ReadData")

    started = clock()
    samples = []
    written_bytes = 0

    for exchange_index, exchange in enumerate(exchanges):
        blocks = tuple(getattr(exchange, "blocks", ()))
        if not blocks:
            raise RevCStatusError(
                f"exchange {exchange_index} contains no wire blocks"
            )
        region = getattr(exchange, "region", None)
        if region is not None and not isinstance(region, FrameRegion):
            try:
                region = FrameRegion(
                    int(region.x),
                    int(region.y),
                    int(region.width),
                    int(region.height),
                )
            except Exception as exc:
                raise RevCStatusError(
                    f"exchange {exchange_index} has an invalid region"
                ) from exc

        for block in blocks:
            wire = bytes(getattr(block, "wire", b""))
            block_name = str(getattr(block, "name", "wire-block"))
            if not wire:
                raise RevCStatusError(
                    f"exchange {exchange_index} block {block_name!r} is empty"
                )
            write(bytearray(wire))
            written_bytes += len(wire)

            read_size = int(getattr(block, "read_size", 0) or 0)
            if read_size <= 0:
                continue

            read_started = clock()
            response = _response_bytes(read(read_size))
            read_elapsed_ms = (clock() - read_started) * 1000.0
            sample = RevCStatusSample(
                exchange_index=exchange_index,
                exchange_name=str(
                    getattr(exchange, "name", f"exchange-{exchange_index}")
                ),
                region=region,
                block_name=block_name,
                requested_bytes=read_size,
                response=response,
                elapsed_ms=read_elapsed_ms,
            )
            if sample.received_bytes < minimum:
                raise RevCStatusError(
                    f"status read after exchange {exchange_index} "
                    f"block {block_name!r} returned "
                    f"{sample.received_bytes} byte(s); minimum is {minimum}"
                )
            samples.append(sample)

        if exchange_index + 1 < len(exchanges) and delay:
            sleeper(delay)

    expected_wire_bytes = int(getattr(protocol, "wire_bytes", written_bytes))
    if written_bytes != expected_wire_bytes:
        raise RevCStatusError(
            f"physical writer emitted {written_bytes} bytes; "
            f"protocol declares {expected_wire_bytes}"
        )
    if mode != "noop" and not samples:
        raise RevCStatusError("protocol requested no observable status reads")

    return RevCStatusBatch(
        mode=mode,
        exchange_count=len(exchanges),
        wire_bytes=written_bytes,
        elapsed_ms=(clock() - started) * 1000.0,
        samples=tuple(samples),
    )
