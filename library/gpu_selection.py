# SPDX-License-Identifier: GPL-3.0-or-later
"""Persistent GPU preference and AMD adapter enumeration."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


CONFIG_DIRECTORY = "turing-smart-screen"
CONFIG_FILENAME = "hardware.json"
ENV_AMD_GPU_INDEX = "TURING_AMD_GPU_INDEX"


@dataclass(frozen=True)
class GpuPreference:
    mode: str = "auto"
    amd_index: Optional[int] = None

    def normalized(self) -> "GpuPreference":
        mode = str(self.mode or "auto").strip().lower()
        if mode != "index":
            return GpuPreference(mode="auto", amd_index=None)
        try:
            index = int(self.amd_index) if self.amd_index is not None else None
        except (TypeError, ValueError):
            index = None
        if index is None or index < 0:
            return GpuPreference(mode="auto", amd_index=None)
        return GpuPreference(mode="index", amd_index=index)


@dataclass(frozen=True)
class AmdGpuCandidate:
    index: int
    name: str
    vram_bytes: int

    @property
    def vram_gib(self) -> float:
        return self.vram_bytes / (1024 ** 3)

    @property
    def label(self) -> str:
        if self.vram_bytes > 0:
            return f"GPU {self.index} — {self.name} — {self.vram_gib:.1f} GiB"
        return f"GPU {self.index} — {self.name}"

    def to_dict(self) -> Dict[str, Union[int, float, str]]:
        payload = asdict(self)
        payload["vram_gib"] = round(self.vram_gib, 3)
        payload["label"] = self.label
        return payload


def config_home() -> Path:
    override = os.environ.get("XDG_CONFIG_HOME", "").strip()
    base = Path(override).expanduser() if override else Path.home() / ".config"
    return base / CONFIG_DIRECTORY


def preference_path() -> Path:
    return config_home() / CONFIG_FILENAME


def _preference_from_value(value: str) -> GpuPreference:
    value = str(value or "").strip().lower()
    if not value or value == "auto":
        return GpuPreference()
    try:
        index = int(value)
    except ValueError:
        return GpuPreference()
    return GpuPreference(mode="index", amd_index=index).normalized()


def load_preference(path: Optional[Path] = None) -> GpuPreference:
    environment = os.environ.get(ENV_AMD_GPU_INDEX, "").strip()
    if environment:
        return _preference_from_value(environment)

    selected_path = Path(path) if path is not None else preference_path()
    try:
        payload = json.loads(selected_path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return GpuPreference()

    if not isinstance(payload, dict):
        return GpuPreference()
    return GpuPreference(
        mode=str(payload.get("amd_gpu_mode") or "auto"),
        amd_index=payload.get("amd_gpu_index"),
    ).normalized()


def save_preference(preference: GpuPreference, path: Optional[Path] = None) -> Path:
    selected_path = Path(path) if path is not None else preference_path()
    selected_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = preference.normalized()
    payload = {
        "amd_gpu_mode": normalized.mode,
        "amd_gpu_index": normalized.amd_index,
    }
    temporary = selected_path.with_suffix(selected_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, selected_path)
    return selected_path


def _gpu_name(gpu: Any, index: int) -> str:
    for attribute in ("name", "marketing_name", "device_name"):
        value = getattr(gpu, attribute, None)
        if value:
            return str(value)
    return "AMD adapter"


def _gpu_vram(gpu: Any) -> int:
    try:
        memory_info = getattr(gpu, "memory_info", {}) or {}
        return max(0, int(memory_info.get("vram_size", 0) or 0))
    except (AttributeError, TypeError, ValueError):
        return 0


def enumerate_amd_gpus(api: Any) -> List[AmdGpuCandidate]:
    if api is None:
        return []
    try:
        count = max(0, int(api.detect_gpus()))
    except Exception:
        return []

    candidates = []
    for index in range(count):
        try:
            gpu = api.get_gpu(index)
        except Exception:
            continue
        candidates.append(
            AmdGpuCandidate(
                index=index,
                name=_gpu_name(gpu, index),
                vram_bytes=_gpu_vram(gpu),
            )
        )
    return candidates


def select_amd_gpu_index(
    api: Any,
    preference: Optional[GpuPreference] = None,
) -> int:
    candidates = enumerate_amd_gpus(api)
    if not candidates:
        return -1

    preference = (preference or load_preference()).normalized()
    if preference.mode == "index" and preference.amd_index is not None:
        available = {candidate.index for candidate in candidates}
        if preference.amd_index in available:
            return preference.amd_index

    # Stable automatic fallback: the discrete adapter normally reports the
    # largest dedicated VRAM. Ties preserve the first enumerated device.
    return max(candidates, key=lambda candidate: candidate.vram_bytes).index


def selection_summary(api: Any) -> Dict[str, object]:
    preference = load_preference()
    candidates = enumerate_amd_gpus(api)
    selected_index = select_amd_gpu_index(api, preference)
    selected = next(
        (candidate for candidate in candidates if candidate.index == selected_index),
        None,
    )
    return {
        "preference": {
            "mode": preference.mode,
            "amd_index": preference.amd_index,
            "source": "environment"
            if os.environ.get(ENV_AMD_GPU_INDEX, "").strip()
            else "configuration",
        },
        "selected_index": selected_index,
        "selected_label": selected.label if selected is not None else "",
        "candidates": [candidate.to_dict() for candidate in candidates],
        "configuration_path": str(preference_path()),
    }
