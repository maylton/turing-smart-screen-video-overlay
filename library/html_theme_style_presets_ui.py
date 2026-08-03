# SPDX-License-Identifier: GPL-3.0-or-later
"""Reliable GTK integration for HTML text and bar style presets."""

from __future__ import annotations

import json
from typing import Any

from library.html_theme_style_presets import (
    VisualStylePreset,
    apply_visual_style_preset,
    install_outer_text_outline_renderer,
    visual_style_presets,
)
from library.html_theme_visual_editor import HtmlVisualElementStyle


def _preview_outline_script(style: HtmlVisualElementStyle) -> str:
    selector = json.dumps(f"#{style.element_id}, #{style.element_id} *")
    visible_width = max(0, int(style.outline_width))
    rendered_width = visible_width * 2
    color = json.dumps(style.outline_color)
    return f"""
    (() => {{
      document.querySelectorAll({selector}).forEach(target => {{
        if ({visible_width} > 0) {{
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


def _selected_style(window: Any) -> HtmlVisualElementStyle | None:
    try:
        return window.styles.get(window._selected_id())
    except Exception:
        return None


def _attach_presets_page(window: Any, Gtk: Any) -> None:
    if getattr(window, "_turing_presets_page_attached", False):
        return

    stack = getattr(window, "inspector_stack", None)
    if stack is None:
        raise RuntimeError("editor inspector stack is unavailable")

    existing = stack.get_child_by_name("presets")
    if existing is not None:
        window._turing_presets_page_attached = True
        return

    scroll = Gtk.ScrolledWindow()
    scroll.set_hexpand(True)
    scroll.set_vexpand(True)
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

    page = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=14,
        margin_top=8,
        margin_bottom=8,
        margin_start=4,
        margin_end=4,
    )
    scroll.set_child(page)

    heading = Gtk.Label(label="Presets visuais", xalign=0)
    heading.add_css_class("heading")
    page.append(heading)

    help_label = Gtk.Label(
        label=(
            "Escolha uma combinação pronta para o elemento selecionado. "
            "Textos recebem hierarquia, degradê, contorno externo e brilho; "
            "barras recebem dimensões, acabamento e paleta."
        ),
        xalign=0,
        wrap=True,
    )
    help_label.add_css_class("dim-label")
    page.append(help_label)

    kind_label = Gtk.Label(label="", xalign=0)
    kind_label.add_css_class("caption")
    page.append(kind_label)

    preset_dropdown = Gtk.DropDown.new_from_strings(["Carregando…"])
    preset_dropdown.set_hexpand(True)
    page.append(preset_dropdown)

    description = Gtk.Label(label="", xalign=0, wrap=True)
    description.add_css_class("dim-label")
    page.append(description)

    apply_button = Gtk.Button(label="Aplicar preset ao elemento")
    apply_button.add_css_class("suggested-action")
    page.append(apply_button)

    stack.add_titled(scroll, "presets", "Presets")
    window._turing_presets_page_attached = True

    state: dict[str, tuple[VisualStylePreset, ...]] = {"presets": ()}

    def selected_preset() -> VisualStylePreset | None:
        presets = state["presets"]
        index = int(preset_dropdown.get_selected())
        return presets[index] if 0 <= index < len(presets) else None

    def update_description(*_args) -> None:
        preset = selected_preset()
        description.set_text(preset.description if preset is not None else "")

    def refresh_presets(*_args) -> None:
        style = _selected_style(window)
        kind = style.element_kind if style is not None else "text"
        presets = visual_style_presets(kind)
        state["presets"] = presets
        labels = [preset.label for preset in presets]
        preset_dropdown.set_model(Gtk.StringList.new(labels))
        preset_dropdown.set_selected(0)
        kind_label.set_text(
            "Presets de texto" if kind == "text" else "Presets de barra"
        )
        update_description()
        apply_button.set_sensitive(style is not None and bool(presets))

    def apply_preset(*_args) -> None:
        style = _selected_style(window)
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


def install_style_preset_editor_hook() -> None:
    """Add a dedicated Presets tab once the visual editor is ready."""
    install_outer_text_outline_renderer()

    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import GLib, Gtk

    attempts = 0

    def attach_when_ready() -> bool:
        nonlocal attempts
        attempts += 1
        try:
            application = Gtk.Application.get_default()
            if application is not None:
                for window in application.get_windows():
                    if not all(
                        hasattr(window, attribute)
                        for attribute in (
                            "inspector_stack",
                            "element_dropdown",
                            "element_kind_dropdown",
                            "styles",
                            "backend",
                        )
                    ):
                        continue
                    if not getattr(window, "_loaded_once", False):
                        continue
                    _patch_preview_outline(window)
                    _attach_presets_page(window, Gtk)
                    for style in getattr(window, "styles", {}).values():
                        if style.element_kind == "text" and style.effects_managed:
                            window.backend.evaluate(_preview_outline_script(style))
                    print("Aba Presets anexada ao editor HTML.", flush=True)
                    return False
        except Exception as exc:
            print(f"Falha ao anexar a aba Presets: {exc}", flush=True)

        if attempts >= 600:
            print(
                "A aba Presets não foi anexada porque o editor não concluiu o carregamento.",
                flush=True,
            )
            return False
        return True

    GLib.timeout_add(50, attach_when_ready)
