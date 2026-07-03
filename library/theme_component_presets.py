# SPDX-License-Identifier: GPL-3.0-or-later
"""Component-level presets built on semantic theme tokens."""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Mapping, Optional

from library.theme_engine_presets import REQUIRED_COLOR_ROLES

TOKEN_REF_KEY = "$token"

COMPONENT_TYPES = (
    "typography",
    "effects",
    "bar",
    "radial",
    "line_graph",
    "data_palette",
)

_COMPONENT_PRESETS = (
    {
        "id": "typography_display_clock",
        "label": "Display Clock",
        "component_type": "typography",
        "description": "Large centered text for time or hero values.",
        "version": 1,
        "values": {
            "FONT_SIZE": 96,
            "ALIGN": "center",
            "ANCHOR": "mm",
            "WIDTH": 480,
            "HEIGHT": 120,
            "FONT_COLOR": {TOKEN_REF_KEY: "ON_SURFACE"},
        },
    },
    {
        "id": "typography_metric_value",
        "label": "Metric Value",
        "component_type": "typography",
        "description": "Right-aligned value text for percentages and sensors.",
        "version": 1,
        "values": {
            "FONT_SIZE": 32,
            "ALIGN": "right",
            "ANCHOR": "rm",
            "WIDTH": 140,
            "HEIGHT": 48,
            "MIN_SIZE": 3,
            "FONT_COLOR": {TOKEN_REF_KEY: "ON_SURFACE"},
        },
    },
    {
        "id": "typography_small_label",
        "label": "Small Label",
        "component_type": "typography",
        "description": "Compact left-aligned label text.",
        "version": 1,
        "values": {
            "FONT_SIZE": 16,
            "ALIGN": "left",
            "ANCHOR": "lt",
            "WIDTH": 160,
            "HEIGHT": 28,
            "FONT_COLOR": {TOKEN_REF_KEY: "ON_SURFACE_MUTED"},
        },
    },
    {
        "id": "effects_soft_depth",
        "label": "Soft Depth",
        "component_type": "effects",
        "description": "Subtle shadow for dark or layered surfaces.",
        "version": 1,
        "values": {
            "EFFECTS": {
                "SHADOW": {
                    "ENABLED": True,
                    "COLOR": [0, 0, 0, 150],
                    "OFFSET_X": 2,
                    "OFFSET_Y": 2,
                    "BLUR_RADIUS": 3.0,
                },
                "GLOW": {
                    "ENABLED": False,
                    "COLOR": {TOKEN_REF_KEY: "ON_SURFACE"},
                    "BLUR_RADIUS": 8.0,
                    "INTENSITY": 1,
                },
                "OUTLINE": {
                    "ENABLED": False,
                    "COLOR": {TOKEN_REF_KEY: "OUTLINE"},
                    "WIDTH": 2,
                },
            },
        },
    },
    {
        "id": "effects_video_readable",
        "label": "Video Readable",
        "component_type": "effects",
        "description": "Shadow and outline intended for video overlays.",
        "version": 1,
        "values": {
            "EFFECTS": {
                "SHADOW": {
                    "ENABLED": True,
                    "COLOR": [0, 0, 0, 200],
                    "OFFSET_X": 2,
                    "OFFSET_Y": 2,
                    "BLUR_RADIUS": 2.0,
                },
                "GLOW": {
                    "ENABLED": False,
                    "COLOR": {TOKEN_REF_KEY: "ON_SURFACE"},
                    "BLUR_RADIUS": 4.0,
                    "INTENSITY": 1,
                },
                "OUTLINE": {
                    "ENABLED": True,
                    "COLOR": [0, 0, 0, 255],
                    "WIDTH": 2,
                },
            },
        },
    },
    {
        "id": "bar_primary",
        "label": "Primary Bar",
        "component_type": "bar",
        "description": "Primary filled bar with alternate surface track.",
        "version": 1,
        "values": {
            "BAR_COLOR": {TOKEN_REF_KEY: "PRIMARY"},
            "BAR_BACKGROUND_COLOR": {TOKEN_REF_KEY: "SURFACE_ALT"},
            "BAR_OUTLINE": True,
        },
    },
    {
        "id": "bar_success",
        "label": "Success Bar",
        "component_type": "bar",
        "description": "Success-colored bar for healthy metrics.",
        "version": 1,
        "values": {
            "BAR_COLOR": {TOKEN_REF_KEY: "SUCCESS"},
            "BAR_BACKGROUND_COLOR": {TOKEN_REF_KEY: "SURFACE_ALT"},
            "BAR_OUTLINE": True,
        },
    },
    {
        "id": "radial_primary",
        "label": "Primary Radial",
        "component_type": "radial",
        "description": "Primary radial gauge stroke with semantic text color.",
        "version": 1,
        "values": {
            "BAR_COLOR": {TOKEN_REF_KEY: "PRIMARY"},
            "BAR_BACKGROUND_COLOR": {TOKEN_REF_KEY: "SURFACE_ALT"},
            "FONT_COLOR": {TOKEN_REF_KEY: "ON_SURFACE"},
            "WIDTH": 8,
        },
    },
    {
        "id": "radial_warning",
        "label": "Warning Radial",
        "component_type": "radial",
        "description": "Warning radial gauge for high-attention metrics.",
        "version": 1,
        "values": {
            "BAR_COLOR": {TOKEN_REF_KEY: "WARNING"},
            "BAR_BACKGROUND_COLOR": {TOKEN_REF_KEY: "SURFACE_ALT"},
            "FONT_COLOR": {TOKEN_REF_KEY: "ON_SURFACE"},
            "WIDTH": 8,
        },
    },
    {
        "id": "line_graph_primary",
        "label": "Primary Line Graph",
        "component_type": "line_graph",
        "description": "Primary line graph with muted axis.",
        "version": 1,
        "values": {
            "LINE_COLOR": {TOKEN_REF_KEY: "PRIMARY"},
            "AXIS_COLOR": {TOKEN_REF_KEY: "OUTLINE"},
            "AXIS_FONT_SIZE": 10,
        },
    },
    {
        "id": "line_graph_muted",
        "label": "Muted Line Graph",
        "component_type": "line_graph",
        "description": "Quiet line graph for secondary data.",
        "version": 1,
        "values": {
            "LINE_COLOR": {TOKEN_REF_KEY: "SECONDARY"},
            "AXIS_COLOR": {TOKEN_REF_KEY: "GRID"},
            "AXIS_FONT_SIZE": 10,
        },
    },
    {
        "id": "data_palette_status",
        "label": "Status Data Palette",
        "component_type": "data_palette",
        "description": "Semantic status colors for existing data fields.",
        "version": 1,
        "values": {
            "FONT_COLOR": {TOKEN_REF_KEY: "ON_SURFACE"},
            "BAR_COLOR": {TOKEN_REF_KEY: "PRIMARY"},
            "LINE_COLOR": {TOKEN_REF_KEY: "PRIMARY"},
            "AXIS_COLOR": {TOKEN_REF_KEY: "OUTLINE"},
            "DISPLAY_RGB_LED": {TOKEN_REF_KEY: "PRIMARY"},
        },
    },
)


