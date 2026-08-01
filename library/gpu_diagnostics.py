# SPDX-License-Identifier: GPL-3.0-or-later
"""Safe GPU selection and sensor diagnostics."""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, Optional

from library.gpu_selection import selection_summary

try:
    import pyamdgpuinfo
except Exception:
    pyamdgpuinfo = None


def _metric(callback: Callable[[], Any], scale: float = 1.0) -> Optional[float]:
    try:
        value = float(callback()) * scale
    except Exception:
        return None
    return value if math.isfinite(value) else None


def collect_gpu_diagnostics(api: Any = None) -> Dict[str, object]:
    selected_api = pyamdgpuinfo if api is None else api
    summary = selection_summary(selected_api)
    selected_index = int(summary.get("selected_index", -1))
    payload: Dict[str, object] = {
        "backend": "pyamdgpuinfo",
        "available": selected_api is not None,
        **summary,
        "metrics": {},
    }

    if selected_api is None:
        payload["error"] = "pyamdgpuinfo is not installed"
        return payload
    if selected_index < 0:
        payload["error"] = "No AMD GPU was detected"
        return payload

    try:
        gpu = selected_api.get_gpu(selected_index)
    except Exception as exc:
        payload["error"] = f"Could not open AMD GPU index {selected_index}: {exc}"
        return payload

    memory_info = getattr(gpu, "memory_info", {}) or {}
    total_vram = _metric(lambda: memory_info.get("vram_size", 0))
    used_vram = _metric(gpu.query_vram_usage)
    metrics = {
        "load_percent": _metric(gpu.query_load, 100.0),
        "temperature_c": _metric(gpu.query_temperature),
        "vram_used_bytes": used_vram,
        "vram_total_bytes": total_vram,
        "clock_mhz": _metric(gpu.query_sclk, 1.0 / 1_000_000.0),
    }
    if used_vram is not None and total_vram not in (None, 0):
        metrics["vram_percent"] = used_vram / total_vram * 100.0
    else:
        metrics["vram_percent"] = None
    payload["metrics"] = metrics
    return payload
