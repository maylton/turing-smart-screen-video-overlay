# SPDX-License-Identifier: GPL-3.0-or-later
"""Sensor data shown by the HTML theme editor preview.

The presets mirror the snapshot structure the runtime sends to themes.
"Custom" starts from a preset and overrides individual bindings, so theme
authors can check how long or extreme values fit.
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass
from typing import Mapping

PRESET_KEYS = ("normal", "maximum", "unavailable", "custom")
PRESET_LABELS = ("Valores normais", "Valores máximos", "Sensores indisponíveis", "Valores personalizados")


@dataclass(frozen=True)
class CustomField:
    binding: str
    label: str


# The bindings themes use most; see docs/HTML_THEME_AUTHORING_GUIDE.md.
CUSTOM_FIELDS = (
    CustomField("cpu.usage", "CPU · uso (%)"),
    CustomField("cpu.temperature", "CPU · temperatura (°C)"),
    CustomField("cpu.frequency", "CPU · frequência (GHz)"),
    CustomField("gpu.usage", "GPU · uso (%)"),
    CustomField("gpu.temperature", "GPU · temperatura (°C)"),
    CustomField("gpu.fps", "GPU · FPS"),
    CustomField("memory.usage", "RAM · uso (%)"),
    CustomField("memory.used", "RAM · usada (GiB)"),
    CustomField("disk.usage", "Disco · uso (%)"),
    CustomField("network.download", "Rede · download (MiB/s)"),
    CustomField("network.upload", "Rede · upload (MiB/s)"),
    CustomField("weather.temperature", "Clima · temperatura"),
    CustomField("weather.description", "Clima · descrição"),
    CustomField("system.hostname", "Sistema · nome do host"),
    CustomField("system.time", "Sistema · hora"),
)


def preset_data(preset: str = "normal") -> dict:
    preset = str(preset or "normal").strip().lower()
    if preset == "maximum":
        return {
            "cpu": {"usage": 100, "temperature": 99, "frequency": 5.9, "load": [32.0, 31.5, 30.0]},
            "gpu": {"usage": 100, "temperature": 99, "fps": 999, "vramUsed": 99.9, "vramTotal": 128},
            "memory": {"usage": 100, "used": 128.0, "total": 128},
            "disk": {"usage": 100},
            "network": {"download": 999.9, "upload": 999.9},
            "weather": {"temperature": "49.9°C", "description": "Tempestade com trovoadas fortes"},
            "system": {"hostname": "workstation-com-nome-bem-longo", "time": "23:59:59"},
        }
    if preset == "unavailable":
        return {
            "cpu": {}, "gpu": {}, "memory": {}, "disk": {}, "network": {}, "weather": {},
            "system": {"time": "--:--"},
        }
    return {
        "cpu": {"usage": 62, "temperature": 49, "frequency": 4.7, "load": [1.25, 1.1, 0.95]},
        "gpu": {"usage": 71, "temperature": 58, "fps": 144, "vramUsed": 9.2, "vramTotal": 16},
        "memory": {"usage": 45, "used": 14.5, "total": 32},
        "disk": {"usage": 54},
        "network": {"download": 18.4, "upload": 2.8},
        "weather": {"temperature": "24.0°C", "description": "Parcialmente nublado"},
        "system": {"hostname": "desktop", "time": time.strftime("%H:%M:%S")},
    }


def binding_value(data: Mapping, binding: str):
    node = data
    for part in binding.split("."):
        if not isinstance(node, Mapping) or part not in node:
            return None
        node = node[part]
    return node


def format_field_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def parse_field_value(text: str):
    """Numbers become numbers (comma or dot decimals); other text stays text.

    An empty field returns None: the sensor is reported as unavailable.
    """
    text = str(text).strip()
    if not text:
        return None
    candidate = text.replace(",", ".")
    try:
        number = float(candidate)
    except ValueError:
        return text
    return int(number) if number.is_integer() and "." not in candidate else number


def custom_data(base: Mapping, values: Mapping[str, str]) -> dict:
    """Apply ``{binding: field text}`` overrides to a copy of ``base``."""
    data = copy.deepcopy(dict(base))
    for binding, text in values.items():
        section, _, key = binding.partition(".")
        if not section or not key:
            continue
        target = data.setdefault(section, {})
        value = parse_field_value(text)
        if value is None:
            target.pop(key, None)
        else:
            target[key] = value
    return data
