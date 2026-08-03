# SPDX-License-Identifier: GPL-3.0-or-later
"""Outer text-outline rendering and curated HTML theme style presets."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any, Iterable

from library.html_theme_visual_editor import HtmlVisualElementStyle
from library.theme_engine import ThemeManifest, ThemeValidationError


@dataclass(frozen=True)
class VisualStylePreset:
    key: str
    label: str
    kind: str
    description: str
    font_size: int | None = None
    font_weight: int | None = None
    color: str = "#ffffff"
    width: int | None = None
    height: int | None = None
    gradient_enabled: bool = False
    gradient_start_color: str = "#ffffff"
    gradient_end_color: str = "#66e0ff"
    gradient_direction: str = "horizontal"
    outline_width: int = 0
    outline_color: str = "#000000"
    glow_radius: int = 0
    glow_color: str = "#ffffff"


_TEXT_PRESETS = (
    VisualStylePreset(
        key="text-high-contrast",
        label="Legível · Alto contraste",
        kind="text",
        description="Texto branco forte com contorno externo preto para fundos complexos.",
        font_size=32,
        font_weight=700,
        color="#ffffff",
        outline_width=2,
        outline_color="#080b10",
    ),
    VisualStylePreset(
        key="text-material-expressive",
        label="Display · Material Expressive",
        kind="text",
        description="Título grande com degradê lilás e azul, peso alto e brilho suave.",
        font_size=52,
        font_weight=800,
        color="#f6d8ff",
        gradient_enabled=True,
        gradient_start_color="#f4b8ff",
        gradient_end_color="#8fdcff",
        gradient_direction="diagonal",
        outline_width=1,
        outline_color="#241335",
        glow_radius=8,
        glow_color="#c77dff",
    ),
    VisualStylePreset(
        key="text-neon-cyan",
        label="Neon · Ciano e violeta",
        kind="text",
        description="Degradê frio com brilho luminoso para interfaces gamer e sci-fi.",
        font_size=42,
        font_weight=700,
        color="#87f7ff",
        gradient_enabled=True,
        gradient_start_color="#70f4ff",
        gradient_end_color="#b388ff",
        outline_width=1,
        outline_color="#06121d",
        glow_radius=14,
        glow_color="#58e9ff",
    ),
    VisualStylePreset(
        key="text-arcade",
        label="Arcade · Amarelo e preto",
        kind="text",
        description="Peso máximo, amarelo vibrante e contorno externo marcante.",
        font_size=52,
        font_weight=900,
        color="#ffe45e",
        outline_width=3,
        outline_color="#090909",
        glow_radius=4,
        glow_color="#ff9f1c",
    ),
    VisualStylePreset(
        key="text-data-clean",
        label="Dados · Monocromático",
        kind="text",
        description="Valor técnico claro, compacto e sem efeitos decorativos excessivos.",
        font_size=34,
        font_weight=600,
        color="#eef7ff",
        outline_width=1,
        outline_color="#111820",
    ),
    VisualStylePreset(
        key="text-aurora",
        label="Aurora · Rosa e roxo",
        kind="text",
        description="Degradê expressivo quente-frio com brilho controlado.",
        font_size=40,
        font_weight=800,
        color="#ffd0f3",
        gradient_enabled=True,
        gradient_start_color="#ff8bd7",
        gradient_end_color="#8c7dff",
        gradient_direction="horizontal",
        outline_width=1,
        outline_color="#281030",
        glow_radius=10,
        glow_color="#d36bff",
    ),
    VisualStylePreset(
        key="text-alert",
        label="Alerta · Coral",
        kind="text",
        description="Cor de atenção com contorno escuro e brilho moderado.",
        font_size=32,
        font_weight=800,
        color="#ff6b6b",
        outline_width=2,
        outline_color="#2a0909",
        glow_radius=7,
        glow_color="#ff453a",
    ),
    VisualStylePreset(
        key="text-soft-glass",
        label="Suave · Glass",
        kind="text",
        description="Texto claro de peso médio com brilho difuso e sem contorno.",
        font_size=30,
        font_weight=500,
        color="#dce9ff",
        glow_radius=8,
        glow_color="#9fc4ff",
    ),
)


_BAR_PRESETS = (
    VisualStylePreset(
        key="bar-material-pill",
        label="Pill · Material",
        kind="bar",
        description="Barra arredondada, média e tonal em violeta Material.",
        width=180,
        height=16,
        color="#d0bcff",
        gradient_enabled=True,
        gradient_start_color="#6750a4",
        gradient_end_color="#d0bcff",
    ),
    VisualStylePreset(
        key="bar-expressive",
        label="Expressiva · Coral e violeta",
        kind="bar",
        description="Barra mais espessa com degradê vibrante e brilho suave.",
        width=200,
        height=18,
        color="#ff8a80",
        gradient_enabled=True,
        gradient_start_color="#ff8a80",
        gradient_end_color="#b388ff",
        gradient_direction="horizontal",
        outline_width=1,
        outline_color="#281326",
        glow_radius=6,
        glow_color="#d978ff",
    ),
    VisualStylePreset(
        key="bar-neon-cyan",
        label="Neon · Ciano",
        kind="bar",
        description="Barra fina e luminosa para temas tecnológicos.",
        width=180,
        height=10,
        color="#63f5ff",
        outline_width=1,
        outline_color="#041116",
        glow_radius=10,
        glow_color="#42eaff",
    ),
    VisualStylePreset(
        key="bar-minimal",
        label="Minimal · Monocromática",
        kind="bar",
        description="Barra fina, branca e sem efeitos adicionais.",
        width=160,
        height=8,
        color="#f4f7fb",
    ),
    VisualStylePreset(
        key="bar-thermal",
        label="Térmica · Amarelo e vermelho",
        kind="bar",
        description="Degradê de temperatura para CPU, GPU e alertas.",
        width=190,
        height=14,
        color="#ffb300",
        gradient_enabled=True,
        gradient_start_color="#ffd54f",
        gradient_end_color="#ff5252",
        outline_width=1,
        outline_color="#2b0b05",
        glow_radius=5,
        glow_color="#ff7043",
    ),
    VisualStylePreset(
        key="bar-mint",
        label="Status · Menta",
        kind="bar",
        description="Barra positiva em tons de menta com contraste escuro.",
        width=180,
        height=12,
        color="#80ffd3",
        gradient_enabled=True,
        gradient_start_color="#5de6c1",
        gradient_end_color="#b8ffdc",
        outline_width=1,
        outline_color="#08251d",
    ),
    VisualStylePreset(
        key="bar-arcade",
        label="Arcade · Amarela",
        kind="bar",
        description="Barra espessa amarela com borda preta para temas retrô.",
        width=170,
        height=18,
        color="#ffe45e",
        outline_width=2,
        outline_color="#090909",
    ),
)


_ALL_PRESETS = _TEXT_PRESETS + _BAR_PRESETS
_PRESETS_BY_KEY = {preset.key: preset for preset in _ALL_PRESETS}
_RENDERER_INSTALLED = False


def visual_style_presets(kind: str | None = None) -> tuple[VisualStylePreset, ...]:
    value = str(kind or "").strip().lower()
    if value == "text":
        return _TEXT_PRESETS
    if value == "bar":
        return _BAR_PRESETS
    return _ALL_PRESETS


def get_visual_style_preset(key: str) -> VisualStylePreset:
    try:
        return _PRESETS_BY_KEY[str(key)]
    except KeyError as exc:
        raise ThemeValidationError(f"unknown visual style preset: {key}") from exc


def apply_visual_style_preset(
    style: HtmlVisualElementStyle,
    preset: VisualStylePreset | str,
    manifest: ThemeManifest,
) -> HtmlVisualElementStyle:
    value = get_visual_style_preset(preset) if isinstance(preset, str) else preset
    if style.element_kind != value.kind:
        raise ThemeValidationError(
            f"preset {value.label!r} is for {value.kind}, not {style.element_kind}"
        )

    width = style.width
    height = style.height
    if value.width is not None:
        width = min(int(value.width), manifest.width - style.x)
    if value.height is not None:
        height = min(int(value.height), manifest.height - style.y)

    updated = replace(
        style,
        width=max(1, width),
        height=max(1, height),
        font_size=(style.font_size if value.font_size is None else value.font_size),
        font_weight=(style.font_weight if value.font_weight is None else value.font_weight),
        color=value.color,
        effects_managed=True,
        gradient_enabled=value.gradient_enabled,
        gradient_start_color=value.gradient_start_color,
        gradient_end_color=value.gradient_end_color,
        gradient_direction=value.gradient_direction,
        outline_width=value.outline_width,
        outline_color=value.outline_color,
        glow_radius=value.glow_radius,
        glow_color=value.glow_color,
    )
    return updated.validated(manifest)


def _text_selector(style: HtmlVisualElementStyle) -> str:
    escaped = json.dumps(style.element_id, ensure_ascii=True)
    return f"[id={escaped}], [id={escaped}] *"


def outer_outline_css(style: HtmlVisualElementStyle) -> str:
    """Return a late CSS override that keeps the visible stroke outside glyph fill."""
    if style.element_kind != "text" or not style.effects_managed:
        return ""
    selector = _text_selector(style)
    visible_stroke = max(0, int(style.outline_width))
    if visible_stroke == 0:
        return (
            f"{selector} {{\n"
            "  paint-order: normal !important;\n"
            "  -webkit-text-stroke-width: 0 !important;\n"
            "  -webkit-text-stroke-color: transparent !important;\n"
            "}\n"
        )
    # CSS text strokes are centered on the glyph edge. Drawing a stroke twice
    # the requested size behind the fill leaves exactly the requested amount
    # visible outside while the fill covers its inner half.
    rendered_width = visible_stroke * 2
    return (
        f"{selector} {{\n"
        "  paint-order: stroke fill !important;\n"
        f"  -webkit-text-stroke-width: {rendered_width}px !important;\n"
        f"  -webkit-text-stroke-color: {style.outline_color} !important;\n"
        "  stroke-linejoin: round !important;\n"
        "}\n"
    )


def install_outer_text_outline_renderer() -> bool:
    """Patch the stylesheet renderer once; save_visual_styles uses its module global."""
    global _RENDERER_INSTALLED
    if _RENDERER_INSTALLED:
        return False
    from library import html_theme_visual_editor as visual

    original = visual.render_visual_stylesheet
    if getattr(original, "_turing_outer_outline_renderer", False):
        _RENDERER_INSTALLED = True
        return False

    def render(styles: Iterable[HtmlVisualElementStyle]) -> str:
        values = tuple(styles)
        css = original(values).rstrip() + "\n\n"
        additions = [outer_outline_css(style).rstrip() for style in values]
        additions = [value for value in additions if value]
        if additions:
            css += "/* Outer-only text outlines: stroke behind fill. */\n"
            css += "\n\n".join(additions) + "\n"
        return css

    render._turing_outer_outline_renderer = True
    visual.render_visual_stylesheet = render
    _RENDERER_INSTALLED = True
    return True


def _preview_outline_script(style: HtmlVisualElementStyle) -> str:
    selector = json.dumps(f"#{style.element_id}, #{style.element_id} *")
    width = max(0, int(style.outline_width))
    rendered_width = width * 2
    color = json.dumps(style.outline_color)
    return f"""
    (() => {{
      document.querySelectorAll({selector}).forEach(target => {{
        if ({width} > 0) {{
          target.style.setProperty('paint-order', 'stroke fill', 'important');
          target.style.setProperty('-webkit-text-stroke-width', '{rendered_width}px', 'important');
          target.style.setProperty('-webkit-text-stroke-color', {color}, 'important');
          target.style.setProperty('stroke-linejoin', 'round', 'important');
        }} else {{
          target.style.setProperty('paint-order', 'normal', 'important');
          target.style.setProperty('-webkit-text-stroke-width', '0', 'important');
          target.style.setProperty('-webkit-text-stroke-color', 'transparent', 'important');
        }}
      }});
    }})();
    """


def _attach_preset_controls(window: Any, Gtk: Any) -> None:
    if getattr(window, "_turing_style_presets_attached", False):
        return
    stack = getattr(window, "inspector_stack", None)
    if stack is None:
        return
    effects_scroll = stack.get_child_by_name("effects")
    effects_page = effects_scroll.get_child() if effects_scroll is not None else None
    if effects_page is None:
        return

    window._turing_style_presets_attached = True
    state: dict[str, Any] = {"presets": ()}

    effects_page.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
    heading = Gtk.Label(label="Presets visuais", xalign=0)
    heading.add_css_class("heading")
    effects_page.append(heading)

    preset_dropdown = Gtk.DropDown.new_from_strings(("Carregando…",))
    preset_dropdown.set_hexpand(True)
    effects_page.append(preset_dropdown)

    description = Gtk.Label(label="", xalign=0, wrap=True)
    description.add_css_class("dim-label")
    effects_page.append(description)

    apply_button = Gtk.Button(label="Aplicar preset ao elemento")
    apply_button.add_css_class("suggested-action")
    effects_page.append(apply_button)

    def selected_style() -> HtmlVisualElementStyle | None:
        try:
            return window.styles.get(window._selected_id())
        except Exception:
            return None

    def selected_preset() -> VisualStylePreset | None:
        presets = tuple(state.get("presets") or ())
        index = int(preset_dropdown.get_selected())
        return presets[index] if 0 <= index < len(presets) else None

    def update_description(*_args) -> None:
        preset = selected_preset()
        description.set_text(preset.description if preset is not None else "")

    def refresh_presets(*_args) -> None:
        style = selected_style()
        kind = style.element_kind if style is not None else "text"
        presets = visual_style_presets(kind)
        state["presets"] = presets
        preset_dropdown.set_model(Gtk.StringList.new(tuple(item.label for item in presets)))
        preset_dropdown.set_selected(0)
        update_description()

    def apply_preset(*_args) -> None:
        style = selected_style()
        preset = selected_preset()
        if style is None or preset is None:
            return
        try:
            window._checkpoint()
            updated = apply_visual_style_preset(style, preset, window.manifest)
            window.styles[updated.element_id] = updated
            window._apply_style_to_preview(updated)
            window._load_selected_controls()
            window._mark_changed()
            window._update_history_actions()
            window._toast(f"Preset aplicado: {preset.label}")
        except Exception as exc:
            window.status_label.set_text(f"Não foi possível aplicar o preset: {exc}")
            window._toast("Falha ao aplicar preset")

    preset_dropdown.connect("notify::selected", update_description)
    apply_button.connect("clicked", apply_preset)
    window.element_dropdown.connect("notify::selected", refresh_presets)
    window.element_kind_dropdown.connect("notify::selected", refresh_presets)
    refresh_presets()


def _patch_preview_outline(window: Any) -> None:
    window_class = window.__class__
    if getattr(window_class, "_turing_outer_outline_preview", False):
        return
    original = window_class._apply_style_to_preview

    def apply_style_to_preview(self, style: HtmlVisualElementStyle) -> None:
        original(self, style)
        if style.element_kind == "text" and style.effects_managed:
            self.backend.evaluate(_preview_outline_script(style))

    window_class._apply_style_to_preview = apply_style_to_preview
    window_class._turing_outer_outline_preview = True


def install_style_preset_editor_hook() -> None:
    """Install renderer support now and attach controls when the editor is ready."""
    install_outer_text_outline_renderer()

    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import GLib, Gtk

    attempts = 0

    def attach_when_ready() -> bool:
        nonlocal attempts
        attempts += 1
        application = Gtk.Application.get_default()
        if application is not None:
            for window in application.get_windows():
                if window.__class__.__name__ != "HtmlThemeEditorWindow":
                    continue
                if not getattr(window, "_loaded_once", False):
                    continue
                _patch_preview_outline(window)
                _attach_preset_controls(window, Gtk)
                for style in getattr(window, "styles", {}).values():
                    if style.element_kind == "text" and style.effects_managed:
                        window.backend.evaluate(_preview_outline_script(style))
                return False
        if attempts >= 600:
            print(
                "Os presets visuais não foram anexados porque o editor não concluiu o carregamento.",
                flush=True,
            )
            return False
        return True

    GLib.timeout_add(50, attach_when_ready)
