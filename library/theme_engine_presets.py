# SPDX-License-Identifier: GPL-3.0-or-later
"""Semantic visual presets for theme data.

This module is deliberately independent from GTK, the LCD engine, and the YAML
serializer. It works only with Python mappings/lists and returns deep copies.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional

REQUIRED_COLOR_ROLES = (
    "BACKGROUND",
    "SURFACE",
    "SURFACE_ALT",
    "PRIMARY",
    "SECONDARY",
    "TERTIARY",
    "ON_BACKGROUND",
    "ON_SURFACE",
    "ON_SURFACE_MUTED",
    "OUTLINE",
    "GRID",
    "SUCCESS",
    "WARNING",
    "DANGER",
)

VALID_CATEGORIES = ("foundation", "overlay", "accessibility")

APPLICATION_POLICY_FIELDS = (
    "preserve_geometry",
    "preserve_text",
    "preserve_media",
    "preserve_background",
)

PROPERTY_COLOR_ROLES = {
    "FONT_COLOR": "ON_SURFACE",
    "BACKGROUND_COLOR": "SURFACE",
    "BAR_COLOR": "PRIMARY",
    "BAR_BACKGROUND_COLOR": "SURFACE_ALT",
    "LINE_COLOR": "PRIMARY",
    "AXIS_COLOR": "OUTLINE",
    "DISPLAY_RGB_LED": "PRIMARY",
}

PRESERVED_SECTIONS = {"video", "static_images"}


def _policy(*, preserve_background: bool) -> Dict[str, bool]:
    return {
        "preserve_geometry": True,
        "preserve_text": True,
        "preserve_media": True,
        "preserve_background": preserve_background,
    }


_PRESET_REGISTRY = (
    {
        "id": "tonal_expressive_dark",
        "label": "Tonal Expressive Dark",
        "category": "foundation",
        "description": "Expressive dark tonal palette for rich dashboards.",
        "version": 1,
        "tokens": {
            "BACKGROUND": [24, 18, 29],
            "SURFACE": [36, 30, 41],
            "SURFACE_ALT": [53, 47, 59],
            "PRIMARY": [214, 174, 255],
            "SECONDARY": [206, 189, 219],
            "TERTIARY": [244, 183, 205],
            "ON_BACKGROUND": [247, 239, 248],
            "ON_SURFACE": [247, 239, 248],
            "ON_SURFACE_MUTED": [205, 196, 208],
            "OUTLINE": [148, 141, 151],
            "GRID": [75, 68, 79],
            "SUCCESS": [93, 214, 131],
            "WARNING": [255, 190, 92],
            "DANGER": [255, 180, 171],
        },
        "application_policy": _policy(preserve_background=False),
    },
    {
        "id": "tonal_expressive_light",
        "label": "Tonal Expressive Light",
        "category": "foundation",
        "description": "Expressive light tonal palette for bright themes.",
        "version": 1,
        "tokens": {
            "BACKGROUND": [255, 247, 255],
            "SURFACE": [247, 239, 247],
            "SURFACE_ALT": [232, 222, 232],
            "PRIMARY": [103, 80, 164],
            "SECONDARY": [98, 91, 113],
            "TERTIARY": [125, 82, 96],
            "ON_BACKGROUND": [29, 27, 32],
            "ON_SURFACE": [29, 27, 32],
            "ON_SURFACE_MUTED": [73, 69, 79],
            "OUTLINE": [121, 116, 126],
            "GRID": [218, 209, 218],
            "SUCCESS": [32, 120, 67],
            "WARNING": [145, 90, 0],
            "DANGER": [186, 26, 26],
        },
        "application_policy": _policy(preserve_background=False),
    },
    {
        "id": "soft_neutral_dark",
        "label": "Soft Neutral Dark",
        "category": "foundation",
        "description": "Neutral dark palette with restrained color accents.",
        "version": 1,
        "tokens": {
            "BACKGROUND": [28, 28, 28],
            "SURFACE": [42, 42, 42],
            "SURFACE_ALT": [54, 54, 54],
            "PRIMARY": [96, 205, 255],
            "SECONDARY": [179, 157, 219],
            "TERTIARY": [111, 220, 190],
            "ON_BACKGROUND": [255, 255, 255],
            "ON_SURFACE": [250, 250, 250],
            "ON_SURFACE_MUTED": [196, 196, 196],
            "OUTLINE": [112, 112, 112],
            "GRID": [67, 67, 67],
            "SUCCESS": [107, 203, 119],
            "WARNING": [252, 197, 65],
            "DANGER": [255, 125, 125],
        },
        "application_policy": _policy(preserve_background=False),
    },
    {
        "id": "soft_neutral_light",
        "label": "Soft Neutral Light",
        "category": "foundation",
        "description": "Neutral light palette for quiet technical panels.",
        "version": 1,
        "tokens": {
            "BACKGROUND": [250, 250, 250],
            "SURFACE": [243, 243, 243],
            "SURFACE_ALT": [234, 234, 234],
            "PRIMARY": [0, 120, 212],
            "SECONDARY": [111, 66, 193],
            "TERTIARY": [0, 126, 115],
            "ON_BACKGROUND": [31, 31, 31],
            "ON_SURFACE": [31, 31, 31],
            "ON_SURFACE_MUTED": [96, 96, 96],
            "OUTLINE": [138, 138, 138],
            "GRID": [218, 218, 218],
            "SUCCESS": [16, 124, 16],
            "WARNING": [157, 93, 0],
            "DANGER": [196, 43, 28],
        },
        "application_policy": _policy(preserve_background=False),
    },
    {
        "id": "technical_data_dark",
        "label": "Technical Data Dark",
        "category": "foundation",
        "description": "Dark data palette with strong technical contrast.",
        "version": 1,
        "tokens": {
            "BACKGROUND": [22, 22, 22],
            "SURFACE": [38, 38, 38],
            "SURFACE_ALT": [57, 57, 57],
            "PRIMARY": [120, 169, 255],
            "SECONDARY": [69, 137, 255],
            "TERTIARY": [61, 219, 217],
            "ON_BACKGROUND": [244, 244, 244],
            "ON_SURFACE": [244, 244, 244],
            "ON_SURFACE_MUTED": [198, 198, 198],
            "OUTLINE": [111, 111, 111],
            "GRID": [57, 57, 57],
            "SUCCESS": [66, 190, 101],
            "WARNING": [241, 194, 27],
            "DANGER": [255, 131, 137],
        },
        "application_policy": _policy(preserve_background=False),
    },
    {
        "id": "technical_data_light",
        "label": "Technical Data Light",
        "category": "foundation",
        "description": "Light data palette for crisp technical readouts.",
        "version": 1,
        "tokens": {
            "BACKGROUND": [255, 255, 255],
            "SURFACE": [244, 244, 244],
            "SURFACE_ALT": [232, 232, 232],
            "PRIMARY": [15, 98, 254],
            "SECONDARY": [105, 41, 196],
            "TERTIARY": [0, 125, 121],
            "ON_BACKGROUND": [22, 22, 22],
            "ON_SURFACE": [22, 22, 22],
            "ON_SURFACE_MUTED": [82, 82, 82],
            "OUTLINE": [141, 141, 141],
            "GRID": [224, 224, 224],
            "SUCCESS": [25, 128, 56],
            "WARNING": [177, 113, 0],
            "DANGER": [218, 30, 40],
        },
        "application_policy": _policy(preserve_background=False),
    },
    {
        "id": "video_overlay_readable",
        "label": "Video Overlay Readable",
        "category": "overlay",
        "description": "Readable overlay palette that preserves video backgrounds.",
        "version": 1,
        "tokens": {
            "BACKGROUND": [0, 0, 0],
            "SURFACE": [20, 20, 20],
            "SURFACE_ALT": [45, 45, 45],
            "PRIMARY": [120, 210, 255],
            "SECONDARY": [225, 225, 225],
            "TERTIARY": [105, 240, 145],
            "ON_BACKGROUND": [255, 255, 255],
            "ON_SURFACE": [255, 255, 255],
            "ON_SURFACE_MUTED": [225, 225, 225],
            "OUTLINE": [0, 0, 0],
            "GRID": [80, 80, 80],
            "SUCCESS": [105, 240, 145],
            "WARNING": [255, 204, 90],
            "DANGER": [255, 115, 115],
        },
        "application_policy": _policy(preserve_background=True),
    },
    {
        "id": "monochrome_high_contrast",
        "label": "Monochrome High Contrast",
        "category": "accessibility",
        "description": "Monochrome high-contrast palette for maximum legibility.",
        "version": 1,
        "tokens": {
            "BACKGROUND": [0, 0, 0],
            "SURFACE": [18, 18, 18],
            "SURFACE_ALT": [36, 36, 36],
            "PRIMARY": [255, 255, 255],
            "SECONDARY": [205, 205, 205],
            "TERTIARY": [160, 160, 160],
            "ON_BACKGROUND": [255, 255, 255],
            "ON_SURFACE": [255, 255, 255],
            "ON_SURFACE_MUTED": [205, 205, 205],
            "OUTLINE": [150, 150, 150],
            "GRID": [70, 70, 70],
            "SUCCESS": [255, 255, 255],
            "WARNING": [205, 205, 205],
            "DANGER": [160, 160, 160],
        },
        "application_policy": _policy(preserve_background=False),
    },
)


def _matches_category(preset: Mapping[str, Any], category: Optional[str]) -> bool:
    return category is None or preset.get("category") == category


def preset_ids(category: Optional[str] = None) -> List[str]:
    """Return preset ids in registry order, optionally filtered by category."""

    return [
        str(preset["id"])
        for preset in _PRESET_REGISTRY
        if _matches_category(preset, category)
    ]


def list_presets(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return deep copies of presets, optionally filtered by category."""

    return [
        copy.deepcopy(preset)
        for preset in _PRESET_REGISTRY
        if _matches_category(preset, category)
    ]


