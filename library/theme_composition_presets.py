# SPDX-License-Identifier: GPL-3.0-or-later
"""Theme composition presets built from semantic and component presets."""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from library.theme_component_presets import (
    apply_component_preset,
    component_preset_ids,
)
from library.theme_engine_presets import (
    apply_theme_preset,
    preset_ids,
    resolve_semantic_tokens,
)

COMPOSITION_CATEGORIES = (
    "layout",
    "overlay",
    "accessibility",
)

Path = Tuple[str, ...]

_COMPOSITION_PRESETS = (
    {
        "id": "video_hud_readable",
        "label": "Video HUD Readable",
        "category": "overlay",
        "description": "Readable text and data colors over video backgrounds.",
        "version": 1,
        "semantic_preset_id": "video_overlay_readable",
        "rules": (
            {
                "component_preset_id": "effects_video_readable",
                "path_contains": (),
                "required_any_keys": ("EFFECTS",),
            },
            {
                "component_preset_id": "typography_display_clock",
                "path_contains": ("HOUR", "CLOCK", "TIME"),
                "required_any_keys": ("FONT_SIZE", "FONT_COLOR"),
                "priority": 300,
                "exclusive_group": "typography",
            },
            {
                "component_preset_id": "typography_metric_value",
                "path_contains": (
                    "PERCENT",
                    "PERCENTAGE",
                    "TEMP",
                    "MEMORY",
                    "VALUE",
                ),
                "required_any_keys": ("FONT_SIZE", "FONT_COLOR"),
                "priority": 200,
                "exclusive_group": "typography",
            },
            {
                "component_preset_id": "typography_small_label",
                "path_contains": ("LABEL", "TITLE", "CAPTION"),
                "required_any_keys": ("FONT_SIZE", "FONT_COLOR"),
                "priority": 100,
                "exclusive_group": "typography",
            },
        ),
    },
    {
        "id": "compact_metrics_grid",
        "label": "Compact Metrics Grid",
        "category": "layout",
        "description": "Technical compact styling for dense metric dashboards.",
        "version": 1,
        "semantic_preset_id": "technical_data_dark",
        "rules": (
            {
                "component_preset_id": "typography_metric_value",
                "path_contains": ("PERCENT", "PERCENTAGE", "MEMORY", "TEMP"),
                "required_any_keys": ("FONT_SIZE", "FONT_COLOR"),
                "priority": 200,
                "exclusive_group": "typography",
            },
            {
                "component_preset_id": "typography_small_label",
                "path_contains": ("LABEL", "TITLE", "CAPTION"),
                "required_any_keys": ("FONT_SIZE", "FONT_COLOR"),
                "priority": 100,
                "exclusive_group": "typography",
            },
            {
                "component_preset_id": "bar_primary",
                "path_contains": (),
                "required_any_keys": ("BAR_COLOR", "BAR_BACKGROUND_COLOR"),
            },
            {
                "component_preset_id": "radial_primary",
                "path_contains": (),
                "required_any_keys": ("RADIUS",),
            },
            {
                "component_preset_id": "line_graph_primary",
                "path_contains": (),
                "required_any_keys": ("LINE_COLOR",),
            },
        ),
    },
    {
        "id": "monochrome_accessible_readout",
        "label": "Monochrome Accessible Readout",
        "category": "accessibility",
        "description": "High-contrast monochrome composition for readability.",
        "version": 1,
        "semantic_preset_id": "monochrome_high_contrast",
        "rules": (
            {
                "component_preset_id": "data_palette_status",
                "path_contains": (),
                "required_any_keys": (
                    "FONT_COLOR",
                    "BAR_COLOR",
                    "LINE_COLOR",
                    "AXIS_COLOR",
                    "DISPLAY_RGB_LED",
                ),
            },
            {
                "component_preset_id": "effects_video_readable",
                "path_contains": (),
                "required_any_keys": ("EFFECTS",),
            },
        ),
    },
)


def composition_preset_ids(category: Optional[str] = None) -> List[str]:
    """Return composition preset ids, optionally filtered by category."""

    return [
        str(preset["id"])
        for preset in _COMPOSITION_PRESETS
        if category is None or preset["category"] == category
    ]


