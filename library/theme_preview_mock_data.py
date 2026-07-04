# SPDX-License-Identifier: GPL-3.0-or-later
"""Mock/sample values used by the app-shell theme preview renderer.

The Overview preview should be useful even when the monitor process is not
running.  These values deliberately stay deterministic so generated GIF previews
are cacheable and visually stable during UI testing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping


SAMPLE_METRICS: dict[str, Any] = {
    "CPU": 37,
    "CPU_USAGE": 37,
    "CPU_LOAD": 37,
    "CPU_TEMP": 58,
    "TEMP_CPU": 58,
    "GPU": 54,
    "GPU_USAGE": 54,
    "GPU_TEMP": 61,
    "TEMP_GPU": 61,
    "RAM": 62,
    "MEMORY": 62,
    "MEMORY_USAGE": 62,
    "VRAM": 48,
    "DISK": 71,
    "DISK_USAGE": 71,
    "NET": 42,
    "NET_RX": "12.4 MB/s",
    "NET_TX": "2.1 MB/s",
    "DOWNLOAD": "12.4 MB/s",
    "UPLOAD": "2.1 MB/s",
    "FAN": "1420 RPM",
    "FAN_SPEED": "1420 RPM",
    "FPS": 144,
    "UPTIME": "3h 12m",
    "BATTERY": 86,
    "STORAGE": 71,
}


def build_mock_preview_context(theme_doc: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return deterministic but realistic sample values for theme previews."""
    now = datetime(2026, 7, 4, 22, 48, 0)
    context = dict(SAMPLE_METRICS)
    context.update(
        {
            "DATE": now.strftime("%a %d %b"),
            "DAY": now.strftime("%A"),
            "TIME": now.strftime("%H:%M"),
            "TIME_SECONDS": now.strftime("%H:%M:%S"),
            "HOUR": now.strftime("%H"),
            "MINUTE": now.strftime("%M"),
            "YEAR": now.strftime("%Y"),
            "MONTH": now.strftime("%B"),
            "THEME": _theme_name(theme_doc),
        }
    )
    return context


def _theme_name(theme_doc: Mapping[str, Any] | None) -> str:
    if not isinstance(theme_doc, Mapping):
        return "Preview"
    display = theme_doc.get("display", {})
    if isinstance(display, Mapping):
        name = display.get("THEME_NAME") or display.get("NAME")
        if name:
            return str(name)
    return "Preview"


def value_for_path(path: tuple[Any, ...], node: Mapping[str, Any] | None, context: Mapping[str, Any]) -> Any:
    """Pick a mock value for an arbitrary theme element path/node."""
    candidates: list[str] = []
    for part in path:
        text = str(part).upper()
        candidates.append(text)
        candidates.extend(text.replace("-", "_").split("_"))

    if isinstance(node, Mapping):
        for key in ("TEXT", "FORMAT", "SENSOR", "SOURCE", "METRIC", "VALUE", "SHOW_UNIT"):
            raw = node.get(key)
            if raw is not None:
                candidates.append(str(raw).upper())

    joined = "_".join(candidates)
    for key, value in context.items():
        key_upper = str(key).upper()
        if key_upper in candidates or key_upper in joined:
            return value

    if any(token in joined for token in ("CLOCK", "TIME", "HOUR")):
        return context.get("TIME")
    if any(token in joined for token in ("DATE", "DAY", "MONTH")):
        return context.get("DATE")
    if "TEMP" in joined:
        return 58
    if any(token in joined for token in ("RX", "DOWNLOAD")):
        return context.get("NET_RX")
    if any(token in joined for token in ("TX", "UPLOAD")):
        return context.get("NET_TX")
    if any(token in joined for token in ("BAR", "GAUGE", "GRAPH", "LINE")):
        return 62
    return 42


def numeric_percent(value: Any, *, default: int = 42) -> int:
    """Coerce a sample value to 0..100 for bars/gauges/graphs."""
    if isinstance(value, (int, float)):
        number = int(round(float(value)))
    else:
        text = str(value or "")
        digits = "".join(ch if ch.isdigit() or ch == "." else " " for ch in text).split()
        try:
            number = int(round(float(digits[0]))) if digits else default
        except ValueError:
            number = default
    return max(0, min(100, number))