def get_preset(preset_id: str) -> Dict[str, Any]:
    """Return a deep copy of one preset, or raise KeyError if unknown."""

    for preset in _PRESET_REGISTRY:
        if preset["id"] == preset_id:
            return copy.deepcopy(preset)
    raise KeyError(f"Unknown theme engine preset: {preset_id}")


def resolve_semantic_tokens(preset_id: str) -> Dict[str, List[int]]:
    """Return a deep copy of the semantic color tokens for a preset."""

    return copy.deepcopy(get_preset(preset_id)["tokens"])


def _validate_color(role: str, value: Any) -> List[str]:
    errors = []
    if not isinstance(value, list):
        return [f"Token {role} must be an RGB list."]
    if len(value) != 3:
        errors.append(f"Token {role} must have exactly 3 components.")
    for index, component in enumerate(value):
        if not isinstance(component, int) or isinstance(component, bool):
            errors.append(f"Token {role}[{index}] must be an int.")
        elif component < 0 or component > 255:
            errors.append(f"Token {role}[{index}] must be between 0 and 255.")
    return errors


def validate_preset(preset: Mapping[str, Any]) -> List[str]:
    """Return validation errors for one preset; an empty list means valid."""

    errors: List[str] = []
    required_fields = {
        "id",
        "label",
        "category",
        "description",
        "version",
        "tokens",
        "application_policy",
    }
    missing = required_fields.difference(preset.keys())
    for field in sorted(missing):
        errors.append(f"Missing required field: {field}.")

    preset_id = preset.get("id")
    if not isinstance(preset_id, str) or not re.fullmatch(r"[a-z0-9_]+", preset_id):
        errors.append("id must be snake_case.")

    label = preset.get("label")
    if not isinstance(label, str) or not label.strip():
        errors.append("label must be a non-empty string.")

    description = preset.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append("description must be a non-empty string.")

    category = preset.get("category")
    if category not in VALID_CATEGORIES:
        errors.append(f"category must be one of {', '.join(VALID_CATEGORIES)}.")

    version = preset.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        errors.append("version must be an int greater than or equal to 1.")

    tokens = preset.get("tokens")
    if not isinstance(tokens, Mapping):
        errors.append("tokens must be a mapping.")
    else:
        missing_roles = set(REQUIRED_COLOR_ROLES).difference(tokens.keys())
        for role in sorted(missing_roles):
            errors.append(f"Missing required token: {role}.")
        for role in REQUIRED_COLOR_ROLES:
            if role in tokens:
                errors.extend(_validate_color(role, tokens[role]))

    policy = preset.get("application_policy")
    if not isinstance(policy, Mapping):
        errors.append("application_policy must be a mapping.")
    else:
        missing_policy = set(APPLICATION_POLICY_FIELDS).difference(policy.keys())
        for field in sorted(missing_policy):
            errors.append(f"Missing application_policy field: {field}.")
        for field in APPLICATION_POLICY_FIELDS:
            if field in policy and not isinstance(policy[field], bool):
                errors.append(f"application_policy.{field} must be a bool.")

    return errors


