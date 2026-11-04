#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Simple visual editor for local HTML themes."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from urllib.parse import unquote

os.environ.setdefault("GSK_RENDERER", "gl")
os.environ.setdefault("WEBKIT_DISABLE_DMABUF_RENDERER", "1")

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, WebKit

from library.html_theme_authoring import discover_overlay_candidates
from library.html_theme_components import (
    html_widget_components,
    next_widget_id,
    render_widget_runtime_script,
)
from library.html_theme_engine import WebKitGtkBackend, build_snapshot_script
from library.html_editor_drafts import clear_draft, load_draft, write_draft
from library.live_display_reload import active_html_theme, request_monitor_reload
from library.html_editor_preview_data import (
    CUSTOM_FIELDS,
    PRESET_KEYS,
    PRESET_LABELS,
    binding_value,
    custom_data,
    format_field_value,
    preset_data,
)
from library.html_editor_rulers import (
    RULER_THICKNESS_PX,
    cursor_position,
    ruler_ticks,
    selection_span,
)
from library.html_editor_zoom import DEFAULT_ZOOM, step_zoom, zoom_label, zoomed_size
from library.html_theme_round_mask import is_probably_round, round_mask_script
from library.html_theme_visual_editor import (
    HtmlVisualElementStyle,
    VisualStyleHistory,
    align_visual_group,
    duplicate_visual_style,
    find_visual_slot,
    load_persisted_visual_element_ids,
    load_visual_styles,
    move_visual_group,
    nudge_visual_style,
    place_visual_style,
    resize_visual_style,
    save_visual_styles,
)
from library.runtime_python import resolve_project_python
from library.sensor_snapshot import SensorSnapshot
from library.theme_engine import ThemeManifest, ThemeValidationError
from library.theme_gallery import (
    ThemeRecord,
    export_theme,
    import_theme,
    show_export_theme_dialog,
    show_import_theme_dialog,
)


ROOT = Path(__file__).resolve().parent
THEMES_DIR = ROOT / "res" / "themes"
CONFIG_FILE = ROOT / "config.yaml"
BUILD_SCRIPT = ROOT / "html-theme-build-video.py"
SELECT_TITLE_PREFIX = "turing-editor-select:"
DRAG_TITLE_PREFIX = "turing-editor-drag:"
RESIZE_TITLE_PREFIX = "turing-editor-resize:"
NUDGE_TITLE_PREFIX = "turing-editor-nudge:"
GROUP_TITLE_PREFIX = "turing-editor-group:"
INSPECTOR_WIDTH = 420
PREVIEW_FRAME_BORDER_PX = 1
PREVIEW_REPAINT_DELAYS_MS = (250, 1000)
DRAFT_DELAY_SECONDS = 2
DUPLICATE_AUTHOR_ELEMENT_HINT = (
    "Este elemento faz parte do HTML do tema; só elementos adicionados no editor podem ser duplicados"
)


def _color_to_hex(value: str) -> str:
    value = str(value or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return value.lower()
    match = re.match(
        r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)",
        value,
        re.IGNORECASE,
    )
    if match:
        channels = [max(0, min(255, int(item))) for item in match.groups()]
        return "#" + "".join(f"{channel:02x}" for channel in channels)
    return "#ffffff"


def _preview_snapshot(preset: str = "normal", data: dict | None = None) -> SensorSnapshot:
    if data is None:
        data = preset_data(preset)
    return SensorSnapshot(
        schema_version=1,
        timestamp=time.time(),
        sequence=1,
        data=data,
        errors={},
    )


class PreviewRuler(Gtk.DrawingArea):
    """Ruler along one edge of the preview, in theme pixels.

    Shows ticks for the current zoom, a band over the selected element(s)
    and a marker at the cursor.
    """

    def __init__(self, orientation: Gtk.Orientation, length: int):
        super().__init__()
        self.horizontal = orientation == Gtk.Orientation.HORIZONTAL
        self.length = int(length)
        self.zoom = 1.0
        self.cursor: int | None = None
        self.span: tuple[int, int] | None = None
        self.add_css_class("turing-preview-ruler")
        self.set_draw_func(self._draw)
        self.set_zoom(1.0)

    def set_zoom(self, zoom: float) -> None:
        self.zoom = zoom
        size = round(self.length * zoom)
        if self.horizontal:
            self.set_content_width(size)
            self.set_content_height(RULER_THICKNESS_PX)
        else:
            self.set_content_width(RULER_THICKNESS_PX)
            self.set_content_height(size)
        self.queue_draw()

    def set_cursor(self, position: int | None) -> None:
        if position != self.cursor:
            self.cursor = position
            self.queue_draw()

    def set_span(self, span: tuple[int, int] | None) -> None:
        if span != self.span:
            self.span = span
            self.queue_draw()

    def _draw(self, _area, cr, width: int, height: int) -> None:
        color = self.get_color()
        fg = (color.red, color.green, color.blue)
        thickness = height if self.horizontal else width
        cr.set_source_rgba(*fg, 0.06)
        cr.paint()
        if self.span is not None:
            start, end = (round(v * self.zoom) for v in self.span)
            cr.set_source_rgba(0.4, 0.88, 1.0, 0.28)
            if self.horizontal:
                cr.rectangle(start, 0, max(1, end - start), height)
            else:
                cr.rectangle(0, start, width, max(1, end - start))
            cr.fill()
        cr.set_line_width(1)
        cr.select_font_face("monospace")
        cr.set_font_size(9)
        for tick in ruler_ticks(self.length, self.zoom):
            offset = round(tick.position * self.zoom) + 0.5
            mark = thickness * (0.55 if tick.major else 0.25)
            cr.set_source_rgba(*fg, 0.65 if tick.major else 0.35)
            if self.horizontal:
                cr.move_to(offset, height)
                cr.line_to(offset, height - mark)
            else:
                cr.move_to(width, offset)
                cr.line_to(width - mark, offset)
            cr.stroke()
            if tick.label:
                cr.set_source_rgba(*fg, 0.75)
                if self.horizontal:
                    cr.move_to(offset + 2, 9)
                    cr.show_text(tick.label)
                else:
                    cr.save()
                    cr.translate(9, offset - 2)
                    cr.rotate(-1.5707963)
                    cr.move_to(0, 0)
                    cr.show_text(tick.label)
                    cr.restore()
        if self.cursor is not None:
            offset = round(self.cursor * self.zoom) + 0.5
            cr.set_source_rgba(1.0, 0.45, 0.3, 0.95)
            cr.set_line_width(1.5)
            if self.horizontal:
                cr.move_to(offset, 0)
                cr.line_to(offset, height)
            else:
                cr.move_to(0, offset)
                cr.line_to(width, offset)
            cr.stroke()


class PreviewFrame(Gtk.Frame):
    """Frame whose natural size is its minimum, i.e. the zoomed preview.

    WebKitWebView keeps reporting the largest size it has been given as its
    natural size, so after zooming out the frame would stay stretched.
    """

    def do_measure(self, orientation, for_size):
        minimum, _natural, _min_baseline, _nat_baseline = Gtk.Frame.do_measure(self, orientation, for_size)
        return minimum, minimum, -1, -1


