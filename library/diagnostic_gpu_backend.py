# SPDX-License-Identifier: GPL-3.0-or-later
"""AMD GPU adapter that does not import optional NVIDIA dependencies.

The HTML simulator needs only a renderer-neutral snapshot. On Linux systems with
an AMD adapter, importing ``sensors_python`` just to read that snapshot also
imports GPUtil, even though GPUtil is NVIDIA-only. This adapter exposes the small
``Gpu`` API expected by :class:`RealSensorSource` directly from the existing AMD
diagnostics module.
"""

from __future__ import annotations

import math
import time
from types import SimpleNamespace
from typing import Any, Callable, Mapping, Optional, Tuple

from library.gpu_diagnostics import collect_gpu_diagnostics


MIB = float(1024 ** 2)


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


class DiagnosticGpuProvider:
    """Cache one diagnostics sample for the related GPU reader calls."""

    def __init__(
        self,
        collector: Callable[[], Mapping[str, Any]] = collect_gpu_diagnostics,
        *,
        clock: Callable[[], float] = time.monotonic,
        cache_seconds: float = 0.20,
    ) -> None:
        self._collector = collector
        self._clock = clock
        self._cache_seconds = max(0.0, float(cache_seconds))
        self._cached_at: Optional[float] = None
        self._cached: Mapping[str, Any] = {}
        self.backend = SimpleNamespace(Gpu=self._build_gpu_proxy())

    def diagnostics(self, *, refresh: bool = False) -> Mapping[str, Any]:
        now = float(self._clock())
        expired = (
            self._cached_at is None
            or now - self._cached_at >= self._cache_seconds
        )
        if refresh or expired:
            payload = self._collector() or {}
            self._cached = payload if isinstance(payload, Mapping) else {}
            self._cached_at = now
        return self._cached

    def is_available(self) -> bool:
        diagnostics = self.diagnostics()
        try:
            selected_index = int(diagnostics.get("selected_index", -1))
        except (TypeError, ValueError):
            selected_index = -1
        return bool(diagnostics.get("available", False)) and selected_index >= 0

    def _metrics(self) -> Mapping[str, Any]:
        metrics = self.diagnostics().get("metrics", {})
        return metrics if isinstance(metrics, Mapping) else {}

    def stats(self) -> Tuple[float, float, float, float, float]:
        metrics = self._metrics()
        load = _finite(metrics.get("load_percent"))
        memory_percent = _finite(metrics.get("vram_percent"))
        used_bytes = _finite(metrics.get("vram_used_bytes"))
        total_bytes = _finite(metrics.get("vram_total_bytes"))
        temperature = _finite(metrics.get("temperature_c"))
        return (
            load if load is not None else math.nan,
            memory_percent if memory_percent is not None else math.nan,
            used_bytes / MIB if used_bytes is not None else math.nan,
            total_bytes / MIB if total_bytes is not None else math.nan,
            temperature if temperature is not None else math.nan,
        )

    def frequency(self) -> float:
        value = _finite(self._metrics().get("clock_mhz"))
        return value if value is not None else math.nan

    @staticmethod
    def fan_percent() -> float:
        return math.nan

    @staticmethod
    def fps() -> int:
        return -1

    def _build_gpu_proxy(self):
        provider = self

        class GpuProxy:
            @staticmethod
            def is_available() -> bool:
                return provider.is_available()

            @staticmethod
            def stats():
                return provider.stats()

            @staticmethod
            def frequency():
                return provider.frequency()

            @staticmethod
            def fan_percent():
                return provider.fan_percent()

            @staticmethod
            def fps():
                return provider.fps()

        return GpuProxy
