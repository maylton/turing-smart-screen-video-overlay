# SPDX-License-Identifier: GPL-3.0-or-later
"""Read real system sensors into renderer-neutral snapshot sections.

Imports stay lazy so opening the HTML theme simulator with synthetic data does
not initialize GPU libraries or probe hardware. Each reader is independent and
is therefore isolated by :class:`SensorSnapshotCollector`.
"""

from __future__ import annotations

import math
import platform
import socket
import time
from typing import Any, Callable, Dict, Mapping, Optional

from library.sensor_snapshot import Reader


GIB = float(1024 ** 3)
MIB = float(1024 ** 2)


def _finite(value: Any, digits: Optional[int] = None) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits) if digits is not None else number


def _non_negative(value: Any, digits: Optional[int] = None) -> Optional[float]:
    number = _finite(value, digits)
    if number is None:
        return None
    return max(0.0, number)


class RealSensorSource:
    """Build real sensor readers without coupling them to a theme engine."""

    def __init__(
        self,
        *,
        network_interface: str = "",
        psutil_module: Any = None,
        gpu_backend_factory: Optional[Callable[[], Any]] = None,
        gpu_diagnostics_factory: Optional[Callable[[], Mapping[str, Any]]] = None,
        monotonic_clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        self.network_interface = str(network_interface or "").strip()
        self._psutil_module = psutil_module
        self._gpu_backend_factory = gpu_backend_factory
        self._gpu_diagnostics_factory = gpu_diagnostics_factory
        self._monotonic_clock = monotonic_clock
        self._wall_clock = wall_clock
        self._gpu_backend: Any = None
        self._gpu_initialized = False
        self._network_before: Dict[str, Any] = {}
        self._network_time: Optional[float] = None

    def _psutil(self) -> Any:
        if self._psutil_module is None:
            import psutil

            self._psutil_module = psutil
        return self._psutil_module

    def _gpu(self) -> Any:
        if self._gpu_backend is None:
            if self._gpu_backend_factory is not None:
                self._gpu_backend = self._gpu_backend_factory()
            else:
                from library.gpu_selection_runtime import install

                install()
                from library.sensors import sensors_python

                self._gpu_backend = sensors_python

        if not self._gpu_initialized:
            available = getattr(self._gpu_backend.Gpu, "is_available", None)
            if callable(available):
                available()
            self._gpu_initialized = True
        return self._gpu_backend

    def _gpu_diagnostics(self) -> Mapping[str, Any]:
        if self._gpu_diagnostics_factory is not None:
            return self._gpu_diagnostics_factory()
        from library.gpu_diagnostics import collect_gpu_diagnostics

        return collect_gpu_diagnostics()

    @staticmethod
    def _cpu_temperature(psutil_module: Any) -> Optional[float]:
        getter = getattr(psutil_module, "sensors_temperatures", None)
        if not callable(getter):
            return None
        readings = getter() or {}
        preferred = ("k10temp", "coretemp", "zenpower", "cpu_thermal")
        groups = [readings[name] for name in preferred if name in readings]
        if not groups:
            groups = list(readings.values())
        for entries in groups:
            for entry in entries or ():
                value = _finite(getattr(entry, "current", None), 1)
                if value is not None:
                    return value
        return None

    def read_cpu(self) -> Dict[str, Any]:
        psutil_module = self._psutil()
        frequency = None
        frequency_reader = getattr(psutil_module, "cpu_freq", None)
        if callable(frequency_reader):
            result = frequency_reader()
            frequency = _finite(getattr(result, "current", None))
            if frequency is not None:
                frequency = round(frequency / 1000.0, 2)

        load = []
        load_reader = getattr(psutil_module, "getloadavg", None)
        if callable(load_reader):
            try:
                load = [
                    _finite(value, 2)
                    for value in load_reader()
                ]
            except (OSError, AttributeError):
                load = []

        usage_reader = getattr(psutil_module, "cpu_percent")
        usage = _non_negative(usage_reader(interval=None), 1)
        return {
            "usage": usage,
            "temperature": self._cpu_temperature(psutil_module),
            "frequency": frequency,
            "load": load,
            "logicalCores": getattr(psutil_module, "cpu_count")(logical=True),
            "physicalCores": getattr(psutil_module, "cpu_count")(logical=False),
        }

    def read_gpu(self) -> Dict[str, Any]:
        backend = self._gpu()
        load, memory_percent, used_mib, total_mib, temperature = (
            backend.Gpu.stats()
        )
        diagnostics = dict(self._gpu_diagnostics() or {})
        selected_label = str(diagnostics.get("selected_label") or "").strip()
        metrics = diagnostics.get("metrics")
        metrics = metrics if isinstance(metrics, Mapping) else {}

        frequency_reader = getattr(backend.Gpu, "frequency", None)
        fan_reader = getattr(backend.Gpu, "fan_percent", None)
        fps_reader = getattr(backend.Gpu, "fps", None)
        frequency = frequency_reader() if callable(frequency_reader) else None
        fan = fan_reader() if callable(fan_reader) else None
        fps = fps_reader() if callable(fps_reader) else None

        used_bytes = _finite(metrics.get("vram_used_bytes"))
        total_bytes = _finite(metrics.get("vram_total_bytes"))
        used_gib = (
            round(used_bytes / GIB, 2)
            if used_bytes is not None
            else (
                round(float(used_mib) / 1024.0, 2)
                if _finite(used_mib) is not None
                else None
            )
        )
        total_gib = (
            round(total_bytes / GIB, 2)
            if total_bytes is not None
            else (
                round(float(total_mib) / 1024.0, 2)
                if _finite(total_mib) is not None
                else None
            )
        )

        return {
            "available": bool(diagnostics.get("available", True)),
            "name": selected_label or str(diagnostics.get("backend") or "GPU"),
            "usage": _non_negative(load, 1),
            "temperature": _finite(temperature, 1),
            "frequency": _non_negative(frequency, 0),
            "fan": _non_negative(fan, 1),
            "fps": int(fps) if _finite(fps) is not None and int(fps) >= 0 else None,
            "vramUsage": _non_negative(memory_percent, 1),
            "vramUsed": used_gib,
            "vramTotal": total_gib,
            "selectedIndex": diagnostics.get("selected_index"),
        }

    def read_memory(self) -> Dict[str, Any]:
        psutil_module = self._psutil()
        memory = psutil_module.virtual_memory()
        swap = psutil_module.swap_memory()
        used = max(0, int(memory.total) - int(memory.available))
        return {
            "usage": _non_negative(memory.percent, 1),
            "used": round(used / GIB, 2),
            "available": round(max(0, int(memory.available)) / GIB, 2),
            "total": round(max(0, int(memory.total)) / GIB, 2),
            "swapUsage": _non_negative(swap.percent, 1),
            "swapUsed": round(max(0, int(swap.used)) / GIB, 2),
            "swapTotal": round(max(0, int(swap.total)) / GIB, 2),
        }

    def read_disk(self) -> Dict[str, Any]:
        usage = self._psutil().disk_usage("/")
        return {
            "mount": "/",
            "usage": _non_negative(usage.percent, 1),
            "used": round(max(0, int(usage.used)) / GIB, 2),
            "free": round(max(0, int(usage.free)) / GIB, 2),
            "total": round(max(0, int(usage.total)) / GIB, 2),
        }

    def _choose_network_interface(
        self,
        counters: Mapping[str, Any],
        stats: Mapping[str, Any],
    ) -> str:
        if self.network_interface:
            if self.network_interface not in counters:
                raise ValueError(
                    "Network interface not found: "
                    f"{self.network_interface}"
                )
            return self.network_interface

        candidates = []
        for name, counter in counters.items():
            if name.lower().startswith("lo"):
                continue
            status = stats.get(name)
            if status is not None and not bool(getattr(status, "isup", False)):
                continue
            activity = int(getattr(counter, "bytes_sent", 0)) + int(
                getattr(counter, "bytes_recv", 0)
            )
            candidates.append((activity, name))
        if not candidates:
            return ""
        return max(candidates)[1]

    def read_network(self) -> Dict[str, Any]:
        psutil_module = self._psutil()
        counters = psutil_module.net_io_counters(pernic=True) or {}
        stats_reader = getattr(psutil_module, "net_if_stats", None)
        stats = stats_reader() if callable(stats_reader) else {}
        interface = self._choose_network_interface(counters, stats)
        now = float(self._monotonic_clock())

        if not interface:
            self._network_before = {}
            self._network_time = now
            return {
                "interface": "",
                "upload": 0.0,
                "download": 0.0,
                "uploaded": 0,
                "downloaded": 0,
            }

        current = counters[interface]
        previous = self._network_before.get(interface)
        elapsed = (
            max(0.001, now - self._network_time)
            if self._network_time is not None
            else None
        )
        upload_rate = 0.0
        download_rate = 0.0
        if previous is not None and elapsed is not None:
            upload_rate = max(
                0.0,
                (int(current.bytes_sent) - int(previous.bytes_sent)) / elapsed,
            )
            download_rate = max(
                0.0,
                (int(current.bytes_recv) - int(previous.bytes_recv)) / elapsed,
            )

        self._network_before = {interface: current}
        self._network_time = now
        return {
            "interface": interface,
            "upload": round(upload_rate / MIB, 2),
            "download": round(download_rate / MIB, 2),
            "uploaded": int(current.bytes_sent),
            "downloaded": int(current.bytes_recv),
        }

    def read_system(self) -> Dict[str, Any]:
        psutil_module = self._psutil()
        now = float(self._wall_clock())
        boot_time = getattr(psutil_module, "boot_time", lambda: now)()
        return {
            "hostname": socket.gethostname(),
            "platform": platform.system(),
            "platformRelease": platform.release(),
            "architecture": platform.machine(),
            "time": time.strftime("%H:%M:%S", time.localtime(now)),
            "uptime": max(0, int(now - float(boot_time))),
        }

    def readers(self) -> Dict[str, Reader]:
        return {
            "cpu": self.read_cpu,
            "gpu": self.read_gpu,
            "memory": self.read_memory,
            "disk": self.read_disk,
            "network": self.read_network,
            "system": self.read_system,
        }
