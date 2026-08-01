# SPDX-License-Identifier: GPL-3.0-or-later
"""In-memory framing simulator for TURZX Revision C bitmap transactions.

This module reproduces the byte framing used by ``lcd_comm_rev_c.py`` without
opening a serial port. It accepts packets from the renderer-neutral transport
simulator, builds the same 250-byte command/data blocks, then parses the result
back to validate headers, row records, separators, terminators, and payloads.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

from library.frame_pipeline import FrameRegion
from library.simulated_display_transport import (
    BGRA32,
    BGR24,
    SimulatedPacket,
    TransportAnalysis,
)


BLOCK_SIZE = 250
DATA_CHUNK_SIZE = 249
TERMINATOR = b"\xef\x69"

PRE_UPDATE_BITMAP = bytes((0x86, 0xEF, 0x69, 0x00, 0x00, 0x00, 0x01))
START_DISPLAY_BITMAP = bytes((0x2C,))
DISPLAY_BITMAP_2INCH = bytes((0xC8, 0xEF, 0x69, 0x00, 0x0E, 0x10))
UPDATE_BITMAP = bytes((0xCC, 0xEF, 0x69, 0x00))
QUERY_STATUS = bytes((0xCF, 0xEF, 0x69, 0x00, 0x00, 0x00, 0x01))


def pad_to_block(payload: bytes, fill: int = 0) -> bytes:
    """Pad a command or payload to the next 250-byte boundary."""
    raw = bytes(payload)
    if not 0 <= int(fill) <= 255:
        raise ValueError("fill must be between 0 and 255")
    remainder = len(raw) % BLOCK_SIZE
    if remainder == 0:
        return raw
    return raw + bytes((int(fill),)) * (BLOCK_SIZE - remainder)


def frame_chunked_payload(payload: bytes) -> bytes:
    """Apply the full-frame 249-byte chunks and zero separators."""
    raw = bytes(payload)
    if not raw:
        return b""
    chunks = [
        raw[offset : offset + DATA_CHUNK_SIZE]
        for offset in range(0, len(raw), DATA_CHUNK_SIZE)
    ]
    separated = b"\x00".join(chunks)
    return pad_to_block(separated)


def recover_chunked_payload(wire: bytes, raw_length: int) -> bytes:
    """Recover a known-length payload and verify every separator/padding byte."""
    framed = bytes(wire)
    expected_length = int(raw_length)
    if expected_length < 0:
        raise ValueError("raw_length must not be negative")
    if len(framed) % BLOCK_SIZE:
        raise ValueError("framed payload is not aligned to 250-byte blocks")
    if expected_length == 0:
        if framed:
            raise ValueError("empty payload must not contain framed bytes")
        return b""

    recovered = bytearray()
    offset = 0
    remaining = expected_length
    while remaining:
        chunk_length = min(DATA_CHUNK_SIZE, remaining)
        end = offset + chunk_length
        if end > len(framed):
            raise ValueError("framed payload ended before the raw payload")
        recovered.extend(framed[offset:end])
        offset = end
        remaining -= chunk_length
        if remaining:
            if offset >= len(framed) or framed[offset] != 0:
                raise ValueError("missing zero separator between 249-byte chunks")
            offset += 1

    if any(framed[offset:]):
        raise ValueError("non-zero bytes found in final block padding")
    return bytes(recovered)


def frame_partial_records(records: bytes) -> bytes:
    """Mirror Rev. C partial framing: chunk records, then append ``ef 69``."""
    raw = bytes(records)
    if len(raw) > BLOCK_SIZE:
        chunks = [
            raw[offset : offset + DATA_CHUNK_SIZE]
            for offset in range(0, len(raw), DATA_CHUNK_SIZE)
        ]
        encoded = b"\x00".join(chunks)
    else:
        encoded = raw
    return pad_to_block(encoded + TERMINATOR)


def recover_partial_records(wire: bytes, records_length: int) -> bytes:
    """Recover partial row records and verify separators, terminator, and pad."""
    framed = bytes(wire)
    expected_length = int(records_length)
    if expected_length < 0:
        raise ValueError("records_length must not be negative")
    if len(framed) % BLOCK_SIZE:
        raise ValueError("partial payload is not aligned to 250-byte blocks")

    recovered = bytearray()
    offset = 0
    remaining = expected_length
    chunked = expected_length > BLOCK_SIZE
    while remaining:
        chunk_length = (
            min(DATA_CHUNK_SIZE, remaining)
            if chunked
            else remaining
        )
        end = offset + chunk_length
        if end > len(framed):
            raise ValueError("partial payload ended before all row records")
        recovered.extend(framed[offset:end])
        offset = end
        remaining -= chunk_length
        if chunked and remaining:
            if offset >= len(framed) or framed[offset] != 0:
                raise ValueError("missing partial-record chunk separator")
            offset += 1

    if framed[offset : offset + len(TERMINATOR)] != TERMINATOR:
        raise ValueError("partial payload is missing the ef 69 terminator")
    offset += len(TERMINATOR)
    if any(framed[offset:]):
        raise ValueError("non-zero bytes found after partial terminator")
    return bytes(recovered)


@dataclass(frozen=True)
class RevCWireBlock:
    name: str
    wire: bytes
    meaningful_bytes: int
    read_size: int = 0

    def __post_init__(self) -> None:
        if len(self.wire) % BLOCK_SIZE:
            raise ValueError(f"{self.name} is not aligned to 250-byte blocks")
        if not 0 <= self.meaningful_bytes <= len(self.wire):
            raise ValueError(f"{self.name} has an invalid meaningful byte count")

    @property
    def padding_bytes(self) -> int:
        return len(self.wire) - self.meaningful_bytes

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.wire).hexdigest()[:16]

    def as_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "wireBytes": len(self.wire),
            "meaningfulBytes": self.meaningful_bytes,
            "paddingBytes": self.padding_bytes,
            "readSize": self.read_size,
            "checksum": self.checksum,
            "prefixHex": self.wire[:16].hex(" "),
            "suffixHex": self.wire[-16:].hex(" "),
        }


@dataclass(frozen=True)
class RevCExchange:
    name: str
    region: FrameRegion
    update_count: Optional[int]
    blocks: Tuple[RevCWireBlock, ...]
    payload_valid: bool
    row_records_valid: bool
    error: str = ""

    @property
    def wire(self) -> bytes:
        return b"".join(block.wire for block in self.blocks)

    @property
    def wire_bytes(self) -> int:
        return sum(len(block.wire) for block in self.blocks)

    @property
    def meaningful_bytes(self) -> int:
        return sum(block.meaningful_bytes for block in self.blocks)

    @property
    def framing_overhead_bytes(self) -> int:
        return self.wire_bytes - self.meaningful_bytes

    @property
    def valid(self) -> bool:
        return self.payload_valid and self.row_records_valid and not self.error

    def as_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "region": self.region.as_dict(),
            "updateCount": self.update_count,
            "wireBytes": self.wire_bytes,
            "meaningfulBytes": self.meaningful_bytes,
            "framingOverheadBytes": self.framing_overhead_bytes,
            "payloadValid": self.payload_valid,
            "rowRecordsValid": self.row_records_valid,
            "valid": self.valid,
            "error": self.error,
            "blocks": [block.as_dict() for block in self.blocks],
        }


@dataclass(frozen=True)
class RevCProtocolAnalysis:
    sequence: int
    mode: str
    exchanges: Tuple[RevCExchange, ...]
    source_pixel_bytes: int
    full_frame_wire_bytes: int

    @property
    def wire(self) -> bytes:
        return b"".join(exchange.wire for exchange in self.exchanges)

    @property
    def wire_bytes(self) -> int:
        return sum(exchange.wire_bytes for exchange in self.exchanges)

    @property
    def meaningful_bytes(self) -> int:
        return sum(exchange.meaningful_bytes for exchange in self.exchanges)

    @property
    def framing_overhead_bytes(self) -> int:
        return self.wire_bytes - self.meaningful_bytes

    @property
    def valid(self) -> bool:
        return all(exchange.valid for exchange in self.exchanges)

    @property
    def wire_savings_ratio(self) -> float:
        if self.full_frame_wire_bytes <= 0:
            return 0.0
        return max(0.0, 1.0 - self.wire_bytes / self.full_frame_wire_bytes)

    def as_dict(self) -> Dict[str, object]:
        return {
            "sequence": self.sequence,
            "mode": self.mode,
            "exchangeCount": len(self.exchanges),
            "sourcePixelBytes": self.source_pixel_bytes,
            "wireBytes": self.wire_bytes,
            "meaningfulBytes": self.meaningful_bytes,
            "framingOverheadBytes": self.framing_overhead_bytes,
            "fullFrameWireBytes": self.full_frame_wire_bytes,
            "wireSavingsRatio": round(self.wire_savings_ratio, 6),
            "valid": self.valid,
            "physicalIo": False,
            "exchanges": [
                exchange.as_dict() for exchange in self.exchanges
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n"


def _command_block(
    name: str,
    command: bytes,
    *,
    fill: int = 0,
    read_size: int = 0,
) -> RevCWireBlock:
    return RevCWireBlock(
        name=name,
        wire=pad_to_block(command, fill),
        meaningful_bytes=len(command),
        read_size=read_size,
    )


def _data_block(
    name: str,
    payload: bytes,
    *,
    read_size: int = 0,
) -> RevCWireBlock:
    wire = frame_chunked_payload(payload)
    return RevCWireBlock(
        name=name,
        wire=wire,
        meaningful_bytes=len(payload),
        read_size=read_size,
    )


def _partial_records(
    packet: SimulatedPacket,
    display_stride: int,
) -> bytes:
    region = packet.region
    bytes_per_row = region.width * 3
    expected = bytes_per_row * region.height
    if len(packet.payload) != expected:
        raise ValueError(
            f"partial BGR payload has {len(packet.payload)} bytes; "
            f"expected {expected}"
        )

    records = bytearray()
    for row in range(region.height):
        start = (region.y + row) * display_stride + region.x
        row_start = row * bytes_per_row
        row_payload = packet.payload[row_start : row_start + bytes_per_row]
        records += int(start).to_bytes(3, "big")
        records += int(region.width).to_bytes(2, "big")
        records += row_payload
    return bytes(records)


def _validate_partial_records(
    records: bytes,
    packet: SimulatedPacket,
    display_stride: int,
) -> bool:
    region = packet.region
    bytes_per_row = region.width * 3
    record_size = 5 + bytes_per_row
    if len(records) != record_size * region.height:
        return False

    recovered_pixels = bytearray()
    offset = 0
    for row in range(region.height):
        start = int.from_bytes(records[offset : offset + 3], "big")
        width = int.from_bytes(records[offset + 3 : offset + 5], "big")
        offset += 5
        pixels = records[offset : offset + bytes_per_row]
        offset += bytes_per_row
        expected_start = (region.y + row) * display_stride + region.x
        if start != expected_start or width != region.width:
            return False
        recovered_pixels.extend(pixels)
    return bytes(recovered_pixels) == packet.payload


def _full_exchange(packet: SimulatedPacket) -> RevCExchange:
    if packet.encoding != BGRA32 or not packet.full_refresh:
        raise ValueError("full Rev. C exchange requires one BGRA32 full packet")

    pixel_block = _data_block(
        "full-pixels",
        packet.payload,
        read_size=1024,
    )
    recovered = recover_chunked_payload(
        pixel_block.wire,
        len(packet.payload),
    )
    blocks = (
        _command_block("pre-update", PRE_UPDATE_BITMAP),
        _command_block(
            "start-display",
            START_DISPLAY_BITMAP,
            fill=START_DISPLAY_BITMAP[0],
        ),
        _command_block("display-bitmap-2inch", DISPLAY_BITMAP_2INCH),
        pixel_block,
        _command_block("query-status", QUERY_STATUS, read_size=1024),
    )
    return RevCExchange(
        name="full-frame",
        region=packet.region,
        update_count=None,
        blocks=blocks,
        payload_valid=recovered == packet.payload,
        row_records_valid=True,
    )


def _partial_exchange(
    packet: SimulatedPacket,
    *,
    update_count: int,
    display_stride: int,
) -> RevCExchange:
    if packet.encoding != BGR24 or packet.full_refresh:
        raise ValueError("partial Rev. C exchange requires one BGR24 packet")

    records = _partial_records(packet, display_stride)
    image_size = len(records) + len(TERMINATOR)
    header = (
        UPDATE_BITMAP
        + image_size.to_bytes(3, "big")
        + b"\x00\x00\x00"
        + int(update_count).to_bytes(4, "big")
    )
    header_block = RevCWireBlock(
        name="update-header",
        wire=pad_to_block(header),
        meaningful_bytes=len(header),
    )
    partial_wire = frame_partial_records(records)
    pixel_block = RevCWireBlock(
        name="partial-records",
        wire=partial_wire,
        meaningful_bytes=image_size,
    )
    recovered_records = recover_partial_records(
        pixel_block.wire,
        len(records),
    )
    header_size = int.from_bytes(header[4:7], "big")
    header_count = int.from_bytes(header[10:14], "big")
    blocks = (
        header_block,
        pixel_block,
        _command_block("query-status", QUERY_STATUS, read_size=1024),
    )
    return RevCExchange(
        name="partial-region",
        region=packet.region,
        update_count=update_count,
        blocks=blocks,
        payload_valid=(
            recovered_records == records
            and header_size == image_size
            and header_count == update_count
        ),
        row_records_valid=_validate_partial_records(
            recovered_records,
            packet,
            display_stride,
        ),
    )


def _full_frame_wire_size(pixel_bytes: int) -> int:
    raw = max(0, int(pixel_bytes))
    pixel_wire = (
        ((raw + DATA_CHUNK_SIZE - 1) // DATA_CHUNK_SIZE) * BLOCK_SIZE
        if raw
        else 0
    )
    return (4 * BLOCK_SIZE) + pixel_wire


class RevCProtocolSimulator:
    """Build and validate Rev. C wire transactions entirely in memory."""

    def __init__(self, *, display_stride: int = 480) -> None:
        if display_stride <= 0:
            raise ValueError("display_stride must be greater than zero")
        self.display_stride = int(display_stride)
        self._update_count = 0

    def reset(self) -> None:
        self._update_count = 0

    def submit(self, transport: TransportAnalysis) -> RevCProtocolAnalysis:
        if transport.profile != "rev-c-2inch":
            raise ValueError(
                "Rev. C framing requires the rev-c-2inch transport profile"
            )
        exchanges = []
        if transport.full_refresh:
            if len(transport.packets) != 1:
                raise ValueError(
                    "a Rev. C full refresh must contain exactly one packet"
                )
            exchanges.append(_full_exchange(transport.packets[0]))
        else:
            for packet in transport.packets:
                exchanges.append(
                    _partial_exchange(
                        packet,
                        update_count=self._update_count,
                        display_stride=self.display_stride,
                    )
                )
                self._update_count += 1

        mode = (
            "full"
            if transport.full_refresh
            else ("partial" if transport.packets else "noop")
        )
        return RevCProtocolAnalysis(
            sequence=transport.sequence,
            mode=mode,
            exchanges=tuple(exchanges),
            source_pixel_bytes=transport.pixel_bytes,
            full_frame_wire_bytes=_full_frame_wire_size(
                transport.full_frame_bytes
            ),
        )


def _atomic_write(destination: Path, payload: bytes) -> None:
    temporary = destination.with_name(
        f".{destination.name}.{os.getpid()}.tmp"
    )
    temporary.write_bytes(payload)
    os.replace(temporary, destination)


def _layout_lines(analysis: RevCProtocolAnalysis) -> Iterable[str]:
    yield (
        f"sequence={analysis.sequence} mode={analysis.mode} "
        f"valid={analysis.valid} wire={analysis.wire_bytes}"
    )
    offset = 0
    for exchange_index, exchange in enumerate(analysis.exchanges):
        yield (
            f"exchange[{exchange_index}] {exchange.name} "
            f"region={exchange.region.x},{exchange.region.y},"
            f"{exchange.region.width}x{exchange.region.height} "
            f"valid={exchange.valid}"
        )
        for block in exchange.blocks:
            end = offset + len(block.wire)
            yield (
                f"  {offset:08x}-{end - 1:08x} {block.name} "
                f"wire={len(block.wire)} meaningful={block.meaningful_bytes} "
                f"padding={block.padding_bytes} sha256={block.checksum}"
            )
            offset = end


def write_rev_c_protocol_artifacts(
    directory: Path,
    analysis: RevCProtocolAnalysis,
) -> Path:
    """Atomically publish binary framing, metrics, and a readable block map."""
    root = Path(directory).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    files = {
        "rev-c-protocol.bin": analysis.wire,
        "rev-c-protocol.json": analysis.to_json().encode("utf-8"),
        "rev-c-protocol-layout.txt": (
            "\n".join(_layout_lines(analysis)) + "\n"
        ).encode("utf-8"),
    }
    for name, payload in files.items():
        _atomic_write(root / name, payload)
    return root
