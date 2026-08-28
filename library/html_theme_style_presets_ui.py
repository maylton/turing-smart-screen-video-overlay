# SPDX-License-Identifier: GPL-3.0-or-later
"""Reliable GTK integration for HTML text, bar, date, and shape presets."""

from __future__ import annotations

import json
from typing import Any

from library.html_theme_decorations import (
    DateFormatOption,
    ShapeOption,
    apply_date_format,
    apply_shape_type,
    date_format_options,
    install_decorative_shape_renderer,
    is_date_style,
    is_shape_style,
    shape_option_for_component,
    shape_options,
    shape_preview_script,
)
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


def _patch_preview_effects(window: Any) -> None:
    window_class = window.__class__
    if getattr(window_class, "_turing_decorative_preview", False):
        return
    original = window_class._apply_style_to_preview

    def apply_style_to_preview(self, style: HtmlVisualElementStyle) -> None:
        original(self, style)
        if is_shape_style(style):
            self.backend.evaluate(shape_preview_script(style))
        elif style.element_kind == "text" and style.effects_managed:
            self.backend.evaluate(_preview_outline_script(style))

    window_class._apply_style_to_preview = apply_style_to_preview
    window_class._turing_decorative_preview = True


def _selected_style(window: Any) -> HtmlVisualElementStyle | None:
    try:
        return window.styles.get(window._selected_id())
    except Exception:
        return None


