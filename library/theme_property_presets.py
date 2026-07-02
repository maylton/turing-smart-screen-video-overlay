# SPDX-License-Identifier: GPL-3.0-or-later
"""Reusable preset choices for the GTK theme property editor."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence, Tuple, Union

Preset = Tuple[str, Any]

FONT_SUFFIXES = {".ttf", ".otf", ".ttc"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}

PROPERTY_PRESETS = {
    "DISPLAY_SIZE": (
        ('0.96"', '0.96"'), ('2.1"', '2.1"'), ('2.8"', '2.8"'),
        ('3.5"', '3.5"'), ('4.6"', '4.6"'), ('5"', '5"'),
        ('5.2"', '5.2"'), ('8"', '8"'), ('8.8"', '8.8"'),
        ('9.2"', '9.2"'), ('12.3"', '12.3"'),
    ),
    "DISPLAY_ORIENTATION": (
        ("Portrait", "portrait"),
        ("Landscape", "landscape"),
    ),
    "ALIGN": (
        ("Left", "left"),
        ("Center", "center"),
        ("Right", "right"),
    ),
    "ANCHOR": (
        ("Top left", "lt"), ("Top center", "mt"), ("Top right", "rt"),
        ("Middle left", "lm"), ("Center", "mm"), ("Middle right", "rm"),
        ("Bottom left", "lb"), ("Bottom center", "mb"),
        ("Bottom right", "rb"),
    ),
    "FORMAT": (
        ("Short", "short"), ("Medium", "medium"),
        ("Long", "long"), ("Full", "full"),
    ),
    "BAR_DECORATION": (
        ("None", ""),
        ("Ellipse", "Ellipse"),
    ),
    "FONT_SIZE": tuple((f"{value} px", value) for value in (
        10, 12, 14, 16, 18, 20, 24, 28, 32,
        36, 40, 48, 56, 64, 72, 96, 112,
    )),
    "AXIS_FONT_SIZE": tuple((f"{value} px", value) for value in (
        8, 10, 12, 14, 16, 18, 20, 24,
    )),
    "INTERVAL": (
        ("Disabled", 0), ("Every second", 1), ("Every 2 seconds", 2),
        ("Every 5 seconds", 5), ("Every 10 seconds", 10),
        ("Every 30 seconds", 30), ("Every minute", 60),
        ("Every 5 minutes", 300),
    ),
    "REFRESH_INTERVAL": (
        ("0.25 seconds", 0.25), ("0.5 seconds", 0.5),
        ("1 second", 1.0), ("2 seconds", 2.0), ("5 seconds", 5.0),
    ),
    "X": tuple((f"{value} px", value) for value in (
        0, 24, 48, 96, 120, 160, 240, 320, 360, 400, 480,
    )),
    "Y": tuple((f"{value} px", value) for value in (
        0, 24, 48, 96, 120, 160, 240, 320, 360, 400, 480,
    )),
    "WIDTH": (
        ("Automatic", 0), ("24 px", 24), ("32 px", 32),
        ("48 px", 48), ("64 px", 64), ("96 px", 96),
        ("120 px", 120), ("160 px", 160), ("240 px", 240),
        ("320 px", 320), ("Full — 480 px", 480),
    ),
    "HEIGHT": (
        ("Automatic", 0), ("24 px", 24), ("32 px", 32),
        ("48 px", 48), ("64 px", 64), ("96 px", 96),
        ("120 px", 120), ("160 px", 160), ("240 px", 240),
        ("320 px", 320), ("Full — 480 px", 480),
    ),
    "RADIUS": tuple((f"{value} px", value) for value in (
        10, 20, 30, 40, 50, 60, 80, 100, 120, 160, 200,
    )),
    "LINE_WIDTH": tuple((f"{value} px", value) for value in (
        1, 2, 3, 4, 5, 8, 10, 12,
    )),
    "MIN_SIZE": (
        ("No padding", 0), ("2 characters", 2), ("3 characters", 3),
        ("4 characters", 4), ("5 characters", 5),
        ("6 characters", 6), ("8 characters", 8),
        ("10 characters", 10),
    ),
    "MIN_VALUE": tuple((str(value), value) for value in (0, 10, 25, 50)),
    "MAX_VALUE": tuple((str(value), value) for value in (
        50, 75, 95, 100, 120, 1000,
    )),
    "HISTORY_SIZE": tuple((f"{value} samples", value) for value in (
        10, 20, 30, 60, 120,
    )),
    "ANGLE_START": tuple((f"{value}°", value) for value in (
        0, 45, 90, 135, 180, 225, 270, 315,
    )),
    "ANGLE_END": tuple((f"{value}°", value) for value in (
        0, 45, 90, 135, 180, 225, 270, 315, 360,
    )),
    "ANGLE_STEPS": tuple((f"{value} steps", value) for value in (
        1, 5, 10, 20, 50, 100,
    )),
    "ANGLE_SEP": (
        ("No separation", 0), ("1°", 1), ("2°", 2),
        ("3°", 3), ("5°", 5), ("10°", 10),
    ),
}


def _same_value(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return float(left) == float(right)
    return left == right


def _deduplicate(options: Iterable[Preset]) -> List[Preset]:
    result: List[Preset] = []
    for label, value in options:
        if any(_same_value(value, existing) for _, existing in result):
            continue
        result.append((str(label), value))
    return result


PathLike = Union[str, Path]


def _relative_asset_presets(
    directory: Optional[PathLike],
    suffixes: Sequence[str],
) -> List[Preset]:
    if directory is None:
        return []

    base_dir = Path(directory)
    if not base_dir.is_dir():
        return []

    suffix_set = {suffix.lower() for suffix in suffixes}
    assets = []
    for path in base_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in suffix_set:
            continue
        relative = path.relative_to(base_dir).as_posix()
        assets.append((relative, relative))

    return sorted(assets, key=lambda item: item[0].casefold())


def property_preset_options(
    key: str,
    current_value: Any,
    *,
    fonts_dir: Optional[PathLike] = None,
    theme_dir: Optional[PathLike] = None,
) -> List[Preset]:
    """Return typed, display-ready preset options for one theme property.

    Unsupported properties return a current-value option when a value exists,
    otherwise an empty list. The current option keeps custom values visible
    without changing them.
    """

    options: List[Preset] = list(PROPERTY_PRESETS.get(key, ()))

    if key in {"FONT", "AXIS_FONT"}:
        options.extend(_relative_asset_presets(fonts_dir, tuple(FONT_SUFFIXES)))
    elif key in {"BACKGROUND_IMAGE", "PREVIEW_BACKGROUND"}:
        options.extend(_relative_asset_presets(theme_dir, tuple(IMAGE_SUFFIXES)))

    options = _deduplicate(options)

    if current_value is not None and not any(
        _same_value(current_value, value) for _, value in options
    ):
        options.insert(0, (f"Current — {current_value}", current_value))

    return options