def validate_registry() -> List[str]:
    """Validate the built-in registry and return all discovered errors."""

    errors: List[str] = []
    seen_ids = set()
    for index, preset in enumerate(_PRESET_REGISTRY):
        preset_id = preset.get("id")
        if preset_id in seen_ids:
            errors.append(f"Duplicate preset id: {preset_id}.")
        seen_ids.add(preset_id)
        for error in validate_preset(preset):
            errors.append(f"Preset {index} ({preset_id}): {error}")
    return errors


def _merged_policy(preset: Mapping[str, Any], overrides: Mapping[str, Optional[bool]]):
    policy = dict(preset["application_policy"])
    for key, value in overrides.items():
        if value is not None:
            policy[key] = value
    return policy


def _apply_value(value: Any, tokens: Mapping[str, List[int]], preserve_background: bool):
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            if key in PRESERVED_SECTIONS:
                result[key] = copy.deepcopy(item)
            elif (
                key == "BACKGROUND_COLOR"
                and preserve_background
                and key in PROPERTY_COLOR_ROLES
            ):
                result[key] = copy.deepcopy(item)
            elif key in PROPERTY_COLOR_ROLES:
                result[key] = copy.deepcopy(tokens[PROPERTY_COLOR_ROLES[key]])
            else:
                result[key] = _apply_value(item, tokens, preserve_background)
        return result
    if isinstance(value, list):
        return [_apply_value(item, tokens, preserve_background) for item in value]
    return copy.deepcopy(value)


def apply_theme_preset(
    theme_data: Any,
    preset_id: str,
    *,
    preserve_geometry: Optional[bool] = None,
    preserve_text: Optional[bool] = None,
    preserve_media: Optional[bool] = None,
    preserve_background: Optional[bool] = None,
) -> Any:
    """Apply semantic color roles to a deep copy of theme_data.

    The preserve_geometry, preserve_text, and preserve_media switches are part
    of the public policy API. Phase A only changes mapped color properties that
    already exist, so those data are preserved naturally.
    """

    preset = get_preset(preset_id)
    policy = _merged_policy(
        preset,
        {
            "preserve_geometry": preserve_geometry,
            "preserve_text": preserve_text,
            "preserve_media": preserve_media,
            "preserve_background": preserve_background,
        },
    )
    tokens = preset["tokens"]
    return _apply_value(theme_data, tokens, policy["preserve_background"])