def _section(Gtk: Any) -> Any:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    box.set_hexpand(True)
    return box


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

    heading = Gtk.Label(label="Presets e variações", xalign=0)
    heading.add_css_class("heading")
    page.append(heading)

    help_label = Gtk.Label(
        label=(
            "As opções abaixo mudam conforme o elemento selecionado. Textos e "
            "barras recebem estilos visuais; datas recebem formatos; formas "
            "podem trocar de geometria sem perder posição, camada ou efeitos."
        ),
        xalign=0,
        wrap=True,
    )
    help_label.add_css_class("dim-label")
    page.append(help_label)

    context_label = Gtk.Label(label="", xalign=0)
    context_label.add_css_class("caption")
    page.append(context_label)

    visual_section = _section(Gtk)
    visual_title = Gtk.Label(label="Estilo visual", xalign=0)
    visual_title.add_css_class("heading")
    visual_section.append(visual_title)
    preset_dropdown = Gtk.DropDown.new_from_strings(["Carregando…"])
    preset_dropdown.set_hexpand(True)
    visual_section.append(preset_dropdown)
    preset_description = Gtk.Label(label="", xalign=0, wrap=True)
    preset_description.add_css_class("dim-label")
    visual_section.append(preset_description)
    apply_preset_button = Gtk.Button(label="Aplicar preset ao elemento")
    apply_preset_button.add_css_class("suggested-action")
    visual_section.append(apply_preset_button)
    page.append(visual_section)

    date_section = _section(Gtk)
    date_section.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
    date_title = Gtk.Label(label="Formato da data", xalign=0)
    date_title.add_css_class("heading")
    date_section.append(date_title)
    date_dropdown = Gtk.DropDown.new_from_strings(
        [option.label for option in date_format_options()]
    )
    date_dropdown.set_hexpand(True)
    date_section.append(date_dropdown)
    date_description = Gtk.Label(label="", xalign=0, wrap=True)
    date_description.add_css_class("dim-label")
    date_section.append(date_description)
    apply_date_button = Gtk.Button(label="Aplicar formato da data")
    apply_date_button.add_css_class("suggested-action")
    date_section.append(apply_date_button)
    page.append(date_section)

    shape_section = _section(Gtk)
    shape_section.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
    shape_title = Gtk.Label(label="Tipo de forma", xalign=0)
    shape_title.add_css_class("heading")
    shape_section.append(shape_title)
    shape_dropdown = Gtk.DropDown.new_from_strings(
        [option.label for option in shape_options()]
    )
    shape_dropdown.set_hexpand(True)
    shape_section.append(shape_dropdown)
    shape_description = Gtk.Label(label="", xalign=0, wrap=True)
    shape_description.add_css_class("dim-label")
    shape_section.append(shape_description)
    apply_shape_button = Gtk.Button(label="Aplicar tipo de forma")
    apply_shape_button.add_css_class("suggested-action")
    shape_section.append(apply_shape_button)
    shape_help = Gtk.Label(
        label=(
            "Depois, use Layout para posicionar/redimensionar e Efeitos para "
            "definir preenchimento, degradê, borda e brilho."
        ),
        xalign=0,
        wrap=True,
    )
    shape_help.add_css_class("dim-label")
    shape_section.append(shape_help)
    page.append(shape_section)

    stack.add_titled(scroll, "presets", "Presets")
    window._turing_presets_page_attached = True

    state: dict[str, tuple[VisualStylePreset, ...]] = {"presets": ()}
    date_values = date_format_options()
    shape_values = shape_options()

    def selected_preset() -> VisualStylePreset | None:
        presets = state["presets"]
        index = int(preset_dropdown.get_selected())
        return presets[index] if 0 <= index < len(presets) else None

    def selected_date_option() -> DateFormatOption:
        index = int(date_dropdown.get_selected())
        return date_values[index] if 0 <= index < len(date_values) else date_values[0]

    def selected_shape_option() -> ShapeOption:
        index = int(shape_dropdown.get_selected())
        return shape_values[index] if 0 <= index < len(shape_values) else shape_values[0]

    def update_preset_description(*_args) -> None:
        preset = selected_preset()
        preset_description.set_text(preset.description if preset is not None else "")

    def update_date_description(*_args) -> None:
        option = selected_date_option()
        date_description.set_text(option.description)

    def update_shape_description(*_args) -> None:
        option = selected_shape_option()
        shape_description.set_text(option.description)

    def set_selected_date(style: HtmlVisualElementStyle) -> None:
        keys = [option.key for option in date_values]
        formatter = style.formatter if style.formatter in keys else "date"
        date_dropdown.set_selected(keys.index(formatter))
        update_date_description()

    def set_selected_shape(style: HtmlVisualElementStyle) -> None:
        current = shape_option_for_component(style.component_type) or shape_values[0]
        keys = [option.key for option in shape_values]
        shape_dropdown.set_selected(keys.index(current.key))
        update_shape_description()

    def refresh_context(*_args) -> None:
        style = _selected_style(window)
        shape = is_shape_style(style)
        date = is_date_style(style)

        shape_section.set_visible(shape)
        date_section.set_visible(date and not shape)
        visual_section.set_visible(not shape)

        if style is None:
            context_label.set_text("Nenhum elemento selecionado")
            apply_preset_button.set_sensitive(False)
            apply_date_button.set_sensitive(False)
            apply_shape_button.set_sensitive(False)
            return

        if shape:
            context_label.set_text("Forma decorativa")
            set_selected_shape(style)
            apply_shape_button.set_sensitive(True)
            return

        kind = style.element_kind
        presets = visual_style_presets(kind)
        state["presets"] = presets
        preset_dropdown.set_model(
            Gtk.StringList.new([preset.label for preset in presets])
        )
        preset_dropdown.set_selected(0)
        update_preset_description()
        apply_preset_button.set_sensitive(bool(presets))
        apply_date_button.set_sensitive(date)
        context_label.set_text(
            "Data" if date else ("Texto" if kind == "text" else "Barra")
        )
        if date:
            set_selected_date(style)

    def finish_structural_update(
        updated: HtmlVisualElementStyle,
        success_message: str,
    ) -> None:
        def synchronized(error: Exception | None) -> None:
            if error is not None:
                window.status_label.set_text(
                    f"Não foi possível atualizar o elemento: {error}"
                )
                window._toast("Falha ao atualizar elemento")
                return
            window._apply_style_to_preview(updated)
            window._apply_preview_snapshot()
            window._load_selected_controls()
            refresh_context()

        window._sync_preview_elements(synchronized)
        window._mark_changed()
        window._update_history_actions()
        window._toast(success_message)

    def apply_preset(*_args) -> None:
        style = _selected_style(window)
        preset = selected_preset()
        if style is None or preset is None or is_shape_style(style):
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

    def apply_date(*_args) -> None:
        style = _selected_style(window)
        if style is None or not is_date_style(style):
            return
        option = selected_date_option()
        try:
            window._checkpoint()
            updated = apply_date_format(style, option.key, window.manifest)
            window.styles[updated.element_id] = updated
            finish_structural_update(
                updated,
                f"Formato de data aplicado: {option.label}",
            )
        except Exception as exc:
            window.status_label.set_text(
                f"Não foi possível trocar o formato da data: {exc}"
            )
            window._toast("Falha ao trocar formato da data")

    def apply_shape(*_args) -> None:
        style = _selected_style(window)
        if style is None or not is_shape_style(style):
            return
        option = selected_shape_option()
        try:
            window._checkpoint()
            updated = apply_shape_type(style, option.key, window.manifest)
            window.styles[updated.element_id] = updated
            finish_structural_update(
                updated,
                f"Forma alterada para {option.label}",
            )
        except Exception as exc:
            window.status_label.set_text(
                f"Não foi possível trocar o tipo de forma: {exc}"
            )
            window._toast("Falha ao trocar tipo de forma")

    preset_dropdown.connect("notify::selected", update_preset_description)
    date_dropdown.connect("notify::selected", update_date_description)
    shape_dropdown.connect("notify::selected", update_shape_description)
    apply_preset_button.connect("clicked", apply_preset)
    apply_date_button.connect("clicked", apply_date)
    apply_shape_button.connect("clicked", apply_shape)
    window.element_dropdown.connect("notify::selected", refresh_context)
    window.element_kind_dropdown.connect("notify::selected", refresh_context)
    refresh_context()


def install_style_preset_editor_hook() -> None:
    """Add a dedicated contextual Presets tab once the editor is ready."""
    install_outer_text_outline_renderer()
    install_decorative_shape_renderer()

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
                    _patch_preview_effects(window)
                    _attach_presets_page(window, Gtk)
                    for style in getattr(window, "styles", {}).values():
                        if is_shape_style(style):
                            window.backend.evaluate(shape_preview_script(style))
                        elif style.element_kind == "text" and style.effects_managed:
                            window.backend.evaluate(_preview_outline_script(style))
                    print(
                        "Aba Presets anexada com formatos de data e formas.",
                        flush=True,
                    )
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
