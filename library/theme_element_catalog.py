# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure helpers for the GTK theme elements navigator."""

from __future__ import annotations

import copy
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

ThemePath = Tuple[Any, ...]

STATE_ACTIVE = "active"
STATE_INACTIVE = "inactive"
STATE_MIXED = "mixed"
STATE_STRUCTURAL = "structural"

CATALOG_CATEGORIES = ("Content", "System", "Network", "Information")

THEME_ELEMENT_CATALOG = (
    {
        "id": "custom_text",
        "label": "Custom text",
        "category": "Content",
        "kind": "custom",
        "component_id": "text",
        "icon_name": "insert-text-symbolic",
        "repeatable": True,
    },
    {
        "id": "static_image",
        "label": "Static image",
        "category": "Content",
        "kind": "custom",
        "component_id": "image",
        "icon_name": "image-x-generic-symbolic",
        "repeatable": True,
    },
    {
        "id": "cpu_usage",
        "label": "CPU usage",
        "category": "System",
        "kind": "sensor",
        "component_id": "CPU.PERCENTAGE",
        "icon_name": "utilities-system-monitor-symbolic",
        "repeatable": False,
    },
    {
        "id": "cpu_usage_percentage_layout",
        "label": "CPU usage % bar + text",
        "category": "System",
        "kind": "sensor_combo",
        "component_id": "CPU.PERCENTAGE",
        "icon_name": "view-statistics-symbolic",
        "repeatable": False,
    },
    {
        "id": "cpu_temperature",
        "label": "CPU temperature",
        "category": "System",
        "kind": "sensor",
        "component_id": "CPU.TEMPERATURE",
        "icon_name": "utilities-system-monitor-symbolic",
        "repeatable": False,
    },
    {
        "id": "ram_usage",
        "label": "RAM usage",
        "category": "System",
        "kind": "sensor",
        "component_id": "MEMORY",
        "icon_name": "utilities-system-monitor-symbolic",
        "repeatable": False,
    },
    {
        "id": "gpu_usage",
        "label": "GPU usage",
        "category": "System",
        "kind": "sensor",
        "component_id": "GPU.PERCENTAGE",
        "icon_name": "utilities-system-monitor-symbolic",
        "repeatable": False,
    },
    {
        "id": "gpu_usage_percentage_layout",
        "label": "GPU usage % bar + text",
        "category": "System",
        "kind": "sensor_combo",
        "component_id": "GPU.PERCENTAGE",
        "icon_name": "view-statistics-symbolic",
        "repeatable": False,
    },
    {
        "id": "gpu_temperature",
        "label": "GPU temperature",
        "category": "System",
        "kind": "sensor",
        "component_id": "GPU.TEMPERATURE",
        "icon_name": "utilities-system-monitor-symbolic",
        "repeatable": False,
    },
    {
        "id": "gpu_memory_usage",
        "label": "GPU memory usage",
        "category": "System",
        "kind": "sensor",
        "component_id": "GPU.MEMORY_PERCENT",
        "icon_name": "utilities-system-monitor-symbolic",
        "repeatable": False,
    },
    {
        "id": "disk_usage",
        "label": "Disk usage",
        "category": "System",
        "kind": "sensor",
        "component_id": "DISK",
        "icon_name": "drive-harddisk-symbolic",
        "repeatable": False,
    },
    {
        "id": "internet_download",
        "label": "Internet download",
        "category": "Network",
        "kind": "sensor",
        "component_id": "NET.WLO.DOWNLOAD",
        "icon_name": "network-workgroup-symbolic",
        "repeatable": False,
    },
    {
        "id": "internet_upload",
        "label": "Internet upload",
        "category": "Network",
        "kind": "sensor",
        "component_id": "NET.WLO.UPLOAD",
        "icon_name": "network-workgroup-symbolic",
        "repeatable": False,
    },
    {
        "id": "ping",
        "label": "Ping",
        "category": "Network",
        "kind": "sensor",
        "component_id": "PING",
        "icon_name": "network-transmit-receive-symbolic",
        "repeatable": False,
    },
    {
        "id": "weather",
        "label": "Weather",
        "category": "Information",
        "kind": "sensor",
        "component_id": "WEATHER",
        "icon_name": "weather-clear-symbolic",
        "repeatable": False,
    },
    {
        "id": "system_uptime",
        "label": "System uptime",
        "category": "Information",
        "kind": "sensor",
        "component_id": "UPTIME",
        "icon_name": "appointment-soon-symbolic",
        "repeatable": False,
    },
    {
        "id": "date",
        "label": "Date",
        "category": "Information",
        "kind": "sensor",
        "component_id": "DATE.DAY",
        "icon_name": "x-office-calendar-symbolic",
        "repeatable": False,
    },
    {
        "id": "time",
        "label": "Time",
        "category": "Information",
        "kind": "sensor",
        "component_id": "DATE.HOUR",
        "icon_name": "appointment-soon-symbolic",
        "repeatable": False,
    },
)

