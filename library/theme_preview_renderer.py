# SPDX-License-Identifier: GPL-3.0-or-later
"""Renderer used by the main app Overview animated theme preview.

The Overview preview is generated off-screen from the real theme YAML. Keep this
renderer conservative: the video frame is the background for video-overlay
themes, and YAML overlay nodes are composited on top with deterministic mock
values.

Text rendering intentionally mirrors library.lcd.lcd_comm.DisplayText so the
Overview uses the same X/Y/WIDTH/HEIGHT/ANCHOR/EFFECTS semantics as the Theme
Editor/live runtime instead of a parallel approximation.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

from PIL import Image, ImageDraw, ImageFilter, ImageFont

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

DATE_TIME_FORMAT_PRESETS = {"short", "medium", "long", "full"}


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
    video_overlay = _video_overlay_enabled(theme_doc)

    draw_static_images(
        frame,
        theme_dir,
        theme_doc,
        canvas_size=(canvas_width, canvas_height),
        video_overlay=video_overlay,
    )
    draw_static_text(
        frame,
        root,
        theme_dir,
        theme_doc,
        context,
        transparent_background=video_overlay,
    )
    draw_dynamic_widgets(
        frame,
        root,
        theme_dir,
        theme_doc,
        context,
        transparent_background=video_overlay,
    )

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
        return value.strip().strip('"\'').lower() in {
            "1",
            "true",
            "yes",
            "on",
            "enabled",
            "show",
        }
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


def _video_overlay_enabled(theme_doc: Mapping[str, Any]) -> bool:
    video = theme_doc.get("video", {}) if isinstance(theme_doc, Mapping) else {}
    if not isinstance(video, Mapping):
        return False
    return _truthy(video.get("ENABLED"), False) and _truthy(video.get("OVERLAY"), True)


def draw_static_images(
    frame: Image.Image,
    theme_dir: Path,
    theme_doc: Mapping[str, Any],
    *,
    canvas_size: tuple[int, int],
    video_overlay: bool,
) -> None:
    images = theme_doc.get("static_images", {}) if isinstance(theme_doc, Mapping) else {}
    if not isinstance(images, Mapping):
        return
    for key, item in images.items():
        if not isinstance(item, Mapping) or not _node_visible(item):
            continue
        if video_overlay and _is_full_canvas_background(("static_images", key), item, canvas_size):
            continue
        draw_image_node(frame, theme_dir, item)


def _is_full_canvas_background(
    path: tuple[Any, ...],
    node: Mapping[str, Any],
    canvas_size: tuple[int, int],
) -> bool:
    canvas_width, canvas_height = canvas_size
    x = _safe_int(node.get("X"), 0)
    y = _safe_int(node.get("Y"), 0)
    width = _safe_int(node.get("WIDTH"), 0)
    height = _safe_int(node.get("HEIGHT"), 0)
    label = f"{'_'.join(str(part) for part in path)} {_unquote(node.get('PATH'))}".lower()
    fills_canvas = (
        x <= 1
        and y <= 1
        and width >= canvas_width * 0.95
        and height >= canvas_height * 0.95
    )
    return fills_canvas and "background" in label


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
    *,
    transparent_background: bool = False,
) -> None:
    texts = theme_doc.get("static_text", {}) if isinstance(theme_doc, Mapping) else {}
    if not isinstance(texts, Mapping):
        return
    for key, item in texts.items():
        if not isinstance(item, Mapping) or not _node_visible(item):
            continue
        draw_text_node(
            frame,
            root,
            theme_dir,
            item,
            context,
            path=("static_text", key),
            transparent_background=transparent_background,
        )


def draw_text_node(
    frame: Image.Image,
    root: Path,
    theme_dir: Path,
    node: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    path: tuple[Any, ...],
    fallback_label: str | None = None,
    transparent_background: bool = False,
) -> None:
    text = _format_node_text(path, node, context, fallback_label=fallback_label)
    if not text:
        return

    x = _safe_int(node.get("X"))
    y = _safe_int(node.get("Y"))
    width = _safe_int(node.get("WIDTH"), 0)
    height = _safe_int(node.get("HEIGHT"), 0)
    font_size = max(1, _safe_int(node.get("FONT_SIZE"), 16))
    font = _load_font(root, theme_dir, node.get("FONT"), font_size)
    font_color = _color(node.get("FONT_COLOR"), (255, 255, 255, 255))
    align = str(node.get("ALIGN", "left")).lower()
    anchor = str(node.get("ANCHOR", "lt")).lower() or "lt"
    if len(anchor) != 2:
        anchor = "lt"

    _draw_lcd_text_semantics(
        frame=frame,
        theme_dir=theme_dir,
        node=node,
        text=text,
        x=x,
        y=y,
        width=width,
        height=height,
        font=font,
        font_size=font_size,
        font_color=font_color,
        align=align,
        anchor=anchor,
        transparent_background=transparent_background,
    )


def _draw_lcd_text_semantics(
    *,
    frame: Image.Image,
    theme_dir: Path,
    node: Mapping[str, Any],
    text: str,
    x: int,
    y: int,
    width: int,
    height: int,
    font: ImageFont.ImageFont,
    font_size: int,
    font_color: tuple[int, int, int, int],
    align: str,
    anchor: str,
    transparent_background: bool,
) -> None:
    """Mirror library.lcd.lcd_comm.DisplayText geometry and crop semantics."""
    if width > 0 and height == 0:
        height = font_size

    text_image = _make_text_canvas(
        frame=frame,
        theme_dir=theme_dir,
        node=node,
        transparent_background=transparent_background,
    )
    draw = ImageDraw.Draw(text_image)

    try:
        if width == 0 or height == 0:
            left, top, right, bottom = draw.textbbox(
                (x, y),
                text,
                font=font,
                align=align,
                anchor=anchor,
            )
            left, top = math.floor(left), math.floor(top)
            right, bottom = math.ceil(right), math.ceil(bottom)
            draw_x, draw_y = x, y
        else:
            left, top, right, bottom = x, y, x + width, y + height
            if anchor.startswith("m"):
                draw_x = int((right + left) / 2)
            elif anchor.startswith("r"):
                draw_x = right
            else:
                draw_x = left

            if anchor.endswith("m"):
                draw_y = int((bottom + top) / 2)
            elif anchor.endswith("b"):
                draw_y = bottom
            else:
                draw_y = top
    except (TypeError, ValueError):
        anchor = "lt"
        if width == 0 or height == 0:
            left, top, right, bottom = draw.textbbox(
                (x, y),
                text,
                font=font,
                align=align,
                anchor=anchor,
            )
            left, top = math.floor(left), math.floor(top)
            right, bottom = math.ceil(right), math.ceil(bottom)
            draw_x, draw_y = x, y
        else:
            left, top, right, bottom = x, y, x + width, y + height
            draw_x, draw_y = x, y

    effects = node.get("EFFECTS", {})
    text_image = _draw_preview_text_effects(
        text_image,
        (draw_x, draw_y),
        text,
        font,
        font_color,
        align,
        anchor,
        effects,
    )

    effect_padding = _text_effect_padding(effects)
    left -= effect_padding
    top -= effect_padding
    right += effect_padding
    bottom += effect_padding

    left = max(left, 0)
    top = max(top, 0)
    right = min(right, frame.width)
    bottom = min(bottom, frame.height)
    if right <= left or bottom <= top:
        return

    crop = text_image.crop((left, top, right, bottom))
    frame.alpha_composite(crop, (left, top))


def _make_text_canvas(
    *,
    frame: Image.Image,
    theme_dir: Path,
    node: Mapping[str, Any],
    transparent_background: bool,
) -> Image.Image:
    if transparent_background:
        return Image.new("RGBA", frame.size, (0, 0, 0, 0))

    background_image = _resolve_theme_asset(theme_dir, node.get("BACKGROUND_IMAGE"))
    if background_image is not None:
        try:
            return _cover_canvas(Image.open(background_image), frame.width, frame.height)
        except OSError:
            pass

    color = _color(node.get("BACKGROUND_COLOR"), (0, 0, 0, 0))
    return Image.new("RGBA", frame.size, color)


def _effect_enabled(config: Any) -> bool:
    return isinstance(config, Mapping) and bool(config.get("ENABLED", False))


def _draw_preview_text_effects(
    image: Image.Image,
    position: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    font_color: tuple[int, int, int, int],
    align: str,
    anchor: str,
    effects: Any,
) -> Image.Image:
    effects = effects if isinstance(effects, Mapping) else {}
    canvas = image.convert("RGBA")
    width, height = canvas.size

    shadow = effects.get("SHADOW", {})
    if _effect_enabled(shadow):
        dx = int(shadow.get("OFFSET_X", 3))
        dy = int(shadow.get("OFFSET_Y", 3))
        blur = max(0.0, float(shadow.get("BLUR_RADIUS", 4)))
        mask = Image.new("L", (width, height), 0)
        ImageDraw.Draw(mask).text(
            (position[0] + dx, position[1] + dy),
            text,
            font=font,
            fill=255,
            align=align,
            anchor=anchor,
        )
        if blur:
            mask = mask.filter(ImageFilter.GaussianBlur(blur))
        color = _color(shadow.get("COLOR"), (0, 0, 0, 180))
        layer = Image.new("RGBA", (width, height), color)
        layer.putalpha(mask.point(lambda value: value * color[3] // 255))
        canvas = Image.alpha_composite(canvas, layer)

    glow = effects.get("GLOW", {})
    if _effect_enabled(glow):
        blur = max(0.0, float(glow.get("BLUR_RADIUS", 8)))
        intensity = max(1, min(4, int(glow.get("INTENSITY", 1))))
        mask = Image.new("L", (width, height), 0)
        ImageDraw.Draw(mask).text(
            position,
            text,
            font=font,
            fill=255,
            align=align,
            anchor=anchor,
        )
        if blur:
            mask = mask.filter(ImageFilter.GaussianBlur(blur))
        color = _color(glow.get("COLOR"), (255, 255, 255, 160))
        for _ in range(intensity):
            layer = Image.new("RGBA", (width, height), color)
            layer.putalpha(mask.point(lambda value: value * color[3] // 255))
            canvas = Image.alpha_composite(canvas, layer)

    outline = effects.get("OUTLINE", {})
    stroke_width = 0
    stroke_fill = None
    if _effect_enabled(outline):
        stroke_width = max(0, min(20, int(outline.get("WIDTH", 2))))
        stroke_fill = _color(outline.get("COLOR"), (0, 0, 0, 255))

    ImageDraw.Draw(canvas).text(
        position,
        text,
        font=font,
        fill=font_color,
        align=align,
        anchor=anchor,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )
    return canvas


def _text_effect_padding(effects: Any) -> int:
    effects = effects if isinstance(effects, Mapping) else {}
    padding = 0

    shadow = effects.get("SHADOW", {})
    if isinstance(shadow, Mapping) and shadow.get("ENABLED", False):
        padding = max(
            padding,
            abs(int(shadow.get("OFFSET_X", 3)))
            + abs(int(shadow.get("OFFSET_Y", 3)))
            + int(float(shadow.get("BLUR_RADIUS", 4))) * 2,
        )

    glow = effects.get("GLOW", {})
    if isinstance(glow, Mapping) and glow.get("ENABLED", False):
        padding = max(padding, int(float(glow.get("BLUR_RADIUS", 8))) * 2)

    outline = effects.get("OUTLINE", {})
    if isinstance(outline, Mapping) and outline.get("ENABLED", False):
        padding = max(padding, int(outline.get("WIDTH", 2)) + 2)

    return max(0, min(80, padding))


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
        if _is_stats_text_path(path):
            return _format_stats_text_value(path, node, value)
        if _looks_like_time_path(path) or _looks_like_date_path(path):
            return str(value)
        label = fallback_label or _human_label(path)
        return f"{label}: {value}"

    text = str(raw)
    preset_text = _format_date_time_preset(path, text, context)
    if preset_text is not None:
        return preset_text

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


def _format_date_time_preset(path: tuple[Any, ...], text: str, context: Mapping[str, Any]) -> str | None:
    preset = text.strip().strip('"\'').lower()
    if preset not in DATE_TIME_FORMAT_PRESETS:
        return None
    if _looks_like_time_path(path):
        return str(context.get("TIME", "22:48"))
    if _looks_like_date_path(path):
        return str(context.get("DATE", "Fri 04 Jul"))
    return None


def _looks_like_time_path(path: tuple[Any, ...]) -> bool:
    label = "_".join(str(part).upper() for part in path if not isinstance(part, int))
    return any(token in label for token in ("CLOCK", "TIME", "HOUR", "MINUTE"))


def _looks_like_date_path(path: tuple[Any, ...]) -> bool:
    label = "_".join(str(part).upper() for part in path if not isinstance(part, int))
    return any(token in label for token in ("DATE", "DAY", "MONTH", "YEAR"))


def _human_label(path: tuple[Any, ...]) -> str:
    parts = [str(part) for part in path if not isinstance(part, int)]
    if not parts:
        return "Value"
    label = parts[-1].replace("_", " ").replace("-", " ").strip()
    return label.title() or "Value"


def _path_label(path: tuple[Any, ...]) -> str:
    return "_".join(str(part).upper() for part in path if not isinstance(part, int))


def _is_stats_text_path(path: tuple[Any, ...]) -> bool:
    parts = [str(part).upper() for part in path if not isinstance(part, int)]
    return len(parts) >= 3 and parts[0] == "STATS" and parts[-1] == "TEXT"


def _format_compact_number(value: Any, *, decimals: int = 0) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)

    if decimals > 0:
        return f"{number:.{decimals}f}"

    return str(int(round(number)))


def _format_stats_text_value(
    path: tuple[Any, ...],
    node: Mapping[str, Any],
    value: Any,
) -> str:
    """Format STATS leaf TEXT widgets like the runtime stats callbacks.

    The generic Overview renderer walks YAML nodes directly. Runtime stats do
    not render STATS.*.*.TEXT as "Text: value"; they render the metric value
    with the proper unit, for example 67°C, 50%, or 2.40 GHz.
    """
    label = _path_label(path)
    show_unit = _truthy(node.get("SHOW_UNIT"), True)

    if "TEMP" in label or "TEMPERATURE" in label:
        text = _format_compact_number(value)
        return f"{text}°C" if show_unit else text

    if "FREQUENCY" in label or "FREQ" in label:
        text = _format_compact_number(value, decimals=2)
        return f"{text} GHz" if show_unit else text

    if "FPS" in label:
        return _format_compact_number(value)

    percent_tokens = (
        "PERCENT",
        "PERCENTAGE",
        "USAGE",
        "LOAD",
        "FAN",
        "BATTERY",
        "VRAM",
        "RAM",
        "MEMORY_PERCENT",
        "DISK",
        "STORAGE",
    )
    if any(token in label for token in percent_tokens):
        text = _format_compact_number(value)
        return f"{text}%" if show_unit else text

    if "MEMORY_USED" in label or "MEMORY_TOTAL" in label or "GPU_MEMORY_USED" in label or "GPU_MEMORY_TOTAL" in label:
        text = _format_compact_number(value)
        return f"{text} M" if show_unit else text

    return str(value)


def draw_dynamic_widgets(
    frame: Image.Image,
    root: Path,
    theme_dir: Path,
    theme_doc: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    transparent_background: bool = False,
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
        draw_dynamic_node(
            frame,
            root,
            theme_dir,
            path,
            node,
            context,
            transparent_background=transparent_background,
        )


def draw_dynamic_node(
    frame: Image.Image,
    root: Path,
    theme_dir: Path,
    path: tuple[Any, ...],
    node: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    transparent_background: bool = False,
) -> None:
    if not _looks_like_chart(path, node) and not _looks_like_bar(node):
        draw_text_node(
            frame,
            root,
            theme_dir,
            node,
            context,
            path=path,
            transparent_background=transparent_background,
        )
        return

    width = max(1, _safe_int(node.get("WIDTH"), 120))
    height = max(1, _safe_int(node.get("HEIGHT"), 34))
    x = _safe_int(node.get("X"))
    y = _safe_int(node.get("Y"))
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    if not transparent_background:
        _draw_node_background(draw, layer, theme_dir, node, width, height)

    value = value_for_path(path, node, context)
    percent = numeric_percent(value)
    if _looks_like_chart(path, node):
        draw_chart_node(draw, node, width, height, percent)
    else:
        draw_bar_node(draw, node, width, height, percent)

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
