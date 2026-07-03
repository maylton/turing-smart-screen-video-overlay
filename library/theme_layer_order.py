# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure helpers for static theme layer ordering."""

from __future__ import annotations

import copy
from typing import Any, Dict, Mapping, MutableMapping, Tuple

ThemePath = Tuple[Any, ...]

MOVE_BACKWARD = "move_backward"
MOVE_FORWARD = "move_forward"
SEND_TO_BACK = "send_to_back"
BRING_TO_FRONT = "bring_to_front"

LAYER_ACTIONS = (
    MOVE_BACKWARD,
    MOVE_FORWARD,
    SEND_TO_BACK,
    BRING_TO_FRONT,
)

_CONTAINER_LABELS = {
    "static_images": "Images",
    "static_text": "Text",
}


class LayerOrderError(ValueError):
    """Raised when a layer order operation cannot be applied."""


def _empty_action_state() -> Dict[str, bool]:
    return {action: False for action in LAYER_ACTIONS}


def _node_at_path(theme_data: Mapping[str, Any], path: ThemePath) -> Any:
    node: Any = theme_data
    for part in path:
        node = node[part]
    return node


def _validate_path(path: ThemePath) -> Tuple[str, Any]:
    if not isinstance(path, tuple):
        path = tuple(path)
    if len(path) != 2:
        raise LayerOrderError("Only individual static text/image entries can be reordered")
    container_name, key = path
    if container_name not in _CONTAINER_LABELS:
        raise LayerOrderError("Only static_text and static_images entries can be reordered")
    return str(container_name), key


def is_reorderable_layer(theme_data: Mapping[str, Any], path: ThemePath) -> bool:
    """Return True when path points to an individual static layer entry."""
    try:
        container_name, key = _validate_path(path)
    except LayerOrderError:
        return False
    container = theme_data.get(container_name)
    return isinstance(container, Mapping) and key in container


def layer_info(theme_data: Mapping[str, Any], path: ThemePath) -> Dict[str, Any]:
    """Return layer position and movement capabilities for a path."""
    if not is_reorderable_layer(theme_data, path):
        state = _empty_action_state()
        return {
            "reorderable": False,
            "container": None,
            "container_label": None,
            "key": None,
            "index": None,
            "position": None,
            "total": 0,
            "can_move_backward": False,
            "can_move_forward": False,
            "can_send_to_back": False,
            "can_bring_to_front": False,
            "actions": state,
        }

    container_name, key = _validate_path(path)
    container = theme_data[container_name]
    keys = list(container.keys())
    index = keys.index(key)
    total = len(keys)
    can_move_backward = index > 0 and total > 1
    can_move_forward = index < total - 1 and total > 1
    return {
        "reorderable": True,
        "container": container_name,
        "container_label": _CONTAINER_LABELS[container_name],
        "key": key,
        "index": index,
        "position": index + 1,
        "total": total,
        "can_move_backward": can_move_backward,
        "can_move_forward": can_move_forward,
        "can_send_to_back": can_move_backward,
        "can_bring_to_front": can_move_forward,
        "actions": {
            MOVE_BACKWARD: can_move_backward,
            MOVE_FORWARD: can_move_forward,
            SEND_TO_BACK: can_move_backward,
            BRING_TO_FRONT: can_move_forward,
        },
    }


def layer_action_state(theme_data: Mapping[str, Any], path: ThemePath) -> Dict[str, bool]:
    """Return movement sensitivity for every layer action."""
    return dict(layer_info(theme_data, path).get("actions", _empty_action_state()))


def layer_position_label(theme_data: Mapping[str, Any], path: ThemePath) -> str:
    """Return a human-readable layer position label, or an empty string."""
    info = layer_info(theme_data, path)
    if not info["reorderable"]:
        return ""
    return f"Layer {info['position']} of {info['total']} · {info['container_label']}"


def _target_index(index: int, total: int, action: str) -> int:
    if action == MOVE_BACKWARD:
        return max(0, index - 1)
    if action == MOVE_FORWARD:
        return min(total - 1, index + 1)
    if action == SEND_TO_BACK:
        return 0
    if action == BRING_TO_FRONT:
        return total - 1
    raise LayerOrderError(f"Unknown layer action: {action}")


def move_layer(theme_data: Mapping[str, Any], path: ThemePath, action: str) -> Mapping[str, Any]:
    """Return a deep-copied theme with one static layer reordered."""
    if action not in LAYER_ACTIONS:
        raise LayerOrderError(f"Unknown layer action: {action}")
    info = layer_info(theme_data, path)
    if not info["reorderable"]:
        raise LayerOrderError("Selected path is not a reorderable static layer")
    if not info["actions"][action]:
        raise LayerOrderError("Layer is already at the requested boundary")

    updated = copy.deepcopy(theme_data)
    container = _node_at_path(updated, (info["container"],))
    if not isinstance(container, MutableMapping):
        raise LayerOrderError("Layer container is not a mapping")

    items = list(container.items())
    current_index = int(info["index"])
    new_index = _target_index(current_index, len(items), action)
    key, value = items.pop(current_index)
    items.insert(new_index, (key, value))

    container.clear()
    for item_key, item_value in items:
        container[item_key] = item_value
    return updated


def runtime_layer_sequence(theme_data: Mapping[str, Any]) -> Tuple[ThemePath, ...]:
    """Return static layers in the order they are drawn by the runtime."""
    sequence = []
    for container_name in ("static_images", "static_text"):
        container = theme_data.get(container_name, {})
        if isinstance(container, Mapping):
            sequence.extend((container_name, key) for key in container.keys())
    return tuple(sequence)
