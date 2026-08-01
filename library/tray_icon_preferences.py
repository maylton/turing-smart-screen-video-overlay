# SPDX-License-Identifier: GPL-3.0-or-later
"""Persistent tray icon appearance preferences.

The setting is intentionally independent from the GTK application process so
both the StatusNotifierItem tray and the legacy pystray path can consume it.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


MODE_FOLLOW_THEME = "follow-theme"
MODE_COLOR = "color"
MODE_DARK_THEME = "dark-theme"
MODE_LIGHT_THEME = "light-theme"

VALID_MODES = (
    MODE_FOLLOW_THEME,
    MODE_COLOR,
    MODE_DARK_THEME,
    MODE_LIGHT_THEME,
)
DEFAULT_MODE = MODE_FOLLOW_THEME


def settings_directory() -> Path:
    override = os.environ.get("XDG_CONFIG_HOME", "").strip()
    base = Path(override).expanduser() if override else Path.home() / ".config"
    return base / "turing-smart-screen"


def preference_path() -> Path:
    return settings_directory() / "tray-icon.conf"


def application_scheme_path() -> Path:
    return settings_directory() / "ui-settings.conf"


def normalize_mode(value: str) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in VALID_MODES else DEFAULT_MODE


def load_tray_icon_mode(path: Optional[Path] = None) -> str:
    target = Path(path) if path is not None else preference_path()
    try:
        value = target.read_text(encoding="utf-8")
    except OSError:
        return DEFAULT_MODE
    return normalize_mode(value)


def save_tray_icon_mode(mode: str, path: Optional[Path] = None) -> str:
    normalized = normalize_mode(mode)
    target = Path(path) if path is not None else preference_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    temporary.write_text(normalized + "\n", encoding="utf-8")
    os.replace(temporary, target)
    return normalized


def load_saved_application_scheme() -> str:
    try:
        value = application_scheme_path().read_text(encoding="utf-8").strip().lower()
    except OSError:
        return "system"
    return value if value in {"system", "light", "dark"} else "system"


def environment_prefers_dark() -> bool:
    for variable in ("GTK_THEME", "QT_STYLE_OVERRIDE", "COLOR_SCHEME"):
        value = os.environ.get(variable, "").strip().lower()
        if not value:
            continue
        if "dark" in value:
            return True
        if "light" in value:
            return False

    # The app is primarily used in dark Linux panels such as Caelestia. When
    # the system preference cannot be queried, the light symbolic glyph is the
    # safer and more legible fallback.
    return True


def resolve_tray_icon_variant(
    mode: Optional[str] = None,
    *,
    dark_theme: Optional[bool] = None,
) -> str:
    selected = normalize_mode(mode if mode is not None else load_tray_icon_mode())
    if selected != MODE_FOLLOW_THEME:
        return selected

    if dark_theme is None:
        scheme = load_saved_application_scheme()
        if scheme == "dark":
            dark_theme = True
        elif scheme == "light":
            dark_theme = False
        else:
            dark_theme = environment_prefers_dark()

    return MODE_DARK_THEME if dark_theme else MODE_LIGHT_THEME