class HtmlThemeEditorWindow(Adw.ApplicationWindow):
    def __init__(self, application: Adw.Application, manifest: ThemeManifest):
        super().__init__(application=application)
        self.manifest = manifest
        self.candidates = tuple(
            candidate
            for candidate in discover_overlay_candidates(manifest)
            if candidate.marked
        )
        if not self.candidates:
            raise ThemeValidationError("o tema não possui overlays editáveis")
        self.element_ids = list(load_persisted_visual_element_ids(manifest))
        self.component_catalog = html_widget_components()
        self.styles: dict[str, HtmlVisualElementStyle] = {}
        self.history = VisualStyleHistory(limit=100)
        self._updating_controls = False
        self._loaded_once = False
        self._drag_active = False
        self._resize_active = False
        self._dirty = False
        self._build_process: subprocess.Popen[str] | None = None
        self._draft_source: int | None = None
        # Elements selected together with the primary one (Shift+click).
        self.group_ids: list[str] = []
        self._draft_offered = False
        self._close_confirmed = False

        self.set_title(f"Editor HTML — {manifest.name}")
        self.set_default_size(1120, 720)
        self.set_size_request(960, 620)
        self.connect("close-request", self._on_close_request)

        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)
        toolbar = Adw.ToolbarView()
        self.toast_overlay.set_child(toolbar)

        header = Adw.HeaderBar()
        header.set_title_widget(
            Adw.WindowTitle(
                title="Editor visual de tema HTML",
                subtitle=manifest.root.name,
            )
        )
        self.undo_action = Gio.SimpleAction.new("undo", None)
        self.undo_action.connect("activate", lambda *_: self._undo())
        self.undo_action.set_enabled(False)
        self.add_action(self.undo_action)
        self.redo_action = Gio.SimpleAction.new("redo", None)
        self.redo_action.connect("activate", lambda *_: self._redo())
        self.redo_action.set_enabled(False)
        self.add_action(self.redo_action)
        application.set_accels_for_action("win.undo", ["<Primary>z"])
        application.set_accels_for_action(
            "win.redo",
            ["<Primary><Shift>z", "<Primary>y"],
        )
        save_action = Gio.SimpleAction.new("save", None)
        save_action.connect("activate", lambda *_: self._on_save_shortcut())
        self.add_action(save_action)
        application.set_accels_for_action("win.save", ["<Primary>s"])
        self.duplicate_action = Gio.SimpleAction.new("duplicate", None)
        self.duplicate_action.connect("activate", lambda *_: self._on_duplicate_element())
        # Always enabled so Ctrl+D can explain why an element was not copied.
        self.add_action(self.duplicate_action)
        application.set_accels_for_action("win.duplicate", ["<Primary>d"])
        self.preview_zoom = DEFAULT_ZOOM
        for name, direction, accels in (
            ("zoom-in", +1, ["<Primary>plus", "<Primary>equal", "<Primary>KP_Add"]),
            ("zoom-out", -1, ["<Primary>minus", "<Primary>KP_Subtract"]),
            ("zoom-reset", 0, ["<Primary>0", "<Primary>KP_0"]),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda *_a, d=direction: self._step_preview_zoom(d))
            self.add_action(action)
            application.set_accels_for_action(f"win.{name}", accels)
        undo_button = Gtk.Button(icon_name="edit-undo-symbolic", tooltip_text="Desfazer")
        undo_button.set_action_name("win.undo")
        header.pack_start(undo_button)
        redo_button = Gtk.Button(icon_name="edit-redo-symbolic", tooltip_text="Refazer")
        redo_button.set_action_name("win.redo")
        header.pack_start(redo_button)

        zoom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        zoom_box.add_css_class("linked")
        zoom_out_button = Gtk.Button(icon_name="zoom-out-symbolic", tooltip_text="Diminuir zoom (Ctrl+−)")
        zoom_out_button.set_action_name("win.zoom-out")
        zoom_box.append(zoom_out_button)
        self.zoom_reset_button = Gtk.Button(label=zoom_label(DEFAULT_ZOOM), tooltip_text="Tamanho real (Ctrl+0)")
        self.zoom_reset_button.set_action_name("win.zoom-reset")
        zoom_box.append(self.zoom_reset_button)
        zoom_in_button = Gtk.Button(icon_name="zoom-in-symbolic", tooltip_text="Aumentar zoom (Ctrl++)")
        zoom_in_button.set_action_name("win.zoom-in")
        zoom_box.append(zoom_in_button)
        header.pack_start(zoom_box)
        # Theme pixel under the cursor; empty outside the preview.
        self.cursor_label = Gtk.Label(width_chars=15, xalign=0)
        self.cursor_label.add_css_class("dim-label")
        self.cursor_label.add_css_class("numeric")
        header.pack_start(self.cursor_label)
        import_button = Gtk.Button(label="Importar tema")
        import_button.set_tooltip_text("Importar pacote .theme ou .zip")
        import_button.connect("clicked", self._on_import_theme)
        header.pack_end(import_button)
        export_button = Gtk.Button(label="Exportar tema")
        export_button.set_tooltip_text("Salvar o tema atual como um pacote .theme")
        export_button.connect("clicked", self._on_export_theme)
        header.pack_end(export_button)
        toolbar.add_top_bar(header)

        body = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=18,
            margin_top=18,
            margin_bottom=18,
            margin_start=18,
            margin_end=18,
        )
        toolbar.set_content(body)

        # The preview scrolls when zoomed past the space left by the inspector.
        self.preview_scroller = Gtk.ScrolledWindow()
        self.preview_scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        # The canvas takes the free space; the inspector keeps its width.
        self.preview_scroller.set_hexpand(True)
        self.preview_scroller.set_vexpand(True)
        zoom_scroll = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
        zoom_scroll.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        zoom_scroll.connect("scroll", self._on_preview_scroll)
        self.preview_scroller.add_controller(zoom_scroll)
        body.append(self.preview_scroller)

        preview_frame = PreviewFrame()
        preview_frame.set_halign(Gtk.Align.CENTER)
        preview_frame.set_valign(Gtk.Align.CENTER)
        preview_frame.set_size_request(manifest.width, manifest.height)
        self.preview_frame = preview_frame
        # The scrolled viewport stretches its child; the center box keeps the
        # frame at the preview size and centered when zoomed out.
        # Rulers sit beside the frame, offset by its border so 0 lines up
        # with the first theme pixel.
        border = PREVIEW_FRAME_BORDER_PX
        self.top_ruler = PreviewRuler(Gtk.Orientation.HORIZONTAL, manifest.width)
        self.top_ruler.set_margin_start(border)
        self.left_ruler = PreviewRuler(Gtk.Orientation.VERTICAL, manifest.height)
        self.left_ruler.set_margin_top(border)
        for ruler in (self.top_ruler, self.left_ruler):
            ruler.set_halign(Gtk.Align.START)
            ruler.set_valign(Gtk.Align.START)
        preview_grid = Gtk.Grid()
        preview_grid.attach(self.top_ruler, 1, 0, 1, 1)
        preview_grid.attach(self.left_ruler, 0, 1, 1, 1)
        preview_grid.attach(preview_frame, 1, 1, 1, 1)
        preview_center = Gtk.CenterBox()
        preview_center.set_center_widget(preview_grid)
        self.preview_scroller.set_child(preview_center)
        self._sync_preview_scroller_size(manifest.width, manifest.height)

        self.backend = WebKitGtkBackend(manifest)
        self.backend.set_transparent_background()
        settings = self.backend.view.get_settings()
        policy = getattr(WebKit, "HardwareAccelerationPolicy", None)
        never = getattr(policy, "NEVER", None)
        setter = getattr(settings, "set_hardware_acceleration_policy", None)
        if callable(setter) and never is not None:
            setter(never)
        for setter_name in ("set_enable_webgl", "set_enable_accelerated_2d_canvas"):
            feature_setter = getattr(settings, setter_name, None)
            if callable(feature_setter):
                feature_setter(False)
        self.backend.view.set_size_request(manifest.width, manifest.height)
        self.backend.view.connect("load-changed", self._on_preview_load_changed)
        self.backend.view.connect("notify::title", self._on_preview_title_changed)
        preview_frame.set_child(self.backend.view)
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_preview_motion)
        motion.connect("leave", self._on_preview_leave)
        self.backend.view.add_controller(motion)

        inspector_panel = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
            margin_top=4,
            margin_bottom=8,
            margin_start=4,
            margin_end=4,
        )
        inspector_panel.set_vexpand(True)
        # The clamp caps the inspector's natural width (long help labels would
        # otherwise claim the space the canvas needs).
        inspector_clamp = Adw.Clamp(maximum_size=INSPECTOR_WIDTH, tightening_threshold=INSPECTOR_WIDTH)
        inspector_clamp.set_size_request(INSPECTOR_WIDTH, -1)
        inspector_clamp.set_hexpand(False)
        inspector_clamp.set_child(inspector_panel)
        body.append(inspector_clamp)

        self.element_model = Gtk.StringList.new(self.element_ids)
        self.element_dropdown = Gtk.DropDown(model=self.element_model)
        self.element_dropdown.set_hexpand(True)
        self.element_dropdown.connect("notify::selected", self._on_element_selected)
        inspector_panel.append(
            self._field("Elemento selecionado", self.element_dropdown)
        )

        self.inspector_stack = Gtk.Stack()
        self.inspector_stack.set_hexpand(True)
        self.inspector_stack.set_vexpand(True)
        self.inspector_stack.set_vhomogeneous(False)
        self.inspector_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        inspector_switcher = Gtk.StackSwitcher()
        inspector_switcher.set_stack(self.inspector_stack)
        # libadwaita gives each text tab a 100 px minimum; six of them made
        # the inspector ~800 px wide and left the canvas no room.
        inspector_switcher.add_css_class("turing-inspector-tabs")
        tabs_css = Gtk.CssProvider()
        tabs_css.load_from_string(
            ".turing-inspector-tabs > button { min-width: 0; padding-left: 10px; padding-right: 10px; }"
        )
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), tabs_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        inspector_switcher.set_halign(Gtk.Align.CENTER)
        inspector_panel.append(inspector_switcher)
        inspector_panel.append(self.inspector_stack)

        def inspector_page() -> tuple[Gtk.ScrolledWindow, Gtk.Box]:
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
            return scroll, page

        elements_scroll, elements_page = inspector_page()
        layout_scroll, layout_page = inspector_page()
        style_scroll, style_page = inspector_page()
        effects_scroll, effects_page = inspector_page()
        self.inspector_stack.add_titled(elements_scroll, "elements", "Elementos")
        self.inspector_stack.add_titled(layout_scroll, "layout", "Layout")
        self.inspector_stack.add_titled(style_scroll, "style", "Estilo")
        self.inspector_stack.add_titled(effects_scroll, "effects", "Efeitos")

        help_label = Gtk.Label(
            label=(
                "Clique e arraste um valor na prévia, ou use as setas para ajustes "
                "de 1 px (Shift: 10 px). Use as alças azuis para redimensionar. "
                "As alterações só são persistidas ao salvar."
            ),
            xalign=0,
            wrap=True,
        )
        help_label.add_css_class("dim-label")
        elements_page.append(help_label)

        self.grid_check = Gtk.CheckButton(label="Alinhar arraste à grade de 5 px")
        self.grid_check.set_active(True)
        self.grid_check.connect("toggled", lambda *_: self._sync_grid())
        elements_page.append(self.grid_check)

        self.group_label = Gtk.Label(label="Shift+clique na prévia seleciona vários elementos", xalign=0, wrap=True)
        self.group_label.add_css_class("dim-label")
        elements_page.append(self.group_label)

        self.preview_preset_values = PRESET_KEYS
        self.preview_preset_dropdown = Gtk.DropDown.new_from_strings(PRESET_LABELS)
        self.preview_preset_dropdown.connect(
            "notify::selected",
            self._on_preview_preset_changed,
        )
        elements_page.append(
            self._field("Dados de teste", self.preview_preset_dropdown)
        )
        elements_page.append(self._build_custom_preview_panel())

        self.overlay_mode_check = Gtk.CheckButton(
            label="Mostrar somente o overlay enviado ao dispositivo"
        )
        self.overlay_mode_check.connect("toggled", self._on_overlay_mode_changed)
        elements_page.append(self.overlay_mode_check)

        self.round_mask_check = Gtk.CheckButton(
            label="Mostrar a área visível da tela redonda"
        )
        self.round_mask_check.set_active(
            is_probably_round(manifest.width, manifest.height)
        )
        self.round_mask_check.connect("toggled", lambda *_: self._sync_round_mask())
        elements_page.append(self.round_mask_check)
        self.round_mask_label = Gtk.Label(xalign=0, wrap=True)
        self.round_mask_label.add_css_class("dim-label")
        elements_page.append(self.round_mask_label)

        self.component_dropdown = Gtk.DropDown.new_from_strings(
            tuple(component.label for component in self.component_catalog)
        )
        self.component_dropdown.set_hexpand(True)
        elements_page.append(self._field("Novo elemento", self.component_dropdown))

        self.add_component_button = Gtk.Button(label="Adicionar elemento")
        self.add_component_button.add_css_class("suggested-action")
        self.add_component_button.connect("clicked", self._on_add_component)
        elements_page.append(self.add_component_button)

        self.duplicate_element_button = Gtk.Button(
            label="Duplicar elemento",
            tooltip_text="Cria uma cópia do elemento selecionado (Ctrl+D)",
        )
        self.duplicate_element_button.set_sensitive(False)
        self.duplicate_element_button.connect("clicked", lambda *_: self._on_duplicate_element())
        elements_page.append(self.duplicate_element_button)

        self.remove_element_button = Gtk.Button(label="Remover elemento")
        self.remove_element_button.add_css_class("destructive-action")
        self.remove_element_button.connect("clicked", self._on_remove_element)
        elements_page.append(self.remove_element_button)

        geometry = Gtk.Grid(column_spacing=10, row_spacing=10)
        layout_page.append(geometry)
        self.x_spin = self._spin(0, manifest.width - 1)
        self.y_spin = self._spin(0, manifest.height - 1)
        self.width_spin = self._spin(1, manifest.width)
        self.height_spin = self._spin(1, manifest.height)
        self.font_spin = self._spin(6, 160)
        self.opacity_spin = self._spin(0, 100)
        self.layer_spin = self._spin(1, 9999)
        for row, (label, widget) in enumerate(
            (
                ("X", self.x_spin),
                ("Y", self.y_spin),
                ("Largura", self.width_spin),
                ("Altura", self.height_spin),
            )
        ):
            geometry.attach(Gtk.Label(label=label, xalign=0), 0, row, 1, 1)
            geometry.attach(widget, 1, row, 1, 1)

        style_geometry = Gtk.Grid(column_spacing=10, row_spacing=10)
        style_page.append(style_geometry)
        for row, (label, widget) in enumerate(
            (
                ("Fonte (px)", self.font_spin),
                ("Opacidade (%)", self.opacity_spin),
                ("Camada", self.layer_spin),
            )
        ):
            style_geometry.attach(Gtk.Label(label=label, xalign=0), 0, row, 1, 1)
            style_geometry.attach(widget, 1, row, 1, 1)
        for spin in (
            self.x_spin,
            self.y_spin,
            self.width_spin,
            self.height_spin,
            self.font_spin,
            self.opacity_spin,
            self.layer_spin,
        ):
            spin.connect("value-changed", self._on_style_changed)
            spin.connect("changed", self._on_spin_text_changed)

        self.font_weight_values = (0, 100, 200, 300, 400, 500, 600, 700, 800, 900)
        self.font_weight_dropdown = Gtk.DropDown.new_from_strings(
            (
                "Do tema",
                "100 · fina",
                "200 · extraleve",
                "300 · leve",
                "400 · normal",
                "500 · média",
                "600 · seminegrito",
                "700 · negrito",
                "800 · extranegrito",
                "900 · pesada",
            )
        )
        self.font_weight_dropdown.connect("notify::selected", self._on_style_changed)
        style_page.append(self._field("Peso da fonte", self.font_weight_dropdown))

        self.text_align_values = ("inherit", "left", "center", "right")
        self.text_align_dropdown = Gtk.DropDown.new_from_strings(
            ("Do tema", "Esquerda", "Centro", "Direita")
        )
        self.text_align_dropdown.connect("notify::selected", self._on_style_changed)
        style_page.append(
            self._field("Alinhamento do texto", self.text_align_dropdown)
        )

        alignment = Gtk.Grid(column_spacing=6, row_spacing=6)
        for column, (label, name) in enumerate(
            (("Esq.", "left"), ("Centro H", "horizontal-center"), ("Dir.", "right"))
        ):
            button = Gtk.Button(label=label)
            button.connect("clicked", lambda _button, value=name: self._align_selected(value))
            alignment.attach(button, column, 0, 1, 1)
        for column, (label, name) in enumerate(
            (("Topo", "top"), ("Centro V", "vertical-center"), ("Base", "bottom"))
        ):
            button = Gtk.Button(label=label)
            button.connect("clicked", lambda _button, value=name: self._align_selected(value))
            alignment.attach(button, column, 1, 1, 1)
        layout_page.append(self._field("Alinhamento (à tela; com vários selecionados, entre eles)", alignment))

        self.color_entry = Gtk.Entry(placeholder_text="#ffffff")
        self.color_entry.set_max_length(7)
        self.color_entry.connect("changed", self._on_style_changed)
        style_page.append(self._field("Cor do texto/barra", self.color_entry))

        self.element_kind_values = ("text", "bar")
        self.element_kind_dropdown = Gtk.DropDown.new_from_strings(
            ("Texto", "Barra")
        )
        self.element_kind_dropdown.connect(
            "notify::selected",
            self._on_effect_changed,
        )
        effects_page.append(
            self._field("Aplicar efeitos como", self.element_kind_dropdown)
        )

        self.gradient_check = Gtk.CheckButton(label="Usar degradê")
        self.gradient_check.connect("toggled", self._on_effect_changed)
        effects_page.append(self.gradient_check)

        self.gradient_start_entry = Gtk.Entry(placeholder_text="#ffffff")
        self.gradient_start_entry.set_max_length(7)
        self.gradient_start_entry.connect("changed", self._on_effect_changed)
        effects_page.append(
            self._field("Cor inicial do degradê", self.gradient_start_entry)
        )

        self.gradient_end_entry = Gtk.Entry(placeholder_text="#66e0ff")
        self.gradient_end_entry.set_max_length(7)
        self.gradient_end_entry.connect("changed", self._on_effect_changed)
        effects_page.append(
            self._field("Cor final do degradê", self.gradient_end_entry)
        )

        self.gradient_direction_values = ("horizontal", "vertical", "diagonal")
        self.gradient_direction_dropdown = Gtk.DropDown.new_from_strings(
            ("Horizontal", "Vertical", "Diagonal")
        )
        self.gradient_direction_dropdown.connect(
            "notify::selected",
            self._on_effect_changed,
        )
        effects_page.append(
            self._field("Direção do degradê", self.gradient_direction_dropdown)
        )

        self.outline_width_spin = self._spin(0, 8)
        self.outline_width_spin.connect("value-changed", self._on_effect_changed)
        self.outline_width_spin.connect("changed", self._on_spin_text_changed)
        effects_page.append(
            self._field("Contorno (px)", self.outline_width_spin)
        )

        self.outline_color_entry = Gtk.Entry(placeholder_text="#000000")
        self.outline_color_entry.set_max_length(7)
        self.outline_color_entry.connect("changed", self._on_effect_changed)
        effects_page.append(
            self._field("Cor do contorno", self.outline_color_entry)
        )

        self.glow_radius_spin = self._spin(0, 40)
        self.glow_radius_spin.connect("value-changed", self._on_effect_changed)
        self.glow_radius_spin.connect("changed", self._on_spin_text_changed)
        effects_page.append(self._field("Brilho (px)", self.glow_radius_spin))

        self.glow_color_entry = Gtk.Entry(placeholder_text="#ffffff")
        self.glow_color_entry.set_max_length(7)
        self.glow_color_entry.connect("changed", self._on_effect_changed)
        effects_page.append(self._field("Cor do brilho", self.glow_color_entry))

        video = manifest.native_video_overlay
        video_summary = Gtk.Label(
            label=(
                f"Vídeo: {video.local_path} · {video.fps} fps · {video.duration:g} s"
                if video is not None
                else "Vídeo nativo não configurado"
            ),
            xalign=0,
            wrap=True,
        )
        video_summary.add_css_class("dim-label")
        elements_page.append(video_summary)

        self.status_label = Gtk.Label(label="Carregando prévia…", xalign=0, wrap=True)
        self.status_label.add_css_class("dim-label")
        inspector_panel.append(
            Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        )
        inspector_panel.append(self.status_label)

        actions = Gtk.Grid(column_spacing=8, row_spacing=8)
        actions.set_column_homogeneous(True)
        inspector_panel.append(actions)

        self.reset_button = Gtk.Button(label="Descartar alterações")
        self.reset_button.connect("clicked", self._on_reset)
        actions.attach(self.reset_button, 0, 0, 2, 1)

        self.save_button = Gtk.Button(label="Salvar")
        self.save_button.add_css_class("suggested-action")
        self.save_button.connect("clicked", lambda *_: self._save(False))
        self.save_button.set_sensitive(False)
        actions.attach(self.save_button, 0, 1, 1, 1)

        self.build_button = Gtk.Button(label="Salvar e gerar vídeo")
        self.build_button.add_css_class("suggested-action")
        self.build_button.connect("clicked", lambda *_: self._save(True))
        self.build_button.set_sensitive(False)
        actions.attach(self.build_button, 1, 1, 1, 1)

        # Only offered for the theme the monitor shows: after saving, the
        # monitor restarts its HTML renderer (about 6 s, display stays on).
        self.live_display_check = Gtk.CheckButton(
            label="Atualizar a tela física ao salvar",
            active=True,
            tooltip_text="Depois de salvar, a tela física pisca e mostra o novo layout em cerca de 6 segundos",
        )
        self.live_display_check.set_visible(self._is_active_display_theme())
        actions.attach(self.live_display_check, 0, 2, 2, 1)

        self.backend.load()

    def _field(self, title: str, widget: Gtk.Widget) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        box.append(Gtk.Label(label=title, xalign=0))
        box.append(widget)
        return box

    def _spin(self, minimum: int, maximum: int) -> Gtk.SpinButton:
        spin = Gtk.SpinButton.new_with_range(minimum, maximum, 1)
        spin.set_digits(0)
        spin.set_hexpand(True)
        return spin

    def _toast(self, message: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast(title=message, timeout=4))

    def _theme_record(self) -> ThemeRecord:
        preview = self.manifest.root / "preview.png"
        return ThemeRecord(
            name=self.manifest.root.name,
            directory=self.manifest.root,
            yaml_file=None,
            preview_file=preview,
            engine="html",
            resolution=(self.manifest.width, self.manifest.height),
            permissions=self.manifest.permissions,
        )

    def _on_import_theme(self, *_args) -> None:
        show_import_theme_dialog(
            self,
            self._import_theme_from_path,
            on_error=lambda message: self.status_label.set_text(
                f"Não foi possível importar o tema: {message}"
            ),
        )

    def _import_theme_from_path(self, source_path: str) -> None:
        try:
            imported_name = import_theme(source_path)
        except Exception as exc:
            self.status_label.set_text(f"Não foi possível importar o tema: {exc}")
            self._toast("Falha ao importar o tema")
            return
        imported_root = THEMES_DIR / imported_name
        if not (imported_root / "manifest.json").is_file():
            self.status_label.set_text(
                f"Tema YAML importado como {imported_name}; abra-o no editor YAML"
            )
            self._toast("Tema YAML importado")
            return
        try:
            imported_manifest = ThemeManifest.load(imported_root)
        except Exception as exc:
            self.status_label.set_text(
                f"Tema importado, mas o manifesto HTML não pôde ser aberto: {exc}"
            )
            self._toast("Tema importado com erro de manifesto")
            return
        if imported_manifest.engine != "html":
            self.status_label.set_text(
                f"Tema importado como {imported_name}, mas não usa o motor HTML"
            )
            self._toast("Tema importado")
            return
        self.status_label.set_text(f"Tema importado como {imported_name}")
        self._toast("Tema HTML importado; abrindo nova janela")
        try:
            subprocess.Popen(
                [
                    resolve_project_python(ROOT),
                    str(ROOT / "html-theme-editor-gtk.py"),
                    imported_name,
                ],
                cwd=str(ROOT),
                start_new_session=True,
            )
        except Exception as exc:
            self.status_label.set_text(
                f"Tema importado, mas a nova janela não abriu: {exc}"
            )

    def _on_export_theme(self, *_args) -> None:
        if not self._loaded_once:
            self._toast("Aguarde o carregamento do tema")
            return
        show_export_theme_dialog(
            self,
            self._theme_record(),
            self._export_theme_to_path,
        )

    def _export_theme_to_path(
        self,
        record: ThemeRecord,
        destination: str,
    ) -> None:
        if self._dirty and not self._save(False):
            return
        try:
            exported = export_theme(record, destination)
        except Exception as exc:
            self.status_label.set_text(f"Não foi possível exportar o tema: {exc}")
            self._toast("Falha ao exportar o tema")
            return
        self.status_label.set_text(f"Tema exportado: {exported}")
        self._toast("Pacote .theme exportado")

    def _build_custom_preview_panel(self) -> Gtk.Widget:
        """Fields that override single bindings in "Valores personalizados".

        A number field accepts comma or dot decimals; any other text is sent
        as text, and an empty field makes that sensor unavailable.
        """
        self._custom_base = "normal"
        self._custom_initialized = False
        self._custom_source: int | None = None
        self.custom_entries: dict[str, Gtk.Entry] = {}
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        hint = Gtk.Label(
            label="Números aceitam vírgula ou ponto. Deixe um campo vazio para simular o sensor indisponível.",
            xalign=0,
            wrap=True,
        )
        hint.add_css_class("dim-label")
        box.append(hint)
        grid = Gtk.Grid(column_spacing=8, row_spacing=6)
        for row, field in enumerate(CUSTOM_FIELDS):
            label = Gtk.Label(label=field.label, xalign=0)
            label.set_hexpand(True)
            entry = Gtk.Entry(width_chars=12)
            entry.set_tooltip_text(field.binding)
            entry.connect("changed", lambda *_: self._schedule_custom_preview())
            grid.attach(label, 0, row, 1, 1)
            grid.attach(entry, 1, row, 1, 1)
            self.custom_entries[field.binding] = entry
        box.append(grid)
        restore = Gtk.Button(label="Restaurar valores normais")
        restore.connect("clicked", lambda *_: self._fill_custom_fields("normal"))
        box.append(restore)
        self.custom_preview_panel = Gtk.Expander(label="Editar valores de teste", expanded=True)
        self.custom_preview_panel.set_child(box)
        self.custom_preview_panel.set_visible(False)
        return self.custom_preview_panel

    def _fill_custom_fields(self, preset: str) -> None:
        source = preset_data(preset)
        for binding, entry in self.custom_entries.items():
            entry.set_text(format_field_value(binding_value(source, binding)))
        self._custom_base = preset
        self._custom_initialized = True

    def _schedule_custom_preview(self) -> None:
        if self._preview_preset() != "custom" or not self._loaded_once:
            return
        if self._custom_source is not None:
            GLib.source_remove(self._custom_source)

        def apply() -> bool:
            self._custom_source = None
            self._apply_preview_snapshot()
            return False

        self._custom_source = GLib.timeout_add(250, apply)

    def _preview_data(self) -> dict:
        preset = self._preview_preset()
        if preset != "custom":
            return preset_data(preset)
        values = {binding: entry.get_text() for binding, entry in self.custom_entries.items()}
        return custom_data(preset_data(self._custom_base), values)

    def _preview_preset(self) -> str:
        selected = min(
            self.preview_preset_dropdown.get_selected(),
            len(self.preview_preset_values) - 1,
        )
        return self.preview_preset_values[selected]

    def _apply_preview_snapshot(self, callback=None) -> None:
        def finished(error):
            if error is None:
                self.backend.evaluate("window.__turingEditorRefreshSelection?.();")
            if callback is not None:
                callback(error)

        self.backend.evaluate(
            build_snapshot_script(_preview_snapshot(data=self._preview_data())),
            finished,
        )

    def _on_preview_preset_changed(self, *_args) -> None:
        preset = self._preview_preset()
        if preset == "custom" and not self._custom_initialized:
            # Start from the data the preview was showing.
            self._fill_custom_fields(getattr(self, "_last_fixed_preset", "normal"))
        elif preset != "custom":
            self._last_fixed_preset = preset
        self.custom_preview_panel.set_visible(preset == "custom")
        if not self._loaded_once:
            return
        self._apply_preview_snapshot(
            lambda error: self.status_label.set_text(
                f"Falha ao trocar dados de teste: {error}"
                if error is not None
                else "Dados de teste atualizados"
            )
        )

    def _on_overlay_mode_changed(self, *_args) -> None:
        if not self._loaded_once:
            return
        self._sync_overlay_mode()
        self.status_label.set_text(
            "Prévia exibe somente a camada enviada ao dispositivo"
            if self.overlay_mode_check.get_active()
            else "Prévia completa do tema"
        )

    def _on_preview_load_changed(self, _view, event) -> None:
        if event != WebKit.LoadEvent.FINISHED:
            return
        self._apply_preview_snapshot(self._after_snapshot)

    def _after_snapshot(self, error: Exception | None) -> None:
        if error is not None:
            self.status_label.set_text(f"Falha ao atualizar a prévia: {error}")
            return
        self._repaint_preview_when_ready()
        self.backend.evaluate(
            """
            (() => {
              if (window.__turingVisualEditorClickInstalled) return;
              window.__turingVisualEditorClickInstalled = true;
              window.__turingEditorGrid = 5;
              window.__turingEditorSelected = null;
              let group = new Set();
              const groupBoxes = new Map();
              let drag = null;
              let resize = null;
              let suppressClick = false;

              const emit = (prefix, payload) => {
                payload.nonce = performance.now();
                document.title = prefix + encodeURIComponent(JSON.stringify(payload));
              };
              const overlay = target => target && target.closest
                ? target.closest('[data-turing-overlay]')
                : null;
              const position = (element, x, y) => {
                const properties = {
                  position: 'fixed', left: x + 'px', top: y + 'px',
                  right: 'auto', bottom: 'auto', translate: 'none',
                  transform: 'none', zIndex: '1000'
                };
                Object.entries(properties).forEach(([name, value]) =>
                  element.style.setProperty(
                    name.replace(/[A-Z]/g, character => '-' + character.toLowerCase()),
                    value,
                    'important'
                  ));
                window.__turingPositionEditorElement?.(element, x, y);
              };
              const dimensions = (element, width, height) => {
                element.style.setProperty('width', width + 'px', 'important');
                element.style.setProperty('height', height + 'px', 'important');
              };

              const selectionBox = document.createElement('div');
              selectionBox.id = '__turing-editor-selection';
              Object.entries({
                position: 'fixed', display: 'none', pointerEvents: 'none',
                border: '2px solid #66e0ff', boxSizing: 'border-box',
                zIndex: '2147483647'
              }).forEach(([name, value]) => selectionBox.style.setProperty(
                name.replace(/[A-Z]/g, character => '-' + character.toLowerCase()),
                value,
                'important'
              ));
              const handleLayout = {
                nw: ['-6px', '-6px', 'nwse-resize'],
                n: ['calc(50% - 5px)', '-6px', 'ns-resize'],
                ne: ['calc(100% - 4px)', '-6px', 'nesw-resize'],
                e: ['calc(100% - 4px)', 'calc(50% - 5px)', 'ew-resize'],
                se: ['calc(100% - 4px)', 'calc(100% - 4px)', 'nwse-resize'],
                s: ['calc(50% - 5px)', 'calc(100% - 4px)', 'ns-resize'],
                sw: ['-6px', 'calc(100% - 4px)', 'nesw-resize'],
                w: ['-6px', 'calc(50% - 5px)', 'ew-resize']
              };
              Object.entries(handleLayout).forEach(([handleName, values]) => {
                const handle = document.createElement('div');
                handle.dataset.turingResizeHandle = handleName;
                Object.entries({
                  position: 'absolute', left: values[0], top: values[1],
                  width: '10px', height: '10px', borderRadius: '50%',
                  boxSizing: 'border-box', background: '#0e7192',
                  border: '2px solid #b9f2ff', pointerEvents: 'auto',
                  touchAction: 'none', cursor: values[2]
                }).forEach(([name, value]) => handle.style.setProperty(
                  name.replace(/[A-Z]/g, character => '-' + character.toLowerCase()),
                  value,
                  'important'
                ));
                selectionBox.appendChild(handle);
              });
              document.body.appendChild(selectionBox);

              const refreshGroup = () => {
                const primary = window.__turingEditorSelected;
                for (const [id, frame] of groupBoxes) {
                  if (!group.has(id)) { frame.remove(); groupBoxes.delete(id); }
                }
                for (const id of group) {
                  const element = document.getElementById(id);
                  let frame = groupBoxes.get(id);
                  if (!element || element === primary) { if (frame) frame.style.setProperty('display', 'none', 'important'); continue; }
                  if (!frame) {
                    frame = document.createElement('div');
                    frame.dataset.turingGroupFrame = id;
                    Object.entries({
                      position: 'fixed', pointerEvents: 'none', boxSizing: 'border-box',
                      border: '2px dashed #66e0ff', zIndex: '2147483646'
                    }).forEach(([name, value]) => frame.style.setProperty(
                      name.replace(/[A-Z]/g, character => '-' + character.toLowerCase()), value, 'important'));
                    document.body.appendChild(frame);
                    groupBoxes.set(id, frame);
                  }
                  const rect = element.getBoundingClientRect();
                  frame.style.setProperty('display', 'block', 'important');
                  frame.style.setProperty('left', rect.left + 'px', 'important');
                  frame.style.setProperty('top', rect.top + 'px', 'important');
                  frame.style.setProperty('width', rect.width + 'px', 'important');
                  frame.style.setProperty('height', rect.height + 'px', 'important');
                }
              };
              window.__turingEditorSetGroup = ids => {
                group = new Set(ids || []);
                refreshGroup();
              };
              const refreshSelection = () => {
                refreshGroup();
                const selected = window.__turingEditorSelected;
                if (!selected || !selected.isConnected) {
                  selectionBox.style.setProperty('display', 'none', 'important');
                  return;
                }
                const rect = selected.getBoundingClientRect();
                selectionBox.style.setProperty('display', 'block', 'important');
                selectionBox.style.setProperty('left', rect.left + 'px', 'important');
                selectionBox.style.setProperty('top', rect.top + 'px', 'important');
                selectionBox.style.setProperty('width', rect.width + 'px', 'important');
                selectionBox.style.setProperty('height', rect.height + 'px', 'important');
              };
              window.__turingEditorSelect = element => {
                window.__turingEditorSelected = element || null;
                refreshSelection();
              };
              window.__turingEditorRefreshSelection = refreshSelection;

              const overlayStyleState = new WeakMap();
              const overlayProperties = ['visibility', 'animation', 'transition'];
              const pageBackgroundState = [document.documentElement, document.body].map(
                node => ({
                  node,
                  value: node.style.getPropertyValue('background'),
                  priority: node.style.getPropertyPriority('background')
                })
              );
              const rememberOverlayStyle = node => {
                if (overlayStyleState.has(node)) return;
                const state = {};
                overlayProperties.forEach(name => {
                  state[name] = {
                    value: node.style.getPropertyValue(name),
                    priority: node.style.getPropertyPriority(name)
                  };
                });
                overlayStyleState.set(node, state);
              };
              const restoreProperty = (node, name, state) => {
                if (state.value)
                  node.style.setProperty(name, state.value, state.priority);
                else
                  node.style.removeProperty(name);
              };
              window.__turingEditorSetOverlayMode = enabled => {
                const elements = [...document.body.querySelectorAll('*')].filter(
                  node => node !== selectionBox && !selectionBox.contains(node)
                );
                if (enabled) {
                  for (const node of elements) {
                    rememberOverlayStyle(node);
                    node.style.setProperty('visibility', 'hidden', 'important');
                    node.style.setProperty('animation', 'none', 'important');
                    node.style.setProperty('transition', 'none', 'important');
                  }
                  for (const root of document.querySelectorAll('[data-turing-overlay]')) {
                    root.style.setProperty('visibility', 'visible', 'important');
                    for (const child of root.querySelectorAll('*'))
                      child.style.setProperty('visibility', 'visible', 'important');
                  }
                  for (const page of pageBackgroundState)
                    page.node.style.setProperty('background', 'transparent', 'important');
                  document.documentElement.dataset.turingRenderMode = 'overlay-editor';
                } else {
                  for (const node of elements) {
                    const state = overlayStyleState.get(node);
                    if (!state) continue;
                    overlayProperties.forEach(name =>
                      restoreProperty(node, name, state[name]));
                  }
                  for (const page of pageBackgroundState)
                    restoreProperty(page.node, 'background', page);
                  delete document.documentElement.dataset.turingRenderMode;
                }
                refreshSelection();
              };

              document.querySelectorAll('[data-turing-overlay]').forEach(element => {
                element.style.setProperty('pointer-events', 'auto', 'important');
                element.style.setProperty('cursor', 'move', 'important');
                element.style.setProperty('touch-action', 'none', 'important');
              });

              document.addEventListener('pointerdown', event => {
                const resizeHandle = event.target.closest
                  ? event.target.closest('[data-turing-resize-handle]')
                  : null;
                const selected = window.__turingEditorSelected;
                if (resizeHandle && selected && event.button === 0) {
                  const rect = selected.getBoundingClientRect();
                  resize = {
                    element: selected,
                    id: selected.id,
                    handle: resizeHandle.dataset.turingResizeHandle,
                    startX: event.clientX,
                    startY: event.clientY,
                    x: Math.round(rect.left),
                    y: Math.round(rect.top),
                    width: Math.max(1, Math.round(rect.width)),
                    height: Math.max(1, Math.round(rect.height))
                  };
                  suppressClick = true;
                  try { resizeHandle.setPointerCapture?.(event.pointerId); } catch (_error) {}
                  emit('turing-editor-resize:', {
                    phase: 'start', id: resize.id,
                    x: resize.x, y: resize.y,
                    width: resize.width, height: resize.height
                  });
                  event.preventDefault();
                  event.stopPropagation();
                  return;
                }
                const element = overlay(event.target);
                if (!element || !element.id || event.button !== 0) return;
                if (event.shiftKey) {
                  // Shift+click adds or removes an element from the group.
                  suppressClick = true;
                  emit('turing-editor-group:', {action: 'toggle', id: element.id});
                  event.preventDefault();
                  event.stopPropagation();
                  return;
                }
                const rect = element.getBoundingClientRect();
                const members = group.has(element.id) && group.size > 1
                  ? [...group].map(id => document.getElementById(id)).filter(Boolean).map(node => {
                      const box = node.getBoundingClientRect();
                      return {element: node, id: node.id, x: Math.round(box.left), y: Math.round(box.top),
                              width: Math.ceil(box.width), height: Math.ceil(box.height)};
                    })
                  : null;
                drag = {
                  element,
                  id: element.id,
                  offsetX: event.clientX - rect.left,
                  offsetY: event.clientY - rect.top,
                  startX: Math.round(rect.left),
                  startY: Math.round(rect.top),
                  width: rect.width,
                  height: rect.height,
                  members,
                  moved: false
                };
                suppressClick = false;
                try { element.setPointerCapture?.(event.pointerId); } catch (_error) {}
                emit('turing-editor-drag:', {
                  phase: 'start', id: drag.id,
                  x: Math.round(rect.left), y: Math.round(rect.top)
                });
                event.preventDefault();
                event.stopPropagation();
              }, true);

              document.addEventListener('pointermove', event => {
                if (resize) {
                  const grid = Math.max(1, Number(window.__turingEditorGrid) || 1);
                  const canvasWidth = document.documentElement.clientWidth || 480;
                  const canvasHeight = document.documentElement.clientHeight || 480;
                  const dx = Math.round((event.clientX - resize.startX) / grid) * grid;
                  const dy = Math.round((event.clientY - resize.startY) / grid) * grid;
                  let left = resize.x;
                  let top = resize.y;
                  let right = resize.x + resize.width;
                  let bottom = resize.y + resize.height;
                  if (resize.handle.includes('w'))
                    left = Math.max(0, Math.min(resize.x + dx, right - 1));
                  if (resize.handle.includes('e'))
                    right = Math.max(left + 1, Math.min(resize.x + resize.width + dx, canvasWidth));
                  if (resize.handle.includes('n'))
                    top = Math.max(0, Math.min(resize.y + dy, bottom - 1));
                  if (resize.handle.includes('s'))
                    bottom = Math.max(top + 1, Math.min(resize.y + resize.height + dy, canvasHeight));
                  const width = right - left;
                  const height = bottom - top;
                  position(resize.element, left, top);
                  dimensions(resize.element, width, height);
                  refreshSelection();
                  emit('turing-editor-resize:', {
                    phase: 'move', id: resize.id,
                    x: left, y: top, width, height
                  });
                  event.preventDefault();
                  event.stopPropagation();
                  return;
                }
                if (!drag) return;
                const grid = Math.max(1, Number(window.__turingEditorGrid) || 1);
                const canvasWidth = document.documentElement.clientWidth || 480;
                const canvasHeight = document.documentElement.clientHeight || 480;
                let x = Math.round((event.clientX - drag.offsetX) / grid) * grid;
                let y = Math.round((event.clientY - drag.offsetY) / grid) * grid;
                if (drag.members) {
                  // Move the group by one delta, clamped by its bounding box.
                  const left = Math.min(...drag.members.map(m => m.x));
                  const top = Math.min(...drag.members.map(m => m.y));
                  const right = Math.max(...drag.members.map(m => m.x + m.width));
                  const bottom = Math.max(...drag.members.map(m => m.y + m.height));
                  const dx = Math.max(-left, Math.min(x - drag.startX, canvasWidth - right));
                  const dy = Math.max(-top, Math.min(y - drag.startY, canvasHeight - bottom));
                  drag.positions = drag.members.map(m => [m.id, m.x + dx, m.y + dy]);
                  drag.members.forEach(m => position(m.element, m.x + dx, m.y + dy));
                  x = drag.startX + dx;
                  y = drag.startY + dy;
                } else {
                  x = Math.max(0, Math.min(x, canvasWidth - Math.ceil(drag.width)));
                  y = Math.max(0, Math.min(y, canvasHeight - Math.ceil(drag.height)));
                  position(drag.element, x, y);
                }
                refreshSelection();
                drag.moved = true;
                suppressClick = true;
                emit('turing-editor-drag:', {phase: 'move', id: drag.id, x, y, group: drag.positions || null});
                event.preventDefault();
                event.stopPropagation();
              }, true);

              const endInteraction = event => {
                if (resize) {
                  const rect = resize.element.getBoundingClientRect();
                  emit('turing-editor-resize:', {
                    phase: 'end', id: resize.id,
                    x: Math.round(rect.left), y: Math.round(rect.top),
                    width: Math.max(1, Math.round(rect.width)),
                    height: Math.max(1, Math.round(rect.height))
                  });
                  resize = null;
                  event.preventDefault();
                  event.stopPropagation();
                  return;
                }
                if (!drag) return;
                const rect = drag.element.getBoundingClientRect();
                emit('turing-editor-drag:', {
                  phase: 'end', id: drag.id,
                  x: Math.round(rect.left), y: Math.round(rect.top),
                  group: drag.positions || null
                });
                drag = null;
                event.preventDefault();
                event.stopPropagation();
              };
              document.addEventListener('pointerup', endInteraction, true);
              document.addEventListener('pointercancel', endInteraction, true);

              document.addEventListener('click', event => {
                const element = overlay(event.target);
                if (!element || !element.id) return;
                event.preventDefault();
                event.stopPropagation();
                if (suppressClick) {
                  suppressClick = false;
                  return;
                }
                document.title = 'turing-editor-select:' + element.id;
              }, true);

              document.addEventListener('keydown', event => {
                const directions = {
                  ArrowLeft: [-1, 0], ArrowRight: [1, 0],
                  ArrowUp: [0, -1], ArrowDown: [0, 1]
                };
                if (event.key === 'Escape' && group.size) {
                  emit('turing-editor-group:', {action: 'clear'});
                  event.preventDefault();
                  return;
                }
                if (!directions[event.key] || !window.__turingEditorSelected) return;
                const scale = event.shiftKey ? 10 : 1;
                emit('turing-editor-nudge:', {
                  id: window.__turingEditorSelected.id,
                  dx: directions[event.key][0] * scale,
                  dy: directions[event.key][1] * scale
                });
                event.preventDefault();
                event.stopPropagation();
              }, true);
            })();
            """
        )
        self.backend.evaluate(render_widget_runtime_script())
        self.backend.evaluate(
            round_mask_script(self.manifest.width, self.manifest.height)
        )
        self._sync_grid()
        self._sync_overlay_mode()
        self._sync_round_mask()
        try:
            saved = load_visual_styles(self.manifest)
        except Exception as exc:
            self.status_label.set_text(f"Configuração visual inválida: {exc}")
            return
        if saved:
            self.styles = {style.element_id: style for style in saved}
            self._finish_style_loading()
            return
        GLib.timeout_add(100, self._query_dom_styles)

    def _evaluate_json(self, script: str, callback) -> None:
        def finished(view, result, _user_data=None):
            try:
                value = view.evaluate_javascript_finish(result)
                callback(json.loads(value.to_json(0)), None)
            except Exception as exc:
                callback(None, exc)

        self.backend.view.evaluate_javascript(
            script,
            -1,
            None,
            None,
            None,
            finished,
            None,
        )

    def _query_dom_styles(self) -> bool:
        ids = json.dumps(self.element_ids, ensure_ascii=False)
        self._evaluate_json(
            f"""
            (() => {ids}.map(id => {{
              const element = document.getElementById(id);
              if (!element) return {{id, missing: true}};
              const rect = element.getBoundingClientRect();
              const style = getComputedStyle(element);
              return {{
                id,
                x: Math.round(rect.x),
                y: Math.round(rect.y),
                width: Math.max(1, Math.round(rect.width)),
                height: Math.max(1, Math.round(rect.height)),
                fontSize: Math.max(6, Math.round(parseFloat(style.fontSize) || 16)),
                color: style.color,
                fontWeight: style.fontWeight,
                textAlign: style.textAlign,
                opacity: Math.round((parseFloat(style.opacity) || 0) * 100),
                zIndex: style.zIndex,
                visible: style.display !== 'none',
                componentType: element.dataset.turingComponent || '',
                generatedWidget: element.hasAttribute('data-turing-generated-widget'),
                binding: element.dataset.turingBinding || '',
                formatter: element.dataset.turingFormat || '',
                sample: element.dataset.turingKind === 'bar'
                  ? (element.getAttribute('aria-valuenow') || '50')
                  : (element.textContent.trim() || '--'),
                elementKind: element.dataset.turingKind || (
                  element.textContent.trim() === '' && rect.width >= rect.height * 2
                    ? 'bar'
                    : 'text'
                )
              }};
            }}))()
            """,
            self._receive_dom_styles,
        )
        return False

    def _receive_dom_styles(self, payload, error) -> None:
        if error is not None:
            self.status_label.set_text(f"Falha ao inspecionar elementos: {error}")
            return
        try:
            styles = {}
            for item in payload:
                if item.get("missing"):
                    raise ThemeValidationError(f"elemento #{item['id']} não encontrado")
                x = max(0, min(self.manifest.width - 1, int(item["x"])))
                y = max(0, min(self.manifest.height - 1, int(item["y"])))
                width = max(1, min(int(item["width"]), self.manifest.width - x))
                height = max(1, min(int(item["height"]), self.manifest.height - y))
                try:
                    font_weight = int(float(item.get("fontWeight") or 0))
                except (TypeError, ValueError):
                    font_weight = 0
                if font_weight not in self.font_weight_values:
                    numeric_weights = self.font_weight_values[1:]
                    font_weight = min(
                        numeric_weights,
                        key=lambda value: abs(value - font_weight),
                    )
                    font_weight = 0
                text_align = str(item.get("textAlign") or "inherit").lower()
                text_align = {"start": "left", "end": "right"}.get(
                    text_align,
                    text_align,
                )
                if text_align not in self.text_align_values:
                    text_align = "inherit"
                try:
                    z_index = int(float(item.get("zIndex") or 1000))
                except (TypeError, ValueError):
                    z_index = 1000
                style = HtmlVisualElementStyle(
                    element_id=item["id"],
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    font_size=max(6, min(160, int(item["fontSize"]))),
                    color=_color_to_hex(item["color"]),
                    font_weight=font_weight,
                    text_align=text_align,
                    opacity=max(0, min(100, int(item.get("opacity", 100)))),
                    z_index=max(1, min(9999, z_index)),
                    visible=bool(item.get("visible", True)),
                    component_type=str(item.get("componentType") or ""),
                    generated_widget=bool(item.get("generatedWidget", False)),
                    binding=str(item.get("binding") or ""),
                    formatter=str(item.get("formatter") or ""),
                    sample=str(item.get("sample") or ""),
                    element_kind=str(item.get("elementKind") or "text"),
                ).validated(self.manifest)
                styles[style.element_id] = style
            self.styles = styles
        except Exception as exc:
            self.status_label.set_text(f"Falha ao preparar propriedades: {exc}")
            return
        self._finish_style_loading()

    def _finish_style_loading(self) -> None:
        if set(self.styles) != set(self.element_ids):
            self.status_label.set_text("A configuração não cobre todos os overlays")
            return
        self._loaded_once = True
        self._dirty = False
        self._drag_active = False
        self._resize_active = False
        self.history.clear()
        self._update_history_actions()
        self.save_button.set_sensitive(True)
        self.build_button.set_sensitive(self.manifest.native_video_overlay is not None)
        self.status_label.set_text(f"{len(self.styles)} overlays prontos para edição")
        print(
            f"HTML visual editor ready: {self.manifest.root.name}; "
            f"overlays={len(self.styles)}",
            flush=True,
        )
        self._load_selected_controls()
        if not self._draft_offered:
            self._draft_offered = True
            GLib.idle_add(lambda: self._offer_draft_recovery() or False)

    def _selected_id(self) -> str:
        selected = min(self.element_dropdown.get_selected(), len(self.element_ids) - 1)
        return self.element_ids[selected]

    def _on_element_selected(self, *_args) -> None:
        if self._loaded_once and not self._updating_controls:
            self._load_selected_controls()

    def _refresh_element_model(self, selected_id: str | None = None) -> None:
        if not self.element_ids:
            return
        selected_id = selected_id if selected_id in self.element_ids else self.element_ids[0]
        self._updating_controls = True
        try:
            self.element_model = Gtk.StringList.new(self.element_ids)
            self.element_dropdown.set_model(self.element_model)
            self.element_dropdown.set_selected(self.element_ids.index(selected_id))
        finally:
            self._updating_controls = False

    def _sync_element_ids_from_styles(self, selected_id: str | None = None) -> None:
        original_ids = [
            candidate.element_id
            for candidate in self.candidates
            if candidate.element_id in self.styles
            and not self.styles[candidate.element_id].is_generated
        ]
        generated_ids = [
            element_id
            for element_id, style in self.styles.items()
            if style.is_generated
        ]
        self.element_ids = original_ids + generated_ids
        self._refresh_element_model(selected_id)

    def _restore_persisted_element_structure(self) -> None:
        """Replace session-only element state with the files currently on disk."""
        manifest = ThemeManifest.load(self.manifest.root)
        candidates = tuple(
            candidate
            for candidate in discover_overlay_candidates(manifest)
            if candidate.marked
        )
        element_ids = list(load_persisted_visual_element_ids(manifest))

        self.manifest = manifest
        self.backend.manifest = manifest
        self.candidates = candidates
        self.element_ids = element_ids
        self._refresh_element_model()

    def _sync_preview_elements(self, callback=None) -> None:
        widgets = []
        for style in self.styles.values():
            if not style.is_generated:
                continue
            widget = style.widget_definition()
            widgets.append(
                {
                    "id": widget.element_id,
                    "component": widget.component_type,
                    "binding": widget.binding,
                    "format": widget.formatter,
                    "sample": widget.sample,
                    "kind": widget.kind,
                }
            )
        payload = json.dumps(widgets, ensure_ascii=False)
        self.backend.evaluate(
            f"""
            (() => {{
              const widgets = {payload};
              const allowed = new Set(widgets.map(widget => widget.id));
              document.querySelectorAll('[data-turing-generated-widget]').forEach(
                element => {{ if (!allowed.has(element.id)) element.remove(); }});
              let container = document.getElementById('turing-editor-widgets');
              if (!container && widgets.length) {{
                container = document.createElement('div');
                container.id = 'turing-editor-widgets';
                document.body.appendChild(container);
              }}
              for (const widget of widgets) {{
                let element = document.getElementById(widget.id);
                if (!element) {{
                  element = document.createElement('div');
                  element.id = widget.id;
                  element.className = 'turing-editor-widget';
                  element.textContent = widget.sample;
                  container.appendChild(element);
                }}
                element.setAttribute('data-turing-overlay', '');
                element.setAttribute('data-turing-generated-widget', '');
                element.dataset.turingComponent = widget.component;
                element.dataset.turingBinding = widget.binding;
                element.dataset.turingFormat = widget.format;
                element.dataset.turingKind = widget.kind;
                if (widget.kind === 'bar') {{
                  let fill = element.querySelector('[data-turing-bar-fill]');
                  if (!fill) {{
                    fill = document.createElement('div');
                    fill.setAttribute('data-turing-bar-fill', '');
                    fill.setAttribute('aria-hidden', 'true');
                    element.replaceChildren(fill);
                  }}
                  element.setAttribute('role', 'progressbar');
                  element.setAttribute('aria-valuemin', '0');
                  element.setAttribute('aria-valuemax', '100');
                  element.setAttribute('aria-valuenow', widget.sample);
                  fill.style.setProperty('width', widget.sample + '%', 'important');
                }} else {{
                  element.textContent = widget.sample;
                  element.removeAttribute('role');
                  element.removeAttribute('aria-valuemin');
                  element.removeAttribute('aria-valuemax');
                  element.removeAttribute('aria-valuenow');
                }}
                element.style.setProperty('pointer-events', 'auto', 'important');
                element.style.setProperty('cursor', 'move', 'important');
                element.style.setProperty('touch-action', 'none', 'important');
                element.style.setProperty('visibility', 'visible', 'important');
              }}
              if (container && !widgets.length) container.remove();
              return widgets.length;
            }})()
            """,
            callback,
        )

    def _on_add_component(self, *_args) -> None:
        if not self._loaded_once:
            return
        selected = min(
            self.component_dropdown.get_selected(),
            len(self.component_catalog) - 1,
        )
        component = self.component_catalog[selected]
        element_id = next_widget_id(component.key, self.styles)
        x, y = find_visual_slot(
            self.styles.values(),
            width=component.width,
            height=component.height,
            display_width=self.manifest.width,
            display_height=self.manifest.height,
        )
        self._checkpoint()
        style = HtmlVisualElementStyle(
            element_id=element_id,
            x=x,
            y=y,
            width=component.width,
            height=component.height,
            font_size=22,
            color="#ffffff",
            font_weight=600,
            text_align="center",
            z_index=1000 + len(self.styles),
            component_type=component.key,
            element_kind=component.kind,
        ).validated(self.manifest)
        self.styles[element_id] = style
        self._sync_element_ids_from_styles(element_id)

        def created(error: Exception | None) -> None:
            if error is not None:
                self.status_label.set_text(f"Falha ao adicionar elemento: {error}")
                return
            self._apply_style_to_preview(style)
            self._apply_preview_snapshot()
            self._load_selected_controls()

        self._sync_preview_elements(created)
        self._mark_changed()
        self._update_history_actions()
        self._toast(f"{component.label} adicionado")

    def _on_duplicate_element(self, *_args) -> None:
        if not self._loaded_once:
            return
        style = self.styles.get(self._selected_id())
        if style is None:
            return
        if not style.is_generated:
            self._toast(DUPLICATE_AUTHOR_ELEMENT_HINT)
            return
        try:
            copy = duplicate_visual_style(
                style,
                self.styles.values(),
                display_width=self.manifest.width,
                display_height=self.manifest.height,
            ).validated(self.manifest)
        except ThemeValidationError as exc:
            self._toast(f"Não foi possível duplicar: {exc}")
            return
        self._checkpoint()
        self.styles[copy.element_id] = copy
        self._sync_element_ids_from_styles(copy.element_id)

        def created(error: Exception | None) -> None:
            if error is not None:
                self.status_label.set_text(f"Falha ao duplicar elemento: {error}")
                return
            self._apply_style_to_preview(copy)
            self._apply_preview_snapshot()
            self._load_selected_controls()

        self._sync_preview_elements(created)
        self._mark_changed()
        self._update_history_actions()
        self._toast(f"Cópia criada: {copy.element_id}")

    def _step_preview_zoom(self, direction: int) -> None:
        zoom = step_zoom(self.preview_zoom, direction)
        if zoom == self.preview_zoom:
            return
        self.preview_zoom = zoom
        width, height = zoomed_size(self.manifest.width, self.manifest.height, zoom)
        # Page zoom keeps the page at manifest size in CSS pixels, so drag,
        # resize and the color picker keep working in theme coordinates.
        self.backend.view.set_zoom_level(zoom)
        self.backend.view.set_size_request(width, height)
        self.preview_frame.set_size_request(width, height)
        self._sync_preview_scroller_size(width, height)
        self.top_ruler.set_zoom(zoom)
        self.left_ruler.set_zoom(zoom)
        self.zoom_reset_button.set_label(zoom_label(zoom))

    def _repaint_preview_when_ready(self) -> None:
        """Make the first preview paint cover the whole page.

        After loading, the software-rendered WebView painted only part of
        the page; the rest appeared piece by piece as overlays changed, or
        all at once after a zoom change. A redraw from the page (CSS) does
        not help, but a zoom change does, so nudge the zoom and restore it,
        once after load and once after slow images have decoded.
        """
        def nudge() -> bool:
            view = self.backend.view
            view.set_zoom_level(self.preview_zoom + 0.01)
            GLib.idle_add(lambda: view.set_zoom_level(self.preview_zoom) or False)
            return False

        for delay in PREVIEW_REPAINT_DELAYS_MS:
            GLib.timeout_add(delay, nudge)

    def _on_preview_motion(self, _controller, x: float, y: float) -> None:
        position = cursor_position(x, y, self.preview_zoom, self.manifest.width, self.manifest.height)
        self.top_ruler.set_cursor(position[0] if position else None)
        self.left_ruler.set_cursor(position[1] if position else None)
        self.cursor_label.set_text(f"X {position[0]} · Y {position[1]}" if position else "")

    def _on_preview_leave(self, *_args) -> None:
        self.top_ruler.set_cursor(None)
        self.left_ruler.set_cursor(None)
        self.cursor_label.set_text("")

    def _sync_ruler_selection(self) -> None:
        boxes = [
            (s.x, s.y, s.width, s.height)
            for s in (self.styles.get(i) for i in self._selection_ids())
            if s is not None
        ]
        self.top_ruler.set_span(selection_span(boxes, "x"))
        self.left_ruler.set_span(selection_span(boxes, "y"))

    def _sync_preview_scroller_size(self, width: int, height: int) -> None:
        # Never claim less than the zoomed preview up to its actual-size
        # footprint, so a tiled or narrow window cannot squeeze it away; past
        # that, the preview scrolls instead of widening the window.
        border = PREVIEW_FRAME_BORDER_PX * 2 + RULER_THICKNESS_PX
        self.preview_scroller.set_min_content_width(min(width, self.manifest.width) + border)
        self.preview_scroller.set_min_content_height(min(height, self.manifest.height) + border)

    def _on_preview_scroll(self, controller, _dx: float, dy: float) -> bool:
        state = controller.get_current_event_state()
        if not state & Gdk.ModifierType.CONTROL_MASK or dy == 0:
            return False
        self._step_preview_zoom(-1 if dy > 0 else +1)
        return True

    def _on_save_shortcut(self) -> None:
        if self._loaded_once and self.save_button.get_sensitive():
            self._save(False)

    def _on_remove_element(self, *_args) -> None:
        if not self._loaded_once:
            return
        element_id = self._selected_id()
        style = self.styles[element_id]
        self._checkpoint()
        if style.is_generated:
            del self.styles[element_id]
            self._sync_element_ids_from_styles()
            self._sync_preview_elements()
            self._load_selected_controls()
            self._toast("Elemento criado removido")
        else:
            style = replace(style, visible=not style.visible)
            self.styles[element_id] = style
            self._apply_style_to_preview(style)
            self._load_selected_controls()
            self._toast(
                "Elemento restaurado" if style.visible else "Elemento removido"
            )
        self._mark_changed()
        self._update_history_actions()

    def _load_selected_controls(self, *, highlight: bool = True) -> None:
        style = self.styles.get(self._selected_id())
        if style is None:
            return
        self._updating_controls = True
        try:
            self.x_spin.set_value(style.x)
            self.y_spin.set_value(style.y)
            self.width_spin.set_value(style.width)
            self.height_spin.set_value(style.height)
            self.font_spin.set_value(style.font_size)
            self.opacity_spin.set_value(style.opacity)
            self.layer_spin.set_value(style.z_index)
            self.color_entry.set_text(style.color)
            self.element_kind_dropdown.set_selected(
                self.element_kind_values.index(style.element_kind)
            )
            self.element_kind_dropdown.set_sensitive(not style.is_generated)
            self.gradient_check.set_active(style.gradient_enabled)
            self.gradient_start_entry.set_text(style.gradient_start_color)
            self.gradient_end_entry.set_text(style.gradient_end_color)
            self.gradient_direction_dropdown.set_selected(
                self.gradient_direction_values.index(style.gradient_direction)
            )
            self.outline_width_spin.set_value(style.outline_width)
            self.outline_color_entry.set_text(style.outline_color)
            self.glow_radius_spin.set_value(style.glow_radius)
            self.glow_color_entry.set_text(style.glow_color)
            self.font_weight_dropdown.set_selected(
                self.font_weight_values.index(style.font_weight)
            )
            self.text_align_dropdown.set_selected(
                self.text_align_values.index(style.text_align)
            )
            self.duplicate_element_button.set_sensitive(style.is_generated)
            self.duplicate_element_button.set_tooltip_text(
                "Cria uma cópia do elemento selecionado (Ctrl+D)"
                if style.is_generated
                else DUPLICATE_AUTHOR_ELEMENT_HINT
            )
            self.remove_element_button.set_label(
                "Excluir elemento criado"
                if style.is_generated
                else ("Remover elemento" if style.visible else "Restaurar elemento")
            )
        finally:
            self._updating_controls = False
        self._sync_effect_control_sensitivity()
        self._sync_ruler_selection()
        if highlight:
            self._highlight_selected()

    def _select_element(self, element_id: str) -> bool:
        try:
            selected = self.element_ids.index(element_id)
        except ValueError:
            return False
        self.element_dropdown.set_selected(selected)
        return True

    def _on_preview_title_changed(self, view, _param) -> None:
        title = str(view.get_title() or "")
        if title.startswith(SELECT_TITLE_PREFIX):
            self._set_group([])
            self._select_element(title[len(SELECT_TITLE_PREFIX) :])
            return
        for prefix, callback in (
            (GROUP_TITLE_PREFIX, self._handle_group_message),
            (DRAG_TITLE_PREFIX, self._handle_drag_message),
            (RESIZE_TITLE_PREFIX, self._handle_resize_message),
            (NUDGE_TITLE_PREFIX, self._handle_nudge_message),
        ):
            if not title.startswith(prefix):
                continue
            try:
                payload = json.loads(unquote(title[len(prefix) :]))
                callback(payload)
            except Exception as exc:
                self.status_label.set_text(f"Evento inválido da prévia: {exc}")
            return

    def _checkpoint(self) -> None:
        self.history.record(self.styles)
        self._update_history_actions()

    def _update_history_actions(self) -> None:
        self.undo_action.set_enabled(self.history.can_undo)
        self.redo_action.set_enabled(self.history.can_redo)

    def _mark_changed(self) -> None:
        self._dirty = True
        self._schedule_draft()
        self.save_button.set_sensitive(True)
        self.build_button.set_sensitive(self.manifest.native_video_overlay is not None)
        self.status_label.set_text("Alterações ainda não salvas")
        if self.round_mask_check.get_active():
            # Let the preview apply the edit before measuring it.
            GLib.timeout_add(250, lambda: self._sync_round_mask() or False)

    def _restore_history(self, snapshot) -> None:
        selected_id = self._selected_id()
        self.styles = {style.element_id: style for style in snapshot}
        self._sync_element_ids_from_styles(selected_id)
        self._sync_preview_elements()
        for style in self.styles.values():
            self._apply_style_to_preview(style)
        self._load_selected_controls()
        self._mark_changed()
        self._update_history_actions()

    def _undo(self) -> None:
        snapshot = self.history.undo(self.styles)
        if snapshot is not None:
            self._restore_history(snapshot)

    def _redo(self) -> None:
        snapshot = self.history.redo(self.styles)
        if snapshot is not None:
            self._restore_history(snapshot)

    def _selection_ids(self) -> list[str]:
        primary = self._selected_id()
        return [primary] + [i for i in self.group_ids if i != primary and i in self.styles]

    def _set_group(self, ids) -> None:
        primary = self._selected_id() if self.element_ids else ""
        self.group_ids = [i for i in dict.fromkeys(ids) if i in self.styles and i != primary]
        everyone = json.dumps(([primary] if self.group_ids else []) + self.group_ids, ensure_ascii=False)
        self.backend.evaluate(f"window.__turingEditorSetGroup?.({everyone});")
        self._sync_ruler_selection()
        count = len(self.group_ids) + 1
        self.group_label.set_text(
            f"{count} elementos selecionados · Shift+clique adiciona ou remove, Esc limpa"
            if self.group_ids
            else "Shift+clique na prévia seleciona vários elementos"
        )

    def _handle_group_message(self, payload: dict[str, object]) -> None:
        if str(payload.get("action")) == "clear":
            self._set_group([])
            return
        element_id = str(payload.get("id") or "")
        if element_id not in self.styles or element_id == self._selected_id():
            return
        ids = list(self.group_ids)
        if element_id in ids:
            ids.remove(element_id)
        else:
            ids.append(element_id)
        self._set_group(ids)

    def _apply_group(self, styles) -> None:
        for style in styles:
            self.styles[style.element_id] = style
            self._apply_style_to_preview(style)

    def _handle_drag_message(self, payload: dict[str, object]) -> None:
        element_id = str(payload.get("id") or "")
        selection = self._selection_ids()
        if not self._select_element(element_id) or element_id not in self.styles:
            return
        # Dragging another group member makes it the primary; keep the group.
        self._set_group(selection if element_id in selection else [])
        positions = payload.get("group")
        if positions and str(payload.get("phase")) in {"move", "end"}:
            for item_id, x, y in positions:
                if item_id in self.styles:
                    self.styles[item_id] = place_visual_style(
                        self.styles[item_id], x=int(x), y=int(y),
                        display_width=self.manifest.width, display_height=self.manifest.height,
                    )
            phase = str(payload.get("phase"))
            self._load_selected_controls(highlight=phase == "end")
            self._mark_changed()
            if phase == "end":
                self._drag_active = False
                self._update_history_actions()
            return
        phase = str(payload.get("phase") or "")
        if phase == "start":
            if not self._drag_active:
                self._checkpoint()
            self._drag_active = True
            return
        if phase not in {"move", "end"}:
            return
        style = place_visual_style(
            self.styles[element_id],
            x=int(payload.get("x", 0)),
            y=int(payload.get("y", 0)),
            display_width=self.manifest.width,
            display_height=self.manifest.height,
        )
        self.styles[element_id] = style
        self._load_selected_controls(highlight=phase == "end")
        self._mark_changed()
        if phase == "end":
            self._drag_active = False
            self._update_history_actions()

    def _handle_resize_message(self, payload: dict[str, object]) -> None:
        element_id = str(payload.get("id") or "")
        if not self._select_element(element_id) or element_id not in self.styles:
            return
        phase = str(payload.get("phase") or "")
        if phase == "start":
            if not self._resize_active:
                self._checkpoint()
            self._resize_active = True
            return
        if phase not in {"move", "end"}:
            return
        style = resize_visual_style(
            self.styles[element_id],
            x=int(payload.get("x", 0)),
            y=int(payload.get("y", 0)),
            width=int(payload.get("width", 1)),
            height=int(payload.get("height", 1)),
            display_width=self.manifest.width,
            display_height=self.manifest.height,
        )
        self.styles[element_id] = style
        self._load_selected_controls(highlight=phase == "end")
        self._mark_changed()
        if phase == "end":
            self._resize_active = False
            self._update_history_actions()

    def _handle_nudge_message(self, payload: dict[str, object]) -> None:
        element_id = str(payload.get("id") or "")
        if not self._select_element(element_id) or element_id not in self.styles:
            return
        self._checkpoint()
        if self.group_ids:
            self._apply_group(move_visual_group(
                [self.styles[i] for i in self._selection_ids()],
                dx=int(payload.get("dx", 0)),
                dy=int(payload.get("dy", 0)),
                display_width=self.manifest.width,
                display_height=self.manifest.height,
            ))
            self._load_selected_controls()
            self._mark_changed()
            self._update_history_actions()
            return
        style = nudge_visual_style(
            self.styles[element_id],
            dx=int(payload.get("dx", 0)),
            dy=int(payload.get("dy", 0)),
            display_width=self.manifest.width,
            display_height=self.manifest.height,
        )
        self.styles[element_id] = style
        self._apply_style_to_preview(style)
        self._load_selected_controls()
        self._mark_changed()
        self._update_history_actions()

    def _sync_grid(self) -> None:
        grid = 5 if self.grid_check.get_active() else 1
        self.backend.evaluate(f"window.__turingEditorGrid = {grid};")

    def _sync_overlay_mode(self) -> None:
        enabled = "true" if self.overlay_mode_check.get_active() else "false"
        self.backend.evaluate(
            f"window.__turingEditorSetOverlayMode?.({enabled});"
        )

    def _sync_round_mask(self) -> None:
        enabled = self.round_mask_check.get_active()

        def finished(outside, error) -> None:
            if error is not None or not enabled:
                self.round_mask_label.set_text("")
                return
            outside = [str(item) for item in outside or []]
            self.round_mask_label.set_text(
                "Todos os elementos estão dentro da área visível"
                if not outside
                else f"Fora da área visível ({len(outside)}): " + ", ".join(outside)
            )

        self._evaluate_json(
            f"window.__turingEditorSetRoundMask?.({'true' if enabled else 'false'}) || []",
            finished,
        )

    def _align_selected(self, alignment: str) -> None:
        if not self._loaded_once:
            return
        self._checkpoint()
        self._apply_group(align_visual_group(
            [self.styles[i] for i in self._selection_ids()],
            alignment,
            display_width=self.manifest.width,
            display_height=self.manifest.height,
        ))
        self._load_selected_controls()
        self._mark_changed()
        self._update_history_actions()

    def _highlight_selected(self) -> None:
        selected = json.dumps(self._selected_id(), ensure_ascii=False)
        group = json.dumps(self._selection_ids() if self.group_ids else [], ensure_ascii=False)
        self.backend.evaluate(
            # A function scope: a top-level const would fail to redeclare on
            # the next selection and leave the preview selection stale.
            f"""
            (() => {{
              document.querySelectorAll('[data-turing-overlay]').forEach(element =>
                element.style.removeProperty('outline'));
              const selected = document.getElementById({selected});
              window.__turingEditorSelect?.(selected);
              window.__turingEditorSetGroup?.({group});
              if (selected) {{
                selected.focus?.({{preventScroll: true}});
              }}
            }})();
            """
        )

    def _apply_style_to_preview(self, style: HtmlVisualElementStyle) -> None:
        payload_data = style.as_dict()
        payload = json.dumps(payload_data, ensure_ascii=False)

        def finished(error: Exception | None) -> None:
            if error is None:
                return
            self.save_button.set_sensitive(False)
            self.build_button.set_sensitive(False)
            self.status_label.set_text(
                f"Falha ao atualizar a prévia de #{style.element_id}: {error}"
            )

        self.backend.evaluate(
            f"""
            (() => {{
              const value = {payload};
              const element = document.getElementById(value.id);
              if (!element) return;
              const properties = {{
                position: 'fixed', left: value.x + 'px', top: value.y + 'px',
                right: 'auto', bottom: 'auto', translate: 'none', transform: 'none',
                width: value.width + 'px', height: value.height + 'px',
                fontSize: value.fontSize + 'px', color: value.color,
                fontWeight: value.fontWeight ? String(value.fontWeight) : 'inherit',
                textAlign: value.textAlign,
                opacity: String(value.visible ? value.opacity / 100 : 0),
                zIndex: String(value.zIndex)
              }};
              Object.entries(properties).forEach(([name, property]) =>
                element.style.setProperty(name.replace(/[A-Z]/g, c => '-' + c.toLowerCase()), property, 'important'));
              window.__turingPositionEditorElement?.(element, value.x, value.y);
              if (value.elementKind === 'bar' && value.componentType) {{
                element.style.setProperty('display', 'block', 'important');
                element.style.setProperty('box-sizing', 'border-box', 'important');
                element.style.setProperty('overflow', 'hidden', 'important');
                element.style.setProperty('padding', '0', 'important');
                element.style.setProperty('border', '0', 'important');
                element.style.setProperty('border-radius', '999px', 'important');
                element.style.setProperty('background', 'rgba(255, 255, 255, 0.18)', 'important');
                const fill = element.querySelector('[data-turing-bar-fill]');
                if (fill) {{
                  fill.style.setProperty('display', 'block', 'important');
                  fill.style.setProperty('height', '100%', 'important');
                  fill.style.setProperty('border-radius', 'inherit', 'important');
                  fill.style.setProperty('background', 'currentColor', 'important');
                  fill.style.setProperty('transition', 'none', 'important');
                }}
              }} else if (value.componentType) {{
                element.style.setProperty('display', 'flex', 'important');
                element.style.setProperty('align-items', 'center', 'important');
                element.style.setProperty('justify-content', 'center', 'important');
                element.style.setProperty('line-height', '1.1', 'important');
                element.style.setProperty('white-space', 'nowrap', 'important');
              }} else {{
                element.style.removeProperty('display');
              }}
              if (value.effectsManaged) {{
                const angle = {{
                  horizontal: '90deg', vertical: '180deg', diagonal: '135deg'
                }}[value.gradientDirection] || '90deg';
                const gradient = `linear-gradient(${{angle}}, ${{value.gradientStartColor}}, ${{value.gradientEndColor}})`;
                const textTargets = [element, ...element.querySelectorAll('*')];
                if (value.elementKind === 'bar') {{
                  for (const target of textTargets) {{
                    target.style.setProperty('background-image', 'none', 'important');
                    target.style.setProperty('background-clip', 'border-box', 'important');
                    target.style.setProperty('-webkit-background-clip', 'border-box', 'important');
                    target.style.setProperty('-webkit-text-fill-color', 'currentColor', 'important');
                    target.style.setProperty('-webkit-text-stroke', '0 transparent', 'important');
                    target.style.setProperty('text-shadow', 'none', 'important');
                  }}
                  const fill = element.querySelector('[data-turing-bar-fill]');
                  const paintTarget = fill || element;
                  paintTarget.style.setProperty(
                    'background',
                    value.gradientEnabled ? gradient : value.color,
                    'important'
                  );
                  element.style.setProperty('box-sizing', 'border-box', 'important');
                  element.style.setProperty(
                    'border',
                    value.outlineWidth
                      ? `${{value.outlineWidth}}px solid ${{value.outlineColor}}`
                      : '0',
                    'important'
                  );
                  element.style.setProperty(
                    'box-shadow',
                    value.glowRadius
                      ? `0 0 ${{value.glowRadius}}px ${{value.glowColor}}`
                      : 'none',
                    'important'
                  );
                }} else {{
                  element.style.setProperty('border', '0', 'important');
                  element.style.setProperty('box-shadow', 'none', 'important');
                  for (const target of textTargets) {{
                    target.style.setProperty(
                      'background-image',
                      value.gradientEnabled ? gradient : 'none',
                      'important'
                    );
                    target.style.setProperty(
                      'background-clip',
                      value.gradientEnabled ? 'text' : 'border-box',
                      'important'
                    );
                    target.style.setProperty(
                      '-webkit-background-clip',
                      value.gradientEnabled ? 'text' : 'border-box',
                      'important'
                    );
                    target.style.setProperty(
                      '-webkit-text-fill-color',
                      value.gradientEnabled ? 'transparent' : 'currentColor',
                      'important'
                    );
                    target.style.setProperty(
                      '-webkit-text-stroke',
                      value.outlineWidth
                        ? `${{value.outlineWidth}}px ${{value.outlineColor}}`
                        : '0 transparent',
                      'important'
                    );
                    target.style.setProperty(
                      'text-shadow',
                      value.glowRadius
                        ? `0 0 ${{value.glowRadius}}px ${{value.glowColor}}`
                        : 'none',
                      'important'
                    );
                  }}
                }}
              }}
              window.__turingEditorRefreshSelection?.();
            }})()
            """,
            finished,
        )

    def _on_spin_text_changed(self, spin: Gtk.SpinButton) -> None:
        """Commit typed spin values immediately instead of waiting for blur."""

        if self._updating_controls or not self._loaded_once:
            return
        text = spin.get_text().strip()
        if not re.fullmatch(r"\d+", text):
            return
        value = int(text)
        adjustment = spin.get_adjustment()
        if not adjustment.get_lower() <= value <= adjustment.get_upper():
            return
        if spin.get_value_as_int() != value:
            spin.set_value(value)

    def _sync_effect_control_sensitivity(self) -> None:
        gradient_enabled = self.gradient_check.get_active()
        self.gradient_start_entry.set_sensitive(gradient_enabled)
        self.gradient_end_entry.set_sensitive(gradient_enabled)
        self.gradient_direction_dropdown.set_sensitive(gradient_enabled)
        self.outline_color_entry.set_sensitive(
            self.outline_width_spin.get_value_as_int() > 0
        )
        self.glow_color_entry.set_sensitive(
            self.glow_radius_spin.get_value_as_int() > 0
        )

    def _on_effect_changed(self, *_args) -> None:
        self._sync_effect_control_sensitivity()
        self._on_style_changed(manage_effects=True)

    def _validated_color_entries(self) -> dict[str, str] | None:
        entries = {
            "color": self.color_entry,
            "gradient_start_color": self.gradient_start_entry,
            "gradient_end_color": self.gradient_end_entry,
            "outline_color": self.outline_color_entry,
            "glow_color": self.glow_color_entry,
        }
        colors: dict[str, str] = {}
        valid = True
        for name, entry in entries.items():
            color = entry.get_text().strip().lower()
            if re.fullmatch(r"#[0-9a-f]{6}", color):
                entry.remove_css_class("error")
                colors[name] = color
            else:
                entry.add_css_class("error")
                valid = False
        return colors if valid else None

    def _on_style_changed(self, *_args, manage_effects: bool = False) -> None:
        if self._updating_controls or not self._loaded_once:
            return
        colors = self._validated_color_entries()
        if colors is None:
            self.save_button.set_sensitive(False)
            self.build_button.set_sensitive(False)
            return
        element_id = self._selected_id()
        previous = self.styles[element_id]
        style = HtmlVisualElementStyle(
            element_id=element_id,
            x=self.x_spin.get_value_as_int(),
            y=self.y_spin.get_value_as_int(),
            width=self.width_spin.get_value_as_int(),
            height=self.height_spin.get_value_as_int(),
            font_size=self.font_spin.get_value_as_int(),
            color=colors["color"],
            font_weight=self.font_weight_values[
                self.font_weight_dropdown.get_selected()
            ],
            text_align=self.text_align_values[
                self.text_align_dropdown.get_selected()
            ],
            opacity=self.opacity_spin.get_value_as_int(),
            z_index=self.layer_spin.get_value_as_int(),
            visible=previous.visible,
            component_type=previous.component_type,
            generated_widget=previous.generated_widget,
            binding=previous.binding,
            formatter=previous.formatter,
            sample=previous.sample,
            element_kind=self.element_kind_values[
                self.element_kind_dropdown.get_selected()
            ],
            effects_managed=previous.effects_managed or manage_effects,
            gradient_enabled=self.gradient_check.get_active(),
            gradient_start_color=colors["gradient_start_color"],
            gradient_end_color=colors["gradient_end_color"],
            gradient_direction=self.gradient_direction_values[
                self.gradient_direction_dropdown.get_selected()
            ],
            outline_width=self.outline_width_spin.get_value_as_int(),
            outline_color=colors["outline_color"],
            glow_radius=self.glow_radius_spin.get_value_as_int(),
            glow_color=colors["glow_color"],
        )
        if self.styles.get(element_id) == style:
            self.save_button.set_sensitive(True)
            self.build_button.set_sensitive(
                self.manifest.native_video_overlay is not None
            )
            return
        self._checkpoint()
        self.styles[element_id] = style
        self._apply_style_to_preview(style)
        self._mark_changed()
        self._update_history_actions()
        self._highlight_selected()

    def _on_reset(self, *_args) -> None:
        self._discard_draft()
        self._loaded_once = False
        self._drag_active = False
        self._resize_active = False
        self.history.clear()
        self._update_history_actions()
        self.styles = {}
        self.save_button.set_sensitive(False)
        self.build_button.set_sensitive(False)
        try:
            self._restore_persisted_element_structure()
        except Exception as exc:
            self.status_label.set_text(
                f"Não foi possível restaurar os valores salvos: {exc}"
            )
            self._toast("Falha ao descartar as alterações")
            return
        self.status_label.set_text("Recarregando valores salvos…")
        self.backend.view.reload()

    def _save(self, build: bool) -> bool:
        try:
            self.manifest = save_visual_styles(
                self.manifest,
                [self.styles[element_id] for element_id in self.element_ids],
            )
        except Exception as exc:
            self.status_label.set_text(f"Não foi possível salvar: {exc}")
            self._toast("Falha ao salvar o tema")
            return False
        self._dirty = False
        self._discard_draft()
        self.status_label.set_text("Layout salvo; o vídeo precisa ser reconstruído")
        self._toast("Layout HTML salvo com backup")
        if build:
            self._start_build()
        elif self.live_display_check.get_visible() and self.live_display_check.get_active():
            self._update_physical_display()
        return True

    def _is_active_display_theme(self) -> bool:
        try:
            in_themes_dir = self.manifest.root.resolve().parent == THEMES_DIR.resolve()
        except OSError:
            return False
        return in_themes_dir and active_html_theme(CONFIG_FILE) == self.manifest.root.name

    def _update_physical_display(self) -> None:
        try:
            requested = request_monitor_reload()
        except Exception as exc:
            print(f"Could not ask the monitor to reload: {exc}", file=sys.stderr, flush=True)
            requested = False
        if requested:
            self.status_label.set_text("Layout salvo; atualizando a tela física…")
            self._toast("Atualizando a tela física")
        else:
            self._toast("O monitor não está em execução; inicie-o para ver o tema na tela")

    def _start_build(self) -> None:
        if self._build_process is not None:
            return
        self.save_button.set_sensitive(False)
        self.build_button.set_sensitive(False)
        self.status_label.set_text("Gerando o vídeo nativo…")
        try:
            self._build_process = subprocess.Popen(
                [
                    resolve_project_python(ROOT),
                    str(BUILD_SCRIPT),
                    "--theme",
                    str(self.manifest.root),
                ],
                cwd=str(ROOT),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception as exc:
            self._build_process = None
            self.status_label.set_text(f"Não foi possível iniciar a geração: {exc}")
            self.save_button.set_sensitive(True)
            self.build_button.set_sensitive(True)
            return
        GLib.timeout_add(200, self._poll_build)

    def _poll_build(self) -> bool:
        process = self._build_process
        if process is None:
            return False
        if process.poll() is None:
            return True
        stdout, stderr = process.communicate()
        self._build_process = None
        self.save_button.set_sensitive(True)
        self.build_button.set_sensitive(True)
        if process.returncode == 0:
            self.status_label.set_text("Vídeo gerado e pronto para sincronização")
            self._toast("Vídeo do tema gerado")
        else:
            detail = (stderr or stdout or "erro desconhecido").strip().splitlines()[-1]
            self.status_label.set_text(f"Falha ao gerar vídeo: {detail}")
            self._toast("Falha ao gerar o vídeo")
        return False

    def _on_close_request(self, _window) -> bool:
        if self._build_process is not None and self._build_process.poll() is None:
            self._toast("Aguarde a geração do vídeo terminar")
            return True
        if self._dirty and self._loaded_once and not self._close_confirmed:
            self._confirm_close()
            return True
        self._cancel_pending_draft()
        self.backend.close()
        return False

    def _confirm_close(self) -> None:
        dialog = Adw.AlertDialog(
            heading="Salvar as alterações antes de fechar?",
            body="Se você fechar sem salvar, as alterações deste tema serão perdidas.",
        )
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("discard", "Descartar")
        dialog.add_response("save", "Salvar")
        dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("save")
        dialog.set_close_response("cancel")

        def on_response(_dialog, response: str) -> None:
            if response == "save" and not self._save(False):
                return
            if response == "discard":
                self._discard_draft()
            if response in {"save", "discard"}:
                self._close_confirmed = True
                self.close()

        dialog.connect("response", on_response)
        dialog.present(self)

    # Drafts protect unsaved work against crashes and closed sessions. They
    # are written outside the theme folder (see library/html_editor_drafts.py).
    def _schedule_draft(self) -> None:
        self._cancel_pending_draft()
        self._draft_source = GLib.timeout_add_seconds(DRAFT_DELAY_SECONDS, self._write_draft_now)

    def _cancel_pending_draft(self) -> None:
        if self._draft_source is not None:
            GLib.source_remove(self._draft_source)
            self._draft_source = None

    def _write_draft_now(self) -> bool:
        self._draft_source = None
        if self._dirty and self._loaded_once:
            try:
                write_draft(self.manifest, [self.styles[i] for i in self.element_ids if i in self.styles])
            except Exception as exc:
                print(f"Could not write editor draft: {exc}", file=sys.stderr, flush=True)
        return False

    def _discard_draft(self) -> None:
        self._cancel_pending_draft()
        try:
            clear_draft(self.manifest)
        except OSError as exc:
            print(f"Could not remove editor draft: {exc}", file=sys.stderr, flush=True)

    def _offer_draft_recovery(self) -> None:
        try:
            draft = load_draft(self.manifest, self.styles.values())
        except Exception as exc:
            print(f"Could not read editor draft: {exc}", file=sys.stderr, flush=True)
            return
        if draft is None:
            return
        when = draft.saved_at.astimezone().strftime("%d/%m/%Y %H:%M")
        body = f"Há alterações deste tema que não foram salvas, de {when}."
        if not draft.matches_saved_theme:
            body += " O tema foi salvo depois disso; recuperar substitui essa versão no editor."
        dialog = Adw.AlertDialog(heading="Recuperar alterações não salvas?", body=body)
        dialog.add_response("discard", "Descartar rascunho")
        dialog.add_response("restore", "Recuperar")
        dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_response_appearance("restore", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("restore")
        dialog.set_close_response("restore")

        def on_response(_dialog, response: str) -> None:
            if response == "restore":
                self._restore_draft(draft.styles)
            else:
                self._discard_draft()

        dialog.connect("response", on_response)
        dialog.present(self)

    def _restore_draft(self, draft_styles) -> None:
        # Overlays written in the theme HTML always exist; keep their current
        # style when the draft predates them. Editor-created widgets follow
        # the draft, including ones it removed.
        current = dict(self.styles)
        restored = {
            style.element_id: style
            for style in draft_styles
            if style.is_generated or style.element_id in current
        }
        for element_id, style in current.items():
            if not style.is_generated and element_id not in restored:
                restored[element_id] = style
        self._checkpoint()
        self._restore_history(tuple(restored.values()))
        self._toast("Rascunho recuperado; salve para manter as alterações")


class HtmlThemeEditorApplication(Adw.Application):
    def __init__(self, manifest: ThemeManifest):
        super().__init__(
            application_id="io.github.turing.HtmlThemeVisualEditor",
            flags=Gio.ApplicationFlags.NON_UNIQUE,
        )
        self.manifest = manifest
        self.window = None

    def do_activate(self) -> None:
        if self.window is None:
            self.window = HtmlThemeEditorWindow(self, self.manifest)
        self.window.present()


def load_manifest(theme_name: str) -> ThemeManifest:
    requested = str(theme_name).strip()
    if not requested or Path(requested).name != requested:
        raise ThemeValidationError("informe somente o nome da pasta do tema")
    manifest = ThemeManifest.load(THEMES_DIR / requested)
    if manifest.engine != "html":
        raise ThemeValidationError("o editor visual requer um tema HTML")
    return manifest


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        print("Uso: html-theme-editor-gtk.py NOME_DO_TEMA", file=sys.stderr)
        return 2
    try:
        manifest = load_manifest(argv[0])
    except Exception as exc:
        print(f"Erro do editor HTML: {exc}", file=sys.stderr)
        return 2
    install_editor_extensions()
    return HtmlThemeEditorApplication(manifest).run([])


def install_editor_extensions() -> None:
    """Background page, visual presets and color tools for this editor."""
    from library.html_theme_background_compat import install_background_editor_hook
    from library.html_theme_color_tools import install_color_tools_hook
    from library.html_theme_style_presets_ui import install_style_preset_editor_hook

    for install in (install_background_editor_hook, install_style_preset_editor_hook, install_color_tools_hook):
        try:
            install()
        except Exception as exc:
            print(f"Could not install HTML editor extension {install.__name__}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
