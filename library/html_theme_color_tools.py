# SPDX-License-Identifier: GPL-3.0-or-later
"""Inline native color pickers and preview-derived palettes for the HTML editor."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Any
from urllib.parse import unquote


PICK_TITLE_PREFIX = "turing-editor-color-pick:"
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def normalize_hex(value: str, fallback: str = "#ffffff") -> str:
    value = str(value or "").strip()
    return value.lower() if _HEX_COLOR.fullmatch(value) else fallback


def hex_channels(value: str) -> tuple[int, int, int]:
    value = normalize_hex(value)
    return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))


def relative_luminance(value: str) -> float:
    converted = []
    for channel in hex_channels(value):
        normalized = channel / 255.0
        converted.append(
            normalized / 12.92
            if normalized <= 0.04045
            else ((normalized + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * converted[0] + 0.7152 * converted[1] + 0.0722 * converted[2]


def color_saturation(value: str) -> float:
    channels = [channel / 255.0 for channel in hex_channels(value)]
    maximum = max(channels)
    minimum = min(channels)
    return 0.0 if maximum == 0 else (maximum - minimum) / maximum


def color_distance(first: str, second: str) -> int:
    left = hex_channels(first)
    right = hex_channels(second)
    return sum((a - b) ** 2 for a, b in zip(left, right))


def smart_palette(values: tuple[str, ...] | list[str]) -> dict[str, str]:
    colors = tuple(dict.fromkeys(normalize_hex(value) for value in values))
    if not colors:
        colors = ("#18131f", "#ffffff", "#b388ff", "#ff8bd7")

    darkest = min(colors, key=relative_luminance)
    lightest = max(colors, key=relative_luminance)
    dominant = colors[0]
    main = lightest if relative_luminance(dominant) < 0.45 else darkest
    outline = darkest if main == lightest else lightest
    saturated = sorted(
        colors,
        key=lambda color: (color_saturation(color), color_distance(color, dominant)),
        reverse=True,
    )
    accent_one = saturated[0]
    accent_two = next(
        (
            color
            for color in saturated[1:]
            if color_distance(color, accent_one) >= 32**2
        ),
        lightest if accent_one != lightest else darkest,
    )
    return {
        "main": main,
        "gradient_start": accent_one,
        "gradient_end": accent_two,
        "outline": outline,
        "glow": accent_one,
    }


def preview_picker_script() -> str:
    """Return a one-shot click sampler for the visible preview."""
    prefix = json.dumps(PICK_TITLE_PREFIX)
    return f"""
    (() => {{
      window.__turingCancelColorPick?.();
      const prefix = {prefix};
      const root = document.documentElement;
      const oldCursor = root.style.getPropertyValue('cursor');
      const oldPriority = root.style.getPropertyPriority('cursor');
      let active = true;
      const hex = (r, g, b) => '#' + [r, g, b].map(value =>
        Math.max(0, Math.min(255, Math.round(value))).toString(16).padStart(2, '0')
      ).join('');
      const emit = payload => {{
        payload.nonce = performance.now();
        document.title = prefix + encodeURIComponent(JSON.stringify(payload));
      }};
      const cleanup = () => {{
        if (!active) return;
        active = false;
        document.removeEventListener('click', pick, true);
        document.removeEventListener('keydown', escape, true);
        if (oldCursor) root.style.setProperty('cursor', oldCursor, oldPriority);
        else root.style.removeProperty('cursor');
        delete window.__turingCancelColorPick;
      }};
      const fraction = value => {{
        const text = String(value || '').toLowerCase();
        if (text === 'left' || text === 'top') return 0;
        if (text === 'right' || text === 'bottom') return 1;
        if (text === 'center') return 0.5;
        const match = text.match(/^(-?[\\d.]+)%$/);
        return match ? Number(match[1]) / 100 : 0.5;
      }};
      const sampleImage = (image, clientX, clientY) => {{
        if (!image?.complete || !image.naturalWidth || !image.naturalHeight) return null;
        const rect = image.getBoundingClientRect();
        if (clientX < rect.left || clientX > rect.right || clientY < rect.top || clientY > rect.bottom)
          return null;
        const style = getComputedStyle(image);
        const fit = style.objectFit || 'fill';
        const position = String(style.objectPosition || '50% 50%').split(/\\s+/);
        const px = fraction(position[0] || '50%');
        const py = fraction(position[1] || position[0] || '50%');
        let scaleX = rect.width / image.naturalWidth;
        let scaleY = rect.height / image.naturalHeight;
        let width = rect.width;
        let height = rect.height;
        if (fit !== 'fill') {{
          const scale = fit === 'cover'
            ? Math.max(scaleX, scaleY)
            : Math.min(scaleX, scaleY);
          scaleX = scale;
          scaleY = scale;
          width = image.naturalWidth * scale;
          height = image.naturalHeight * scale;
        }}
        const offsetX = (rect.width - width) * px;
        const offsetY = (rect.height - height) * py;
        const x = clientX - rect.left - offsetX;
        const y = clientY - rect.top - offsetY;
        if (x < 0 || y < 0 || x >= width || y >= height) return null;
        const sourceX = Math.max(0, Math.min(image.naturalWidth - 1, Math.floor(x / scaleX)));
        const sourceY = Math.max(0, Math.min(image.naturalHeight - 1, Math.floor(y / scaleY)));
        const canvas = document.createElement('canvas');
        canvas.width = 1;
        canvas.height = 1;
        const context = canvas.getContext('2d', {{willReadFrequently: true}});
        context.drawImage(image, sourceX, sourceY, 1, 1, 0, 0, 1, 1);
        const pixel = context.getImageData(0, 0, 1, 1).data;
        return pixel[3] < 16 ? null : hex(pixel[0], pixel[1], pixel[2]);
      }};
      const parseCss = value => {{
        const match = String(value || '').match(
          /rgba?\\(\\s*([\\d.]+)[, ]+\\s*([\\d.]+)[, ]+\\s*([\\d.]+)(?:\\s*[,/]\\s*([\\d.]+))?/i
        );
        if (!match || (match[4] !== undefined && Number(match[4]) <= 0.02)) return null;
        return hex(Number(match[1]), Number(match[2]), Number(match[3]));
      }};
      const pick = event => {{
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
        let color = null;
        try {{
          const preferred = document.getElementById('__turing-background-preview');
          const images = preferred
            ? [preferred, ...Array.from(document.images).filter(item => item !== preferred)]
            : Array.from(document.images);
          for (const image of images) {{
            color = sampleImage(image, event.clientX, event.clientY);
            if (color) break;
          }}
          if (!color) {{
            for (const element of document.elementsFromPoint(event.clientX, event.clientY)) {{
              if (element.id === '__turing-editor-selection') continue;
              const style = getComputedStyle(element);
              color = parseCss(style.backgroundColor) || parseCss(style.borderTopColor) || parseCss(style.color);
              if (color) break;
            }}
          }}
        }} catch (error) {{
          cleanup();
          emit({{ok: false, error: String(error)}});
          return;
        }}
        cleanup();
        emit(color
          ? {{ok: true, color}}
          : {{ok: false, error: 'Não foi possível identificar uma cor nesse ponto'}});
      }};
      const escape = event => {{
        if (event.key !== 'Escape') return;
        cleanup();
        emit({{ok: false, cancelled: true}});
      }};
      window.__turingCancelColorPick = cleanup;
      root.style.setProperty('cursor', 'crosshair', 'important');
      document.addEventListener('click', pick, true);
      document.addEventListener('keydown', escape, true);
    }})();
    """


def preview_palette_script() -> str:
    """Return a synchronous script that extracts up to eight preview colors."""
    return r"""
    (() => {
      const hex = (r, g, b) => '#' + [r, g, b].map(value =>
        Math.max(0, Math.min(255, Math.round(value))).toString(16).padStart(2, '0')
      ).join('');
      const counts = new Map();
      const add = (r, g, b, weight = 1) => {
        const quantize = value => Math.max(0, Math.min(255, Math.round(value / 24) * 24));
        const color = hex(quantize(r), quantize(g), quantize(b));
        counts.set(color, (counts.get(color) || 0) + weight);
      };
      const parseCss = value => {
        const match = String(value || '').match(
          /rgba?\(\s*([\d.]+)[, ]+\s*([\d.]+)[, ]+\s*([\d.]+)(?:\s*[,/]\s*([\d.]+))?/i
        );
        if (!match || (match[4] !== undefined && Number(match[4]) <= 0.05)) return null;
        return [Number(match[1]), Number(match[2]), Number(match[3])];
      };
      const collectImage = image => {
        if (!image?.complete || !image.naturalWidth || !image.naturalHeight) return false;
        const size = 56;
        const canvas = document.createElement('canvas');
        canvas.width = size;
        canvas.height = size;
        const context = canvas.getContext('2d', {willReadFrequently: true});
        try {
          context.drawImage(image, 0, 0, size, size);
          const pixels = context.getImageData(0, 0, size, size).data;
          for (let index = 0; index < pixels.length; index += 4) {
            if (pixels[index + 3] < 80) continue;
            add(pixels[index], pixels[index + 1], pixels[index + 2], 2);
          }
          return true;
        } catch (_error) {
          return false;
        }
      };
      const preferred = document.getElementById('__turing-background-preview');
      const images = preferred
        ? [preferred, ...Array.from(document.images).filter(item => item !== preferred)]
        : Array.from(document.images);
      let sampledImage = false;
      for (const image of images.slice(0, 5)) sampledImage = collectImage(image) || sampledImage;
      for (const element of Array.from(document.querySelectorAll('*')).slice(0, 600)) {
        if (element.id === '__turing-editor-selection') continue;
        const style = getComputedStyle(element);
        for (const value of [style.color, style.backgroundColor, style.borderTopColor]) {
          const channels = parseCss(value);
          if (channels) add(channels[0], channels[1], channels[2], 5);
        }
      }
      const channels = color => [1, 3, 5].map(index => parseInt(color.slice(index, index + 2), 16));
      const distance = (first, second) => {
        const a = channels(first);
        const b = channels(second);
        return a.reduce((sum, value, index) => sum + (value - b[index]) ** 2, 0);
      };
      const colors = [];
      for (const [color] of Array.from(counts.entries()).sort((a, b) => b[1] - a[1])) {
        if (colors.every(existing => distance(existing, color) >= 30 ** 2)) colors.push(color);
        if (colors.length >= 8) break;
      }
      return {ok: colors.length > 0, colors, sampledImage};
    })()
    """


def _rgba_to_hex(rgba: Any) -> str:
    return "#{:02x}{:02x}{:02x}".format(
        round(float(rgba.red) * 255),
        round(float(rgba.green) * 255),
        round(float(rgba.blue) * 255),
    )


def _set_entry(entry: Any, color: str) -> None:
    color = normalize_hex(color)
    if entry.get_text().strip().lower() != color:
        entry.set_text(color)


def _attach(window: Any, Gtk: Any, Gdk: Any, GLib: Any) -> None:
    if getattr(window, "_turing_inline_colors_attached", False):
        return
    window._turing_inline_colors_attached = True

    fields = (
        (window.color_entry, "Cor principal", "style"),
        (window.gradient_start_entry, "Início do degradê", "effects"),
        (window.gradient_end_entry, "Fim do degradê", "effects"),
        (window.outline_color_entry, "Cor do contorno", "effects"),
        (window.glow_color_entry, "Cor do brilho", "effects"),
    )
    field_by_entry = {entry: (label, page) for entry, label, page in fields}
    active = {"entry": window.color_entry, "label": "Cor principal"}
    palette_state = {"colors": ()}
    target_labels: list[Any] = []
    palette_flows: list[Any] = []

    def toast(message: str) -> None:
        callback = getattr(window, "_toast", None)
        if callable(callback):
            callback(message)

    def select_target(entry: Any) -> None:
        label, _page = field_by_entry[entry]
        active["entry"] = entry
        active["label"] = label
        for target in target_labels:
            target.set_text(f"Aplicar em: {label}")

    def native_button(entry: Any, label: str) -> Any:
        rgba = Gdk.RGBA()
        rgba.parse(normalize_hex(entry.get_text()))
        button = Gtk.ColorButton.new_with_rgba(rgba)
        button.set_use_alpha(False)
        button.set_title(label)
        button.set_tooltip_text(f"Abrir seletor para {label.lower()}")

        def selected(*_args) -> None:
            select_target(entry)
            _set_entry(entry, _rgba_to_hex(button.get_rgba()))

        def sync(*_args) -> None:
            value = normalize_hex(entry.get_text(), "")
            if not value:
                return
            current = Gdk.RGBA()
            current.parse(value)
            button.set_rgba(current)

        button.connect("color-set", selected)
        entry.connect("changed", sync)
        return button

    def start_picker(entry: Any) -> None:
        select_target(entry)
        window.backend.evaluate(preview_picker_script())
        toast("Clique em uma cor na prévia; Esc cancela")

    for entry, label, _page in fields:
        field_box = entry.get_parent()
        if field_box is None:
            continue
        field_box.remove(entry)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row.set_hexpand(True)
        entry.set_hexpand(True)
        row.append(entry)
        row.append(native_button(entry, label))
        pick_button = Gtk.Button(label="Da prévia")
        pick_button.set_tooltip_text(f"Capturar {label.lower()} da imagem na prévia")
        pick_button.connect("clicked", lambda _button, selected=entry: start_picker(selected))
        row.append(pick_button)
        field_box.append(row)
        entry.connect(
            "notify::has-focus",
            lambda selected, _param, target=entry: select_target(target)
            if selected.has_focus()
            else None,
        )

    def title_changed(view: Any, _param: Any) -> None:
        title = str(view.get_title() or "")
        if not title.startswith(PICK_TITLE_PREFIX):
            return
        try:
            payload = json.loads(unquote(title[len(PICK_TITLE_PREFIX) :]))
        except Exception as exc:
            toast(f"Resposta inválida do conta-gotas: {exc}")
            return
        if payload.get("ok") and payload.get("color"):
            _set_entry(active["entry"], str(payload["color"]))
            toast(f"{active['label']}: {normalize_hex(payload['color'])}")
        elif not payload.get("cancelled"):
            toast(str(payload.get("error") or "Não foi possível capturar a cor"))

    window.backend.view.connect("notify::title", title_changed)

    def clear_flow(flow: Any) -> None:
        child = flow.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            flow.remove(child)
            child = following

    def draw_swatch(_area: Any, context: Any, width: int, height: int, color: str) -> None:
        rgba = Gdk.RGBA()
        rgba.parse(color)
        context.set_source_rgba(rgba.red, rgba.green, rgba.blue, 1.0)
        context.rectangle(1, 1, max(1, width - 2), max(1, height - 2))
        context.fill_preserve()
        context.set_source_rgba(1, 1, 1, 0.55 if relative_luminance(color) < 0.5 else 0.2)
        context.set_line_width(1)
        context.stroke()

    def refresh_swatches() -> None:
        for flow in palette_flows:
            clear_flow(flow)
            for color in palette_state["colors"]:
                button = Gtk.Button()
                button.set_tooltip_text(f"Aplicar {color} em {active['label']}")
                area = Gtk.DrawingArea()
                area.set_content_width(36)
                area.set_content_height(26)
                area.set_draw_func(
                    lambda widget, context, width, height, selected=color: draw_swatch(
                        widget, context, width, height, selected
                    )
                )
                button.set_child(area)
                button.connect(
                    "clicked",
                    lambda _button, selected=color: _set_entry(active["entry"], selected),
                )
                flow.append(button)

    def receive_palette(payload: Any, error: Exception | None) -> None:
        if error is not None:
            toast(f"Não foi possível analisar as cores: {error}")
            return
        colors = tuple(
            normalize_hex(color)
            for color in (payload or {}).get("colors", ())
            if _HEX_COLOR.fullmatch(str(color or ""))
        )
        if not colors:
            toast("A prévia não forneceu cores suficientes")
            return
        palette_state["colors"] = tuple(dict.fromkeys(colors))[:8]
        refresh_swatches()
        toast("Paleta atualizada a partir da prévia")

    def refresh_palette(*_args) -> bool:
        if not getattr(window, "_loaded_once", False):
            return False
        window._evaluate_json(preview_palette_script(), receive_palette)
        return False

    def apply_palette(*_args) -> None:
        colors = palette_state["colors"]
        if not colors:
            refresh_palette()
            toast("A paleta está sendo gerada; clique novamente para aplicar")
            return
        try:
            element_id = window._selected_id()
            previous = window.styles[element_id]
            values = smart_palette(colors)
            window._checkpoint()
            updated = replace(
                previous,
                color=values["main"],
                effects_managed=True,
                gradient_start_color=values["gradient_start"],
                gradient_end_color=values["gradient_end"],
                outline_color=values["outline"],
                glow_color=values["glow"],
            ).validated(window.manifest)
            window.styles[element_id] = updated
            window._apply_style_to_preview(updated)
            window._load_selected_controls()
            window._mark_changed()
            window._update_history_actions()
            toast("Cores automáticas aplicadas ao elemento")
        except Exception as exc:
            toast(f"Não foi possível aplicar a paleta: {exc}")

    def add_palette_expander(page: Any, default_entry: Any, label: str) -> None:
        expander = Gtk.Expander(label="Cores do tema")
        expander.set_expanded(False)
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            margin_top=8,
            margin_bottom=8,
            margin_start=8,
            margin_end=8,
        )
        description = Gtk.Label(
            label=(
                "Gere amostras da imagem visível na prévia. Clique numa cor para "
                "aplicá-la ao campo ativo."
            ),
            xalign=0,
            wrap=True,
        )
        description.add_css_class("dim-label")
        box.append(description)
        target = Gtk.Label(label=f"Aplicar em: {label}", xalign=0)
        target.add_css_class("caption")
        target_labels.append(target)
        box.append(target)
        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_max_children_per_line(8)
        flow.set_row_spacing(4)
        flow.set_column_spacing(4)
        palette_flows.append(flow)
        box.append(flow)
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        generate = Gtk.Button(label="Gerar da prévia")
        generate.connect("clicked", refresh_palette)
        apply = Gtk.Button(label="Aplicar combinação")
        apply.add_css_class("suggested-action")
        apply.connect("clicked", apply_palette)
        actions.append(generate)
        actions.append(apply)
        box.append(actions)
        expander.set_child(box)
        page.append(expander)
        expander.connect(
            "notify::expanded",
            lambda item, _param, selected=default_entry: (
                select_target(selected),
                refresh_palette(),
            )
            if item.get_expanded()
            else None,
        )

    style_page = window.color_entry.get_parent().get_parent().get_parent()
    effects_page = window.gradient_start_entry.get_parent().get_parent().get_parent()
    add_palette_expander(style_page, window.color_entry, "Cor principal")
    add_palette_expander(effects_page, window.gradient_start_entry, "Início do degradê")
    window._turing_refresh_theme_palette = refresh_palette
    GLib.timeout_add(450, refresh_palette)
    print("Seletores de cor inline e paleta da prévia anexados.", flush=True)


def install_color_tools_hook() -> None:
    """Attach color controls only inside the existing Style and Effects pages."""
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gdk, GLib, Gtk

    attempts = 0

    def attach_when_ready() -> bool:
        nonlocal attempts
        attempts += 1
        application = Gtk.Application.get_default()
        if application is not None:
            for window in application.get_windows():
                required = (
                    "color_entry",
                    "gradient_start_entry",
                    "gradient_end_entry",
                    "outline_color_entry",
                    "glow_color_entry",
                    "backend",
                    "styles",
                )
                if all(hasattr(window, name) for name in required) and getattr(
                    window, "_loaded_once", False
                ):
                    try:
                        _attach(window, Gtk, Gdk, GLib)
                    except Exception as exc:
                        print(f"Falha ao anexar seletores de cor: {exc}", flush=True)
                    return False
        if attempts >= 600:
            print("Os seletores de cor não foram anexados: editor não ficou pronto.", flush=True)
            return False
        return True

    GLib.timeout_add(50, attach_when_ready)
