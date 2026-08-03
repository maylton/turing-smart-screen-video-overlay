# SPDX-License-Identifier: GPL-3.0-or-later
"""Date-format choices and decorative shapes for the HTML visual editor."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Iterable

from library.html_theme_visual_editor import HtmlVisualElementStyle
from library.theme_engine import ThemeManifest, ThemeValidationError


@dataclass(frozen=True)
class DateFormatOption:
    key: str
    label: str
    sample: str
    description: str


DATE_FORMAT_OPTIONS = (
    DateFormatOption(
        "date",
        "Numérica · 02/08/2026",
        "02/08/2026",
        "Dia, mês e ano numéricos no padrão brasileiro.",
    ),
    DateFormatOption(
        "date-short",
        "Curta · 02/08/26",
        "02/08/26",
        "Versão compacta com ano de dois dígitos.",
    ),
    DateFormatOption(
        "date-long",
        "Por extenso · 2 de agosto de 2026",
        "2 de agosto de 2026",
        "Data completa com o nome do mês.",
    ),
    DateFormatOption(
        "date-full",
        "Completa · domingo, 2 de agosto de 2026",
        "domingo, 2 de agosto de 2026",
        "Inclui o dia da semana e a data por extenso.",
    ),
    DateFormatOption(
        "date-compact",
        "Compacta · 02 AGO",
        "02 AGO",
        "Dia e mês abreviado em caixa alta.",
    ),
    DateFormatOption(
        "date-iso",
        "ISO · 2026-08-02",
        "2026-08-02",
        "Formato internacional ano-mês-dia.",
    ),
    DateFormatOption(
        "date-weekday",
        "Somente dia · DOMINGO",
        "DOMINGO",
        "Exibe apenas o nome do dia da semana.",
    ),
    DateFormatOption(
        "date-month-day",
        "Dia e mês · 2 AGO",
        "2 AGO",
        "Dia sem zero inicial e mês abreviado.",
    ),
)
_DATE_FORMATS_BY_KEY = {option.key: option for option in DATE_FORMAT_OPTIONS}


@dataclass(frozen=True)
class ShapeOption:
    key: str
    label: str
    component_type: str
    width: int
    height: int
    border_radius: str
    description: str


SHAPE_OPTIONS = (
    ShapeOption(
        "squircle",
        "Squircle",
        "shape-squircle",
        120,
        120,
        "30%",
        "Forma orgânica entre quadrado e círculo, adequada ao Material Expressive.",
    ),
    ShapeOption(
        "circle",
        "Círculo",
        "shape-circle",
        120,
        120,
        "50%",
        "Círculo para ícones, indicadores e composições concêntricas.",
    ),
    ShapeOption(
        "square",
        "Quadrado",
        "shape-square",
        120,
        120,
        "0",
        "Quadrado geométrico sem arredondamento.",
    ),
    ShapeOption(
        "rounded-rectangle",
        "Retângulo arredondado",
        "shape-rounded-rectangle",
        180,
        90,
        "22px",
        "Superfície de apoio para cartões, títulos e grupos de dados.",
    ),
    ShapeOption(
        "pill",
        "Pill",
        "shape-pill",
        180,
        54,
        "999px",
        "Cápsula para etiquetas, status e pequenos painéis.",
    ),
    ShapeOption(
        "line-horizontal",
        "Linha horizontal",
        "shape-line-horizontal",
        180,
        4,
        "999px",
        "Divisor horizontal que pode receber cor, degradê e brilho.",
    ),
    ShapeOption(
        "line-vertical",
        "Linha vertical",
        "shape-line-vertical",
        4,
        180,
        "999px",
        "Divisor vertical que pode receber cor, degradê e brilho.",
    ),
)
_SHAPES_BY_KEY = {option.key: option for option in SHAPE_OPTIONS}
_SHAPES_BY_COMPONENT = {option.component_type: option for option in SHAPE_OPTIONS}
_RENDERER_INSTALLED = False


def date_format_options() -> tuple[DateFormatOption, ...]:
    return DATE_FORMAT_OPTIONS


def get_date_format_option(key: str) -> DateFormatOption:
    try:
        return _DATE_FORMATS_BY_KEY[str(key)]
    except KeyError as exc:
        raise ThemeValidationError(f"unsupported date format: {key}") from exc


def shape_options() -> tuple[ShapeOption, ...]:
    return SHAPE_OPTIONS


def get_shape_option(key: str) -> ShapeOption:
    try:
        return _SHAPES_BY_KEY[str(key)]
    except KeyError as exc:
        raise ThemeValidationError(f"unsupported decorative shape: {key}") from exc


def shape_option_for_component(component_type: str) -> ShapeOption | None:
    return _SHAPES_BY_COMPONENT.get(str(component_type or ""))


def is_date_style(style: HtmlVisualElementStyle | None) -> bool:
    if style is None:
        return False
    return bool(
        style.component_type == "date"
        or (
            style.binding == "$timestamp"
            and (style.formatter == "date" or style.formatter.startswith("date-"))
        )
    )


def is_shape_style(style: HtmlVisualElementStyle | None) -> bool:
    return bool(style is not None and shape_option_for_component(style.component_type))


def apply_date_format(
    style: HtmlVisualElementStyle,
    format_key: str,
    manifest: ThemeManifest,
) -> HtmlVisualElementStyle:
    if not is_date_style(style):
        raise ThemeValidationError(f"#{style.element_id} is not a generated date element")
    option = get_date_format_option(format_key)
    return replace(
        style,
        binding="$timestamp",
        formatter=option.key,
        sample=option.sample,
    ).validated(manifest)


def apply_shape_type(
    style: HtmlVisualElementStyle,
    shape_key: str,
    manifest: ThemeManifest,
) -> HtmlVisualElementStyle:
    if not is_shape_style(style):
        raise ThemeValidationError(f"#{style.element_id} is not a decorative shape")
    option = get_shape_option(shape_key)
    width = max(1, min(option.width, manifest.width - style.x))
    height = max(1, min(option.height, manifest.height - style.y))
    return replace(
        style,
        component_type=option.component_type,
        binding="$timestamp",
        formatter="shape",
        sample="shape",
        element_kind="text",
        width=width,
        height=height,
        font_size=6,
        font_weight=0,
        text_align="inherit",
    ).validated(manifest)


def _css_string(value: str) -> str:
    return json.dumps(str(value), ensure_ascii=True)


def shape_css(style: HtmlVisualElementStyle) -> str:
    option = shape_option_for_component(style.component_type)
    if option is None:
        return ""
    selector = f"[id={_css_string(style.element_id)}]"
    if style.effects_managed and style.gradient_enabled:
        angle = {
            "horizontal": "90deg",
            "vertical": "180deg",
            "diagonal": "135deg",
        }[style.gradient_direction]
        fill = (
            f"linear-gradient({angle}, {style.gradient_start_color}, "
            f"{style.gradient_end_color})"
        )
    else:
        fill = style.color
    border = (
        f"{style.outline_width}px solid {style.outline_color}"
        if style.effects_managed and style.outline_width
        else "0"
    )
    shadow = (
        f"0 0 {style.glow_radius}px {style.glow_color}"
        if style.effects_managed and style.glow_radius
        else "none"
    )
    return (
        f"{selector} {{\n"
        "  display: block !important;\n"
        "  box-sizing: border-box !important;\n"
        "  padding: 0 !important;\n"
        "  margin: 0 !important;\n"
        "  overflow: visible !important;\n"
        "  font-size: 0 !important;\n"
        "  line-height: 0 !important;\n"
        "  color: transparent !important;\n"
        "  -webkit-text-fill-color: transparent !important;\n"
        "  -webkit-text-stroke: 0 transparent !important;\n"
        "  text-shadow: none !important;\n"
        f"  border-radius: {option.border_radius} !important;\n"
        f"  background: {fill} !important;\n"
        f"  border: {border} !important;\n"
        f"  box-shadow: {shadow} !important;\n"
        "}\n"
    )


def install_decorative_shape_renderer() -> bool:
    """Append shape-specific CSS after the editor's standard text/bar CSS."""
    global _RENDERER_INSTALLED
    if _RENDERER_INSTALLED:
        return False
    from library import html_theme_visual_editor as visual

    original = visual.render_visual_stylesheet
    if getattr(original, "_turing_decorative_shape_renderer", False):
        _RENDERER_INSTALLED = True
        return False

    def render(styles: Iterable[HtmlVisualElementStyle]) -> str:
        values = tuple(styles)
        css = original(values).rstrip() + "\n"
        additions = [shape_css(style).rstrip() for style in values]
        additions = [value for value in additions if value]
        if additions:
            css += "\n/* Decorative shapes generated by the visual editor. */\n"
            css += "\n\n".join(additions) + "\n"
        return css

    render._turing_decorative_shape_renderer = True
    visual.render_visual_stylesheet = render
    _RENDERER_INSTALLED = True
    return True


