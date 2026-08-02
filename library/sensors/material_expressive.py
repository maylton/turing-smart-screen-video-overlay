# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional Linux sensor helpers used by the Material Expressive 2.1 theme."""

from __future__ import annotations

import math
import os
import re
from pathlib import Path
from typing import Iterable, Optional

import psutil


def _read_number(path: Path) -> float:
    try:
        return float(path.read_text(encoding="utf-8", errors="ignore").strip())
    except (OSError, ValueError):
        return math.nan


def _read_label(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return ""


def _hwmon_root() -> Path:
    return Path(os.environ.get("TURING_HWMON_ROOT", "/sys/class/hwmon"))


def _candidate_score(text: str, keywords: Iterable[str]) -> int:
    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    score = 0
    for index, keyword in enumerate(keywords):
        key = re.sub(r"[^a-z0-9]+", " ", keyword.lower()).strip()
        if key and key in normalized:
            score = max(score, 100 - index)
    return score


def _find_hwmon_input(kind: str, keywords: Iterable[str], override_env: str) -> Optional[Path]:
    override = os.environ.get(override_env, "").strip()
    if override:
        path = Path(override).expanduser()
        if path.is_file():
            return path

    root = _hwmon_root()
    if not root.is_dir():
        return None

    best: tuple[int, Optional[Path]] = (0, None)
    for hwmon in sorted(root.glob("hwmon*")):
        chip_name = _read_label(hwmon / "name")
        for input_path in sorted(hwmon.glob(f"{kind}[0-9]*_input")):
            stem = input_path.name.removesuffix("_input")
            label = _read_label(hwmon / f"{stem}_label")
            device_name = _read_label(hwmon / "device" / "name")
            score = _candidate_score(
                f"{chip_name} {device_name} {label} {stem}",
                keywords,
            )
            if score > best[0]:
                best = (score, input_path)

    return best[1]


class _HistorySensor:
    last_val = [math.nan] * 10
    value = math.nan

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        # The monitor creates a new sensor instance for every refresh. Keep
        # history per sensor type without letting the three subclasses share
        # one inherited mutable list.
        cls.last_val = [math.nan] * 10
        cls.value = math.nan

    @classmethod
    def _remember(cls, value: float) -> float:
        cls.value = value
        cls.last_val.append(value)
        cls.last_val.pop(0)
        return value

    def last_values(self):
        return self.last_val


class MaterialMemoryUsedGb(_HistorySensor):
    """RAM currently in use, formatted in GiB."""

    def as_numeric(self) -> float:
        return self._remember(psutil.virtual_memory().used / (1024 ** 3))

    def as_string(self) -> str:
        return f"{self.value:.1f} GB"


class MaterialLiquidTemperature(_HistorySensor):
    """Coolant/liquid temperature read from a matching Linux hwmon label."""

    _path: Optional[Path] = None
    _keywords = (
        "liquid",
        "coolant",
        "water temp",
        "water temperature",
        "water in",
        "water out",
        "h2o",
        "t sensor",
        "external temp",
    )

    def as_numeric(self) -> float:
        if self._path is None or not self._path.is_file():
            self.__class__._path = _find_hwmon_input(
                "temp",
                self._keywords,
                "TURING_LIQUID_TEMP_PATH",
            )
        if self._path is None:
            return self._remember(math.nan)

        value = _read_number(self._path)
        if not math.isnan(value) and abs(value) >= 1000:
            value /= 1000.0
        return self._remember(value)

    def as_string(self) -> str:
        if math.isnan(self.value):
            return "--.-°"
        return f"{self.value:.1f}°"


class MaterialPumpRpm(_HistorySensor):
    """AIO/water-pump speed read from a matching Linux hwmon fan label."""

    _path: Optional[Path] = None
    _keywords = (
        "aio pump",
        "water pump",
        "pump",
        "aio",
        "water",
    )

    def as_numeric(self) -> float:
        if self._path is None or not self._path.is_file():
            self.__class__._path = _find_hwmon_input(
                "fan",
                self._keywords,
                "TURING_PUMP_RPM_PATH",
            )
        if self._path is None:
            return self._remember(math.nan)
        return self._remember(_read_number(self._path))

    def as_string(self) -> str:
        if math.isnan(self.value):
            return "----"
        return f"{int(round(self.value))}"
