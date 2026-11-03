# SPDX-License-Identifier: GPL-3.0-or-later
"""Share the time of the last frame the display acknowledged.

A running monitor process does not prove that the screen is updating: after
a cold boot the firmware can stay frozen on its boot image while every
process looks healthy. The renderer records each acknowledged frame here and
the GTK application reports how long ago the display last answered.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

from library.runtime import runtime_directory

HEALTH_FILENAME = "display-health.json"
STALE_AFTER_SECONDS = 90.0


def default_health_path() -> Path:
    return runtime_directory() / HEALTH_FILENAME


def write_frame_ack(timestamp: float, path: Optional[Path] = None) -> None:
    """Atomically record the wall-clock time of the last acknowledged frame."""
    target = path or default_health_path()
    temporary = target.with_name(f".{target.name}.{os.getpid()}")
    temporary.write_text(
        json.dumps({"last_frame_ack": timestamp, "pid": os.getpid()}),
        encoding="utf-8",
    )
    os.replace(temporary, target)


def clear(path: Optional[Path] = None) -> None:
    try:
        (path or default_health_path()).unlink()
    except FileNotFoundError:
        pass


def last_frame_ack(path: Optional[Path] = None) -> Optional[float]:
    try:
        payload = json.loads((path or default_health_path()).read_text(encoding="utf-8"))
        return float(payload["last_frame_ack"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def frame_age(path: Optional[Path] = None, now: Optional[float] = None) -> Optional[float]:
    """Seconds since the display last acknowledged a frame, or None."""
    timestamp = last_frame_ack(path)
    if timestamp is None:
        return None
    return max(0.0, (time.time() if now is None else now) - timestamp)
