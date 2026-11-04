# SPDX-License-Identifier: GPL-3.0-or-later
"""Tick layout for the HTML theme editor rulers.

Positions are in theme pixels; the ruler widget multiplies them by the
preview zoom. Steps grow when zoomed out so labels never overlap.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

RULER_THICKNESS_PX = 20
# Smallest gap, in screen pixels, between two labelled ticks.
MIN_LABEL_GAP_PX = 44
_STEPS = (5, 10, 25, 50, 100, 200)


@dataclass(frozen=True)
class Tick:
    position: int  # theme pixels
    major: bool
    label: str


def tick_steps(zoom: float) -> tuple[int, int]:
    """Return (minor, major) steps in theme pixels for ``zoom``."""
    zoom = max(float(zoom), 0.01)
    major = next((step for step in _STEPS if step * zoom >= MIN_LABEL_GAP_PX), _STEPS[-1])
    minor = next((step for step in reversed(_STEPS) if step < major and step * zoom >= 6), major)
    return minor, major


def ruler_ticks(length: int, zoom: float) -> list[Tick]:
    minor, major = tick_steps(zoom)
    ticks = []
    for position in range(0, int(length) + 1, minor):
        is_major = position % major == 0
        ticks.append(Tick(position, is_major, str(position) if is_major else ""))
    return ticks


def selection_span(boxes: Iterable[tuple[int, int, int, int]], axis: str) -> Optional[tuple[int, int]]:
    """Extent of ``(x, y, width, height)`` boxes along ``axis`` ('x' or 'y')."""
    boxes = list(boxes)
    if not boxes:
        return None
    if axis == "x":
        return min(b[0] for b in boxes), max(b[0] + b[2] for b in boxes)
    return min(b[1] for b in boxes), max(b[1] + b[3] for b in boxes)


def cursor_position(widget_x: float, widget_y: float, zoom: float, width: int, height: int) -> Optional[tuple[int, int]]:
    """Theme pixel under a point of the zoomed preview, or None outside it."""
    zoom = max(float(zoom), 0.01)
    x, y = int(widget_x // zoom), int(widget_y // zoom)
    if 0 <= x < width and 0 <= y < height:
        return x, y
    return None