def list_composition_presets(
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return deep copies of composition presets."""

    return [
        copy.deepcopy(preset)
        for preset in _COMPOSITION_PRESETS
        if category is None or preset["category"] == category
    ]


def get_composition_preset(preset_id: str) -> Dict[str, Any]:
    """Return a deep copy of one composition preset, or raise KeyError."""

    for preset in _COMPOSITION_PRESETS:
        if preset["id"] == preset_id:
            return copy.deepcopy(preset)
    raise KeyError(f"Unknown composition preset: {preset_id}")


def _path_tokens(path: Path) -> set:
    tokens = set()
    for part in path:
        text = str(part).upper()
        tokens.add(text)
        tokens.update(piece for piece in text.replace("-", "_").split("_") if piece)
    return tokens


def _rule_matches(rule: Mapping[str, Any], path: Path, node: Mapping[str, Any]) -> bool:
    path_contains = set(rule.get("path_contains", ()))
    if path_contains and not path_contains.intersection(_path_tokens(path)):
        return False

    required_any = tuple(rule.get("required_any_keys", ()))
    if required_any and not any(key in node for key in required_any):
        return False

    return True


def _apply_rules_to_value(
    value: Any,
    path: Path,
    rules: Sequence[Mapping[str, Any]],
    tokens: Mapping[str, List[int]],
) -> Any:
    if isinstance(value, Mapping):
        result = {
            key: _apply_rules_to_value(item, path + (str(key),), rules, tokens)
            for key, item in value.items()
        }
        applied_groups = set()
        ordered_rules = sorted(
            rules,
            key=lambda rule: int(rule.get("priority", 0)),
            reverse=True,
        )
        for rule in ordered_rules:
            exclusive_group = rule.get("exclusive_group")
            if exclusive_group and exclusive_group in applied_groups:
                continue
            if _rule_matches(rule, path, result):
                result = apply_component_preset(
                    result,
                    str(rule["component_preset_id"]),
                    tokens,
                )
                if exclusive_group:
                    applied_groups.add(str(exclusive_group))
        return result

    if isinstance(value, list):
        return [
            _apply_rules_to_value(item, path + (str(index),), rules, tokens)
            for index, item in enumerate(value)
        ]

    return copy.deepcopy(value)


def apply_composition_preset(theme_data: Any, preset_id: str) -> Any:
    """Apply a composition preset to a deep copy of theme_data.

    The semantic preset is applied first, then component rules are applied to
    matching existing nodes. Missing nodes and missing properties are not added.
    """

    preset = get_composition_preset(preset_id)
    semantic_id = str(preset["semantic_preset_id"])
    tokens = resolve_semantic_tokens(semantic_id)
    themed = apply_theme_preset(theme_data, semantic_id)
    return _apply_rules_to_value(themed, (), preset["rules"], tokens)


def validate_composition_preset(preset: Mapping[str, Any]) -> List[str]:
    """Return validation errors for one composition preset."""

    errors: List[str] = []
    required_fields = {
        "id",
        "label",
        "category",
        "description",
        "version",
        "semantic_preset_id",
        "rules",
    }
    for field in sorted(required_fields.difference(preset.keys())):
        errors.append(f"Missing required field: {field}.")

    preset_id = preset.get("id")
    if not isinstance(preset_id, str) or not re.fullmatch(r"[a-z0-9_]+", preset_id):
        errors.append("id must be snake_case.")
    if not isinstance(preset.get("label"), str) or not preset.get("label", "").strip():
        errors.append("label must be a non-empty string.")
    if preset.get("category") not in COMPOSITION_CATEGORIES:
        errors.append("category is not valid.")
    version = preset.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        errors.append("version must be an int greater than or equal to 1.")
    if preset.get("semantic_preset_id") not in preset_ids():
        errors.append("semantic_preset_id is not valid.")

    rules = preset.get("rules")
    if not isinstance(rules, Iterable) or isinstance(rules, (str, bytes, Mapping)):
        errors.append("rules must be an iterable of mappings.")
    else:
        for index, rule in enumerate(rules):
            if not isinstance(rule, Mapping):
                errors.append(f"rules[{index}] must be a mapping.")
                continue
            if rule.get("component_preset_id") not in component_preset_ids():
                errors.append(f"rules[{index}].component_preset_id is not valid.")
            for key in ("path_contains", "required_any_keys"):
                value = rule.get(key, ())
                if not isinstance(value, tuple):
                    errors.append(f"rules[{index}].{key} must be a tuple.")

            priority = rule.get("priority", 0)
            if not isinstance(priority, int) or isinstance(priority, bool):
                errors.append(f"rules[{index}].priority must be an int.")

            exclusive_group = rule.get("exclusive_group")
            if exclusive_group is not None and (
                not isinstance(exclusive_group, str)
                or not exclusive_group.strip()
            ):
                errors.append(
                    f"rules[{index}].exclusive_group must be a non-empty string."
                )

    return errors


def validate_composition_registry() -> List[str]:
    """Validate all built-in composition presets."""

    errors: List[str] = []
    seen_ids = set()
    for index, preset in enumerate(_COMPOSITION_PRESETS):
        preset_id = preset.get("id")
        if preset_id in seen_ids:
            errors.append(f"Duplicate composition preset id: {preset_id}.")
        seen_ids.add(preset_id)
        for error in validate_composition_preset(preset):
            errors.append(f"Preset {index} ({preset_id}): {error}")
    return errors