def shape_preview_script(style: HtmlVisualElementStyle) -> str:
    option = shape_option_for_component(style.component_type)
    if option is None:
        return ""
    payload = json.dumps(
        {
            "id": style.element_id,
            "radius": option.border_radius,
            "color": style.color,
            "effectsManaged": style.effects_managed,
            "gradientEnabled": style.gradient_enabled,
            "gradientStart": style.gradient_start_color,
            "gradientEnd": style.gradient_end_color,
            "gradientDirection": style.gradient_direction,
            "outlineWidth": style.outline_width,
            "outlineColor": style.outline_color,
            "glowRadius": style.glow_radius,
            "glowColor": style.glow_color,
        },
        ensure_ascii=True,
    )
    return f"""
    (() => {{
      const value = {payload};
      const element = document.getElementById(value.id);
      if (!element) return;
      const angle = {{horizontal: '90deg', vertical: '180deg', diagonal: '135deg'}}[
        value.gradientDirection
      ] || '90deg';
      const fill = value.effectsManaged && value.gradientEnabled
        ? `linear-gradient(${{angle}}, ${{value.gradientStart}}, ${{value.gradientEnd}})`
        : value.color;
      const properties = [
        ['display', 'block'],
        ['box-sizing', 'border-box'],
        ['padding', '0'],
        ['margin', '0'],
        ['overflow', 'visible'],
        ['font-size', '0'],
        ['line-height', '0'],
        ['color', 'transparent'],
        ['-webkit-text-fill-color', 'transparent'],
        ['-webkit-text-stroke', '0 transparent'],
        ['text-shadow', 'none'],
        ['border-radius', value.radius],
        ['background', fill],
        [
          'border',
          value.effectsManaged && value.outlineWidth
            ? `${{value.outlineWidth}}px solid ${{value.outlineColor}}`
            : '0'
        ],
        [
          'box-shadow',
          value.effectsManaged && value.glowRadius
            ? `0 0 ${{value.glowRadius}}px ${{value.glowColor}}`
            : 'none'
        ]
      ];
      for (const [name, property] of properties) {{
        element.style.setProperty(name, property, 'important');
      }}
      element.textContent = '';
      element.setAttribute('aria-hidden', 'true');
      window.__turingEditorRefreshSelection?.();
    }})();
    """
