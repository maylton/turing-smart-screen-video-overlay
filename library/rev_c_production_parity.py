# SPDX-License-Identifier: GPL-3.0-or-later
"""Compare simulated Rev. C framing with the existing production driver.

The production driver is allocated without running ``__init__`` and therefore
never opens a serial port. Its ``WriteData`` and ``ReadData`` methods are
replaced with in-memory collectors before any serializer method is called.
This gives the HTML theme pipeline a byte-for-byte oracle while preserving a
strict physical-I/O boundary.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from PIL import Image

from library.rev_c_protocol_simulator import RevCProtocolAnalysis
from library.simulated_display_transport import TransportAnalysis


def _checksum(payload: bytes) -> str:
    return hashlib.sha256(bytes(payload)).hexdigest()[:16]


def _first_mismatch(expected: bytes, actual: bytes) -> Optional[int]:
    limit = min(len(expected), len(actual))
    for offset in range(limit):
        if expected[offset] != actual[offset]:
            return offset
    if len(expected) != len(actual):
        return limit
    return None


@dataclass(frozen=True)
class ProductionParityBlock:
    name: str
    expected_wire: bytes
    production_wire: bytes
    expected_read_size: int
    production_read_size: int

    @property
    def mismatch_offset(self) -> Optional[int]:
        return _first_mismatch(self.expected_wire, self.production_wire)

    @property
    def wire_matches(self) -> bool:
        return self.mismatch_offset is None

    @property
    def read_matches(self) -> bool:
        return self.expected_read_size == self.production_read_size

    @property
    def valid(self) -> bool:
        return self.wire_matches and self.read_matches

    def as_dict(self) -> Dict[str, object]:
        mismatch = self.mismatch_offset
        return {
            "name": self.name,
            "valid": self.valid,
            "wireMatches": self.wire_matches,
            "readMatches": self.read_matches,
            "mismatchOffset": mismatch,
            "expectedWireBytes": len(self.expected_wire),
            "productionWireBytes": len(self.production_wire),
            "expectedReadSize": self.expected_read_size,
            "productionReadSize": self.production_read_size,
            "expectedChecksum": _checksum(self.expected_wire),
            "productionChecksum": _checksum(self.production_wire),
            "expectedPrefixHex": self.expected_wire[:16].hex(" "),
            "productionPrefixHex": self.production_wire[:16].hex(" "),
        }


@dataclass(frozen=True)
class ProductionParityExchange:
    name: str
    blocks: Tuple[ProductionParityBlock, ...]
    expected_block_count: int
    production_block_count: int

    @property
    def valid(self) -> bool:
        return (
            self.expected_block_count == self.production_block_count
            and all(block.valid for block in self.blocks)
        )

    def as_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "valid": self.valid,
            "expectedBlockCount": self.expected_block_count,
            "productionBlockCount": self.production_block_count,
            "blocks": [block.as_dict() for block in self.blocks],
        }


@dataclass(frozen=True)
class RevCProductionParityAnalysis:
    sequence: int
    mode: str
    exchanges: Tuple[ProductionParityExchange, ...]
    expected_wire: bytes
    production_wire: bytes
    physical_io: bool = False

    @property
    def mismatch_offset(self) -> Optional[int]:
        return _first_mismatch(self.expected_wire, self.production_wire)

    @property
    def valid(self) -> bool:
        return (
            not self.physical_io
            and self.mismatch_offset is None
            and all(exchange.valid for exchange in self.exchanges)
        )

    def as_dict(self) -> Dict[str, object]:
        return {
            "sequence": self.sequence,
            "mode": self.mode,
            "valid": self.valid,
            "physicalIo": self.physical_io,
            "mismatchOffset": self.mismatch_offset,
            "expectedWireBytes": len(self.expected_wire),
            "productionWireBytes": len(self.production_wire),
            "expectedChecksum": _checksum(self.expected_wire),
            "productionChecksum": _checksum(self.production_wire),
            "exchanges": [exchange.as_dict() for exchange in self.exchanges],
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n"


class _ProductionCapture:
    """Minimal Rev. C instance whose I/O methods only collect bytes."""

    def __init__(self, size: Tuple[int, int]) -> None:
        from library.lcd.lcd_comm import Orientation
        from library.lcd.lcd_comm_rev_c import LcdCommRevC, SubRevision

        width, height = size
        if width <= 0 or height <= 0:
            raise ValueError("production parity dimensions must be positive")

        driver = object.__new__(LcdCommRevC)
        driver.display_width = int(width)
        driver.display_height = int(height)
        driver.orientation = Orientation.LANDSCAPE
        driver.sub_revision = SubRevision.REV_2INCH
        driver.rom_version = 87
        driver.update_queue = None
        driver.lcd_serial = None

        self.driver = driver
        self.writes: List[bytes] = []
        self.reads: List[int] = []

        def write_data(payload) -> None:
            self.writes.append(bytes(payload))

        def read_data(size: int) -> bytes:
            self.reads.append(int(size))
            return bytes(int(size))

        driver.WriteData = write_data
        driver.ReadData = read_data

    def clear(self) -> None:
        self.writes.clear()
        self.reads.clear()

    def full_exchange(self, frame: Image.Image) -> Tuple[Tuple[bytes, ...], Tuple[int, ...]]:
        from library.lcd.lcd_comm_rev_c import Command, Padding

        self.clear()
        driver = self.driver
        driver._send_command(Command.PRE_UPDATE_BITMAP)
        driver._send_command(
            Command.START_DISPLAY_BITMAP,
            padding=Padding.START_DISPLAY_BITMAP,
        )
        driver._send_command(Command.DISPLAY_BITMAP_2INCH)
        driver._send_command(
            Command.SEND_PAYLOAD,
            payload=bytearray(driver._generate_full_image(frame)),
            readsize=1024,
        )
        driver._send_command(Command.QUERY_STATUS, readsize=1024)
        return tuple(self.writes), tuple(self.reads)

    def partial_exchange(
        self,
        frame: Image.Image,
        *,
        x: int,
        y: int,
        update_count: int,
    ) -> Tuple[Tuple[bytes, ...], Tuple[int, ...]]:
        from library.lcd.lcd_comm_rev_c import Command

        self.clear()
        driver = self.driver
        image_data, header = driver._generate_update_image(
            frame,
            int(x),
            int(y),
            int(update_count),
            Command.UPDATE_BITMAP,
        )
        driver._send_command(Command.SEND_PAYLOAD, payload=header)
        driver._send_command(Command.SEND_PAYLOAD, payload=image_data)
        driver._send_command(Command.QUERY_STATUS, readsize=1024)
        return tuple(self.writes), tuple(self.reads)


def _read_sizes_for_blocks(blocks) -> Tuple[int, ...]:
    return tuple(int(block.read_size) for block in blocks if block.read_size)


def _pair_blocks(
    expected_blocks,
    production_writes: Tuple[bytes, ...],
    production_reads: Tuple[int, ...],
) -> Tuple[ProductionParityBlock, ...]:
    paired = []
    read_index = 0
    count = max(len(expected_blocks), len(production_writes))
    for index in range(count):
        expected = expected_blocks[index] if index < len(expected_blocks) else None
        actual = production_writes[index] if index < len(production_writes) else b""
        expected_read = int(expected.read_size) if expected is not None else 0
        actual_read = 0
        if expected_read:
            if read_index < len(production_reads):
                actual_read = int(production_reads[read_index])
            read_index += 1
        paired.append(
            ProductionParityBlock(
                name=(expected.name if expected is not None else f"extra-{index}"),
                expected_wire=(expected.wire if expected is not None else b""),
                production_wire=actual,
                expected_read_size=expected_read,
                production_read_size=actual_read,
            )
        )
    if read_index < len(production_reads):
        for index in range(read_index, len(production_reads)):
            paired.append(
                ProductionParityBlock(
                    name=f"extra-read-{index}",
                    expected_wire=b"",
                    production_wire=b"",
                    expected_read_size=0,
                    production_read_size=int(production_reads[index]),
                )
            )
    return tuple(paired)


def compare_with_production_driver(
    frame: Image.Image,
    transport: TransportAnalysis,
    protocol: RevCProtocolAnalysis,
) -> RevCProductionParityAnalysis:
    """Run the production serializer with captured I/O and compare every byte."""
    current = frame.convert("RGBA")
    current.load()
    if current.size != (
        transport.packets[0].region.right if transport.full_refresh and transport.packets else current.width,
        transport.packets[0].region.bottom if transport.full_refresh and transport.packets else current.height,
    ) and transport.full_refresh:
        raise ValueError("full transport packet does not cover the complete frame")
    if transport.sequence != protocol.sequence:
        raise ValueError("transport and protocol sequence numbers differ")
    if len(transport.packets) != len(protocol.exchanges):
        raise ValueError("transport packet count differs from protocol exchanges")

    capture = _ProductionCapture(current.size)
    exchanges = []
    production_wire_parts = []

    for packet, expected_exchange in zip(transport.packets, protocol.exchanges):
        if transport.full_refresh:
            writes, reads = capture.full_exchange(current)
        else:
            crop = current.crop(
                (
                    packet.region.x,
                    packet.region.y,
                    packet.region.right,
                    packet.region.bottom,
                )
            )
            if expected_exchange.update_count is None:
                raise ValueError("partial exchange is missing its update count")
            writes, reads = capture.partial_exchange(
                crop,
                x=packet.region.x,
                y=packet.region.y,
                update_count=expected_exchange.update_count,
            )

        blocks = _pair_blocks(expected_exchange.blocks, writes, reads)
        exchanges.append(
            ProductionParityExchange(
                name=expected_exchange.name,
                blocks=blocks,
                expected_block_count=len(expected_exchange.blocks),
                production_block_count=len(writes),
            )
        )
        production_wire_parts.extend(writes)

    return RevCProductionParityAnalysis(
        sequence=transport.sequence,
        mode=protocol.mode,
        exchanges=tuple(exchanges),
        expected_wire=protocol.wire,
        production_wire=b"".join(production_wire_parts),
        physical_io=False,
    )


def _atomic_write(destination: Path, payload: bytes) -> None:
    temporary = destination.with_name(
        f".{destination.name}.{os.getpid()}.tmp"
    )
    temporary.write_bytes(payload)
    os.replace(temporary, destination)


def _layout_lines(analysis: RevCProductionParityAnalysis) -> Iterable[str]:
    yield (
        f"sequence={analysis.sequence} mode={analysis.mode} "
        f"valid={analysis.valid} expected={len(analysis.expected_wire)} "
        f"production={len(analysis.production_wire)} "
        f"mismatch={analysis.mismatch_offset}"
    )
    for exchange_index, exchange in enumerate(analysis.exchanges):
        yield (
            f"exchange[{exchange_index}] {exchange.name} "
            f"valid={exchange.valid} blocks="
            f"{exchange.production_block_count}/{exchange.expected_block_count}"
        )
        for block_index, block in enumerate(exchange.blocks):
            yield (
                f"  block[{block_index}] {block.name} valid={block.valid} "
                f"wire={len(block.production_wire)}/{len(block.expected_wire)} "
                f"read={block.production_read_size}/{block.expected_read_size} "
                f"mismatch={block.mismatch_offset}"
            )


def write_production_parity_artifacts(
    directory: Path,
    analysis: RevCProductionParityAnalysis,
) -> Path:
    root = Path(directory).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    files = {
        "rev-c-production-wire.bin": analysis.production_wire,
        "rev-c-production-parity.json": analysis.to_json().encode("utf-8"),
        "rev-c-production-parity.txt": (
            "\n".join(_layout_lines(analysis)) + "\n"
        ).encode("utf-8"),
    }
    for name, payload in files.items():
        _atomic_write(root / name, payload)
    return root
