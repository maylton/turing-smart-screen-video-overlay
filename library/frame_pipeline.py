# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure-Python frame normalization and dirty-region analysis.

This module does not know about USB, serial ports, or display revisions. It
accepts complete RGBA frames and reports conservative rectangles that may be
used by a later simulated or physical sink.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageChops, ImageDraw

from library.atomic_regions import AtomicRegion


@dataclass(frozen=True)
class FrameRegion:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def area(self) -> int:
        return max(0, self.width) * max(0, self.height)

    def as_dict(self) -> Dict[str, int]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True)
class FrameAnalysis:
    sequence: int
    width: int
    height: int
    changed_pixels: int
    total_pixels: int
    change_ratio: float
    regions: Tuple[FrameRegion, ...]
    full_refresh: bool

    def as_dict(self) -> Dict[str, object]:
        return {
            "sequence": self.sequence,
            "width": self.width,
            "height": self.height,
            "changedPixels": self.changed_pixels,
            "totalPixels": self.total_pixels,
            "changeRatio": round(self.change_ratio, 6),
            "regions": [region.as_dict() for region in self.regions],
            "fullRefresh": self.full_refresh,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.as_dict(),
            indent=2,
            sort_keys=True,
        ) + "\n"


def decode_png_frame(
    payload: bytes,
    expected_size: Optional[Tuple[int, int]] = None,
) -> Image.Image:
    """Decode a PNG payload into a detached RGBA frame."""
    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise TypeError("PNG frame payload must be bytes-like")
    with Image.open(BytesIO(bytes(payload))) as opened:
        image = opened.convert("RGBA")
        image.load()
    if expected_size is not None and image.size != expected_size:
        raise ValueError(
            f"Frame size {image.size} does not match expected {expected_size}"
        )
    return image


def encode_png_frame(image: Image.Image) -> bytes:
    output = BytesIO()
    image.convert("RGBA").save(output, format="PNG")
    return output.getvalue()


def _difference_mask(
    previous: Image.Image,
    current: Image.Image,
    threshold: int,
) -> Image.Image:
    difference = ImageChops.difference(
        previous.convert("RGBA"),
        current.convert("RGBA"),
    )
    bounded = max(0, min(255, int(threshold)))
    channel_masks = [
        channel.point(lambda value: 255 if value > bounded else 0)
        for channel in difference.split()
    ]
    mask = channel_masks[0]
    for channel in channel_masks[1:]:
        mask = ImageChops.lighter(mask, channel)
    return mask


def _changed_tiles(mask: Image.Image, tile_size: int) -> List[List[bool]]:
    width, height = mask.size
    columns = (width + tile_size - 1) // tile_size
    rows = (height + tile_size - 1) // tile_size
    grid = [[False for _ in range(columns)] for _ in range(rows)]
    for row in range(rows):
        top = row * tile_size
        bottom = min(height, top + tile_size)
        for column in range(columns):
            left = column * tile_size
            right = min(width, left + tile_size)
            grid[row][column] = (
                mask.crop((left, top, right, bottom)).getbbox() is not None
            )
    return grid


def _component_regions(
    grid: Sequence[Sequence[bool]],
    width: int,
    height: int,
    tile_size: int,
) -> List[FrameRegion]:
    if not grid:
        return []
    rows = len(grid)
    columns = len(grid[0]) if rows else 0
    visited = set()
    regions: List[FrameRegion] = []

    for row in range(rows):
        for column in range(columns):
            if not grid[row][column] or (row, column) in visited:
                continue

            stack = [(row, column)]
            visited.add((row, column))
            min_row = max_row = row
            min_column = max_column = column

            while stack:
                current_row, current_column = stack.pop()
                min_row = min(min_row, current_row)
                max_row = max(max_row, current_row)
                min_column = min(min_column, current_column)
                max_column = max(max_column, current_column)

                for neighbor in (
                    (current_row - 1, current_column),
                    (current_row + 1, current_column),
                    (current_row, current_column - 1),
                    (current_row, current_column + 1),
                ):
                    neighbor_row, neighbor_column = neighbor
                    if not (
                        0 <= neighbor_row < rows
                        and 0 <= neighbor_column < columns
                    ):
                        continue
                    if neighbor in visited:
                        continue
                    if not grid[neighbor_row][neighbor_column]:
                        continue
                    visited.add(neighbor)
                    stack.append(neighbor)

            left = min_column * tile_size
            top = min_row * tile_size
            right = min(width, (max_column + 1) * tile_size)
            bottom = min(height, (max_row + 1) * tile_size)
            regions.append(
                FrameRegion(
                    x=left,
                    y=top,
                    width=right - left,
                    height=bottom - top,
                )
            )
    return regions


