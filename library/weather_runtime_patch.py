# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime integration for the weather provider and GTK editor.

This keeps the weather work isolated while the weather feature is being
stabilized. The hooks are intentionally tiny:

* patch ``library.stats.Weather.stats`` after ``library.stats`` is imported;
* teach the GTK editor's existing Weather catalog action how to create a
  minimal ``STATS / WEATHER`` tree when a theme does not have one yet.
"""

from __future__ import annotations

import copy
import importlib.abc
import importlib.machinery
import sys
import threading
from typing import Any, Mapping


_INSTALLED = False
_EDITOR_PATCH_ATTEMPTS = 0
_MAX_EDITOR_PATCH_ATTEMPTS = 100


def _text_node(
    *,
    show: bool,
    x: int,
    y: int,
    width: int,
    height: int,
    font_size: int,
    font_color: list[int],
    align: str = "left",
    anchor: str = "lt",
    bold: bool = False,
) -> dict[str, Any]:
    return {
        "SHOW": show,
        "X": x,
        "Y": y,
        "WIDTH": width,
        "HEIGHT": height,
        "FONT": (
            "roboto-mono/RobotoMono-Bold.ttf"
            if bold
            else "roboto-mono/RobotoMono-Regular.ttf"
        ),
        "FONT_SIZE": font_size,
        "FONT_COLOR": font_color,
        "BACKGROUND_COLOR": [0, 0, 0, 0],
        "ALIGN": align,
        "ANCHOR": anchor,
    }


def weather_theme_defaults(theme_data: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return a compact, safe starter WEATHER node for theme.yaml."""

    width = 320
    height = 480
    display = theme_data.get("display", {}) if isinstance(theme_data, Mapping) else {}
    size = str(display.get("DISPLAY_SIZE", "")).strip()
    orientation = str(display.get("DISPLAY_ORIENTATION", "portrait")).strip().lower()

    if size in {'5"', '8"', '8.8"', '9.2"', '12.3"'} or orientation == "landscape":
        width = 480
        height = 320

    left = 20
    top = max(20, height - 118)
    block_width = max(180, min(260, width - 40))

    return {
        "INTERVAL": 600,
        "TEMPERATURE": {
            "TEXT": _text_node(
                show=True,
                x=left,
                y=top,
                width=block_width,
                height=42,
                font_size=30,
                font_color=[255, 255, 255],
                bold=True,
            )
        },
        "TEMPERATURE_FELT": {
            "TEXT": _text_node(
                show=False,
                x=left + 92,
                y=top + 9,
                width=110,
                height=28,
                font_size=14,
                font_color=[210, 220, 235],
            )
        },
        "WEATHER_DESCRIPTION": {
            "TEXT": _text_node(
                show=True,
                x=left,
                y=top + 44,
                width=block_width,
                height=30,
                font_size=16,
                font_color=[230, 238, 255],
            )
        },
        "HUMIDITY": {
            "TEXT": _text_node(
                show=True,
                x=left,
                y=top + 76,
                width=80,
                height=24,
                font_size=14,
                font_color=[170, 210, 255],
            )
        },
        "UPDATE_TIME": {
            "TEXT": _text_node(
                show=True,
                x=left + 86,
                y=top + 76,
                width=90,
                height=24,
                font_size=14,
                font_color=[170, 210, 255],
            )
        },
    }


def weather_text_nodes(weather_theme_data: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    return (
        weather_theme_data.get("TEMPERATURE", {}).get("TEXT", {}),
        weather_theme_data.get("TEMPERATURE_FELT", {}).get("TEXT", {}),
        weather_theme_data.get("UPDATE_TIME", {}).get("TEXT", {}),
        weather_theme_data.get("WEATHER_DESCRIPTION", {}).get("TEXT", {}),
        weather_theme_data.get("HUMIDITY", {}).get("TEXT", {}),
    )


def patch_stats_module(stats_module: Any) -> None:
    """Patch ``library.stats.Weather.stats`` to use WeatherProvider."""

    if getattr(stats_module.Weather.stats, "_weather_provider_patch", False):
        return

    from library.weather_provider import WeatherProvider

    def weather_stats() -> None:
        config = stats_module.config
        weather_theme_data = config.THEME_DATA.get("STATS", {}).get("WEATHER", {})
        if not isinstance(weather_theme_data, Mapping):
            return

        nodes = weather_text_nodes(weather_theme_data)
        if not any(isinstance(node, Mapping) and node.get("SHOW") for node in nodes):
            return

        settings = config.CONFIG_DATA.get("config", {})
        snapshot = WeatherProvider.fetch(settings, getattr(stats_module, "HW_SENSORS", "AUTO"))
        values = snapshot.as_theme_values()

        wtemperature, wfelt, wupdatetime, wdescription, whumidity = nodes
        stats_module.display_themed_value(theme_data=wtemperature, value=values["temp"])
        stats_module.display_themed_value(theme_data=wfelt, value=values["feel"])
        stats_module.display_themed_value(theme_data=wupdatetime, value=values["time"])
        stats_module.display_themed_value(theme_data=whumidity, value=values["humidity"])
        stats_module.display_themed_value(theme_data=wdescription, value=values["desc"])

    weather_stats._weather_provider_patch = True
    stats_module.Weather.stats = staticmethod(weather_stats)


class _StatsPatchLoader(importlib.abc.Loader):
    def __init__(self, wrapped: importlib.abc.Loader):
        self.wrapped = wrapped

    def create_module(self, spec):  # noqa: D401 - importlib protocol
        create = getattr(self.wrapped, "create_module", None)
        if create is None:
            return None
        return create(spec)

    def exec_module(self, module):  # noqa: D401 - importlib protocol
        self.wrapped.exec_module(module)
        patch_stats_module(module)


class _StatsPatchFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):  # noqa: D401 - importlib protocol
        if fullname != "library.stats":
            return None

        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return None
        if isinstance(spec.loader, _StatsPatchLoader):
            return spec
        spec.loader = _StatsPatchLoader(spec.loader)
        return spec