_ENTRY_BY_ID = {entry["id"]: entry for entry in THEME_ELEMENT_CATALOG}
_ENTRY_BY_COMPONENT = {
    entry["component_id"]: entry for entry in THEME_ELEMENT_CATALOG
}

_SPECIAL_LABELS = {
    "display": "Display",
    "video": "Video and background",
    "static_text": "Text",
    "static_images": "Images",
    "STATS": "System metrics",
    "PERCENT_TEXT": "Percentage text",
    "WEATHER_DESCRIPTION": "Weather description",
    "MEMORY_PERCENT": "Memory usage",
    "DOWNLOAD": "Download",
    "UPLOAD": "Upload",
    "HOUR": "Time",
    "DAY": "Date",
}
_ACRONYMS = {"CPU", "GPU", "RAM", "SSD", "FPS", "IP"}
_ROOT_ORDER = {"display": 0, "video": 1, "static_text": 2, "static_images": 3, "STATS": 4}


def catalog_entries() -> List[Dict[str, Any]]:
    """Return independent copies of catalog entries in display order."""
    return copy.deepcopy(list(THEME_ELEMENT_CATALOG))


def get_catalog_entry(element_id: str) -> Dict[str, Any]:
    """Return an independent copy of one catalog entry."""
    try:
        return copy.deepcopy(_ENTRY_BY_ID[element_id])
    except KeyError as exc:
        raise KeyError(f"Unknown theme element: {element_id}") from exc


def humanize_element_label(value: Any) -> str:
    """Convert a YAML key into a human-friendly display label."""
    text = str(value)
    if text in _SPECIAL_LABELS:
        return _SPECIAL_LABELS[text]
    parts = [part for part in text.replace("-", "_").split("_") if part]
    if not parts:
        return text
    words = [part if part.upper() in _ACRONYMS else part.lower() for part in parts]
    label = " ".join(words)
    return label[:1].upper() + label[1:]


def element_icon_name(path: ThemePath, node: Any) -> str:
    """Return a symbolic icon name for a YAML path."""
    if not path:
        return "folder-symbolic"
    if path[0] == "display":
        return "video-display-symbolic"
    if path[0] == "video":
        return "video-x-generic-symbolic"
    if path[0] == "static_text":
        return "insert-text-symbolic"
    if path[0] == "static_images":
        return "image-x-generic-symbolic"
    label = str(path[-1]).upper()
    if path[0] == "STATS":
        if label in {"GRAPH", "LINE_GRAPH"}:
            return "view-statistics-symbolic"
        return "utilities-system-monitor-symbolic"
    return "folder-symbolic" if isinstance(node, Mapping) else "applications-system-symbolic"


def _interval_enabled(node: Mapping[str, Any], inherited_enabled: bool) -> bool:
    if not inherited_enabled:
        return False
    if "INTERVAL" not in node:
        return True
    try:
        return int(node.get("INTERVAL", 0) or 0) > 0
    except (TypeError, ValueError):
        return False


def element_state(path: ThemePath, node: Any, *, inherited_enabled: bool = True) -> str:
    """Return the direct visibility state for one YAML node."""
    if not isinstance(node, Mapping):
        return STATE_STRUCTURAL
    if path == ("video",):
        return STATE_ACTIVE if node.get("ENABLED", False) else STATE_INACTIVE
    if len(path) == 2 and path[0] in {"static_text", "static_images"}:
        return STATE_ACTIVE if node.get("SHOW", True) else STATE_INACTIVE
    if "SHOW" in node:
        return STATE_ACTIVE if inherited_enabled and bool(node.get("SHOW")) else STATE_INACTIVE
    return STATE_STRUCTURAL


def tree_state(path: ThemePath, node: Any, *, inherited_enabled: bool = True) -> str:
    """Return aggregate state for a YAML node and its descendants."""
    direct = element_state(path, node, inherited_enabled=inherited_enabled)
    if direct != STATE_STRUCTURAL:
        return direct
    if not isinstance(node, Mapping):
        return STATE_STRUCTURAL

    child_enabled = _interval_enabled(node, inherited_enabled)
    child_states: List[str] = []
    for key, value in node.items():
        if isinstance(value, Mapping):
            state = tree_state(path + (key,), value, inherited_enabled=child_enabled)
            if state != STATE_STRUCTURAL:
                child_states.append(state)

    if not child_states:
        return STATE_STRUCTURAL
    if all(state == STATE_ACTIVE for state in child_states):
        return STATE_ACTIVE
    if all(state == STATE_INACTIVE for state in child_states):
        return STATE_INACTIVE
    return STATE_MIXED


