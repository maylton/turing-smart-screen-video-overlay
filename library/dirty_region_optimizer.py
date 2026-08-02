# SPDX-License-Identifier: GPL-3.0-or-later
"""Optimize dirty regions for the guarded Rev. C live path."""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageChops, ImageDraw

from library.atomic_regions import AtomicRegion
from library.frame_pipeline import FrameAnalysis, FrameRegion

TileRect = Tuple[int, int, int, int]


def _difference_mask(previous, current, threshold):
    difference = ImageChops.difference(
        previous.convert("RGBA"), current.convert("RGBA")
    )
    bounded = max(0, min(255, int(threshold)))
    masks = [
        channel.point(lambda value: 255 if value > bounded else 0)
        for channel in difference.split()
    ]
    mask = masks[0]
    for channel in masks[1:]:
        mask = ImageChops.lighter(mask, channel)
    return mask


def _changed_tiles(mask, tile_size):
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


def _row_spans(values):
    spans = []
    column = 0
    while column < len(values):
        if not values[column]:
            column += 1
            continue
        start = column
        while column < len(values) and values[column]:
            column += 1
        spans.append((start, column))
    return spans


def _run_regions(grid, width, height, tile_size):
    active: Dict[Tuple[int, int], TileRect] = {}
    completed: List[TileRect] = []
    for row, values in enumerate(grid):
        next_active = {}
        for span in _row_spans(values):
            existing = active.pop(span, None)
            if existing is None:
                next_active[span] = (span[0], row, span[1], row + 1)
            else:
                next_active[span] = (
                    existing[0], existing[1], existing[2], row + 1
                )
        completed.extend(active.values())
        active = next_active
    completed.extend(active.values())

    regions = []
    for left_tile, top_tile, right_tile, bottom_tile in completed:
        left = left_tile * tile_size
        top = top_tile * tile_size
        right = min(width, right_tile * tile_size)
        bottom = min(height, bottom_tile * tile_size)
        regions.append(
            FrameRegion(left, top, right - left, bottom - top)
        )
    return sorted(
        regions,
        key=lambda region: (
            region.y, region.x, region.height, region.width
        ),
    )


def _bounding_region(first, second):
    left = min(first.x, second.x)
    top = min(first.y, second.y)
    right = max(first.right, second.right)
    bottom = max(first.bottom, second.bottom)
    return FrameRegion(left, top, right - left, bottom - top)


def _overlap_area(first, second):
    width = max(0, min(first.right, second.right) - max(first.x, second.x))
    height = max(0, min(first.bottom, second.bottom) - max(first.y, second.y))
    return width * height


def _axis_gap(first_start, first_end, second_start, second_end):
    return max(
        0,
        max(first_start, second_start) - min(first_end, second_end),
    )


def _merge_to_limit(regions, max_regions):
    merged_regions = list(regions)
    while len(merged_regions) > max_regions:
        best = None
        for first_index in range(len(merged_regions) - 1):
            first = merged_regions[first_index]
            for second_index in range(first_index + 1, len(merged_regions)):
                second = merged_regions[second_index]
                combined = _bounding_region(first, second)
                union_area = (
                    first.area + second.area - _overlap_area(first, second)
                )
                added_area = combined.area - union_area
                gap = (
                    _axis_gap(first.x, first.right, second.x, second.right)
                    + _axis_gap(first.y, first.bottom, second.y, second.bottom)
                )
                key = (
                    added_area,
                    gap,
                    combined.area,
                    combined.y,
                    combined.x,
                    first_index,
                    second_index,
                )
                if best is None or key < best[0]:
                    best = (key, first_index, second_index, combined)
        if best is None:
            break
        _, first_index, second_index, combined = best
        merged_regions = [
            region
            for index, region in enumerate(merged_regions)
            if index not in (first_index, second_index)
        ]
        merged_regions.append(combined)
        merged_regions.sort(
            key=lambda region: (
                region.y, region.x, region.height, region.width
            )
        )
    return merged_regions


def _coverage_mask(size, regions):
    coverage = Image.new("L", size, 0)
    draw = ImageDraw.Draw(coverage)
    for region in regions:
        draw.rectangle(
            (region.x, region.y, region.right - 1, region.bottom - 1),
            fill=255,
        )
    return coverage


def _contains(container: FrameRegion, region: FrameRegion) -> bool:
    return (
        container.x <= region.x
        and container.y <= region.y
        and container.right >= region.right
        and container.bottom >= region.bottom
    )


def _selected_atomic_regions(
    mask: Image.Image,
    atomic_regions: Sequence[AtomicRegion],
) -> List[FrameRegion]:
    selected = []
    for atomic in atomic_regions:
        region = FrameRegion(atomic.x, atomic.y, atomic.width, atomic.height)
        if mask.crop((region.x, region.y, region.right, region.bottom)).getbbox():
            selected.append(region)

    # A containing atomic widget already guarantees every nested widget is sent
    # in one transaction, so avoid duplicate payloads for nested declarations.
    compact = []
    for region in sorted(selected, key=lambda item: item.area, reverse=True):
        if any(_contains(existing, region) for existing in compact):
            continue
        compact.append(region)
    return sorted(
        compact,
        key=lambda region: (region.y, region.x, region.height, region.width),
    )


def optimize_frame_analysis(
    previous: Optional[Image.Image],
    current: Image.Image,
    analysis: FrameAnalysis,
    *,
    tile_size: int,
    pixel_threshold: int,
    max_regions: int,
    full_refresh_ratio: float,
    atomic_regions: Sequence[AtomicRegion] = (),
) -> FrameAnalysis:
    """Return tighter regions while preserving changed pixels and atomic widgets."""
    if analysis.full_refresh or not analysis.regions or previous is None:
        return analysis
    if tile_size <= 0 or max_regions <= 0:
        raise ValueError("tile_size and max_regions must be positive")
    if not 0.0 <= full_refresh_ratio <= 1.0:
        raise ValueError("full_refresh_ratio must be between 0 and 1")

    previous_rgba = previous.convert("RGBA")
    current_rgba = current.convert("RGBA")
    previous_rgba.load()
    current_rgba.load()
    if previous_rgba.size != current_rgba.size:
        return analysis
    if current_rgba.size != (analysis.width, analysis.height):
        raise ValueError("frame size does not match the frame analysis")

    mask = _difference_mask(previous_rgba, current_rgba, pixel_threshold)
    selected_atomic = _selected_atomic_regions(mask, atomic_regions)

    remaining_mask = mask.copy()
    remaining_draw = ImageDraw.Draw(remaining_mask)
    for region in selected_atomic:
        remaining_draw.rectangle(
            (region.x, region.y, region.right - 1, region.bottom - 1),
            fill=0,
        )

    regions = selected_atomic + _run_regions(
        _changed_tiles(remaining_mask, int(tile_size)),
        analysis.width,
        analysis.height,
        int(tile_size),
    )
    if not regions:
        return analysis

    regions = _merge_to_limit(regions, int(max_regions))
    coverage = _coverage_mask(current_rgba.size, regions)
    if ImageChops.subtract(mask, coverage).getbbox() is not None:
        raise RuntimeError("optimized regions do not cover every changed pixel")

    coverage_pixels = int(coverage.histogram()[255])
    total_pixels = analysis.width * analysis.height
    coverage_ratio = coverage_pixels / total_pixels if total_pixels else 0.0
    if coverage_ratio >= full_refresh_ratio:
        return replace(
            analysis,
            regions=(FrameRegion(0, 0, analysis.width, analysis.height),),
            full_refresh=True,
        )
    return replace(analysis, regions=tuple(regions), full_refresh=False)
