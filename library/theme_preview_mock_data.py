# SPDX-License-Identifier: GPL-3.0-or-later
"""Mock/sample values used by the app-shell theme preview renderer.

The Overview preview should match the Theme Editor as closely as possible.  The
editor renders with ``HW_SENSORS=STATIC`` and then calls the normal runtime
``stats`` callbacks.  Keep the values here derived from the same static sensor
constants and date/time formatting rules so the Overview does not drift from the
editor preview.
"""

from __future__ import annotations

import datetime
import locale
import platform
from typing import Any, Mapping

try:
    import babel.dates
except Exception:  # pragma: no cover - optional dependency guard
    babel = None  # type: ignore[assignment]

try:
    from psutil._common import bytes2human
except Exception:  # pragma: no cover - optional dependency guard
    bytes2human = None  # type: ignore[assignment]

try:
    from library.sensors import sensors_stub_static as static_sensors
except Exception:  # pragma: no cover - keep preview import-safe
    static_sensors = None  # type: ignore[assignment]


STATIC_PREVIEW_TIMESTAMP = 1694014609
STATIC_PREVIEW_DATETIME = datetime.datetime.fromtimestamp(STATIC_PREVIEW_TIMESTAMP)


def _static_attr(name: str, fallback: Any) -> Any:
    if static_sensors is None:
        return fallback
    return getattr(static_sensors, name, fallback)


STATIC_PERCENTAGE = float(_static_attr("PERCENTAGE_SENSOR_VALUE", 50.0))
STATIC_TEMPERATURE = float(_static_attr("TEMPERATURE_SENSOR_VALUE", 67.3))
STATIC_CPU_FREQ_MHZ = float(_static_attr("CPU_FREQ_MHZ", 2400.0))
STATIC_GPU_FREQ_MHZ = float(_static_attr("GPU_FREQ_MHZ", 1500.0))
STATIC_GPU_FPS = int(_static_attr("GPU_FPS", 120))
STATIC_GPU_MEM_TOTAL_GB = int(_static_attr("GPU_MEM_TOTAL_SIZE_GB", 32))
STATIC_MEMORY_TOTAL_GB = int(_static_attr("MEMORY_TOTAL_SIZE_GB", 64))
STATIC_DISK_TOTAL_GB = int(_static_attr("DISK_TOTAL_SIZE_GB", 1000))
STATIC_NETWORK_SPEED_BYTES = int(_static_attr("NETWORK_SPEED_BYTES", 1061000000))
STATIC_UPTIME_SECONDS = 4294036


