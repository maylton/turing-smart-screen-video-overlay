# SPDX-License-Identifier: GPL-3.0-or-later
"""Renderer-neutral simulation of display pixel transports.

The simulator deliberately stops before USB or serial I/O. It consumes the
dirty regions emitted by :mod:`library.frame_pipeline`, serializes their pixels
with the same helpers used by the existing display revisions, and applies the
packets to an in-memory framebuffer.

Revision C 2.1/2.8-inch displays do not use RGB565 for ordinary bitmap updates:
full frames are BGRA32 and partial updates are BGR24. Revisions A and B use
little-endian and big-endian RGB565 respectively. Keeping these details in
profiles prevents the HTML engine from assuming one wire format for every
display.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple

from PIL import Image, ImageChops, ImageEnhance

from library.frame_pipeline import FrameAnalysis, FrameRegion
from library.lcd.serialize import image_to_BGRA, image_to_BGR, image_to_RGB565


RGB565_LE = "rgb565-le"
RGB565_BE = "rgb565-be"
BGR24 = "bgr24"
BGRA32 = "bgra32"
SUPPORTED_ENCODINGS = {RGB565_LE, RGB565_BE, BGR24, BGRA32}


@dataclass(frozen=True)
class TransportProfile:
    """Pixel formats and conservative metadata for one display family."""

    name: str
    full_encoding: str
    partial_encoding: str
    region_header_bytes: int = 0
    description: str = ""

    def __post_init__(self) -> None:
        for encoding in (self.full_encoding, self.partial_encoding):
            if encoding not in SUPPORTED_ENCODINGS:
                raise ValueError(f"Unsupported pixel encoding: {encoding}")
        if self.region_header_bytes < 0:
            raise ValueError("region_header_bytes must not be negative")


PROFILES: Mapping[str, TransportProfile] = {
    "rev-c-2inch": TransportProfile(
        name="rev-c-2inch",
        full_encoding=BGRA32,
        partial_encoding=BGR24,
        # Rev. C partial records include a 3-byte start position and a
        # 2-byte run width for every encoded scanline.
        region_header_bytes=5,
        description="TURZX Rev. C 480x480: BGRA full frames, BGR partial rows",
    ),
    "rev-a-rgb565le": TransportProfile(
        name="rev-a-rgb565le",
        full_encoding=RGB565_LE,
        partial_encoding=RGB565_LE,
        description="Turing/UsbMonitor Rev. A RGB565 little-endian",
    ),
    "rev-b-rgb565be": TransportProfile(
        name="rev-b-rgb565be",
        full_encoding=RGB565_BE,
        partial_encoding=RGB565_BE,
        description="XuanFang Rev. B RGB565 big-endian",
    ),
}


def get_transport_profile(name: str) -> TransportProfile:
    try:
        return PROFILES[str(name)]
    except KeyError as exc:
        available = ", ".join(sorted(PROFILES))
        raise ValueError(
            f"Unknown transport profile {name!r}; choose one of: {available}"
        ) from exc


def bytes_per_pixel(encoding: str) -> int:
    return {
        RGB565_LE: 2,
        RGB565_BE: 2,
        BGR24: 3,
        BGRA32: 4,
    }[encoding]


def _bounded_region(region: FrameRegion, size: Tuple[int, int]) -> FrameRegion:
    width, height = size
    left = max(0, min(width, int(region.x)))
    top = max(0, min(height, int(region.y)))
    right = max(left, min(width, int(region.right)))
    bottom = max(top, min(height, int(region.bottom)))
    bounded = FrameRegion(left, top, right - left, bottom - top)
    if bounded.area <= 0:
        raise ValueError(f"Region is empty after clipping: {region}")
    return bounded


def encode_pixels(image: Image.Image, encoding: str) -> bytes:
    """Serialize one logical image region using an existing project format."""
    if encoding == RGB565_LE:
        return image_to_RGB565(image, "little")
    if encoding == RGB565_BE:
        return image_to_RGB565(image, "big")
    if encoding == BGR24:
        payload, pixel_size = image_to_BGR(image)
        assert pixel_size == 3
        return payload
    if encoding == BGRA32:
        payload, pixel_size = image_to_BGRA(image)
        assert pixel_size == 4
        return payload
    raise ValueError(f"Unsupported pixel encoding: {encoding}")


def _expand_5(value: int) -> int:
    return (value << 3) | (value >> 2)


def _expand_6(value: int) -> int:
    return (value << 2) | (value >> 4)


def decode_pixels(
    payload: bytes,
    size: Tuple[int, int],
    encoding: str,
) -> Image.Image:
    """Decode a simulated payload back to an RGBA image."""
    width, height = size
    expected = width * height * bytes_per_pixel(encoding)
    if len(payload) != expected:
        raise ValueError(
            f"{encoding} payload has {len(payload)} bytes; expected {expected}"
        )

    if encoding in {RGB565_LE, RGB565_BE}:
        order = "little" if encoding == RGB565_LE else "big"
        rgba = bytearray()
        for offset in range(0, len(payload), 2):
            value = int.from_bytes(payload[offset : offset + 2], order)
            red = _expand_5((value >> 11) & 0x1F)
            green = _expand_6((value >> 5) & 0x3F)
            blue = _expand_5(value & 0x1F)
            rgba.extend((red, green, blue, 255))
        return Image.frombytes("RGBA", size, bytes(rgba))

    if encoding == BGR24:
        rgba = bytearray()
        for offset in range(0, len(payload), 3):
            blue, green, red = payload[offset : offset + 3]
            rgba.extend((red, green, blue, 255))
        return Image.frombytes("RGBA", size, bytes(rgba))

    if encoding == BGRA32:
        rgba = bytearray()
        for offset in range(0, len(payload), 4):
            blue, green, red, alpha = payload[offset : offset + 4]
            rgba.extend((red, green, blue, alpha))
        return Image.frombytes("RGBA", size, bytes(rgba))

    raise ValueError(f"Unsupported pixel encoding: {encoding}")


@dataclass(frozen=True)
class SimulatedPacket:
    sequence: int
    region: FrameRegion
    encoding: str
    payload: bytes
    full_refresh: bool
    row_overhead_bytes: int = 0

    @property
    def pixel_bytes(self) -> int:
        return len(self.payload)

    @property
    def overhead_bytes(self) -> int:
        return self.row_overhead_bytes * self.region.height

    @property
    def simulated_bytes(self) -> int:
        return self.pixel_bytes + self.overhead_bytes

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()[:16]

    def as_dict(self) -> Dict[str, object]:
        return {
            "sequence": self.sequence,
            "region": self.region.as_dict(),
            "encoding": self.encoding,
            "pixelBytes": self.pixel_bytes,
            "rowOverheadBytes": self.overhead_bytes,
            "simulatedBytes": self.simulated_bytes,
            "checksum": self.checksum,
            "fullRefresh": self.full_refresh,
        }


@dataclass(frozen=True)
class TransportAnalysis:
    sequence: int
    profile: str
    encoding: str
    full_refresh: bool
    packets: Tuple[SimulatedPacket, ...]
    pixel_bytes: int
    overhead_bytes: int
    simulated_bytes: int
    full_frame_bytes: int
    savings_ratio: float
    roundtrip_matches: bool
    differing_pixels: int

    def as_dict(self) -> Dict[str, object]:
        return {
            "sequence": self.sequence,
            "profile": self.profile,
            "encoding": self.encoding,
            "fullRefresh": self.full_refresh,
            "packetCount": len(self.packets),
            "pixelBytes": self.pixel_bytes,
            "overheadBytes": self.overhead_bytes,
            "simulatedBytes": self.simulated_bytes,
            "fullFrameBytes": self.full_frame_bytes,
            "savingsRatio": round(self.savings_ratio, 6),
            "roundtripMatches": self.roundtrip_matches,
            "differingPixels": self.differing_pixels,
            "packets": [packet.as_dict() for packet in self.packets],
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n"


class VirtualFramebuffer:
    """Apply logical region packets without knowing about a physical device."""

    def __init__(self, size: Tuple[int, int]) -> None:
        width, height = size
        if width <= 0 or height <= 0:
            raise ValueError("Framebuffer dimensions must be positive")
        self.size = (int(width), int(height))
        self.image = Image.new("RGBA", self.size, (0, 0, 0, 255))

    def apply(self, packet: SimulatedPacket) -> None:
        region = _bounded_region(packet.region, self.size)
        decoded = decode_pixels(
            packet.payload,
            (region.width, region.height),
            packet.encoding,
        )
        self.image.paste(decoded, (region.x, region.y))

    def copy(self) -> Image.Image:
        return self.image.copy()


class SimulatedDisplayTransport:
    """Encode dirty regions and apply them to a virtual framebuffer."""

    def __init__(
        self,
        profile: TransportProfile,
        size: Optional[Tuple[int, int]] = None,
    ) -> None:
        self.profile = profile
        self._framebuffer = (
            VirtualFramebuffer(size)
            if size is not None
            else None
        )

    @property
    def framebuffer(self) -> Optional[Image.Image]:
        if self._framebuffer is None:
            return None
        return self._framebuffer.copy()

    def reset(self) -> None:
        self._framebuffer = None

    def submit(
        self,
        frame: Image.Image,
        analysis: FrameAnalysis,
    ) -> TransportAnalysis:
        current = frame.convert("RGBA")
        current.load()
        if current.size != (analysis.width, analysis.height):
            raise ValueError(
                f"Frame size {current.size} does not match analysis "
                f"{analysis.width}x{analysis.height}"
            )
        if self._framebuffer is None or self._framebuffer.size != current.size:
            self._framebuffer = VirtualFramebuffer(current.size)

        encoding = (
            self.profile.full_encoding
            if analysis.full_refresh
            else self.profile.partial_encoding
        )
        packets = []
        expected = self._framebuffer.copy()

        for requested_region in analysis.regions:
            region = _bounded_region(requested_region, current.size)
            crop = current.crop(
                (region.x, region.y, region.right, region.bottom)
            )
            payload = encode_pixels(crop, encoding)
            packet = SimulatedPacket(
                sequence=analysis.sequence,
                region=region,
                encoding=encoding,
                payload=payload,
                full_refresh=analysis.full_refresh,
                row_overhead_bytes=(
                    self.profile.region_header_bytes
                    if not analysis.full_refresh
                    else 0
                ),
            )
            packets.append(packet)
            decoded = decode_pixels(
                payload,
                (region.width, region.height),
                encoding,
            )
            expected.paste(decoded, (region.x, region.y))
            self._framebuffer.apply(packet)

        framebuffer = self._framebuffer.copy()
        difference = ImageChops.difference(framebuffer, expected)
        difference_mask = difference.convert("RGB").convert("L")
        histogram = difference_mask.point(
            lambda value: 255 if value else 0
        ).histogram()
        differing_pixels = int(histogram[255])
        pixel_bytes = sum(packet.pixel_bytes for packet in packets)
        overhead_bytes = sum(packet.overhead_bytes for packet in packets)
        simulated_bytes = pixel_bytes + overhead_bytes
        full_frame_bytes = (
            current.width
            * current.height
            * bytes_per_pixel(self.profile.full_encoding)
        )
        savings_ratio = (
            max(0.0, 1.0 - simulated_bytes / full_frame_bytes)
            if full_frame_bytes
            else 0.0
        )

        return TransportAnalysis(
            sequence=analysis.sequence,
            profile=self.profile.name,
            encoding=encoding,
            full_refresh=analysis.full_refresh,
            packets=tuple(packets),
            pixel_bytes=pixel_bytes,
            overhead_bytes=overhead_bytes,
            simulated_bytes=simulated_bytes,
            full_frame_bytes=full_frame_bytes,
            savings_ratio=savings_ratio,
            roundtrip_matches=differing_pixels == 0,
            differing_pixels=differing_pixels,
        )


def _png_bytes(image: Image.Image) -> bytes:
    output = BytesIO()
    image.convert("RGBA").save(output, format="PNG")
    return output.getvalue()


def _difference_preview(source: Image.Image, framebuffer: Image.Image) -> Image.Image:
    difference = ImageChops.difference(
        source.convert("RGBA"),
        framebuffer.convert("RGBA"),
    ).convert("RGB")
    return ImageEnhance.Contrast(difference).enhance(4.0).convert("RGBA")


def _atomic_write(destination: Path, payload: bytes) -> None:
    temporary = destination.with_name(
        f".{destination.name}.{os.getpid()}.tmp"
    )
    temporary.write_bytes(payload)
    os.replace(temporary, destination)


def write_transport_artifacts(
    directory: Path,
    source: Image.Image,
    framebuffer: Image.Image,
    analysis: TransportAnalysis,
) -> Path:
    """Atomically publish the virtual display and transport metrics."""
    root = Path(directory).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    files = {
        "latest-transport.png": _png_bytes(framebuffer),
        "latest-transport-diff.png": _png_bytes(
            _difference_preview(source, framebuffer)
        ),
        "transport-metrics.json": analysis.to_json().encode("utf-8"),
    }
    for name, payload in files.items():
        _atomic_write(root / name, payload)
    return root
