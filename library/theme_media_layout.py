# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure static-image layout helpers for the theme editor."""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from PIL import Image, ImageDraw

from library.media_profiles import oriented_dimensions

MODE_ORIGINAL = "original"
MODE_FIT = "fit"
MODE_FILL = "fill"
MODE_STRETCH = "stretch"
MODE_CUSTOM = "custom"

LAYOUT_MODES = (
    MODE_ORIGINAL,
    MODE_FIT,
    MODE_FILL,
    MODE_STRETCH,
    MODE_CUSTOM,
)

ALIGN_X = ("left", "center", "right")
ALIGN_Y = ("top", "center", "bottom")

MAX_DIMENSION = 4096


class ThemeMediaLayoutError(ValueError):
    """Raised when static image layout inputs are invalid."""


@dataclass(frozen=True)
class ImageLayoutSettings:
    """Validated image layout controls."""

    mode: str = MODE_FIT
    zoom: float = 1.0
    align_x: str = "center"
    align_y: str = "center"
    custom_width: int | None = None
    custom_height: int | None = None

    def __post_init__(self) -> None:
        if self.mode not in LAYOUT_MODES:
            raise ThemeMediaLayoutError(f"Unknown image layout mode: {self.mode}")
        if not math.isfinite(float(self.zoom)) or not 0.25 <= float(self.zoom) <= 4.0:
            raise ThemeMediaLayoutError("Zoom must be between 0.25 and 4.0")
        if self.align_x not in ALIGN_X:
            raise ThemeMediaLayoutError(f"Unknown horizontal alignment: {self.align_x}")
        if self.align_y not in ALIGN_Y:
            raise ThemeMediaLayoutError(f"Unknown vertical alignment: {self.align_y}")
        for name, value in (
            ("custom_width", self.custom_width),
            ("custom_height", self.custom_height),
        ):
            if value is None:
                continue
            if not 1 <= int(value) <= MAX_DIMENSION:
                raise ThemeMediaLayoutError(f"{name} must be between 1 and {MAX_DIMENSION}")
        if self.mode == MODE_CUSTOM and (
            self.custom_width is None or self.custom_height is None
        ):
            raise ThemeMediaLayoutError("Custom width and height are required in custom mode")


def _positive_dimension(value: int | float, label: str) -> int:
    try:
        result = int(round(float(value)))
    except (TypeError, ValueError) as exc:
        raise ThemeMediaLayoutError(f"{label} must be numeric") from exc
    if not 1 <= result <= MAX_DIMENSION:
        raise ThemeMediaLayoutError(f"{label} must be between 1 and {MAX_DIMENSION}")
    return result


def theme_canvas_dimensions(theme_data: Mapping[str, Any]) -> tuple[int, int]:
    """Return display canvas dimensions from theme data with safe fallbacks."""
    display = theme_data.get("display") if isinstance(theme_data, Mapping) else {}
    if not isinstance(display, Mapping):
        display = {}
    display_size = str(display.get("DISPLAY_SIZE") or '3.5"')
    orientation = str(display.get("DISPLAY_ORIENTATION") or "portrait")
    return oriented_dimensions(display_size, orientation)


def resolve_theme_image_path(theme_dir: str | Path, node: Mapping[str, Any]) -> Path:
    """Resolve a static image PATH against its theme directory."""
    if not isinstance(node, Mapping):
        raise ThemeMediaLayoutError("Static image node must be a mapping")
    raw_path = str(node.get("PATH") or "").strip()
    if not raw_path:
        raise ThemeMediaLayoutError("Static image PATH is required")
    source = Path(raw_path).expanduser()
    if not source.is_absolute():
        source = Path(theme_dir).expanduser() / source
    source = source.resolve()
    if not source.is_file():
        raise ThemeMediaLayoutError(f"Static image file is not available: {source}")
    return source


def image_dimensions(path: str | Path) -> tuple[int, int]:
    """Return image dimensions using Pillow while closing the file promptly."""
    with Image.open(path) as image:
        return int(image.width), int(image.height)


def _aligned_position(canvas: int, size: int, alignment: str) -> int:
    if alignment in {"left", "top"}:
        return 0
    if alignment == "center":
        return round((canvas - size) / 2)
    return canvas - size


