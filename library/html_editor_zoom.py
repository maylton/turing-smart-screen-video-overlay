# SPDX-License-Identifier: GPL-3.0-or-later
"""Zoom steps for the HTML theme editor preview."""

from __future__ import annotations

ZOOM_LEVELS = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)
DEFAULT_ZOOM = 1.0


def step_zoom(current: float, direction: int) -> float:
    """Return the next zoom level in ``direction`` (+1 in, -1 out, 0 reset).

    A value between two levels snaps to the neighbouring level in that
    direction; the ends of the range are kept.
    """
    if direction == 0:
        return DEFAULT_ZOOM
    if direction > 0:
        return next((level for level in ZOOM_LEVELS if level > current + 1e-9), ZOOM_LEVELS[-1])
    return next((level for level in reversed(ZOOM_LEVELS) if level < current - 1e-9), ZOOM_LEVELS[0])


def zoomed_size(width: int, height: int, zoom: float) -> tuple[int, int]:
    return max(1, round(width * zoom)), max(1, round(height * zoom))


def zoom_label(zoom: float) -> str:
    return f"{round(zoom * 100)}%"