class FramePipeline:
    """Compare complete frames and emit conservative dirty rectangles."""

    def __init__(
        self,
        *,
        tile_size: int = 16,
        pixel_threshold: int = 4,
        full_refresh_ratio: float = 0.45,
        max_regions: int = 64,
    ) -> None:
        if tile_size <= 0:
            raise ValueError("tile_size must be greater than zero")
        if not 0.0 <= full_refresh_ratio <= 1.0:
            raise ValueError("full_refresh_ratio must be between 0 and 1")
        if max_regions <= 0:
            raise ValueError("max_regions must be greater than zero")
        self.tile_size = int(tile_size)
        self.pixel_threshold = max(0, min(255, int(pixel_threshold)))
        self.full_refresh_ratio = float(full_refresh_ratio)
        self.max_regions = int(max_regions)
        self._previous: Optional[Image.Image] = None
        self._sequence = 0

    @property
    def previous(self) -> Optional[Image.Image]:
        return self._previous.copy() if self._previous is not None else None

    def reset(self) -> None:
        self._previous = None
        self._sequence = 0

    def process(self, image: Image.Image) -> FrameAnalysis:
        current = image.convert("RGBA")
        current.load()
        self._sequence += 1
        width, height = current.size
        total_pixels = width * height
        full_region = FrameRegion(0, 0, width, height)

        if self._previous is None or self._previous.size != current.size:
            analysis = FrameAnalysis(
                sequence=self._sequence,
                width=width,
                height=height,
                changed_pixels=total_pixels,
                total_pixels=total_pixels,
                change_ratio=1.0,
                regions=(full_region,),
                full_refresh=True,
            )
            self._previous = current.copy()
            return analysis

        mask = _difference_mask(
            self._previous,
            current,
            self.pixel_threshold,
        )
        histogram = mask.histogram()
        changed_pixels = int(histogram[255])
        change_ratio = (
            changed_pixels / total_pixels
            if total_pixels
            else 0.0
        )

        if changed_pixels == 0:
            regions: Tuple[FrameRegion, ...] = ()
            full_refresh = False
        else:
            grid = _changed_tiles(mask, self.tile_size)
            calculated = _component_regions(
                grid,
                width,
                height,
                self.tile_size,
            )
            full_refresh = (
                change_ratio >= self.full_refresh_ratio
                or len(calculated) > self.max_regions
            )
            regions = (
                (full_region,)
                if full_refresh
                else tuple(calculated)
            )

        analysis = FrameAnalysis(
            sequence=self._sequence,
            width=width,
            height=height,
            changed_pixels=changed_pixels,
            total_pixels=total_pixels,
            change_ratio=change_ratio,
            regions=regions,
            full_refresh=full_refresh,
        )
        self._previous = current.copy()
        return analysis

    def process_png(self, payload: bytes) -> Tuple[Image.Image, FrameAnalysis]:
        frame = decode_png_frame(payload)
        return frame, self.process(frame)


def annotate_regions(
    image: Image.Image,
    analysis: FrameAnalysis,
) -> Image.Image:
    """Return a debug copy with dirty rectangles and a compact status strip."""
    canvas = image.convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    outline = (255, 80, 120, 255)
    for region in analysis.regions:
        right = max(region.x, region.right - 1)
        bottom = max(region.y, region.bottom - 1)
        draw.rectangle(
            (region.x, region.y, right, bottom),
            outline=outline,
            width=2,
        )
    label = (
        f"frame {analysis.sequence:04d}  "
        f"{analysis.change_ratio * 100:5.1f}%  "
        f"{len(analysis.regions)} region(s)"
    )
    strip_height = 22
    draw.rectangle(
        (0, max(0, canvas.height - strip_height), canvas.width, canvas.height),
        fill=(0, 0, 0, 190),
    )
    draw.text(
        (6, max(0, canvas.height - strip_height + 5)),
        label,
        fill=(255, 255, 255, 255),
    )
    return canvas


def write_frame_artifacts(
    directory: Path,
    frame: Image.Image,
    analysis: FrameAnalysis,
    *,
    atomic_regions: Sequence[AtomicRegion] = (),
) -> Path:
    """Atomically publish the latest frame, overlay, and metrics."""
    root = Path(directory).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    metrics = analysis.as_dict()
    metrics["atomicRegions"] = [region.as_dict() for region in atomic_regions]
    files = {
        "latest.png": encode_png_frame(frame),
        "latest-diff.png": encode_png_frame(
            annotate_regions(frame, analysis)
        ),
        "metrics.json": (
            json.dumps(metrics, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
    }
    for name, payload in files.items():
        destination = root / name
        temporary = destination.with_name(
            f".{destination.name}.{os.getpid()}.tmp"
        )
        temporary.write_bytes(payload)
        os.replace(temporary, destination)
    return root
