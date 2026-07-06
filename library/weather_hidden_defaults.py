# SPDX-License-Identifier: GPL-3.0-or-later
"""Hidden-first defaults for compound Weather theme elements.

Adding a compound element should create the full editable structure without
immediately cluttering the preview. The user can then enable only the text nodes
or presets they actually want.
"""

from __future__ import annotations

import copy
from typing import Any, Mapping


def _set_show_recursive(node: Any, value: bool) -> None:
    if isinstance(node, dict):
        if "SHOW" in node:
            node["SHOW"] = value
        for child in node.values():
            _set_show_recursive(child, value)
    elif isinstance(node, list):
        for child in node:
            _set_show_recursive(child, value)


def install() -> None:
    from library import weather_runtime_patch as runtime

    original_defaults = runtime.weather_theme_defaults

    def hidden_weather_theme_defaults(
        theme_data: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = copy.deepcopy(original_defaults(theme_data))
        _set_show_recursive(data, False)
        return data

    def ensure_weather_in_theme_hidden(editor: Any) -> tuple[bool, tuple[str, ...]]:
        stats = editor.theme_data.setdefault("STATS", {})
        weather = stats.get("WEATHER")
        changed = False

        if not isinstance(weather, dict):
            stats["WEATHER"] = hidden_weather_theme_defaults(editor.theme_data)
            changed = True
        else:
            defaults = hidden_weather_theme_defaults(editor.theme_data)
            for key, value in defaults.items():
                if key not in weather:
                    weather[key] = copy.deepcopy(value)
                    changed = True
                elif isinstance(value, dict) and isinstance(weather.get(key), dict):
                    for subkey, subvalue in value.items():
                        if subkey not in weather[key]:
                            weather[key][subkey] = copy.deepcopy(subvalue)
                            changed = True

        weather = stats["WEATHER"]
        try:
            weather["INTERVAL"] = int(weather.get("INTERVAL") or 600)
        except (TypeError, ValueError):
            weather["INTERVAL"] = 600
            changed = True

        return changed, ("STATS", "WEATHER")

    runtime.weather_theme_defaults = hidden_weather_theme_defaults
    runtime._ensure_weather_in_theme = ensure_weather_in_theme_hidden