def _node_at_path(theme_data: Mapping[str, Any], path: ThemePath) -> Optional[Any]:
    node: Any = theme_data
    try:
        for part in path:
            node = node[part]
    except (KeyError, TypeError, IndexError):
        return None
    return node


def _component_base_path(component_id: str) -> ThemePath:
    return ("STATS",) + tuple(component_id.split("."))


def _first_controllable(path: ThemePath, node: Any, inherited_enabled: bool = True) -> Optional[ThemePath]:
    if element_state(path, node, inherited_enabled=inherited_enabled) != STATE_STRUCTURAL:
        return path
    if not isinstance(node, Mapping):
        return None
    child_enabled = _interval_enabled(node, inherited_enabled)
    for key, value in node.items():
        if isinstance(value, Mapping):
            found = _first_controllable(path + (key,), value, child_enabled)
            if found is not None:
                return found
    return None


def catalog_preferred_path(theme_data: Mapping[str, Any], element_id: str) -> Optional[ThemePath]:
    """Return the preferred editable path for a catalog element, if present."""
    entry = _ENTRY_BY_ID.get(element_id)
    if entry is None:
        raise KeyError(f"Unknown theme element: {element_id}")
    if entry["component_id"] == "text":
        container = theme_data.get("static_text", {})
        if isinstance(container, Mapping) and container:
            return ("static_text", next(iter(container)))
        return ("static_text",)
    if entry["component_id"] == "image":
        container = theme_data.get("static_images", {})
        if isinstance(container, Mapping) and container:
            return ("static_images", next(iter(container)))
        return ("static_images",)

    base_path = _component_base_path(entry["component_id"])
    node = _node_at_path(theme_data, base_path)
    if node is None:
        return None
    preferred = _first_controllable(base_path, node)
    return preferred or base_path


def catalog_presence(theme_data: Mapping[str, Any], element_id: str) -> Dict[str, Any]:
    """Return presence and visibility information for a catalog entry."""
    entry = _ENTRY_BY_ID.get(element_id)
    if entry is None:
        raise KeyError(f"Unknown theme element: {element_id}")

    component_id = entry["component_id"]
    if component_id == "text":
        container = theme_data.get("static_text", {})
        count = len(container) if isinstance(container, Mapping) else 0
        state = tree_state(("static_text",), container) if count else "missing"
        return {
            "present": count > 0,
            "count": count,
            "state": state,
            "path": catalog_preferred_path(theme_data, element_id),
        }
    if component_id == "image":
        container = theme_data.get("static_images", {})
        count = len(container) if isinstance(container, Mapping) else 0
        state = tree_state(("static_images",), container) if count else "missing"
        return {
            "present": count > 0,
            "count": count,
            "state": state,
            "path": catalog_preferred_path(theme_data, element_id),
        }

    path = _component_base_path(component_id)
    node = _node_at_path(theme_data, path)
    if node is None:
        return {"present": False, "count": 0, "state": "missing", "path": None}
    return {
        "present": True,
        "count": 1,
        "state": tree_state(path, node),
        "path": catalog_preferred_path(theme_data, element_id),
    }


def _iter_control_states(path: ThemePath, node: Any, inherited_enabled: bool = True) -> Iterable[str]:
    state = element_state(path, node, inherited_enabled=inherited_enabled)
    if state != STATE_STRUCTURAL:
        yield state
        return
    if not isinstance(node, Mapping):
        return
    child_enabled = _interval_enabled(node, inherited_enabled)
    for key, value in node.items():
        if isinstance(value, Mapping):
            yield from _iter_control_states(path + (key,), value, child_enabled)


def theme_state_summary(theme_data: Mapping[str, Any]) -> Dict[str, int]:
    """Count final controllable elements by state without double-counting groups."""
    summary = {
        STATE_ACTIVE: 0,
        STATE_INACTIVE: 0,
        STATE_MIXED: 0,
        STATE_STRUCTURAL: 0,
    }
    if not isinstance(theme_data, Mapping):
        return summary

    for key, node in theme_data.items():
        if not isinstance(node, Mapping):
            continue
        states = list(_iter_control_states((key,), node))
        if states:
            for state in states:
                summary[state] += 1
        elif key in _ROOT_ORDER:
            summary[STATE_STRUCTURAL] += 1
    return summary


def sorted_root_keys(mapping: Mapping[str, Any]) -> List[str]:
    """Return root keys in navigator display order without changing YAML order."""
    return sorted(mapping.keys(), key=lambda key: (_ROOT_ORDER.get(str(key), 99), list(mapping.keys()).index(key)))
