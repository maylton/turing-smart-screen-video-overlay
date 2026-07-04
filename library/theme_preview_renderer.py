# SPDX-License-Identifier: GPL-3.0-or-later
"""Renderer used by the main app Overview animated theme preview.

This renderer is intentionally independent from the live monitor process.  It
builds a faithful-enough app preview by compositing a video/static background
with theme overlays and deterministic mock sensor values.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

from PIL import Image, ImageDraw, ImageFont

from library.theme_preview_mock_data import (
    build_mock_preview_context,
    numeric_percent,
    value_for_path,
)

DISPLAY_SIZES = {
    '0.96"': (80, 160),
    '2.1"': (480, 480),
    '2.8"': (480, 480),
    '3.5"': (320, 480),
    '4.6"': (320, 960),
    '5"': (480, 800),
    '5.2"': (720, 1280),
    '8"': (800, 1280),
    '8.8"': (480, 1920),
    '9.2"': (480, 1920),
    '12.3"': (720, 1920),
}


def load_theme_document(theme_yaml: Path) -> Mapping[str, Any]:
    """Load a theme YAML file without preserving comments."""
    try:
        import ruamel.yaml

        yaml = ruamel.yaml.YAML(typ="safe")
        with theme_yaml.open("r", encoding="utf-8") as stream:
            document = yaml.load(stream) or {}
        return document if isinstance(document, Mapping) else {}
    except Exception:
        return {}


def theme_canvas_size(theme_doc: Mapping[str, Any]) -> tuple[int, int]:
    display = theme_doc.get("display", {}) if isinstance(theme_doc, Mapping) else {}
    size = str(display.get("DISPLAY_SIZE", '2.1"')) if isinstance(display, Mapping) else '2.1"'
    return DISPLAY_SIZES.get(size, (480, 480))


def build_preview_context(theme_doc: Mapping[str, Any]) -> dict[str, Any]:
    return build_mock_preview_context(theme_doc)


def render_theme_preview_frame(
    *,
    root: Path,
    theme_dir: Path,
    theme_doc: Mapping[str, Any],
    background: Image.Image,
    context: Mapping[str, Any] | None = None,
    preview_size: tuple[int, int] = (360, 360),
) -> Image.Image:
    """Render one Overview preview frame with video/static background + overlays."""
    context = context or build_preview_context(theme_doc)
    canvas_width, canvas_height = theme_canvas_size(theme_doc)
    frame = _cover_canvas(background, canvas_width, canvas_height)

    # Static assets normally appear above the video background.
    draw_static_images(frame, theme_dir, theme_doc)
    draw_static_text(frame, root, theme_dir, theme_doc, context)

    # Then draw a mock snapshot for dynamic/monitor widgets that do not exist in
    # static_text/static_images but still have X/Y/WIDTH/HEIGHT geometry.
    draw_dynamic_widgets(frame, root, theme_dir, theme_doc, context)

    frame.thumbnail(preview_size, Image.Resampling.LANCZOS)
    return frame


def _cover_canvas(background: Image.Image, width: int, height: int) -> Image.Image:
    image = background.convert("RGBA")
    if image.size != (width, height):
        scale = max(width / max(1, image.width), height / max(1, image.height))
        resized = image.resize(
            (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
            Image.Resampling.LANCZOS,
        )
        left = max(0, (resized.width - width) // 2)
        top = max(0, (resized.height - height) // 2)
        image = resized.crop((left, top, left + width, top + height))
    return image


def _truthy(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "enabled", "show"}
    return bool(value)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if math.isfinite(number):
            return number
    except (TypeError, ValueError):
        pass
    return default


def _color(value: Any, default=(255, 255, 255, 255)) -> tuple[int, int, int, int]:
    if isinstance(value, str):
        raw = value.strip()
        parts = [part.strip() for part in raw.split(",")]
        if len(parts) in (3, 4):
            try:
                values = [int(float(part)) for part in parts]
            except ValueError:
                values = list(default)
        elif raw.startswith("#") and len(raw) in {7, 9}:
            try:
                values = [int(raw[i:i + 2], 16) for i in range(1, len(raw), 2)]
            except ValueError:
                values = list(default)
        else:
            values = list(default)
    elif isinstance(value, (list, tuple)):
        values = [int(float(component)) for component in value[:4]]
    else:
        values = list(default)

    while len(values) < 4:
        values.append(255)
    return tuple(max(0, min(255, component)) for component in values[:4])


def _unquote(value: Any) -> str:
    return str(value or "").strip().strip('"\'')


def _resolve_theme_asset(theme_dir: Path, raw_path: Any) -> Path | None:
    raw = _unquote(raw_path)
    if not raw:
        return None
    path = Path(os.path.expanduser(raw))
    candidates = [path] if path.is_absolute() else [theme_dir / raw.lstrip("./")]
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def _paste_clipped(base: Image.Image, overlay: Image.Image, x: int, y: int) -> None:
    overlay = overlay.convert("RGBA")
    left = max(0, x)
    top = max(0, y)
    right = min(base.width, x + overlay.width)
    bottom = min(base.height, y + overlay.height)
    if right <= left or bottom <= top:
        return
    crop_left = left - x
    crop_top = top - y
    crop = overlay.crop((crop_left, crop_top, crop_left + right - left, crop_top + bottom - top))
    base.alpha_composite(crop, (left, top))


def _font_path(root: Path, theme_dir: Path, raw_font: Any) -> Path | None:
    raw = _unquote(raw_font) or "roboto-mono/RobotoMono-Regular.ttf"
    candidates = [
        theme_dir / raw,
        root / raw,
        root / "res" / "fonts" / raw,
        root / "res" / "fonts" / "roboto-mono" / "RobotoMono-Regular.ttf",
    ]
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def _load_font(root: Path, theme_dir: Path, raw_font: Any, size: int) -> ImageFont.ImageFont:
    candidate = _font_path(root, theme_dir, raw_font)
    if candidate is not None:
        try:
            return ImageFont.truetype(str(candidate), max(1, size))
        except OSError:
            pass
    return ImageFont.load_default()


def _iter_nodes(node: Any, path: tuple[Any, ...] = ()) -> Iterable[tuple[tuple[Any, ...], Mapping[str, Any]]]:
    if isinstance(node, Mapping):
        if any(key in node for key in ("X", "Y", "WIDTH", "HEIGHT", "TEXT", "FORMAT", "PATH", "SHOW", "INTERVAL")):
            yield path, node
        for key, value in node.items():
            if isinstance(value, (Mapping, list)):
                yield from _iter_nodes(value, path + (key,))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            if isinstance(value, (Mapping, list)):
                yield from _iter_nodes(value, path + (index,))


def _node_visible(node: Mapping[str, Any]) -> bool:
    if "SHOW" in node and not _truthy(node.get("SHOW"), True):
        return False
    if "ENABLED" in node and not _truthy(node.get("ENABLED"), True):
        return False
    if "INTERVAL" in node and _safe_float(node.get("INTERVAL"), 1.0) <= 0:
        return False
    return True


def draw_static_images(frame: Image.Image, theme_dir: Path, theme_doc: Mapping[str, Any]) -> None:
    images = theme_doc.get("static_images", {}) if isinstance(theme_doc, Mapping) else {}
    if not isinstance(images, Mapping):
        return
    for item in images.values():
        if not isinstance(item, Mapping) or not _node_visible(item):
            continue
        draw_image_node(frame, theme_dir, item)


def draw_image_node(frame: Image.Image, theme_dir: Path, node: Mapping[str, Any]) -> None:
    source = _resolve_theme_asset(theme_dir, node.get("PATH"))
    if source is None:
        return
    try:
        overlay = Image.open(source).convert("RGBA")
    except OSError:
        return
    width = _safe_int(node.get("WIDTH"), overlay.width)
    height = _safe_int(node.get("HEIGHT"), overlay.height)
    if width > 0 and height > 0 and (width, height) != overlay.size:
        overlay = overlay.resize((width, height), Image.Resampling.LANCZOS)
    _paste_clipped(frame, overlay, _safe_int(node.get("X")), _safe_int(node.get("Y")))


def draw_static_text(
    frame: Image.Image,
    root: Path,
    theme_dir: Path,
    theme_doc: Mapping[str, Any],
    context: Mapping[str, Any],
) -> None:
    texts = theme_doc.get("static_text", {}) if isinstance(theme_doc, Mapping) else {}
    if not isinstance(texts, Mapping):
        return
    for key, item in texts.items():
        if not isinstance(item, Mapping) or not _node_visible(item):
            continue
        draw_text_node(frame, root, theme_dir, item, context, path=("static_text", key))


def draw_text_node(
    frame: Image.Image,
    root: Path,
    theme_dir: Path,
    node: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    path: tuple[Any, ...],
    fallback_label: str | None = None,
) -> None:
    text = _format_node_text(path, node, context, fallback_label=fallback_label)
    if not text:
        return

    x = _safe_int(node.get("X"))
    y = _safe_int(node.get("Y"))
    width = max(1, _safe_int(node.get("WIDTH"), 160))
    height = max(1, _safe_int(node.get("HEIGHT"), _safe_int(node.get("FONT_SIZE"), 16) + 8))
    font_size = max(1, _safe_int(node.get("FONT_SIZE"), 16))
    font = _load_font(root, theme_dir, node.get("FONT"), font_size)

    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    _draw_node_background(draw, layer, theme_dir, node, width, height)

    fill = _color(node.get("FONT_COLOR"), (255, 255, 255, 255))
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=2)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    align = str(node.get("ALIGN", "left")).lower()
    anchor = str(node.get("ANCHOR", "lt")).lower()

    tx = 0
    if align in {"center", "middle"}:
        tx = max(0, (width - text_width) // 2)
    elif align in {"right", "end"}:
        tx = max(0, width - text_width)

    ty = 0
    if "m" in anchor or "c" in anchor:
        ty = max(0, (height - text_height) // 2)
    elif "b" in anchor:
        ty = max(0, height - text_height)

    draw.multiline_text(
        (tx, ty),
        text,
        font=font,
        fill=fill,
        spacing=2,
        align=align if align in {"left", "center", "right"} else "left",
    )
    _paste_clipped(frame, layer, x, y)


def _draw_node_background(
    draw: ImageDraw.ImageDraw,
    layer: Image.Image,
    theme_dir: Path,
    node: Mapping[str, Any],
    width: int,
    height: int,
) -> None:
    background_image = _resolve_theme_asset(theme_dir, node.get("BACKGROUND_IMAGE"))
    if background_image is not None:
        try:
            bg = Image.open(background_image).convert("RGBA").resize((width, height), Image.Resampling.LANCZOS)
            layer.alpha_composite(bg, (0, 0))
            return
        except OSError:
            pass
    if "BACKGROUND_COLOR" in node:
        draw.rectangle((0, 0, width, height), fill=_color(node.get("BACKGROUND_COLOR"), (0, 0, 0, 0)))


def _format_node_text(
    path: tuple[Any, ...],
    node: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    fallback_label: str | None = None,
) -> str:
    raw = node.get("TEXT")
    if raw is None:
        raw = node.get("FORMAT")
    value = value_for_path(path, node, context)
    if raw is None or str(raw).strip() == "":
        label = fallback_label or _human_label(path)
        return f"{label}: {value}"

    text = str(raw)
    replacements = {
        "{value}": str(value),
        "{VALUE}": str(value),
        "{time}": str(context.get("TIME", "22:48")),
        "{TIME}": str(context.get("TIME", "22:48")),
        "{date}": str(context.get("DATE", "Fri 04 Jul")),
        "{DATE}": str(context.get("DATE", "Fri 04 Jul")),
    }
    for key, replacement in replacements.items():
        text = text.replace(key, replacement)
    return text


def _human_label(path: tuple[Any, ...]) -> str:
    parts = [str(part) for part in path if not isinstance(part, int)]
    if not parts:
        return "Value"
    label = parts[-1].replace("_", " ").replace("-", " ").strip()
    return label.title() or "Value"


def draw_dynamic_widgets(
    frame: Image.Image,
    root: Path,
    theme_dir: Path,
    theme_doc: Mapping[str, Any],
    context: Mapping[str, Any],
) -> None:
    for path, node in _iter_nodes(theme_doc):
        if not path or path[0] in {"display", "video", "static_text", "static_images"}:
            continue
        if not _node_visible(node):
            continue
        if "PATH" in node and ("X" in node or "Y" in node):
            draw_image_node(frame, theme_dir, node)
            continue
        if not {"X", "Y"}.issubset(node.keys()):
            continue
        draw_dynamic_node(frame, root, theme_dir, path, node, context)


def draw_dynamic_node(
    frame: Image.Image,
    root: Path,
    theme_dir: Path,
    path: tuple[Any, ...],
    node: Mapping[str, Any],
    context: Mapping[str, Any],
) -> None:
    width = max(1, _safe_int(node.get("WIDTH"), 120))
    height = max(1, _safe_int(node.get("HEIGHT"), 34))
    x = _safe_int(node.get("X"))
    y = _safe_int(node.get("Y"))
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    _draw_node_background(draw, layer, theme_dir, node, width, height)

    value = value_for_path(path, node, context)
    percent = numeric_percent(value)
    if _looks_like_chart(path, node):
        draw_chart_node(draw, node, width, height, percent)
    elif _looks_like_bar(node):
        draw_bar_node(draw, node, width, height, percent)
    else:
        draw_metric_text_node(draw, root, theme_dir, path, node, context, width, height)

    _paste_clipped(frame, layer, x, y)


def _looks_like_bar(node: Mapping[str, Any]) -> bool:
    return any(key in node for key in ("BAR_COLOR", "BAR_BACKGROUND_COLOR", "DRAW_BAR_BACKGROUND", "MIN_VALUE", "MAX_VALUE"))


def _looks_like_chart(path: tuple[Any, ...], node: Mapping[str, Any]) -> bool:
    label = "_".join(str(part).upper() for part in path)
    return "GRAPH" in label or "HISTORY" in label or "LINE_COLOR" in node or "HISTORY_SIZE" in node


def draw_bar_node(draw: ImageDraw.ImageDraw, node: Mapping[str, Any], width: int, height: int, percent: int) -> None:
    radius = min(height // 2, _safe_int(node.get("RADIUS"), 4))
    background = _color(node.get("BAR_BACKGROUND_COLOR"), (255, 255, 255, 55))
    foreground = _color(node.get("BAR_COLOR"), _color(node.get("FONT_COLOR"), (255, 255, 255, 230)))
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=radius, fill=background)
    fill_width = max(1, round((width - 1) * percent / 100))
    draw.rounded_rectangle((0, 0, fill_width, height - 1), radius=radius, fill=foreground)


def draw_chart_node(draw: ImageDraw.ImageDraw, node: Mapping[str, Any], width: int, height: int, percent: int) -> None:
    color = _color(node.get("LINE_COLOR"), _color(node.get("FONT_COLOR"), (255, 255, 255, 230)))
    axis = _color(node.get("AXIS_COLOR"), (255, 255, 255, 70))
    draw.line((0, height - 1, width, height - 1), fill=axis, width=1)
    points = []
    for index in range(12):
        x = round(index * (width - 1) / 11)
        wave = math.sin(index / 11 * math.pi * 2)
        sample = max(4, min(96, percent + wave * 18 - 8))
        y = round((height - 1) * (1 - sample / 100))
        points.append((x, y))
    if len(points) > 1:
        draw.line(points, fill=color, width=max(1, _safe_int(node.get("LINE_WIDTH"), 2)))


def draw_metric_text_node(
    draw: ImageDraw.ImageDraw,
    root: Path,
    theme_dir: Path,
    path: tuple[Any, ...],
    node: Mapping[str, Any],
    context: Mapping[str, Any],
    width: int,
    height: int,
) -> None:
    font_size = max(1, _safe_int(node.get("FONT_SIZE"), min(18, max(9, height - 6))))
    font = _load_font(root, theme_dir, node.get("FONT"), font_size)
    color = _color(node.get("FONT_COLOR"), (255, 255, 255, 255))
    text = _format_node_text(path, node, context)
    bbox = draw.textbbox((0, 0), text, font=font)
    y = max(0, (height - (bbox[3] - bbox[1])) // 2)
    draw.text((0, y), text, font=font, fill=color)
