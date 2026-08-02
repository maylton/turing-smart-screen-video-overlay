# SPDX-License-Identifier: GPL-3.0-or-later
"""Persistence model for the first visual HTML theme editor."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, Mapping

from library.html_theme_authoring import discover_overlay_candidates
from library.html_theme_components import (
    WIDGET_RUNTIME_FILENAME,
    generated_widget_ids,
    get_html_widget_component,
    render_widget_runtime_script,
    update_generated_widget_block,
)
from library.theme_engine import ThemeManifest, ThemeValidationError


EDITOR_METADATA_FILENAME = ".html-theme-editor.json"
EDITOR_STYLESHEET_FILENAME = "theme-editor-overrides.css"
EDITOR_SCHEMA_VERSION = 4
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_ELEMENT_KINDS = {"text", "bar"}
_GRADIENT_DIRECTIONS = {
    "horizontal": "90deg",
    "vertical": "180deg",
    "diagonal": "135deg",
}


@dataclass(frozen=True)
class HtmlVisualElementStyle:
    element_id: str
    x: int
    y: int
    width: int
    height: int
    font_size: int
    color: str
    font_weight: int = 0
    text_align: str = "inherit"
    opacity: int = 100
    z_index: int = 1000
    visible: bool = True
    component_type: str = ""
    element_kind: str = "text"
    effects_managed: bool = False
    gradient_enabled: bool = False
    gradient_start_color: str = "#ffffff"
    gradient_end_color: str = "#66e0ff"
    gradient_direction: str = "horizontal"
    outline_width: int = 0
    outline_color: str = "#000000"
    glow_radius: int = 0
    glow_color: str = "#ffffff"

    def validated(self, manifest: ThemeManifest) -> "HtmlVisualElementStyle":
        element_id = str(self.element_id).strip()
        if not element_id:
            raise ThemeValidationError("visual element id cannot be empty")
        values = {
            "x": int(self.x),
            "y": int(self.y),
            "width": int(self.width),
            "height": int(self.height),
            "font size": int(self.font_size),
            "font weight": int(self.font_weight),
            "opacity": int(self.opacity),
            "z index": int(self.z_index),
            "outline width": int(self.outline_width),
            "glow radius": int(self.glow_radius),
        }
        if values["x"] < 0 or values["y"] < 0:
            raise ThemeValidationError(f"#{element_id} coordinates cannot be negative")
        if values["width"] <= 0 or values["height"] <= 0:
            raise ThemeValidationError(f"#{element_id} dimensions must be positive")
        if values["x"] + values["width"] > manifest.width:
            raise ThemeValidationError(f"#{element_id} exceeds the display width")
        if values["y"] + values["height"] > manifest.height:
            raise ThemeValidationError(f"#{element_id} exceeds the display height")
        if not 6 <= values["font size"] <= 160:
            raise ThemeValidationError(f"#{element_id} font size must be 6-160 px")
        if values["font weight"] != 0 and (
            not 100 <= values["font weight"] <= 900
            or values["font weight"] % 100 != 0
        ):
            raise ThemeValidationError(
                f"#{element_id} font weight must be inherited or 100-900 by 100"
            )
        if not 0 <= values["opacity"] <= 100:
            raise ThemeValidationError(f"#{element_id} opacity must be 0-100%")
        if not 1 <= values["z index"] <= 9999:
            raise ThemeValidationError(f"#{element_id} layer must be 1-9999")
        color = str(self.color).strip().lower()
        effect_colors = {
            "color": color,
            "gradient start color": str(self.gradient_start_color).strip().lower(),
            "gradient end color": str(self.gradient_end_color).strip().lower(),
            "outline color": str(self.outline_color).strip().lower(),
            "glow color": str(self.glow_color).strip().lower(),
        }
        for name, value in effect_colors.items():
            if not _HEX_COLOR.fullmatch(value):
                raise ThemeValidationError(
                    f"#{element_id} {name} must use the #rrggbb format"
                )
        text_align = str(self.text_align).strip().lower()
        if text_align not in {"inherit", "left", "center", "right"}:
            raise ThemeValidationError(
                f"#{element_id} text alignment is not supported"
            )
        component_type = str(self.component_type or "").strip()
        component = None
        if component_type:
            component = get_html_widget_component(component_type)
        element_kind = str(self.element_kind or "text").strip().lower()
        if component is not None:
            element_kind = component.kind
        if element_kind not in _ELEMENT_KINDS:
            raise ThemeValidationError(
                f"#{element_id} element kind is not supported"
            )
        gradient_direction = str(self.gradient_direction).strip().lower()
        if gradient_direction not in _GRADIENT_DIRECTIONS:
            raise ThemeValidationError(
                f"#{element_id} gradient direction is not supported"
            )
        if not 0 <= values["outline width"] <= 8:
            raise ThemeValidationError(
                f"#{element_id} outline width must be 0-8 px"
            )
        if not 0 <= values["glow radius"] <= 40:
            raise ThemeValidationError(
                f"#{element_id} glow radius must be 0-40 px"
            )
        return HtmlVisualElementStyle(
            element_id=element_id,
            x=values["x"],
            y=values["y"],
            width=values["width"],
            height=values["height"],
            font_size=values["font size"],
            color=effect_colors["color"],
            font_weight=values["font weight"],
            text_align=text_align,
            opacity=values["opacity"],
            z_index=values["z index"],
            visible=bool(self.visible),
            component_type=component_type,
            element_kind=element_kind,
            effects_managed=bool(self.effects_managed),
            gradient_enabled=bool(self.gradient_enabled),
            gradient_start_color=effect_colors["gradient start color"],
            gradient_end_color=effect_colors["gradient end color"],
            gradient_direction=gradient_direction,
            outline_width=values["outline width"],
            outline_color=effect_colors["outline color"],
            glow_radius=values["glow radius"],
            glow_color=effect_colors["glow color"],
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.element_id,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "fontSize": self.font_size,
            "color": self.color,
            "fontWeight": self.font_weight,
            "textAlign": self.text_align,
            "opacity": self.opacity,
            "zIndex": self.z_index,
            "visible": self.visible,
            "componentType": self.component_type,
            "elementKind": self.element_kind,
            "effectsManaged": self.effects_managed,
            "gradientEnabled": self.gradient_enabled,
            "gradientStartColor": self.gradient_start_color,
            "gradientEndColor": self.gradient_end_color,
            "gradientDirection": self.gradient_direction,
            "outlineWidth": self.outline_width,
            "outlineColor": self.outline_color,
            "glowRadius": self.glow_radius,
            "glowColor": self.glow_color,
        }


def place_visual_style(
    style: HtmlVisualElementStyle,
    *,
    x: int | None = None,
    y: int | None = None,
    display_width: int,
    display_height: int,
) -> HtmlVisualElementStyle:
    """Move a style while keeping its complete rectangle on the canvas."""
    target_x = style.x if x is None else int(x)
    target_y = style.y if y is None else int(y)
    target_x = max(0, min(target_x, max(0, display_width - style.width)))
    target_y = max(0, min(target_y, max(0, display_height - style.height)))
    return replace(
        style,
        x=target_x,
        y=target_y,
    )


def resize_visual_style(
    style: HtmlVisualElementStyle,
    *,
    x: int,
    y: int,
    width: int,
    height: int,
    display_width: int,
    display_height: int,
) -> HtmlVisualElementStyle:
    """Resize/reposition a rectangle without allowing it outside the canvas."""

    target_x = max(0, min(int(x), max(0, display_width - 1)))
    target_y = max(0, min(int(y), max(0, display_height - 1)))
    target_width = max(1, min(int(width), display_width - target_x))
    target_height = max(1, min(int(height), display_height - target_y))
    return replace(
        style,
        x=target_x,
        y=target_y,
        width=target_width,
        height=target_height,
    )


def find_visual_slot(
    styles: Iterable[HtmlVisualElementStyle],
    *,
    width: int,
    height: int,
    display_width: int,
    display_height: int,
    grid: int = 10,
) -> tuple[int, int]:
    """Find the first grid slot that does not overlap a visible element."""

    width = max(1, min(int(width), int(display_width)))
    height = max(1, min(int(height), int(display_height)))
    step = max(1, int(grid))
    occupied = [style for style in styles if style.visible]
    for y in range(0, display_height - height + 1, step):
        for x in range(0, display_width - width + 1, step):
            if all(
                x + width <= style.x
                or style.x + style.width <= x
                or y + height <= style.y
                or style.y + style.height <= y
                for style in occupied
            ):
                return x, y
    return (
        max(0, (display_width - width) // 2),
        max(0, (display_height - height) // 2),
    )


def nudge_visual_style(
    style: HtmlVisualElementStyle,
    *,
    dx: int,
    dy: int,
    display_width: int,
    display_height: int,
) -> HtmlVisualElementStyle:
    return place_visual_style(
        style,
        x=style.x + int(dx),
        y=style.y + int(dy),
        display_width=display_width,
        display_height=display_height,
    )


def align_visual_style(
    style: HtmlVisualElementStyle,
    alignment: str,
    *,
    display_width: int,
    display_height: int,
) -> HtmlVisualElementStyle:
    """Align an element to one canvas edge or center axis."""
    alignment = str(alignment).strip().lower()
    positions = {
        "left": (0, style.y),
        "horizontal-center": ((display_width - style.width) // 2, style.y),
        "right": (display_width - style.width, style.y),
        "top": (style.x, 0),
        "vertical-center": (style.x, (display_height - style.height) // 2),
        "bottom": (style.x, display_height - style.height),
    }
    if alignment not in positions:
        raise ValueError(f"unsupported visual alignment: {alignment}")
    x, y = positions[alignment]
    return place_visual_style(
        style,
        x=x,
        y=y,
        display_width=display_width,
        display_height=display_height,
    )


StyleSnapshot = tuple[HtmlVisualElementStyle, ...]


def visual_style_snapshot(
    styles: Mapping[str, HtmlVisualElementStyle] | Iterable[HtmlVisualElementStyle],
) -> StyleSnapshot:
    values = styles.values() if isinstance(styles, Mapping) else styles
    return tuple(sorted(values, key=lambda style: style.element_id))


class VisualStyleHistory:
    """Small bounded undo/redo history independent from GTK."""

    def __init__(self, limit: int = 100):
        self.limit = max(1, int(limit))
        self._undo: list[StyleSnapshot] = []
        self._redo: list[StyleSnapshot] = []

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

    def record(
        self,
        styles: Mapping[str, HtmlVisualElementStyle]
        | Iterable[HtmlVisualElementStyle],
    ) -> None:
        snapshot = visual_style_snapshot(styles)
        if self._undo and self._undo[-1] == snapshot:
            return
        self._undo.append(snapshot)
        if len(self._undo) > self.limit:
            del self._undo[0]
        self._redo.clear()

    def undo(
        self,
        current: Mapping[str, HtmlVisualElementStyle]
        | Iterable[HtmlVisualElementStyle],
    ) -> StyleSnapshot | None:
        if not self._undo:
            return None
        self._redo.append(visual_style_snapshot(current))
        return self._undo.pop()

    def redo(
        self,
        current: Mapping[str, HtmlVisualElementStyle]
        | Iterable[HtmlVisualElementStyle],
    ) -> StyleSnapshot | None:
        if not self._redo:
            return None
        self._undo.append(visual_style_snapshot(current))
        return self._redo.pop()


def _style_from_mapping(value: Mapping[str, object]) -> HtmlVisualElementStyle:
    try:
        return HtmlVisualElementStyle(
            element_id=str(value["id"]),
            x=int(value["x"]),
            y=int(value["y"]),
            width=int(value["width"]),
            height=int(value["height"]),
            font_size=int(value["fontSize"]),
            color=str(value["color"]),
            font_weight=int(value.get("fontWeight", 0)),
            text_align=str(value.get("textAlign", "inherit")),
            opacity=int(value.get("opacity", 100)),
            z_index=int(value.get("zIndex", 1000)),
            visible=bool(value.get("visible", True)),
            component_type=str(value.get("componentType", "")),
            element_kind=str(value.get("elementKind", "text")),
            effects_managed=bool(value.get("effectsManaged", False)),
            gradient_enabled=bool(value.get("gradientEnabled", False)),
            gradient_start_color=str(value.get("gradientStartColor", "#ffffff")),
            gradient_end_color=str(value.get("gradientEndColor", "#66e0ff")),
            gradient_direction=str(value.get("gradientDirection", "horizontal")),
            outline_width=int(value.get("outlineWidth", 0)),
            outline_color=str(value.get("outlineColor", "#000000")),
            glow_radius=int(value.get("glowRadius", 0)),
            glow_color=str(value.get("glowColor", "#ffffff")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ThemeValidationError(f"invalid visual editor element: {exc}") from exc


def metadata_path(manifest: ThemeManifest) -> Path:
    return manifest.root / EDITOR_METADATA_FILENAME


def stylesheet_path(manifest: ThemeManifest) -> Path:
    return manifest.root / EDITOR_STYLESHEET_FILENAME


def load_visual_styles(
    manifest: ThemeManifest,
) -> tuple[HtmlVisualElementStyle, ...]:
    path = metadata_path(manifest)
    if not path.is_file():
        return ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ThemeValidationError(f"invalid {EDITOR_METADATA_FILENAME}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ThemeValidationError(f"{EDITOR_METADATA_FILENAME} must contain an object")
    if payload.get("schemaVersion") not in {1, 2, 3, EDITOR_SCHEMA_VERSION}:
        raise ThemeValidationError("unsupported HTML visual editor schema")
    raw_elements = payload.get("elements")
    if not isinstance(raw_elements, list):
        raise ThemeValidationError("HTML visual editor elements must be an array")
    styles = tuple(
        _style_from_mapping(item).validated(manifest)
        for item in raw_elements
        if isinstance(item, Mapping)
    )
    if len(styles) != len(raw_elements):
        raise ThemeValidationError("HTML visual editor contains an invalid element")
    if len({style.element_id for style in styles}) != len(styles):
        raise ThemeValidationError("HTML visual editor contains duplicate element ids")
    return styles


def load_persisted_visual_element_ids(
    manifest: ThemeManifest,
) -> tuple[str, ...]:
    """Return the editable element order represented by the files on disk."""
    marked_ids = tuple(
        candidate.element_id
        for candidate in discover_overlay_candidates(manifest)
        if candidate.marked
    )
    if not marked_ids:
        raise ThemeValidationError("the theme has no editable HTML overlays")

    saved = load_visual_styles(manifest)
    if not saved:
        return marked_ids

    saved_ids = tuple(style.element_id for style in saved)
    if set(saved_ids) != set(marked_ids):
        missing = sorted(set(marked_ids) - set(saved_ids))
        stale = sorted(set(saved_ids) - set(marked_ids))
        detail = []
        if missing:
            detail.append("missing: " + ", ".join(missing))
        if stale:
            detail.append("not present in HTML: " + ", ".join(stale))
        raise ThemeValidationError(
            "visual editor metadata does not match editable HTML overlays ("
            + "; ".join(detail)
            + ")"
        )
    return saved_ids


def _css_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_visual_stylesheet(styles: Iterable[HtmlVisualElementStyle]) -> str:
    lines = [
        "/* Generated by the Turing HTML visual theme editor. */",
        "/* Edit through the visual editor so manifest regions stay synchronized. */",
        "",
    ]
    for style in styles:
        selector = f"[id={_css_string(style.element_id)}]"
        component = (
            get_html_widget_component(style.component_type)
            if style.component_type
            else None
        )
        is_generated_bar = component is not None and component.kind == "bar"
        is_bar = style.element_kind == "bar" or is_generated_bar
        properties = [
            f"{selector} {{",
            "  position: fixed !important;",
            f"  --turing-editor-x: {style.x}px;",
            f"  --turing-editor-y: {style.y}px;",
            f"  left: {style.x}px !important;",
            f"  top: {style.y}px !important;",
            "  right: auto !important;",
            "  bottom: auto !important;",
            "  translate: none !important;",
            "  transform: none !important;",
            f"  width: {style.width}px !important;",
            f"  height: {style.height}px !important;",
            f"  font-size: {style.font_size}px !important;",
            f"  color: {style.color} !important;",
        ]
        if style.font_weight:
            properties.append(f"  font-weight: {style.font_weight} !important;")
        if style.text_align != "inherit":
            properties.append(f"  text-align: {style.text_align} !important;")
        if is_generated_bar:
            properties.extend(
                [
                    "  display: block !important;",
                    "  box-sizing: border-box !important;",
                    "  overflow: hidden !important;",
                    "  padding: 0 !important;",
                    "  border: 0 !important;",
                    "  border-radius: 999px !important;",
                    "  background: rgba(255, 255, 255, 0.18) !important;",
                    "  pointer-events: none !important;",
                ]
            )
        elif style.component_type:
            properties.extend(
                [
                    "  display: flex !important;",
                    "  align-items: center !important;",
                    "  justify-content: center !important;",
                    "  line-height: 1.1 !important;",
                    "  white-space: nowrap !important;",
                    "  pointer-events: none !important;",
                ]
            )
        properties.extend(
            [
                f"  opacity: {(style.opacity if style.visible else 0) / 100:g} !important;",
                f"  z-index: {style.z_index} !important;",
                "}",
                "",
            ]
        )
        lines.extend(properties)
        if is_generated_bar:
            fill_background = "currentColor"
            if style.effects_managed and style.gradient_enabled:
                angle = _GRADIENT_DIRECTIONS[style.gradient_direction]
                fill_background = (
                    f"linear-gradient({angle}, {style.gradient_start_color}, "
                    f"{style.gradient_end_color})"
                )
            lines.extend(
                [
                    f"{selector} > [data-turing-bar-fill] {{",
                    "  display: block !important;",
                    "  width: 0;",
                    "  height: 100% !important;",
                    "  min-width: 0 !important;",
                    "  border-radius: inherit !important;",
                    f"  background: {fill_background} !important;",
                    "  transition: none !important;",
                    "}",
                    "",
                ]
            )
        if not style.effects_managed:
            continue
        angle = _GRADIENT_DIRECTIONS[style.gradient_direction]
        gradient = (
            f"linear-gradient({angle}, {style.gradient_start_color}, "
            f"{style.gradient_end_color})"
        )
        if is_bar:
            lines.extend(
                [
                    f"{selector} {{",
                    "  box-sizing: border-box !important;",
                    (
                        f"  border: {style.outline_width}px solid "
                        f"{style.outline_color} !important;"
                        if style.outline_width
                        else "  border: 0 !important;"
                    ),
                    (
                        f"  box-shadow: 0 0 {style.glow_radius}px "
                        f"{style.glow_color} !important;"
                        if style.glow_radius
                        else "  box-shadow: none !important;"
                    ),
                ]
            )
            if not is_generated_bar:
                lines.append(
                    f"  background: {gradient if style.gradient_enabled else style.color} !important;"
                )
            lines.extend(["}", ""])
            continue
        text_selector = f"{selector}, {selector} *"
        lines.extend([f"{text_selector} {{"])
        if style.gradient_enabled:
            lines.extend(
                [
                    f"  background-image: {gradient} !important;",
                    "  background-clip: text !important;",
                    "  -webkit-background-clip: text !important;",
                    "  -webkit-text-fill-color: transparent !important;",
                ]
            )
        else:
            lines.extend(
                [
                    "  background-image: none !important;",
                    "  background-clip: border-box !important;",
                    "  -webkit-background-clip: border-box !important;",
                    "  -webkit-text-fill-color: currentColor !important;",
                ]
            )
        lines.extend(
            [
                (
                    f"  -webkit-text-stroke: {style.outline_width}px "
                    f"{style.outline_color} !important;"
                    if style.outline_width
                    else "  -webkit-text-stroke: 0 transparent !important;"
                ),
                (
                    f"  text-shadow: 0 0 {style.glow_radius}px "
                    f"{style.glow_color} !important;"
                    if style.glow_radius
                    else "  text-shadow: none !important;"
                ),
                "}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def ensure_visual_stylesheet_link(html: str) -> str:
    href_pattern = re.compile(
        rf"<link\b[^>]*\bhref\s*=\s*(['\"]){re.escape(EDITOR_STYLESHEET_FILENAME)}\1[^>]*>",
        re.IGNORECASE,
    )
    if href_pattern.search(html):
        return html
    closing_head = re.search(r"</head\s*>", html, re.IGNORECASE)
    if closing_head is None:
        raise ThemeValidationError("HTML theme entrypoint must contain </head>")
    link = f'  <link rel="stylesheet" href="{EDITOR_STYLESHEET_FILENAME}">\n'
    return html[: closing_head.start()] + link + html[closing_head.start() :]


def ensure_widget_runtime_script(html: str) -> str:
    source_pattern = re.compile(
        rf"<script\b[^>]*\bsrc\s*=\s*(['\"]){re.escape(WIDGET_RUNTIME_FILENAME)}\1[^>]*>\s*</script>",
        re.IGNORECASE,
    )
    if source_pattern.search(html):
        return html
    closing_body = re.search(r"</body\s*>", html, re.IGNORECASE)
    if closing_body is None:
        raise ThemeValidationError("HTML theme entrypoint must contain </body>")
    script = f'  <script src="{WIDGET_RUNTIME_FILENAME}"></script>\n'
    return html[: closing_body.start()] + script + html[closing_body.start() :]


def _atomic_write_text(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def _backup_once(path: Path, original: str | None) -> None:
    if original is None:
        return
    backup = path.with_name(f"{path.name}.visual.editor-backup")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")


def save_visual_styles(
    manifest: ThemeManifest,
    styles: Iterable[HtmlVisualElementStyle],
) -> ThemeManifest:
    """Persist overlay layout/style and keep atomic regions synchronized."""
    if manifest.engine != "html":
        raise ThemeValidationError("visual HTML editing requires an HTML theme")
    entrypoint_original = manifest.entrypoint_path.read_text(encoding="utf-8")
    previous_generated_ids = {
        style.element_id
        for style in load_visual_styles(manifest)
        if style.component_type
    }
    previous_generated_ids.update(generated_widget_ids(entrypoint_original))
    marked_ids = [
        candidate.element_id
        for candidate in discover_overlay_candidates(manifest)
        if candidate.marked
    ]
    original_ids = [
        element_id
        for element_id in marked_ids
        if element_id not in previous_generated_ids
    ]
    by_id: dict[str, HtmlVisualElementStyle] = {}
    style_order: list[str] = []
    for raw_style in styles:
        style = raw_style.validated(manifest)
        if style.element_id in by_id:
            raise ThemeValidationError(f"duplicate visual style for #{style.element_id}")
        by_id[style.element_id] = style
        style_order.append(style.element_id)
    generated_ids = [
        element_id
        for element_id in style_order
        if by_id[element_id].component_type
    ]
    expected_ids = set(original_ids) | set(generated_ids)
    if set(by_id) != expected_ids:
        missing = sorted(expected_ids - set(by_id))
        unknown = sorted(set(by_id) - expected_ids)
        detail = []
        if missing:
            detail.append("missing: " + ", ".join(missing))
        if unknown:
            detail.append("not live overlays: " + ", ".join(unknown))
        raise ThemeValidationError("visual styles must cover every live overlay (" + "; ".join(detail) + ")")
    ordered_ids = original_ids + generated_ids
    ordered = tuple(by_id[element_id] for element_id in ordered_ids)

    manifest_path = manifest.root / "manifest.json"
    entrypoint_path = manifest.entrypoint_path
    css_path = stylesheet_path(manifest)
    editor_path = metadata_path(manifest)
    runtime_path = manifest.root / WIDGET_RUNTIME_FILENAME
    paths = (manifest_path, entrypoint_path, css_path, editor_path, runtime_path)
    originals = {
        path: path.read_text(encoding="utf-8") if path.is_file() else None
        for path in paths
    }

    payload = json.loads(originals[manifest_path] or "{}")
    payload["atomicRegions"] = [
        {
            "name": f"overlay:{style.element_id}",
            "x": style.x,
            "y": style.y,
            "width": style.width,
            "height": style.height,
        }
        for style in ordered
        if style.visible
    ]
    manifest_text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    html_text = ensure_visual_stylesheet_link(originals[entrypoint_path] or "")
    html_text = update_generated_widget_block(
        html_text,
        (
            (style.element_id, style.component_type)
            for style in ordered
            if style.component_type
        ),
    )
    html_text = ensure_widget_runtime_script(html_text)
    css_text = render_visual_stylesheet(ordered)
    metadata_text = json.dumps(
        {
            "schemaVersion": EDITOR_SCHEMA_VERSION,
            "elements": [style.as_dict() for style in ordered],
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    runtime_text = render_widget_runtime_script()
    outputs = {
        manifest_path: manifest_text,
        entrypoint_path: html_text,
        css_path: css_text,
        editor_path: metadata_text,
        runtime_path: runtime_text,
    }

    for path in paths:
        _backup_once(path, originals[path])
    try:
        for path, content in outputs.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                _atomic_write_text(path, content)
        return ThemeManifest.load(manifest.root)
    except Exception:
        for path in paths:
            original = originals[path]
            if original is None:
                path.unlink(missing_ok=True)
            else:
                _atomic_write_text(path, original)
        raise