def compute_image_layout(
    source_width: int,
    source_height: int,
    canvas_width: int,
    canvas_height: int,
    settings: ImageLayoutSettings,
) -> dict[str, int]:
    """Compute X/Y/WIDTH/HEIGHT for a static image on the theme canvas."""
    source_width = _positive_dimension(source_width, "source_width")
    source_height = _positive_dimension(source_height, "source_height")
    canvas_width = _positive_dimension(canvas_width, "canvas_width")
    canvas_height = _positive_dimension(canvas_height, "canvas_height")

    if settings.mode == MODE_ORIGINAL:
        width, height = source_width, source_height
    elif settings.mode == MODE_FIT:
        ratio = min(canvas_width / source_width, canvas_height / source_height)
        width = round(source_width * ratio)
        height = round(source_height * ratio)
    elif settings.mode == MODE_FILL:
        ratio = max(canvas_width / source_width, canvas_height / source_height)
        width = round(source_width * ratio)
        height = round(source_height * ratio)
    elif settings.mode == MODE_STRETCH:
        width, height = canvas_width, canvas_height
    elif settings.mode == MODE_CUSTOM:
        width = int(settings.custom_width or 0)
        height = int(settings.custom_height or 0)
    else:
        raise ThemeMediaLayoutError(f"Unknown image layout mode: {settings.mode}")

    width = _positive_dimension(width * settings.zoom, "WIDTH")
    height = _positive_dimension(height * settings.zoom, "HEIGHT")
    return {
        "X": _aligned_position(canvas_width, width, settings.align_x),
        "Y": _aligned_position(canvas_height, height, settings.align_y),
        "WIDTH": width,
        "HEIGHT": height,
    }


def apply_image_layout(
    node: Mapping[str, Any],
    source_size: tuple[int, int],
    canvas_size: tuple[int, int],
    settings: ImageLayoutSettings,
) -> Mapping[str, Any]:
    """Return a deep copy of node with only X/Y/WIDTH/HEIGHT changed."""
    updated = copy.deepcopy(node)
    layout = compute_image_layout(
        source_size[0],
        source_size[1],
        canvas_size[0],
        canvas_size[1],
        settings,
    )
    for key, value in layout.items():
        updated[key] = value
    return updated


def layout_summary(layout: Mapping[str, int], settings: ImageLayoutSettings) -> str:
    """Return a short human-readable summary for a computed layout."""
    labels = {
        MODE_ORIGINAL: "Original",
        MODE_FIT: "Fit",
        MODE_FILL: "Fill",
        MODE_STRETCH: "Stretch",
        MODE_CUSTOM: "Custom",
    }
    align = {
        ("left", "top"): "top left",
        ("center", "top"): "top centered",
        ("right", "top"): "top right",
        ("left", "center"): "left centered",
        ("center", "center"): "centered",
        ("right", "center"): "right centered",
        ("left", "bottom"): "bottom left",
        ("center", "bottom"): "bottom centered",
        ("right", "bottom"): "bottom right",
    }.get((settings.align_x, settings.align_y), "aligned")
    return (
        f"{labels[settings.mode]} · {int(layout['WIDTH'])}×{int(layout['HEIGHT'])} "
        f"at {int(layout['X'])},{int(layout['Y'])} · {align}"
    )


def infer_layout_mode(
    source_size: tuple[int, int],
    canvas_size: tuple[int, int],
    node_geometry: Mapping[str, Any],
) -> str:
    """Infer the closest layout mode from existing geometry."""
    width = int(node_geometry.get("WIDTH", 0) or 0)
    height = int(node_geometry.get("HEIGHT", 0) or 0)
    source_width, source_height = source_size
    canvas_width, canvas_height = canvas_size
    if (width, height) == (source_width, source_height):
        return MODE_ORIGINAL
    if (width, height) == (canvas_width, canvas_height):
        return MODE_STRETCH
    if source_width <= 0 or source_height <= 0:
        return MODE_CUSTOM
    source_ratio = source_width / source_height
    target_ratio = width / height if height else 0
    if not math.isclose(source_ratio, target_ratio, rel_tol=0.02):
        return MODE_CUSTOM
    fits = width <= canvas_width and height <= canvas_height
    covers = width >= canvas_width and height >= canvas_height
    if fits:
        return MODE_FIT
    if covers:
        return MODE_FILL
    return MODE_CUSTOM


def render_image_layout_preview(
    source_path: str | Path,
    output_path: str | Path,
    *,
    canvas_size: tuple[int, int],
    layout: Mapping[str, int],
    checker_size: int = 16,
) -> Path:
    """Render a checkerboard PNG preview of one laid-out static image."""
    canvas_width = _positive_dimension(canvas_size[0], "canvas_width")
    canvas_height = _positive_dimension(canvas_size[1], "canvas_height")
    width = _positive_dimension(layout["WIDTH"], "WIDTH")
    height = _positive_dimension(layout["HEIGHT"], "HEIGHT")
    x = int(layout["X"])
    y = int(layout["Y"])

    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    checker = Image.new("RGBA", (canvas_width, canvas_height), (224, 224, 224, 255))
    draw = ImageDraw.Draw(checker)
    step = max(2, int(checker_size))
    for top in range(0, canvas_height, step):
        for left in range(0, canvas_width, step):
            if (left // step + top // step) % 2:
                draw.rectangle(
                    (left, top, left + step - 1, top + step - 1),
                    fill=(188, 188, 188, 255),
                )

    with Image.open(source_path) as source:
        image = source.convert("RGBA").resize((width, height), Image.Resampling.LANCZOS)
        checker.alpha_composite(image, (x, y))
    checker.save(output, "PNG")
    return output
