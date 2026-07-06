# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime integration for the weather provider and GTK editor.

This keeps the weather work isolated while the weather feature is being
stabilized. The hooks are intentionally tiny:

* patch ``library.stats.Weather.stats`` after ``library.stats`` is imported;
* teach the GTK editor's existing Weather catalog action how to create a
  minimal ``STATS / WEATHER`` tree when a theme does not have one yet;
* add weather-card presets to the editor Properties panel.
"""

from __future__ import annotations

import copy
import importlib.abc
import importlib.machinery
import sys
import threading
from typing import Any, Mapping


_INSTALLED = False
_STATS_PATCH_ATTEMPTS = 0
_EDITOR_PATCH_ATTEMPTS = 0
_MAX_PATCH_ATTEMPTS = 100


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


def _theme_canvas_dimensions(theme_data: Mapping[str, Any] | None = None) -> tuple[int, int]:
    width = 320
    height = 480
    display = theme_data.get("display", {}) if isinstance(theme_data, Mapping) else {}
    size = str(display.get("DISPLAY_SIZE", "")).strip()
    orientation = str(display.get("DISPLAY_ORIENTATION", "portrait")).strip().lower()

    if size in {'5"', '8"', '8.8"', '9.2"', '12.3"'} or orientation == "landscape":
        width = 480
        height = 320
    return width, height


def weather_theme_defaults(theme_data: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return a compact, safe starter WEATHER node for theme.yaml."""

    width, height = _theme_canvas_dimensions(theme_data)
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