def component_preset_ids(component_type: Optional[str] = None) -> List[str]:
    """Return component preset ids, optionally filtered by component type."""

    return [
        str(preset["id"])
        for preset in _COMPONENT_PRESETS
        if component_type is None or preset["component_type"] == component_type
    ]


def list_component_presets(
    component_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return deep copies of component presets."""

    return [
        copy.deepcopy(preset)
        for preset in _COMPONENT_PRESETS
        if component_type is None or preset["component_type"] == component_type
    ]


def get_component_preset(preset_id: str) -> Dict[str, Any]:
    """Return a deep copy of one component preset, or raise KeyError."""

    for preset in _COMPONENT_PRESETS:
        if preset["id"] == preset_id:
            return copy.deepcopy(preset)
    raise KeyError(f"Unknown component preset: {preset_id}")


def _resolve_value(value: Any, tokens: Optional[Mapping[str, List[int]]]) -> Any:
    if isinstance(value, Mapping):
        if set(value.keys()) == {TOKEN_REF_KEY}:
            role = value[TOKEN_REF_KEY]
            if tokens is None:
                return copy.deepcopy(value)
            if role not in tokens:
                raise KeyError(f"Missing semantic token: {role}")
            return copy.deepcopy(tokens[role])
        return {key: _resolve_value(item, tokens) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_value(item, tokens) for item in value]
    return copy.deepcopy(value)


def resolve_component_values(
    preset_id: str,
    tokens: Optional[Mapping[str, List[int]]] = None,
) -> Dict[str, Any]:
    """Return preset values, resolving token references when tokens are given."""

    values = get_component_preset(preset_id)["values"]
    return _resolve_value(values, tokens)


def _merge_existing(target: Any, values: Any) -> Any:
    if isinstance(target, Mapping) and isinstance(values, Mapping):
        result = copy.deepcopy(target)
        for key, value in values.items():
            if key not in result:
                continue
            result[key] = _merge_existing(result[key], value)
        return result
    return copy.deepcopy(values)


def apply_component_preset(
    node: Mapping[str, Any],
    preset_id: str,
    tokens: Optional[Mapping[str, List[int]]] = None,
) -> Dict[str, Any]:
    """Apply a component preset to a copy of one selected node.

    Only keys that already exist in the selected node are updated. Missing
    properties and sibling elements are never added by this Phase B foundation.
    """

    values = resolve_component_values(preset_id, tokens)
    if not isinstance(node, Mapping):
        return copy.deepcopy(node)
    return _merge_existing(node, values)


def _validate_token_ref(path: str, value: Any) -> List[str]:
    if isinstance(value, Mapping):
        if set(value.keys()) == {TOKEN_REF_KEY}:
            role = value[TOKEN_REF_KEY]
            if role not in REQUIRED_COLOR_ROLES:
                return [f"{path} references unknown token {role}."]
            return []
        errors = []
        for key, item in value.items():
            errors.extend(_validate_token_ref(f"{path}.{key}", item))
        return errors
    if isinstance(value, list):
        errors = []
        for index, item in enumerate(value):
            errors.extend(_validate_token_ref(f"{path}[{index}]", item))
        return errors
    return []


def validate_component_preset(preset: Mapping[str, Any]) -> List[str]:
    """Return validation errors for one component preset."""

    errors: List[str] = []
    required_fields = {
        "id",
        "label",
        "component_type",
        "description",
        "version",
        "values",
    }
    for field in sorted(required_fields.difference(preset.keys())):
        errors.append(f"Missing required field: {field}.")

    preset_id = preset.get("id")
    if not isinstance(preset_id, str) or not re.fullmatch(r"[a-z0-9_]+", preset_id):
        errors.append("id must be snake_case.")
    if not isinstance(preset.get("label"), str) or not preset.get("label", "").strip():
        errors.append("label must be a non-empty string.")
    if preset.get("component_type") not in COMPONENT_TYPES:
        errors.append("component_type is not valid.")
    version = preset.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        errors.append("version must be an int greater than or equal to 1.")
    values = preset.get("values")
    if not isinstance(values, Mapping):
        errors.append("values must be a mapping.")
    else:
        errors.extend(_validate_token_ref("values", values))
    return errors


def validate_component_registry() -> List[str]:
    """Validate all built-in component presets."""

    errors: List[str] = []
    seen_ids = set()
    for index, preset in enumerate(_COMPONENT_PRESETS):
        preset_id = preset.get("id")
        if preset_id in seen_ids:
            errors.append(f"Duplicate component preset id: {preset_id}.")
        seen_ids.add(preset_id)
        for error in validate_component_preset(preset):
            errors.append(f"Preset {index} ({preset_id}): {error}")
    return errors
