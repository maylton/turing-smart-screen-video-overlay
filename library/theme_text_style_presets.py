# SPDX-License-Identifier: GPL-3.0-or-later
"""Text style and text effect presets for the theme editor."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any, Dict, Iterable, List, Optional

TEXT_STYLE_PRESETS = {
    "Large clock": {
        "FONT_SIZE": 96,
        "ALIGN": "center",
        "ANCHOR": "mm",
        "WIDTH": 480,
        "HEIGHT": 120,
    },
    "Centered title": {
        "FONT_SIZE": 36,
        "ALIGN": "center",
        "ANCHOR": "mm",
        "WIDTH": 400,
        "HEIGHT": 60,
    },
    "Metric value": {
        "FONT_SIZE": 32,
        "ALIGN": "right",
        "ANCHOR": "rm",
        "WIDTH": 140,
        "HEIGHT": 48,
        "MIN_SIZE": 3,
    },
    "Compact value": {
        "FONT_SIZE": 20,
        "ALIGN": "right",
        "ANCHOR": "rm",
        "WIDTH": 100,
        "HEIGHT": 32,
        "MIN_SIZE": 3,
    },
    "Small label": {
        "FONT_SIZE": 16,
        "ALIGN": "left",
        "ANCHOR": "lt",
        "WIDTH": 160,
        "HEIGHT": 28,
    },
    "Caption": {
        "FONT_SIZE": 14,
        "ALIGN": "left",
        "ANCHOR": "lt",
        "WIDTH": 240,
        "HEIGHT": 24,
    },
}

TEXT_PROPERTY_KEYS = {
    "TEXT",
    "FORMAT",
    "FONT",
    "FONT_SIZE",
    "FONT_COLOR",
    "ALIGN",
    "ANCHOR",
}

TEXT_RENDER_KEYS = {
    "FONT",
    "FONT_SIZE",
    "FONT_COLOR",
}

TEXT_STYLE_CONTEXTS = {
    "clock": ["Large clock"],
    "metric": ["Metric value", "Compact value"],
    "label": ["Centered title", "Small label", "Caption"],
}

METRIC_PATH_TOKENS = {
    "CPU",
    "GPU",
    "MEMORY",
    "PERCENT",
    "PERCENTAGE",
    "PERCENT_TEXT",
    "MEMORY_PERCENT",
    "MEMORY_USED",
    "MEMORY_TOTAL",
    "TEMPERATURE",
    "TEMP",
    "FAN",
    "FREQUENCY",
    "LOAD",
    "VALUE",
    "SENSOR",
    "NET",
    "NETWORK",
    "UPTIME",
    "WEATHER",
}

LABEL_PATH_TOKENS = {
    "LABEL",
    "TITLE",
    "CAPTION",
    "STATIC_TEXT",
    "TEXT_LABEL",
}

CLOCK_PATH_TOKENS = {
    "HOUR",
    "TIME",
    "CLOCK",
    "UPDATE_TIME",
}


def _effect(
    *,
    shadow_enabled: bool = False,
    shadow_color=None,
    shadow_x: int = 3,
    shadow_y: int = 3,
    shadow_blur: float = 4.0,
    glow_enabled: bool = False,
    glow_color=None,
    glow_blur: float = 8.0,
    glow_intensity: int = 1,
    outline_enabled: bool = False,
    outline_color=None,
    outline_width: int = 2,
) -> Dict[str, Dict[str, Any]]:
    return {
        "SHADOW": {
            "ENABLED": shadow_enabled,
            "COLOR": list(shadow_color or [0, 0, 0, 180]),
            "OFFSET_X": shadow_x,
            "OFFSET_Y": shadow_y,
            "BLUR_RADIUS": shadow_blur,
        },
        "GLOW": {
            "ENABLED": glow_enabled,
            "COLOR": list(glow_color or [255, 255, 255, 160]),
            "BLUR_RADIUS": glow_blur,
            "INTENSITY": glow_intensity,
        },
        "OUTLINE": {
            "ENABLED": outline_enabled,
            "COLOR": list(outline_color or [0, 0, 0, 255]),
            "WIDTH": outline_width,
        },
    }


TEXT_EFFECT_PRESETS = {
    "None": _effect(),
    "Soft shadow": _effect(
        shadow_enabled=True,
        shadow_color=[0, 0, 0, 150],
        shadow_x=2,
        shadow_y=2,
        shadow_blur=3.0,
    ),
    "Strong shadow": _effect(
        shadow_enabled=True,
        shadow_color=[0, 0, 0, 220],
        shadow_x=4,
        shadow_y=4,
        shadow_blur=5.0,
    ),
    "Subtle glow": _effect(
        glow_enabled=True,
        glow_color=[255, 255, 255, 120],
        glow_blur=5.0,
        glow_intensity=1,
    ),
    "Neon glow": _effect(
        glow_enabled=True,
        glow_color=[80, 180, 255, 210],
        glow_blur=10.0,
        glow_intensity=3,
    ),
    "Thin outline": _effect(
        outline_enabled=True,
        outline_color=[0, 0, 0, 255],
        outline_width=1,
    ),
    "High-contrast outline": _effect(
        outline_enabled=True,
        outline_color=[0, 0, 0, 255],
        outline_width=3,
    ),
    "Glow + outline": _effect(
        glow_enabled=True,
        glow_color=[80, 180, 255, 180],
        glow_blur=7.0,
        glow_intensity=2,
        outline_enabled=True,
        outline_color=[0, 0, 0, 255],
        outline_width=2,
    ),
    "Video overlay readable": _effect(
        shadow_enabled=True,
        shadow_color=[0, 0, 0, 200],
        shadow_x=2,
        shadow_y=2,
        shadow_blur=2.0,
        glow_enabled=False,
        glow_color=[255, 255, 255, 120],
        glow_blur=4.0,
        glow_intensity=1,
        outline_enabled=True,
        outline_color=[0, 0, 0, 255],
        outline_width=2,
    ),
}


def is_text_style_node(node: Any) -> bool:
    """Return True when a mapping looks like a text-rendered theme node."""

    if not isinstance(node, Mapping):
        return False
    keys = set(node.keys())
    return bool(TEXT_PROPERTY_KEYS.intersection(keys)) and bool(
        TEXT_RENDER_KEYS.intersection(keys)
    )


def _path_tokens(path: Optional[Iterable[Any]]) -> set:
    if path is None:
        return set()
    tokens = set()
    for part in path:
        text = str(part).upper()
        tokens.add(text)
        tokens.update(piece for piece in text.replace("-", "_").split("_") if piece)
    return tokens


def text_style_context(node: Any, path: Optional[Iterable[Any]] = None) -> str:
    """Return the preset context for a text-like node."""

    if not is_text_style_node(node):
        return "none"

    tokens = _path_tokens(path)
    if tokens.intersection(CLOCK_PATH_TOKENS):
        return "clock"
    if tokens.intersection(LABEL_PATH_TOKENS):
        return "label"
    if tokens.intersection(METRIC_PATH_TOKENS):
        return "metric"

    text = str(node.get("TEXT", "")).strip() if isinstance(node, Mapping) else ""
    if text and not any(character.isdigit() for character in text):
        return "label"

    return "label"


def text_style_preset_names(
    node: Any = None,
    path: Optional[Iterable[Any]] = None,
) -> List[str]:
    if node is None and path is None:
        return list(TEXT_STYLE_PRESETS.keys())
    context = text_style_context(node, path)
    return list(TEXT_STYLE_CONTEXTS.get(context, ()))


def all_text_style_preset_names() -> List[str]:
    return list(TEXT_STYLE_PRESETS.keys())


def text_style_updates(name: str, node: Mapping[str, Any]) -> Dict[str, Any]:
    """Return preset values for keys already present on the selected node."""

    if name not in TEXT_STYLE_PRESETS:
        raise KeyError(f"Unknown text style preset: {name}")
    if not isinstance(node, Mapping):
        return {}

    preset = TEXT_STYLE_PRESETS[name]
    return {
        key: copy.deepcopy(value)
        for key, value in preset.items()
        if key in node
    }


def text_effect_preset_names() -> List[str]:
    return list(TEXT_EFFECT_PRESETS.keys())


def text_effect_preset(name: str) -> Dict[str, Dict[str, Any]]:
    """Return a deep copy of a named text effect preset."""

    if name not in TEXT_EFFECT_PRESETS:
        raise KeyError(f"Unknown text effect preset: {name}")
    return copy.deepcopy(TEXT_EFFECT_PRESETS[name])
