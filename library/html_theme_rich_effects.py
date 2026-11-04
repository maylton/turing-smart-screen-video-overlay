# SPDX-License-Identifier: GPL-3.0-or-later
"""Fonts and richer text/bar effects for HTML theme overlays.

One table of CSS properties per element feeds both the saved stylesheet
(theme-editor-overrides.css) and the editor preview, so they cannot
diverge. Everything here only applies to effects-managed elements.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
FONTS_DIR = ROOT / "res" / "fonts" / "web"
THEME_FONTS_DIR = "fonts"

GLOW_STYLES = ("soft", "neon", "bloom")
GLOW_STYLE_LABELS = ("Suave", "Neon (núcleo branco)", "Bloom (halo largo)")
TEXT_TRANSFORMS = ("none", "uppercase")
BAR_STYLES = ("solid", "striped", "segmented", "glossy")
BAR_STYLE_LABELS = ("Sólida", "Listrada", "Segmentada (LED)", "Brilhante (gloss)")
_GRADIENT_ANGLES = {"horizontal": "90deg", "vertical": "180deg", "diagonal": "135deg"}


@dataclass(frozen=True)
class FontFace:
    file: str
    weight: str


@dataclass(frozen=True)
class ThemeFont:
    key: str
    family: str
    label: str
    category: str
    fallback: str
    faces: tuple[FontFace, ...]
    license: str

    @property
    def css_family(self) -> str:
        return f'"{self.family}", {self.fallback}'


@lru_cache(maxsize=1)
def theme_fonts() -> tuple[ThemeFont, ...]:
    try:
        payload = json.loads((FONTS_DIR / "catalog.json").read_text(encoding="utf-8"))
    except OSError:
        return ()
    return tuple(
        ThemeFont(
            key=item["key"],
            family=item["family"],
            label=item["label"],
            category=item["category"],
            fallback=item["fallback"],
            faces=tuple(FontFace(face["file"], face["weight"]) for face in item["faces"]),
            license=item["license"],
        )
        for item in payload
    )


def get_theme_font(key: str) -> ThemeFont | None:
    return next((font for font in theme_fonts() if font.key == key), None)


def font_keys() -> tuple[str, ...]:
    return tuple(font.key for font in theme_fonts())


def font_face_css(keys: Iterable[str]) -> str:
    """@font-face rules for ``keys``, with URLs relative to the theme root."""
    rules = []
    for key in sorted(set(keys)):
        font = get_theme_font(key)
        if font is None:
            continue
        for face in font.faces:
            rules.append(
                "@font-face {\n"
                f'  font-family: "{font.family}";\n'
                f'  src: url("{THEME_FONTS_DIR}/{face.file}") format("woff2");\n'
                f"  font-weight: {face.weight};\n"
                "  font-display: block;\n"
                "}\n"
            )
    return "\n".join(rules)


def ensure_theme_fonts(theme_root: Path, keys: Iterable[str]) -> list[Path]:
    """Copy the font files and license of ``keys`` into the theme folder."""
    copied = []
    for key in sorted(set(keys)):
        font = get_theme_font(key)
        if font is None:
            continue
        for relative in [face.file for face in font.faces] + [font.license]:
            source = FONTS_DIR / relative
            target = Path(theme_root) / THEME_FONTS_DIR / relative
            if target.is_file() and target.stat().st_size == source.stat().st_size:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            copied.append(target)
    return copied


def _gradient(style) -> str:
    angle = _GRADIENT_ANGLES.get(style.gradient_direction, "90deg")
    stops = [style.gradient_start_color]
    if style.gradient_mid_color:
        stops.append(style.gradient_mid_color)
    stops.append(style.gradient_end_color)
    return f"linear-gradient({angle}, {', '.join(stops)})"


def _glow_layers(style) -> list[str]:
    radius, color = int(style.glow_radius), style.glow_color
    if radius <= 0:
        return []
    if style.glow_style == "neon":
        return [
            f"0 0 {max(1, radius // 6)}px #ffffff",
            f"0 0 {max(1, radius // 3)}px {color}",
            f"0 0 {max(1, (radius * 2) // 3)}px {color}",
            f"0 0 {radius}px {color}",
        ]
    if style.glow_style == "bloom":
        return [f"0 0 {max(1, radius // 2)}px {color}", f"0 0 {radius}px {color}", f"0 0 {radius * 2}px {color}"]
    return [f"0 0 {radius}px {color}"]


def _shadow_layer(style) -> list[str]:
    if not (style.shadow_x or style.shadow_y or style.shadow_blur):
        return []
    return [f"{style.shadow_x}px {style.shadow_y}px {style.shadow_blur}px {style.shadow_color}"]


def _bar_background(style) -> str:
    base = _gradient(style) if style.gradient_enabled else style.color
    if style.bar_style == "striped":
        return (
            "repeating-linear-gradient(45deg, rgba(255, 255, 255, 0.28) 0 6px, "
            f"transparent 6px 12px), {base}"
        )
    if style.bar_style == "glossy":
        return (
            "linear-gradient(180deg, rgba(255, 255, 255, 0.5), rgba(255, 255, 255, 0.1) 50%, "
            f"rgba(0, 0, 0, 0.15) 51%, rgba(0, 0, 0, 0)), {base}"
        )
    return base


def rich_effect_properties(style) -> dict[str, dict[str, str]]:
    """CSS for the rich effects, grouped by target.

    ``element`` is the overlay root, ``text`` the root and its descendants
    (text elements), ``fill`` the painted part of a bar: the generated fill
    child, or the element itself for bars written in the theme HTML.
    """
    if not getattr(style, "effects_managed", False):
        return {}
    if style.element_kind == "bar":
        fill = {"background": _bar_background(style)}
        if style.bar_style == "segmented":
            mask = "repeating-linear-gradient(90deg, #000 0 10px, transparent 10px 13px)"
            fill["-webkit-mask-image"] = mask
            fill["mask-image"] = mask
        else:
            fill["-webkit-mask-image"] = "none"
            fill["mask-image"] = "none"
        element = {}
        layers = _shadow_layer(style) + _glow_layers(style)
        element["box-shadow"] = ", ".join(layers) if layers else "none"
        return {"element": element, "fill": fill}

    text: dict[str, str] = {}
    font = get_theme_font(style.font_family) if style.font_family else None
    if font is not None:
        text["font-family"] = font.css_family
    text["letter-spacing"] = f"{style.letter_spacing}px" if style.letter_spacing else "normal"
    text["text-transform"] = style.text_transform
    layers = _shadow_layer(style) + _glow_layers(style)
    if style.gradient_enabled:
        # Gradient text has a transparent fill, so a text-shadow shows
        # through the glyphs and hides the gradient. drop-shadow() is drawn
        # after the text is clipped, on the overlay root only.
        text["background-image"] = _gradient(style)
        text["text-shadow"] = "none"
        element = {"filter": " ".join(f"drop-shadow({layer})" for layer in layers) if layers else "none"}
        return {"text": text, "element": element}
    text["text-shadow"] = ", ".join(layers) if layers else "none"
    return {"text": text, "element": {"filter": "none"}}


def rich_effect_css(style, selector: str, *, generated_bar: bool) -> str:
    targets = rich_effect_properties(style)
    if not targets:
        return ""
    selectors = {
        "element": selector,
        "text": f"{selector}, {selector} *",
        "fill": f"{selector} > [data-turing-bar-fill]" if generated_bar else selector,
    }
    blocks = []
    for target, properties in targets.items():
        if not properties:
            continue
        body = "".join(f"  {name}: {value} !important;\n" for name, value in properties.items())
        blocks.append(f"{selectors[target]} {{\n{body}}}\n")
    return "\n".join(blocks)


def used_font_keys(styles: Iterable) -> set[str]:
    return {
        style.font_family
        for style in styles
        if getattr(style, "effects_managed", False) and style.font_family and get_theme_font(style.font_family)
    }


def preview_payload(style) -> Mapping[str, Mapping[str, str]]:
    return rich_effect_properties(style)