def build_mock_preview_context(theme_doc: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return deterministic values matching the Theme Editor's STATIC preview."""
    context = _static_metric_context()
    context.update(
        {
            "DATE": format_preview_date("medium"),
            "DAY": format_preview_date("full"),
            "TIME": format_preview_time("short"),
            "TIME_SECONDS": format_preview_time("medium"),
            "HOUR": format_preview_time("short"),
            "MINUTE": STATIC_PREVIEW_DATETIME.strftime("%M"),
            "YEAR": STATIC_PREVIEW_DATETIME.strftime("%Y"),
            "MONTH": format_preview_date("MMM"),
            "THEME": _theme_name(theme_doc),
        }
    )
    return context


def _static_metric_context() -> dict[str, Any]:
    percentage = int(round(STATIC_PERCENTAGE))
    temperature = int(STATIC_TEMPERATURE)
    cpu_freq_ghz = STATIC_CPU_FREQ_MHZ / 1000
    gpu_freq_ghz = STATIC_GPU_FREQ_MHZ / 1000
    memory_used_bytes = int(STATIC_MEMORY_TOTAL_GB / 100 * STATIC_PERCENTAGE) * 1000000000
    memory_free_bytes = int(STATIC_MEMORY_TOTAL_GB / 100 * (100 - STATIC_PERCENTAGE)) * 1000000000
    disk_used_gb = int(STATIC_DISK_TOTAL_GB / 100 * STATIC_PERCENTAGE)
    disk_free_gb = int(STATIC_DISK_TOTAL_GB / 100 * (100 - STATIC_PERCENTAGE))
    gpu_mem_used_mb = int(STATIC_GPU_MEM_TOTAL_GB / 100 * STATIC_PERCENTAGE * 1024)
    gpu_mem_total_mb = int(STATIC_GPU_MEM_TOTAL_GB * 1024)

    return {
        "PERCENTAGE": percentage,
        "USAGE": percentage,
        "LOAD": percentage,
        "CPU": percentage,
        "CPU_USAGE": percentage,
        "CPU_LOAD": percentage,
        "CPU_TEMP": temperature,
        "TEMP_CPU": temperature,
        "CPU_FREQUENCY": f"{cpu_freq_ghz:.2f}",
        "CPU_FREQ": f"{cpu_freq_ghz:.2f}",
        "GPU": percentage,
        "GPU_USAGE": percentage,
        "GPU_LOAD": percentage,
        "GPU_TEMP": temperature,
        "TEMP_GPU": temperature,
        "GPU_FPS": STATIC_GPU_FPS,
        "FPS": STATIC_GPU_FPS,
        "GPU_FREQUENCY": f"{gpu_freq_ghz:.2f}",
        "GPU_FREQ": f"{gpu_freq_ghz:.2f}",
        "VRAM": percentage,
        "GPU_MEMORY": percentage,
        "GPU_MEMORY_USED": gpu_mem_used_mb,
        "GPU_MEMORY_TOTAL": gpu_mem_total_mb,
        "RAM": percentage,
        "MEMORY": percentage,
        "MEMORY_USAGE": percentage,
        "MEMORY_USED": int(memory_used_bytes / 1024**2),
        "MEMORY_FREE": int(memory_free_bytes / 1024**2),
        "MEMORY_TOTAL": int((memory_used_bytes + memory_free_bytes) / 1024**2),
        "DISK": percentage,
        "DISK_USAGE": percentage,
        "DISK_USED": disk_used_gb,
        "DISK_FREE": disk_free_gb,
        "DISK_TOTAL": disk_used_gb + disk_free_gb,
        "NET": percentage,
        "NET_RX": _format_network_rate(STATIC_NETWORK_SPEED_BYTES),
        "NET_TX": _format_network_rate(STATIC_NETWORK_SPEED_BYTES),
        "DOWNLOAD": _format_network_rate(STATIC_NETWORK_SPEED_BYTES),
        "UPLOAD": _format_network_rate(STATIC_NETWORK_SPEED_BYTES),
        "DOWNLOADED": _format_data_total(STATIC_NETWORK_SPEED_BYTES),
        "UPLOADED": _format_data_total(STATIC_NETWORK_SPEED_BYTES),
        "FAN": percentage,
        "FAN_SPEED": percentage,
        "BATTERY": percentage,
        "STORAGE": percentage,
        "UPTIME_SECONDS": STATIC_UPTIME_SECONDS,
        "UPTIME": str(datetime.timedelta(seconds=STATIC_UPTIME_SECONDS)),
    }


def _format_network_rate(value: int) -> str:
    if bytes2human is None:
        return f"{value / 1024**2:.1f} MB/s"
    return bytes2human(value, "%(value).1f %(symbol)s/s")


def _format_data_total(value: int) -> str:
    if bytes2human is None:
        return f"{value / 1024**2:.1f} MB"
    return bytes2human(value)


def format_preview_date(format_name: Any = "medium") -> str:
    """Format the editor's STATIC preview date using stats.Date semantics."""
    format_name = str(format_name or "medium").strip().strip('"\'') or "medium"
    if babel is not None:
        try:
            return babel.dates.format_date(
                STATIC_PREVIEW_DATETIME,
                format=format_name,
                locale=_lc_time_locale(),
            )
        except Exception:
            pass
    return _fallback_date(format_name)


def format_preview_time(format_name: Any = "medium") -> str:
    """Format the editor's STATIC preview time using stats.Date semantics."""
    format_name = str(format_name or "medium").strip().strip('"\'') or "medium"
    if babel is not None:
        try:
            return babel.dates.format_time(
                STATIC_PREVIEW_DATETIME,
                format=format_name,
                locale=_lc_time_locale(),
            )
        except Exception:
            pass
    return _fallback_time(format_name)


def _lc_time_locale() -> str:
    try:
        if platform.system() == "Windows":
            lc_time = locale.getdefaultlocale()[0]
        elif babel is not None:
            lc_time = babel.dates.LC_TIME
        else:
            lc_time = None
    except Exception:
        lc_time = None
    return str(lc_time or "en_US")


def _fallback_date(format_name: str) -> str:
    if format_name == "short":
        return STATIC_PREVIEW_DATETIME.strftime("%-d/%-m/%y")
    if format_name == "full":
        return STATIC_PREVIEW_DATETIME.strftime("%A, %-d de %b. de %Y")
    if format_name == "long":
        return STATIC_PREVIEW_DATETIME.strftime("%-d de %B de %Y")
    return STATIC_PREVIEW_DATETIME.strftime("%-d de %b. de %Y")


def _fallback_time(format_name: str) -> str:
    if format_name in {"medium", "long", "full"}:
        return STATIC_PREVIEW_DATETIME.strftime("%H:%M:%S")
    return STATIC_PREVIEW_DATETIME.strftime("%H:%M")


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
    if any(token in joined for token in ("CLOCK", "TIME", "HOUR")):
        return format_preview_time(node.get("FORMAT", "short") if isinstance(node, Mapping) else "short")
    if any(token in joined for token in ("DATE", "DAY", "MONTH", "YEAR")):
        return format_preview_date(node.get("FORMAT", "medium") if isinstance(node, Mapping) else "medium")

    metric_value = _metric_value_for_candidates(candidates, joined, context)
    if metric_value is not None:
        return metric_value
    return int(round(STATIC_PERCENTAGE))


def _metric_value_for_candidates(candidates: list[str], joined: str, context: Mapping[str, Any]) -> Any:
    exact_candidates = [candidate for candidate in candidates if candidate]

    if any(token in joined for token in ("TEMP", "TEMPERATURE")):
        return int(STATIC_TEMPERATURE)
    if "FPS" in joined:
        return STATIC_GPU_FPS
    if "FREQUENCY" in joined or "FREQ" in joined:
        if "GPU" in joined:
            return f"{STATIC_GPU_FREQ_MHZ / 1000:.2f}"
        return f"{STATIC_CPU_FREQ_MHZ / 1000:.2f}"
    if any(token in joined for token in ("RX", "DOWNLOAD")):
        return context.get("NET_RX")
    if any(token in joined for token in ("TX", "UPLOAD")):
        return context.get("NET_TX")
    if "UPTIME" in joined:
        return context.get("UPTIME")
    if "FAN" in joined:
        return int(round(STATIC_PERCENTAGE))
    if any(token in joined for token in ("USED", "FREE", "TOTAL")):
        for key in exact_candidates:
            if key in context:
                return context[key]
        for key, value in context.items():
            if str(key).upper() in joined:
                return value

    for key in exact_candidates:
        if key in context:
            return context[key]
    for key, value in context.items():
        key_upper = str(key).upper()
        if key_upper in joined:
            return value
    return None


def numeric_percent(value: Any, *, default: int = 50) -> int:
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