def _with_text_effects(node: dict[str, Any], effects: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(node)
    updated["EFFECTS"] = copy.deepcopy(effects)
    return updated


def weather_card_presets(theme_data: Mapping[str, Any] | None = None) -> list[tuple[str, dict[str, Any]]]:
    """Return ready-to-apply WEATHER node layouts for the Properties panel."""

    width, height = _theme_canvas_dimensions(theme_data)
    card_width = min(width - 32, 280)
    bottom_x = max(16, (width - card_width) // 2)
    bottom_y = max(16, height - 122)
    center_x = width // 2
    center_y = height // 2

    subtle_shadow = {
        "SHADOW": {
            "ENABLED": True,
            "COLOR": [0, 0, 0, 180],
            "OFFSET_X": 2,
            "OFFSET_Y": 2,
            "BLUR_RADIUS": 4,
        }
    }
    blue_glow = {
        "GLOW": {
            "ENABLED": True,
            "COLOR": [80, 180, 255, 120],
            "BLUR_RADIUS": 5,
            "INTENSITY": 1,
        }
    }
    warm_shadow = {
        "SHADOW": {
            "ENABLED": True,
            "COLOR": [0, 0, 0, 150],
            "OFFSET_X": 1,
            "OFFSET_Y": 2,
            "BLUR_RADIUS": 3,
        }
    }

    bottom_card = {
        "INTERVAL": 600,
        "TEMPERATURE": {
            "TEXT": _with_text_effects(
                _text_node(
                    show=True,
                    x=bottom_x,
                    y=bottom_y,
                    width=card_width,
                    height=42,
                    font_size=31,
                    font_color=[255, 255, 255],
                    bold=True,
                ),
                subtle_shadow,
            )
        },
        "TEMPERATURE_FELT": {
            "TEXT": _text_node(
                show=True,
                x=bottom_x + 96,
                y=bottom_y + 10,
                width=112,
                height=24,
                font_size=14,
                font_color=[205, 226, 248],
            )
        },
        "WEATHER_DESCRIPTION": {
            "TEXT": _with_text_effects(
                _text_node(
                    show=True,
                    x=bottom_x,
                    y=bottom_y + 44,
                    width=card_width,
                    height=30,
                    font_size=16,
                    font_color=[230, 240, 255],
                ),
                subtle_shadow,
            )
        },
        "HUMIDITY": {
            "TEXT": _text_node(
                show=True,
                x=bottom_x,
                y=bottom_y + 78,
                width=82,
                height=24,
                font_size=14,
                font_color=[160, 215, 255],
            )
        },
        "UPDATE_TIME": {
            "TEXT": _text_node(
                show=True,
                x=bottom_x + 88,
                y=bottom_y + 78,
                width=92,
                height=24,
                font_size=14,
                font_color=[160, 215, 255],
            )
        },
    }

    top_strip = {
        "INTERVAL": 600,
        "TEMPERATURE": {
            "TEXT": _with_text_effects(
                _text_node(
                    show=True,
                    x=16,
                    y=14,
                    width=96,
                    height=36,
                    font_size=24,
                    font_color=[255, 255, 255],
                    bold=True,
                ),
                blue_glow,
            )
        },
        "TEMPERATURE_FELT": {
            "TEXT": _text_node(
                show=False,
                x=0,
                y=0,
                width=1,
                height=1,
                font_size=12,
                font_color=[200, 200, 200],
            )
        },
        "WEATHER_DESCRIPTION": {
            "TEXT": _text_node(
                show=True,
                x=116,
                y=18,
                width=max(120, width - 180),
                height=28,
                font_size=15,
                font_color=[225, 238, 255],
            )
        },
        "HUMIDITY": {
            "TEXT": _text_node(
                show=True,
                x=max(16, width - 128),
                y=48,
                width=56,
                height=22,
                font_size=13,
                font_color=[155, 215, 255],
            )
        },
        "UPDATE_TIME": {
            "TEXT": _text_node(
                show=True,
                x=max(80, width - 70),
                y=48,
                width=60,
                height=22,
                font_size=13,
                font_color=[155, 215, 255],
            )
        },
    }

    centered_card = {
        "INTERVAL": 600,
        "TEMPERATURE": {
            "TEXT": _with_text_effects(
                _text_node(
                    show=True,
                    x=center_x,
                    y=center_y - 40,
                    width=min(260, width - 32),
                    height=58,
                    font_size=42,
                    font_color=[255, 255, 255],
                    align="center",
                    anchor="mm",
                    bold=True,
                ),
                blue_glow,
            )
        },
        "TEMPERATURE_FELT": {
            "TEXT": _text_node(
                show=True,
                x=center_x,
                y=center_y + 3,
                width=min(160, width - 32),
                height=24,
                font_size=14,
                font_color=[215, 226, 245],
                align="center",
                anchor="mm",
            )
        },
        "WEATHER_DESCRIPTION": {
            "TEXT": _with_text_effects(
                _text_node(
                    show=True,
                    x=center_x,
                    y=center_y + 34,
                    width=min(260, width - 32),
                    height=30,
                    font_size=16,
                    font_color=[235, 242, 255],
                    align="center",
                    anchor="mm",
                ),
                subtle_shadow,
            )
        },
        "HUMIDITY": {
            "TEXT": _text_node(
                show=True,
                x=center_x - 42,
                y=center_y + 68,
                width=70,
                height=24,
                font_size=14,
                font_color=[160, 215, 255],
                align="center",
                anchor="mm",
            )
        },
        "UPDATE_TIME": {
            "TEXT": _text_node(
                show=True,
                x=center_x + 42,
                y=center_y + 68,
                width=80,
                height=24,
                font_size=14,
                font_color=[160, 215, 255],
                align="center",
                anchor="mm",
            )
        },
    }

    minimal_corner = {
        "INTERVAL": 600,
        "TEMPERATURE": {
            "TEXT": _with_text_effects(
                _text_node(
                    show=True,
                    x=18,
                    y=18,
                    width=100,
                    height=34,
                    font_size=23,
                    font_color=[255, 246, 220],
                    bold=True,
                ),
                warm_shadow,
            )
        },
        "TEMPERATURE_FELT": {
            "TEXT": _text_node(
                show=False,
                x=0,
                y=0,
                width=1,
                height=1,
                font_size=12,
                font_color=[255, 255, 255],
            )
        },
        "WEATHER_DESCRIPTION": {
            "TEXT": _text_node(
                show=True,
                x=18,
                y=52,
                width=min(190, width - 36),
                height=28,
                font_size=14,
                font_color=[255, 220, 170],
            )
        },
        "HUMIDITY": {
            "TEXT": _text_node(
                show=False,
                x=18,
                y=80,
                width=70,
                height=22,
                font_size=13,
                font_color=[255, 220, 170],
            )
        },
        "UPDATE_TIME": {
            "TEXT": _text_node(
                show=False,
                x=90,
                y=80,
                width=70,
                height=22,
                font_size=13,
                font_color=[255, 220, 170],
            )
        },
    }

    return [
        ("Bottom weather card", bottom_card),
        ("Top compact weather strip", top_strip),
        ("Centered glass weather card", centered_card),
        ("Minimal warm corner", minimal_corner),
    ]


def weather_text_nodes(weather_theme_data: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    return (
        weather_theme_data.get("TEMPERATURE", {}).get("TEXT", {}),
        weather_theme_data.get("TEMPERATURE_FELT", {}).get("TEXT", {}),
        weather_theme_data.get("UPDATE_TIME", {}).get("TEXT", {}),
        weather_theme_data.get("WEATHER_DESCRIPTION", {}).get("TEXT", {}),
        weather_theme_data.get("HUMIDITY", {}).get("TEXT", {}),
    )


def patch_stats_module(stats_module: Any) -> bool:
    """Patch ``library.stats.Weather.stats`` to use WeatherProvider."""

    weather_class = getattr(stats_module, "Weather", None)
    if weather_class is None or not hasattr(weather_class, "stats"):
        return False
    if getattr(weather_class.stats, "_weather_provider_patch", False):
        return True

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
    weather_class.stats = staticmethod(weather_stats)
    return True


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


def _patch_stats_when_ready() -> None:
    global _STATS_PATCH_ATTEMPTS
    _STATS_PATCH_ATTEMPTS += 1

    module = sys.modules.get("library.stats")
    if module is not None and patch_stats_module(module):
        return

    if _STATS_PATCH_ATTEMPTS < _MAX_PATCH_ATTEMPTS:
        timer = threading.Timer(0.05, _patch_stats_when_ready)
        timer.daemon = True
        timer.start()


def _ensure_weather_in_theme(editor: Any) -> tuple[bool, tuple[str, ...]]:
    stats = editor.theme_data.setdefault("STATS", {})
    weather = stats.get("WEATHER")
    changed = False
    if not isinstance(weather, dict):
        stats["WEATHER"] = weather_theme_defaults(editor.theme_data)
        changed = True
    else:
        defaults = weather_theme_defaults(editor.theme_data)
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
    for section in ("TEMPERATURE", "WEATHER_DESCRIPTION", "HUMIDITY", "UPDATE_TIME"):
        node = weather.get(section, {}).get("TEXT")
        if isinstance(node, dict) and not node.get("SHOW", False):
            node["SHOW"] = True
            changed = True

    try:
        weather["INTERVAL"] = int(weather.get("INTERVAL") or 600)
    except (TypeError, ValueError):
        weather["INTERVAL"] = 600
        changed = True

    return changed, ("STATS", "WEATHER", "TEMPERATURE", "TEXT")


def _patch_weather_presets(window_class: type) -> None:
    if getattr(window_class, "_weather_component_preset_patch", False):
        return

    original_kind = window_class.component_kind_for_node
    original_options = window_class.component_preset_options

    def component_kind_for_node(self, path, node):
        if tuple(path or ()) == ("STATS", "WEATHER") and isinstance(node, Mapping):
            return "weather_card"
        return original_kind(self, path, node)

    def component_preset_options(self, node):
        if tuple(getattr(self, "selected_path", ()) or ()) == ("STATS", "WEATHER"):
            return weather_card_presets(getattr(self, "theme_data", {}))
        return original_options(self, node)

    window_class.component_kind_for_node = component_kind_for_node
    window_class.component_preset_options = component_preset_options
    try:
        main = sys.modules.get("__main__")
        if main is not None and hasattr(main, "COMPONENT_PRESET_TITLES"):
            main.COMPONENT_PRESET_TITLES["weather_card"] = "Weather preset"
    except Exception:
        pass
    window_class._weather_component_preset_patch = True


def _patch_theme_editor_window(window_class: type) -> bool:
    _patch_weather_presets(window_class)

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

    if _EDITOR_PATCH_ATTEMPTS < _MAX_PATCH_ATTEMPTS:
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

    _patch_stats_when_ready()
    _patch_editor_when_ready()