def _ensure_weather_in_theme(editor: Any) -> tuple[bool, tuple[str, ...]]:
    stats = editor.theme_data.setdefault("STATS", {})
    weather = stats.get("WEATHER")
    created = False
    if not isinstance(weather, dict):
        stats["WEATHER"] = weather_theme_defaults(editor.theme_data)
        created = True
    else:
        defaults = weather_theme_defaults(editor.theme_data)
        for key, value in defaults.items():
            if key not in weather:
                weather[key] = copy.deepcopy(value)
                created = True
            elif isinstance(value, dict) and isinstance(weather.get(key), dict):
                for subkey, subvalue in value.items():
                    if subkey not in weather[key]:
                        weather[key][subkey] = copy.deepcopy(subvalue)
                        created = True

    # Make the core weather card visible when adding Weather from the catalog.
    weather = stats["WEATHER"]
    for section in ("TEMPERATURE", "WEATHER_DESCRIPTION", "HUMIDITY", "UPDATE_TIME"):
        node = weather.get(section, {}).get("TEXT")
        if isinstance(node, dict) and not node.get("SHOW", False):
            node["SHOW"] = True
            created = True

    try:
        weather["INTERVAL"] = int(weather.get("INTERVAL") or 600)
    except (TypeError, ValueError):
        weather["INTERVAL"] = 600
        created = True

    return created, ("STATS", "WEATHER", "TEMPERATURE", "TEXT")


def _patch_theme_editor_window(window_class: type) -> bool:
    original = getattr(window_class, "on_add_element_clicked", None)
    if original is None or getattr(original, "_weather_editor_patch", False):
        return False

    def on_add_element_clicked(self, *args, **kwargs):
        try:
            index = self.add_element_dropdown.get_selected()
            entry = self.catalog_entries[index]
        except Exception:
            return original(self, *args, **kwargs)

        if entry.get("id") != "weather":
            return original(self, *args, **kwargs)

        self.push_undo()
        changed, target_path = _ensure_weather_in_theme(self)
        if not changed:
            self.toast("Weather is already available")
        if not self.save_theme_data():
            return None
        self.populate_elements()
        self.selected_path = target_path
        self.build_property_rows()
        self.refresh_preview()
        try:
            self.restore_tree_selection(target_path)
        except Exception:
            pass
        self.toast("Weather added")
        return None

    on_add_element_clicked._weather_editor_patch = True
    window_class.on_add_element_clicked = on_add_element_clicked
    return True


def _patch_editor_when_ready() -> None:
    global _EDITOR_PATCH_ATTEMPTS
    _EDITOR_PATCH_ATTEMPTS += 1

    main = sys.modules.get("__main__")
    window_class = getattr(main, "ThemeEditorWindow", None) if main is not None else None
    if isinstance(window_class, type) and _patch_theme_editor_window(window_class):
        return

    if _EDITOR_PATCH_ATTEMPTS < _MAX_EDITOR_PATCH_ATTEMPTS:
        timer = threading.Timer(0.05, _patch_editor_when_ready)
        timer.daemon = True
        timer.start()


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    if not any(isinstance(finder, _StatsPatchFinder) for finder in sys.meta_path):
        sys.meta_path.insert(0, _StatsPatchFinder())

    if "library.stats" in sys.modules:
        patch_stats_module(sys.modules["library.stats"])

    timer = threading.Timer(0.05, _patch_editor_when_ready)
    timer.daemon = True
    timer.start()
