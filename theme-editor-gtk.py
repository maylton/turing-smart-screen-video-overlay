#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""GTK4 + Libadwaita visual theme editor."""

from __future__ import annotations

import copy
import os
import re
import shutil
import threading
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# GTK comes from the system Python on Arch/CachyOS, while the project
# dependencies may live in the virtual environment.
for site_dir in (
    ROOT / "venv" / "lib",
    ROOT / ".venv" / "lib",
):
    if site_dir.is_dir():
        for candidate in site_dir.glob("python*/site-packages"):
            sys.path.insert(0, str(candidate))

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk

from PIL import Image
import ruamel.yaml

from library.theme_video_background import (
    display_video_path,
    find_prepared_local_video,
    generate_background,
)
from library.theme_property_presets import property_preset_options
from library.theme_text_style_presets import (
    is_text_style_node,
    text_effect_preset,
    text_effect_preset_names,
    text_style_preset_names,
    text_style_updates,
)
from video_manager_backend import VideoManager
from ruamel.yaml.comments import CommentedSeq

APP_ID = "io.github.turing.SmartScreen.ThemeEditor"
CONFIG_FILE = ROOT / "config.yaml"
THEMES_DIR = ROOT / "res" / "themes"
CLASSIC_EDITOR = ROOT / "theme-editor.py"
EDITOR_TEMPLATE_DIR = ROOT / "res" / "editor-templates"
DEFAULT_TEMPLATE_FILE = EDITOR_TEMPLATE_DIR / "default.yaml"
EXAMPLE_TEMPLATE_FILE = EDITOR_TEMPLATE_DIR / "theme_example.yaml"

EDITABLE_KEYS = (
    "X", "Y", "WIDTH", "HEIGHT", "RADIUS",
    "DISPLAY_SIZE", "DISPLAY_ORIENTATION",
    "FONT", "FONT_SIZE", "FONT_COLOR",
    "BACKGROUND_IMAGE", "BACKGROUND_COLOR",
    "BAR_COLOR", "BAR_BACKGROUND_COLOR", "LINE_COLOR",
    "AXIS_COLOR", "DISPLAY_RGB_LED",
    "MIN_VALUE", "MAX_VALUE", "MIN_SIZE",
    "HISTORY_SIZE", "LINE_WIDTH", "AXIS_FONT_SIZE",
    "ANGLE_START", "ANGLE_END", "ANGLE_STEPS", "ANGLE_SEP",
    "ALIGN", "ANCHOR", "TEXT", "FORMAT",
    "SHOW", "SHOW_UNIT", "SHOW_TEXT",
    "BAR_OUTLINE", "REVERSE_DIRECTION", "AUTOSCALE",
    "AXIS", "CLOCKWISE", "DRAW_BAR_BACKGROUND",
    "INTERVAL", "REFRESH_INTERVAL", "PATH",
    "MODE", "ENABLED", "OVERLAY", "PREVIEW_BACKGROUND",
    "AXIS_FONT", "CUSTOM_BBOX", "TEXT_OFFSET",
    "BAR_DECORATION",
)

NUMERIC_KEYS = {
    "X", "Y", "WIDTH", "HEIGHT", "RADIUS",
    "FONT_SIZE", "INTERVAL", "REFRESH_INTERVAL",
    "MIN_VALUE", "MAX_VALUE", "MIN_SIZE",
    "HISTORY_SIZE", "LINE_WIDTH", "AXIS_FONT_SIZE",
    "ANGLE_START", "ANGLE_END", "ANGLE_STEPS", "ANGLE_SEP",
}

BOOLEAN_KEYS = {
    "SHOW", "SHOW_UNIT", "SHOW_TEXT",
    "BAR_OUTLINE", "REVERSE_DIRECTION", "AUTOSCALE",
    "AXIS", "CLOCKWISE", "DRAW_BAR_BACKGROUND",
    "ENABLED", "OVERLAY",
}

COLOR_KEYS = {
    "FONT_COLOR", "BACKGROUND_COLOR", "BAR_COLOR",
    "BAR_BACKGROUND_COLOR", "LINE_COLOR", "AXIS_COLOR",
    "DISPLAY_RGB_LED",
}

COMPONENT_PRESETS = {
    "Custom text": ("custom", "text"),
    "Static image": ("custom", "image"),
    "CPU usage": ("sensor", "CPU.PERCENTAGE"),
    "CPU temperature": ("sensor", "CPU.TEMPERATURE"),
    "RAM usage": ("sensor", "MEMORY"),
    "GPU usage": ("sensor", "GPU.PERCENTAGE"),
    "GPU temperature": ("sensor", "GPU.TEMPERATURE"),
    "GPU memory usage": ("sensor", "GPU.MEMORY_PERCENT"),
    "Internet download": ("sensor", "NET.WLO.DOWNLOAD"),
    "Internet upload": ("sensor", "NET.WLO.UPLOAD"),
    "Weather": ("sensor", "WEATHER"),
    "Disk usage": ("sensor", "DISK"),
    "Ping": ("sensor", "PING"),
    "System uptime": ("sensor", "UPTIME"),
    "Date": ("sensor", "DATE.DAY"),
    "Time": ("sensor", "DATE.HOUR"),
}

yaml = ruamel.yaml.YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        return yaml.load(stream)


def prepare_yaml_for_safe_dump(node):
    """
    Keep ruamel comments/maps, but force simple scalar sequences to flow style.

    This prevents comments associated with fields such as FONT_COLOR from being
    emitted between a mapping key and an incorrectly indented block sequence:

        FONT_COLOR:
        # comment
        - 255

    The safe output becomes:

        FONT_COLOR: [255, 255, 255]
    """
    if isinstance(node, dict):
        for value in node.values():
            prepare_yaml_for_safe_dump(value)

    elif isinstance(node, list):
        for value in node:
            if isinstance(value, (dict, list)):
                prepare_yaml_for_safe_dump(value)

        if node and all(
            not isinstance(value, (dict, list))
            for value in node
        ):
            if isinstance(node, CommentedSeq):
                node.fa.set_flow_style()

    return node


def save_yaml_atomic(path: Path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")

    # Work on a copy so serialization formatting never mutates Undo/Redo state.
    dump_data = copy.deepcopy(data)
    prepare_yaml_for_safe_dump(dump_data)

    try:
        with temporary.open("w", encoding="utf-8") as stream:
            yaml.dump(dump_data, stream)

        # Validate the exact bytes that will replace the theme.
        with temporary.open("r", encoding="utf-8") as stream:
            yaml.load(stream)

        os.replace(temporary, path)
    except Exception:
        # Keep the invalid temporary file for diagnosis, but never replace the
        # valid theme.yaml.
        raise


def project_python() -> str:
    for candidate in (
        ROOT / "venv" / "bin" / "python3",
        ROOT / ".venv" / "bin" / "python3",
    ):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return sys.executable


def available_themes() -> list[str]:
    if not THEMES_DIR.exists():
        return []

    themes = []
    try:
        for path in THEMES_DIR.iterdir():
            if not path.is_dir():
                continue
            if (path / "theme.yaml").is_file() or (path / "theme.yml").is_file():
                themes.append(path.name)
    except OSError:
        return []
    return sorted(themes, key=str.casefold)


def write_current_theme(theme_name: str) -> None:
    if not CONFIG_FILE.is_file():
        raise FileNotFoundError(CONFIG_FILE)

    content = CONFIG_FILE.read_text(encoding="utf-8")
    pattern = re.compile(r"(?m)^(\s*THEME\s*:\s*).*$")
    if not pattern.search(content):
        raise RuntimeError("Could not find config.THEME in config.yaml")

    updated = pattern.sub(
        lambda match: f'{match.group(1)}"{theme_name}"',
        content,
        count=1,
    )
    temporary = CONFIG_FILE.with_suffix(".yaml.theme-editor.tmp")
    temporary.write_text(updated, encoding="utf-8")
    os.replace(temporary, CONFIG_FILE)


class ElementItem(GObject.Object):
    """Tree node used by Gtk.TreeListModel."""

    label = GObject.Property(type=str)
    path_text = GObject.Property(type=str)

    def __init__(self, label: str, path: tuple, node=None):
        super().__init__()
        self.label = label
        self.path = path
        self.path_text = " / ".join(str(part) for part in path)
        self.node = node
        self.children = Gio.ListStore.new(ElementItem)

    def has_children(self):
        return self.children.get_n_items() > 0


class ThemeEditorWindow(Adw.ApplicationWindow):
    def __init__(self, app, theme_name: str):
        super().__init__(
            application=app,
            title=f"Theme Editor — {theme_name}",
            default_width=1540,
            default_height=900,
        )
        self.set_size_request(1180, 720)

        self.theme_name = theme_name
        self.theme_dir = THEMES_DIR / theme_name
        self.theme_file = self.theme_dir / "theme.yaml"
        self.preview_file = self.theme_dir / "preview.png"

        if not self.theme_file.is_file():
            raise FileNotFoundError(self.theme_file)

        self.theme_data = load_yaml(self.theme_file)
        self.session_original = copy.deepcopy(self.theme_data)
        self.undo_stack = []
        self.redo_stack = []
        self.selected_path = None
        self.property_widgets = {}
        self.property_rows = []
        self.drag_start_pointer = None
        self.drag_start_element = None
        self.drag_dirty = False
        self.preview_generation = 0
        self.restoring_history = False

        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        toolbar = Adw.ToolbarView()
        self.toast_overlay.set_child(toolbar)

        header = Adw.HeaderBar()
        self.window_title = Adw.WindowTitle(
            title=theme_name,
            subtitle="Theme editor",
        )
        header.set_title_widget(self.window_title)
        toolbar.add_top_bar(header)

        self.undo_button = Gtk.Button(
            icon_name="edit-undo-symbolic",
            tooltip_text="Undo the last change",
        )
        self.undo_button.connect("clicked", lambda *_: self.undo())
        header.pack_start(self.undo_button)

        self.redo_button = Gtk.Button(
            icon_name="edit-redo-symbolic",
            tooltip_text="Redo the last undone change",
        )
        self.redo_button.connect("clicked", lambda *_: self.redo())
        header.pack_start(self.redo_button)

        classic_btn = Gtk.Button(
            icon_name="applications-system-symbolic",
            tooltip_text="Open the classic editor",
        )
        classic_btn.connect("clicked", lambda *_: self.open_classic_editor())
        header.pack_end(classic_btn)

        save_btn = Gtk.Button(
            label="Save",
            tooltip_text="Save the current theme YAML",
        )
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", lambda *_: self.save())
        header.pack_end(save_btn)

        save_as_btn = Gtk.Button(
            label="Save as…",
            tooltip_text="Create a new theme from the current theme",
        )
        save_as_btn.connect("clicked", lambda *_: self.save_as())
        header.pack_end(save_as_btn)

        refresh_btn = Gtk.Button(
            icon_name="view-refresh-symbolic",
            tooltip_text="Render and refresh the theme preview",
        )
        refresh_btn.connect("clicked", lambda *_: self.refresh_preview())
        header.pack_end(refresh_btn)

        media_btn = Gtk.Button(
            icon_name="video-x-generic-symbolic",
            tooltip_text="Choose theme video or generate its preview background",
        )
        media_btn.connect("clicked", self.on_video_tools_clicked)
        header.pack_end(media_btn)

        body = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        body.set_position(340)
        body.set_shrink_start_child(False)
        body.set_shrink_end_child(False)
        toolbar.set_content(body)

        left = self.build_elements_panel()
        body.set_start_child(left)

        center_right = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        center_right.set_position(740)
        center_right.set_shrink_start_child(False)
        center_right.set_shrink_end_child(False)
        body.set_end_child(center_right)

        center_right.set_start_child(self.build_preview_panel())
        center_right.set_end_child(self.build_properties_panel())

        self.populate_elements()
        self.update_history_buttons()
        self.refresh_preview()

    def build_elements_panel(self):
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
            margin_top=16,
            margin_bottom=16,
            margin_start=16,
            margin_end=16,
        )
        box.set_size_request(320, -1)

        title = Gtk.Label(label="Theme elements", xalign=0)
        title.add_css_class("heading")
        box.append(title)

        search = Gtk.SearchEntry(placeholder_text="Search elements")
        search.connect("search-changed", self.on_search_changed)
        box.append(search)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)

        self.root_items = Gio.ListStore.new(ElementItem)
        self.tree_model = Gtk.TreeListModel.new(
            self.root_items,
            False,
            False,
            self.create_children_model,
        )
        self.selection_model = Gtk.SingleSelection.new(self.tree_model)
        self.selection_model.connect("notify::selected-item", self.on_tree_selected)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.setup_tree_item)
        factory.connect("bind", self.bind_tree_item)

        self.element_list = Gtk.ListView(
            model=self.selection_model,
            factory=factory,
        )
        self.element_list.add_css_class("boxed-list")
        scroll.set_child(self.element_list)
        box.append(scroll)

        controls = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )
        expand_btn = Gtk.Button(
            label="Expand all",
            tooltip_text="Expand every group in the component tree",
        )
        expand_btn.connect("clicked", lambda *_: self.set_all_expanded(True))
        collapse_btn = Gtk.Button(
            label="Collapse all",
            tooltip_text="Collapse every group in the component tree",
        )
        collapse_btn.connect("clicked", lambda *_: self.set_all_expanded(False))
        controls.append(expand_btn)
        controls.append(collapse_btn)
        box.append(controls)

        action_grid = Gtk.Grid(
            column_spacing=8,
            row_spacing=8,
            column_homogeneous=True,
        )

        add_button = Gtk.Button(
            label="Add",
            icon_name="list-add-symbolic",
            tooltip_text="Add a new sensor, text, or image component",
        )
        add_button.add_css_class("suggested-action")
        add_button.connect("clicked", lambda *_: self.show_add_component_dialog())
        action_grid.attach(add_button, 0, 0, 1, 1)

        duplicate_button = Gtk.Button(
            label="Duplicate",
            icon_name="edit-copy-symbolic",
            tooltip_text="Duplicate the selected custom text or static image",
        )
        duplicate_button.connect("clicked", lambda *_: self.duplicate_selected())
        action_grid.attach(duplicate_button, 1, 0, 1, 1)

        enable_button = Gtk.Button(
            label="Enable",
            icon_name="object-select-symbolic",
            tooltip_text="Enable the selected component and its visible parts",
        )
        enable_button.connect("clicked", lambda *_: self.enable_selected())
        action_grid.attach(enable_button, 0, 1, 1, 1)

        disable_button = Gtk.Button(
            label="Disable",
            icon_name="process-stop-symbolic",
            tooltip_text="Disable the selected component without deleting its YAML structure",
        )
        disable_button.connect("clicked", lambda *_: self.disable_selected())
        action_grid.attach(disable_button, 1, 1, 1, 1)

        delete_button = Gtk.Button(
            label="Delete",
            icon_name="user-trash-symbolic",
            tooltip_text="Delete custom elements or disable sensor components",
        )
        delete_button.add_css_class("destructive-action")
        delete_button.connect("clicked", lambda *_: self.delete_selected())
        action_grid.attach(delete_button, 0, 2, 2, 1)

        box.append(action_grid)

        classic = Gtk.Button(
            label="Open classic editor…",
            tooltip_text="Open the original editor for tools not yet migrated to GTK",
        )
        classic.connect("clicked", lambda *_: self.open_classic_editor())
        box.append(classic)
        return box

    def create_children_model(self, item):
        if isinstance(item, ElementItem) and item.has_children():
            return item.children
        return None

    def setup_tree_item(self, _factory, list_item):
        expander = Gtk.TreeExpander()
        label = Gtk.Label(xalign=0)
        label.set_hexpand(True)
        label.set_ellipsize(3)
        expander.set_child(label)
        list_item.set_child(expander)

    def bind_tree_item(self, _factory, list_item):
        row = list_item.get_item()
        expander = list_item.get_child()
        expander.set_list_row(row)

        item = row.get_item()
        label = expander.get_child()
        label.set_label(item.label)
        label.set_tooltip_text(item.path_text or item.label)

    def set_all_expanded(self, expanded):
        def walk(position=0):
            count = self.tree_model.get_n_items()
            for index in range(count):
                row = self.tree_model.get_item(index)
                if row is not None and row.is_expandable():
                    row.set_expanded(expanded)
            return False
        GLib.idle_add(walk)

    def build_preview_panel(self):
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_top=16,
            margin_bottom=16,
            margin_start=16,
            margin_end=16,
        )
        box.set_size_request(560, -1)

        title = Gtk.Label(label="Live preview", xalign=0)
        title.add_css_class("heading")
        box.append(title)

        frame = Gtk.AspectFrame(
            ratio=1.0,
            obey_child=False,
            xalign=0.5,
            yalign=0.5,
        )
        frame.set_vexpand(True)
        frame.set_hexpand(True)

        self.preview_picture = Gtk.Picture()
        self.preview_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.preview_picture.add_css_class("display-preview")
        frame.set_child(self.preview_picture)

        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self.on_preview_drag_begin)
        drag.connect("drag-update", self.on_preview_drag_update)
        drag.connect("drag-end", self.on_preview_drag_end)
        self.preview_picture.add_controller(drag)
        box.append(frame)

        hint = Gtk.Label(
            label="Select an element with X/Y, then drag it directly on the preview.",
            xalign=0,
            wrap=True,
        )
        hint.add_css_class("dim-label")
        box.append(hint)

        self.preview_status = Gtk.Label(
            label="",
            xalign=0,
            wrap=True,
        )
        self.preview_status.add_css_class("dim-label")
        box.append(self.preview_status)
        return box

    def build_properties_panel(self):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_size_request(420, -1)

        self.properties_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=14,
            margin_top=16,
            margin_bottom=16,
            margin_start=16,
            margin_end=16,
        )
        scroll.set_child(self.properties_box)

        title = Gtk.Label(label="Properties", xalign=0)
        title.add_css_class("heading")
        self.properties_box.append(title)

        self.path_label = Gtk.Label(
            label="Select an element",
            xalign=0,
            wrap=True,
        )
        self.path_label.add_css_class("dim-label")
        self.properties_box.append(self.path_label)

        self.dynamic_group = Adw.PreferencesGroup()
        self.properties_box.append(self.dynamic_group)

        apply_btn = Gtk.Button(
            label="Apply property changes",
            tooltip_text="Save the edited values and refresh the preview",
        )
        apply_btn.add_css_class("suggested-action")
        apply_btn.connect("clicked", lambda *_: self.apply_properties())
        self.properties_box.append(apply_btn)

        reset_btn = Gtk.Button(
            label="Reset selected element",
            tooltip_text="Restore this element to its state when the editor was opened",
        )
        reset_btn.connect("clicked", lambda *_: self.reset_selected())
        self.properties_box.append(reset_btn)

        video_btn = Gtk.Button(
            label="Video and background…",
            tooltip_text=(
                "Choose a local/display video or generate a preview background"
            ),
        )
        video_btn.connect("clicked", self.on_video_tools_clicked)
        self.properties_box.append(video_btn)

        effects_btn = Gtk.Button(
            label="Text effects…",
            tooltip_text="Configure shadow, glow, and outline",
        )
        effects_btn.connect("clicked", self.on_text_effects_clicked)
        self.properties_box.append(effects_btn)

        return scroll

    def iter_editable_nodes(self, node=None, path=()):
        if node is None:
            node = self.theme_data

        if isinstance(node, dict):
            if any(key in node for key in EDITABLE_KEYS):
                yield path, node
            for key, value in node.items():
                if isinstance(value, (dict, list)):
                    yield from self.iter_editable_nodes(value, path + (key,))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                if isinstance(value, (dict, list)):
                    yield from self.iter_editable_nodes(value, path + (index,))

    def node_at_path(self, path):
        node = self.theme_data
        for part in path:
            node = node[part]
        return node

    def build_element_tree(self):
        """Build a compact hierarchy from editable paths."""
        root = {}

        for path, node in self.iter_editable_nodes():
            cursor = root
            for index, part in enumerate(path):
                cursor = cursor.setdefault(part, {"__children__": {}, "__node__": None})
                if index == len(path) - 1:
                    cursor["__node__"] = node
                cursor = cursor["__children__"]

        def build_store(mapping, prefix=()):
            store = Gio.ListStore.new(ElementItem)
            for key, payload in mapping.items():
                path = prefix + (key,)
                item = ElementItem(str(key), path, payload.get("__node__"))
                children = build_store(payload.get("__children__", {}), path)
                for index in range(children.get_n_items()):
                    item.children.append(children.get_item(index))
                store.append(item)
            return store

        return build_store(root)

    def populate_elements(self, search_text=""):
        self.root_items.remove_all()
        query = search_text.strip().casefold()

        full_tree = self.build_element_tree()

        def clone_filtered(item):
            child_clones = []
            for index in range(item.children.get_n_items()):
                clone = clone_filtered(item.children.get_item(index))
                if clone is not None:
                    child_clones.append(clone)

            own_match = (
                not query
                or query in item.label.casefold()
                or query in item.path_text.casefold()
            )
            if not own_match and not child_clones:
                return None

            clone = ElementItem(item.label, item.path, item.node)
            for child in child_clones:
                clone.children.append(child)
            return clone

        for index in range(full_tree.get_n_items()):
            clone = clone_filtered(full_tree.get_item(index))
            if clone is not None:
                self.root_items.append(clone)

        if query:
            GLib.idle_add(lambda: (self.set_all_expanded(True), False)[1])

    def on_search_changed(self, entry):
        self.populate_elements(entry.get_text())

    def on_tree_selected(self, selection, _param):
        if self.restoring_history:
            return

        row = selection.get_selected_item()
        if row is None:
            return
        item = row.get_item()
        if item is None:
            return

        # Parent/group nodes are selectable for navigation, but properties are
        # shown only when the corresponding YAML node is editable.
        self.selected_path = item.path
        try:
            node = self.node_at_path(self.selected_path)
        except Exception:
            self.clear_property_group()
            self.path_label.set_label(item.path_text)
            return

        if not isinstance(node, dict) or not any(key in node for key in EDITABLE_KEYS):
            self.clear_property_group()
            self.path_label.set_label(item.path_text)
            return

        self.build_property_rows()

    def selected_movable_node(self):
        if self.selected_path is None:
            return None
        try:
            node = self.node_at_path(self.selected_path)
        except Exception:
            return None
        if not isinstance(node, dict):
            return None
        if "X" not in node or "Y" not in node:
            return None
        return node

    def preview_to_display_scale(self):
        width = max(1, self.preview_picture.get_allocated_width())
        height = max(1, self.preview_picture.get_allocated_height())
        rendered = min(width, height)
        return 480.0 / rendered

    def on_preview_drag_begin(self, _gesture, start_x, start_y):
        self.drag_start_pointer = None
        self.drag_start_element = None
        self.drag_dirty = False
        self.drag_history_pushed = False

        node = self.selected_movable_node()
        if node is None:
            self.toast("Select an element with X and Y first")
            self.drag_start_pointer = None
            self.drag_start_element = None
            return

        self.drag_history_pushed = self.push_undo()
        self.drag_start_pointer = (start_x, start_y)
        self.drag_start_element = (int(node["X"]), int(node["Y"]))
        self.drag_dirty = False

    def on_preview_drag_update(self, _gesture, offset_x, offset_y):
        node = self.selected_movable_node()
        if node is None or self.drag_start_element is None:
            return

        scale = self.preview_to_display_scale()
        new_x = round(self.drag_start_element[0] + offset_x * scale)
        new_y = round(self.drag_start_element[1] + offset_y * scale)

        # Keep the anchor point within the display.
        node["X"] = max(0, min(480, new_x))
        node["Y"] = max(0, min(480, new_y))
        self.drag_dirty = True

        # Update fields immediately without rebuilding the whole panel.
        if "X" in self.property_widgets:
            self.property_widgets["X"].set_text(str(node["X"]))
        if "Y" in self.property_widgets:
            self.property_widgets["Y"].set_text(str(node["Y"]))

        self.preview_status.set_label(
            f"Position: X={node['X']}, Y={node['Y']} — release to render"
        )

    def on_preview_drag_end(self, _gesture, _offset_x, _offset_y):
        if self.drag_start_element is None:
            return

        self.drag_start_pointer = None
        self.drag_start_element = None

        if not self.drag_dirty:
            if getattr(self, "drag_history_pushed", False) and self.undo_stack:
                self.undo_stack.pop()
                self.update_history_buttons()
            self.drag_history_pushed = False
            return

        save_yaml_atomic(self.theme_file, self.theme_data)
        self.refresh_preview()
        self.drag_dirty = False
        self.drag_history_pushed = False
        self.update_history_buttons()

    def clear_property_group(self):
        # Adw.PreferencesGroup owns internal layout children. Removing those
        # children directly leaves rows added through .add() registered in the
        # group and causes every rebuild to duplicate PATH/INTERVAL/etc.
        for row in self.property_rows:
            self.dynamic_group.remove(row)
        self.property_rows.clear()
        self.property_widgets.clear()

    @staticmethod
    def parse_theme_color(value, default=(255, 255, 255, 255)):
        if isinstance(value, (list, tuple)):
            parts = [int(component) for component in value]
        elif isinstance(value, str):
            raw = value.strip()
            comma_parts = [part.strip() for part in raw.split(",")]
            if len(comma_parts) in (3, 4):
                try:
                    parts = [int(component) for component in comma_parts]
                except ValueError:
                    parts = []
            else:
                parts = []

            if not parts:
                rgba = Gdk.RGBA()
                if not rgba.parse(raw):
                    raise ValueError(f"Unsupported color value: {value}")
                parts = [
                    round(rgba.red * 255),
                    round(rgba.green * 255),
                    round(rgba.blue * 255),
                    round(rgba.alpha * 255),
                ]
        else:
            parts = list(default)

        if len(parts) not in (3, 4):
            raise ValueError("Colors must contain 3 or 4 components.")
        if any(component < 0 or component > 255 for component in parts):
            raise ValueError("Color components must be between 0 and 255.")

        while len(parts) < 4:
            parts.append(255)
        return tuple(parts[:4])

    @staticmethod
    def theme_color_length(value, force_alpha=False):
        if force_alpha:
            return 4
        if isinstance(value, (list, tuple)) and len(value) in (3, 4):
            return len(value)
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",")]
            if len(parts) in (3, 4):
                try:
                    [int(part) for part in parts]
                except ValueError:
                    pass
                else:
                    return len(parts)
        return 3

    def create_color_selector(self, value, force_alpha=False):
        components = self.parse_theme_color(value)
        rgba = Gdk.RGBA()
        rgba.red = components[0] / 255.0
        rgba.green = components[1] / 255.0
        rgba.blue = components[2] / 255.0
        rgba.alpha = components[3] / 255.0

        use_alpha = force_alpha or self.theme_color_length(value) == 4

        if hasattr(Gtk, "ColorDialogButton") and hasattr(Gtk, "ColorDialog"):
            dialog = Gtk.ColorDialog()
            dialog.set_with_alpha(use_alpha)
            try:
                button = Gtk.ColorDialogButton.new(dialog)
            except AttributeError:
                button = Gtk.ColorDialogButton(dialog=dialog)
        elif hasattr(Gtk, "ColorButton"):
            try:
                button = Gtk.ColorButton.new_with_rgba(rgba)
            except AttributeError:
                button = Gtk.ColorButton()
            if hasattr(button, "set_use_alpha"):
                button.set_use_alpha(use_alpha)
        else:
            raise RuntimeError(
                "This GTK build does not provide a supported color selector."
            )

        button.set_rgba(rgba)
        button.set_size_request(72, 34)
        button.set_valign(Gtk.Align.CENTER)
        button.set_tooltip_text("Choose a color")
        button._theme_color_widget = True
        button._theme_color_length = self.theme_color_length(
            value,
            force_alpha=force_alpha,
        )
        return button

    @staticmethod
    def color_selector_value(widget, length=None):
        rgba = widget.get_rgba()
        values = [
            round(rgba.red * 255),
            round(rgba.green * 255),
            round(rgba.blue * 255),
            round(rgba.alpha * 255),
        ]
        target_length = length or getattr(widget, "_theme_color_length", 3)
        return values[:target_length]

    def set_color_selector_value(self, widget, value):
        components = self.parse_theme_color(value)
        rgba = Gdk.RGBA()
        rgba.red = components[0] / 255.0
        rgba.green = components[1] / 255.0
        rgba.blue = components[2] / 255.0
        rgba.alpha = components[3] / 255.0
        widget.set_rgba(rgba)

    @staticmethod
    def same_property_value(left, right):
        if isinstance(left, bool) or isinstance(right, bool):
            return left is right
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return float(left) == float(right)
        return left == right

    def sync_property_preset_dropdown(self, widget, value):
        dropdown = getattr(widget, "_theme_preset_dropdown", None)
        if dropdown is None:
            return

        values = getattr(dropdown, "_theme_preset_values", ())
        for index, preset_value in enumerate(values):
            if self.same_property_value(preset_value, value):
                dropdown.set_selected(index)
                return
        dropdown.set_selected(Gtk.INVALID_LIST_POSITION)

    def set_property_widget_value(self, key, value):
        widget = self.property_widgets.get(key)
        if widget is None:
            return

        if isinstance(widget, Adw.EntryRow):
            widget.set_text(self.value_to_text(value))
            self.sync_property_preset_dropdown(widget, value)
        elif isinstance(widget, Adw.SwitchRow):
            widget.set_active(bool(value))
        elif getattr(widget, "_theme_color_widget", False):
            self.set_color_selector_value(widget, value)
        elif hasattr(widget, "set_text"):
            widget.set_text(self.value_to_text(value))

    def property_preset_options(self, key, current_value):
        return property_preset_options(
            key,
            current_value,
            fonts_dir=ROOT / "res" / "fonts",
            theme_dir=self.theme_dir,
        )

    def create_property_preset_dropdown(
        self,
        key,
        current_value,
        target_entry,
    ):
        options = self.property_preset_options(key, current_value)
        if len(options) < 2:
            return None

        labels = tuple(label for label, _value in options)
        values = tuple(value for _label, value in options)
        dropdown = Gtk.DropDown.new_from_strings(labels)
        dropdown.set_size_request(220, -1)
        dropdown.set_valign(Gtk.Align.CENTER)
        dropdown.set_tooltip_text(
            "Choose a common value, or type a custom value in the field."
        )
        if hasattr(dropdown, "set_enable_search"):
            dropdown.set_enable_search(len(options) > 12)

        selected = 0
        for index, value in enumerate(values):
            if value == current_value:
                selected = index
                break
            if (
                isinstance(value, (int, float))
                and isinstance(current_value, (int, float))
                and not isinstance(value, bool)
                and not isinstance(current_value, bool)
                and float(value) == float(current_value)
            ):
                selected = index
                break

        dropdown.set_selected(selected)
        dropdown._theme_preset_values = values

        def preset_changed(widget, _param):
            index = widget.get_selected()
            if index == Gtk.INVALID_LIST_POSITION:
                return
            preset_values = widget._theme_preset_values
            if index < 0 or index >= len(preset_values):
                return
            target_entry.set_text(
                self.value_to_text(preset_values[index])
            )

        dropdown.connect("notify::selected", preset_changed)
        return dropdown

    def create_text_style_preset_row(self, node):
        preset_names = text_style_preset_names(node, self.selected_path)
        if not preset_names:
            return None

        labels = ["Choose a preset…"] + preset_names
        dropdown = Gtk.DropDown.new_from_strings(labels)
        dropdown.set_size_request(220, -1)
        dropdown.set_valign(Gtk.Align.CENTER)
        dropdown.set_tooltip_text("Fill available text fields")
        dropdown._theme_resetting_text_style = False

        row = Adw.ActionRow(
            title="Text style preset",
            subtitle="Apply values to the current text fields.",
        )
        row.add_suffix(dropdown)

        def preset_changed(widget, _param):
            if getattr(widget, "_theme_resetting_text_style", False):
                return
            index = widget.get_selected()
            if index in (0, Gtk.INVALID_LIST_POSITION):
                return
            if index - 1 >= len(preset_names):
                return

            updates = text_style_updates(preset_names[index - 1], node)
            for key, value in updates.items():
                self.set_property_widget_value(key, value)

            widget._theme_resetting_text_style = True
            widget.set_selected(0)
            widget._theme_resetting_text_style = False

        dropdown.connect("notify::selected", preset_changed)
        return row

    def create_theme_switch_row(self):
        theme_names = available_themes()
        if not theme_names:
            return None

        dropdown = Gtk.DropDown.new_from_strings(theme_names)
        dropdown.set_size_request(190, -1)
        dropdown.set_valign(Gtk.Align.CENTER)
        if self.theme_name in theme_names:
            dropdown.set_selected(theme_names.index(self.theme_name))

        button = Gtk.Button(
            label="Change",
            icon_name="view-refresh-symbolic",
            tooltip_text="Set the selected theme as active and open it here",
            valign=Gtk.Align.CENTER,
        )

        row = Adw.ActionRow(
            title="Active theme",
            subtitle=self.theme_name,
        )
        row.add_suffix(dropdown)
        row.add_suffix(button)

        def change_selected_theme(*_args):
            index = dropdown.get_selected()
            if index < 0 or index >= len(theme_names):
                self.toast("Choose a theme first")
                return
            self.switch_theme(theme_names[index])

        button.connect("clicked", change_selected_theme)
        return row

    def build_property_rows(self):
        self.clear_property_group()

        if self.selected_path is None:
            self.path_label.set_label("Select an element")
            return

        node = self.node_at_path(self.selected_path)
        self.path_label.set_label(" / ".join(str(p) for p in self.selected_path))

        if not isinstance(node, dict):
            return

        if self.selected_path == ("display",):
            theme_row = self.create_theme_switch_row()
            if theme_row is not None:
                self.dynamic_group.add(theme_row)
                self.property_rows.append(theme_row)

        ordered_keys = [key for key in EDITABLE_KEYS if key in node]
        ordered_keys.extend(
            key
            for key, value in node.items()
            if key not in ordered_keys
            and key != "EFFECTS"
            and not isinstance(value, dict)
            and not (
                isinstance(value, list)
                and any(isinstance(item, (dict, list)) for item in value)
            )
        )

        if is_text_style_node(node):
            preset_row = self.create_text_style_preset_row(node)
            if preset_row is not None:
                self.dynamic_group.add(preset_row)
                self.property_rows.append(preset_row)

        for key in ordered_keys:
            value = node[key]
            is_color = (
                key in COLOR_KEYS or key.endswith("_COLOR")
            )

            if key in BOOLEAN_KEYS or isinstance(value, bool):
                row = Adw.SwitchRow(title=key)
                row.set_active(bool(value))
                widget = row
            elif is_color:
                try:
                    selector = self.create_color_selector(value)
                except (TypeError, ValueError):
                    row = Adw.EntryRow(title=key)
                    row.set_text(self.value_to_text(value))
                    widget = row
                else:
                    row = Adw.ActionRow(
                        title=key,
                        subtitle=self.value_to_text(value),
                    )
                    row.add_suffix(selector)
                    widget = selector
            else:
                row = Adw.EntryRow(title=key)
                row.set_text(self.value_to_text(value))
                preset_dropdown = self.create_property_preset_dropdown(
                    key,
                    value,
                    row,
                )
                if preset_dropdown is not None:
                    row.add_suffix(preset_dropdown)
                    row._theme_preset_dropdown = preset_dropdown
                widget = row

            self.dynamic_group.add(row)
            self.property_rows.append(row)
            self.property_widgets[key] = widget

    @staticmethod
    def value_to_text(value):
        if isinstance(value, (list, tuple)):
            return ", ".join(str(item) for item in value)
        if value is None:
            return ""
        return str(value)

    def parse_value(self, key, raw, old_value):
        if isinstance(old_value, bool):
            return bool(raw)

        if isinstance(old_value, int) and not isinstance(old_value, bool):
            return int(float(raw))

        if isinstance(old_value, float):
            return float(raw)

        if isinstance(old_value, (list, tuple)):
            parts = [part.strip() for part in str(raw).split(",")]
            if all(
                isinstance(item, int) and not isinstance(item, bool)
                for item in old_value
            ):
                return [int(float(part)) for part in parts]
            if all(
                isinstance(item, (int, float)) and not isinstance(item, bool)
                for item in old_value
            ):
                return [float(part) for part in parts]
            return parts

        if old_value is None and str(raw).strip().lower() in {
            "",
            "none",
            "null",
        }:
            return None

        if key in NUMERIC_KEYS:
            return int(float(raw))

        return raw

    def restore_tree_selection(self, target_path):
        """Expand the hierarchy and select the exact restored element."""
        if target_path is None:
            self.selection_model.set_selected(Gtk.INVALID_LIST_POSITION)
            return False

        # Expand rows progressively because child rows only enter the flattened
        # TreeListModel after their parents are expanded.
        for _round in range(max(2, len(target_path) + 1)):
            count = self.tree_model.get_n_items()
            changed = False

            for index in range(count):
                row = self.tree_model.get_item(index)
                if row is None:
                    continue

                item = row.get_item()
                if item is None:
                    continue

                path = tuple(item.path)
                is_ancestor = (
                    len(path) < len(target_path)
                    and tuple(target_path[:len(path)]) == path
                )

                if is_ancestor and row.is_expandable() and not row.get_expanded():
                    row.set_expanded(True)
                    changed = True

            if not changed:
                break

        for index in range(self.tree_model.get_n_items()):
            row = self.tree_model.get_item(index)
            if row is None:
                continue
            item = row.get_item()
            if item is not None and tuple(item.path) == tuple(target_path):
                self.selection_model.set_selected(index)
                return False

        # Keep the logical selection even if a filtered/collapsed tree could
        # not expose it immediately.
        self.selected_path = tuple(target_path)
        return False

    def make_history_state(self):
        return {
            "theme_data": copy.deepcopy(self.theme_data),
            "selected_path": copy.deepcopy(self.selected_path),
        }

    def restore_history_state(self, state):
        target_path = copy.deepcopy(state.get("selected_path"))

        self.restoring_history = True
        try:
            self.theme_data = copy.deepcopy(state["theme_data"])
            self.selected_path = target_path

            save_yaml_atomic(self.theme_file, self.theme_data)
            self.populate_elements()

            # Re-assert the restored logical selection after rebuilding the
            # tree model. Without this, Gtk.SingleSelection can point to the
            # same numeric row index but a different parent/group item.
            self.selected_path = target_path

            if self.selected_path is not None:
                try:
                    self.build_property_rows()
                except Exception:
                    self.selected_path = None
                    self.clear_property_group()
            else:
                self.clear_property_group()
        finally:
            self.restoring_history = False

        GLib.idle_add(self.restore_tree_selection, self.selected_path)
        self.refresh_preview()
        self.update_history_buttons()

    def update_history_buttons(self):
        if hasattr(self, "undo_button"):
            self.undo_button.set_sensitive(bool(self.undo_stack))
        if hasattr(self, "redo_button"):
            self.redo_button.set_sensitive(bool(self.redo_stack))

    def push_undo(self):
        state = self.make_history_state()

        # Avoid duplicate consecutive history states.
        if (
            self.undo_stack
            and self.undo_stack[-1]["theme_data"] == state["theme_data"]
            and self.undo_stack[-1].get("selected_path") == state.get("selected_path")
        ):
            return False

        self.undo_stack.append(state)
        if len(self.undo_stack) > 100:
            self.undo_stack.pop(0)

        self.redo_stack.clear()
        self.update_history_buttons()
        return True

    def apply_properties(self):
        if self.selected_path is None:
            return

        node = self.node_at_path(self.selected_path)
        updates = {}
        changed = False

        try:
            for key, widget in self.property_widgets.items():
                old = node[key]

                if key in BOOLEAN_KEYS:
                    new = self.parse_value(key, widget.get_active(), old)
                elif getattr(widget, "_theme_color_widget", False):
                    new = self.color_selector_value(widget)
                else:
                    new = self.parse_value(key, widget.get_text(), old)

                updates[key] = new
                changed = changed or new != old
        except Exception as exc:
            self.error_dialog("Invalid property", str(exc))
            return

        if not changed:
            self.toast("No property changes")
            return

        self.push_undo()
        for key, value in updates.items():
            node[key] = value

        save_yaml_atomic(self.theme_file, self.theme_data)
        self.build_property_rows()
        self.refresh_preview()
        self.toast("Properties updated")

    def reset_selected(self):
        if self.selected_path is None:
            return

        original = self.session_original
        try:
            for part in self.selected_path:
                original = original[part]
        except Exception:
            self.toast("This element did not exist when the editor opened")
            return

        self.push_undo()
        parent = self.theme_data
        for part in self.selected_path[:-1]:
            parent = parent[part]
        parent[self.selected_path[-1]] = copy.deepcopy(original)

        save_yaml_atomic(self.theme_file, self.theme_data)
        self.build_property_rows()
        self.refresh_preview()
        self.toast("Element restored")

    def undo(self):
        if not self.undo_stack:
            self.toast("Nothing to undo")
            self.update_history_buttons()
            return

        self.redo_stack.append(self.make_history_state())
        state = self.undo_stack.pop()
        self.restore_history_state(state)
        self.toast("Undo")

    def redo(self):
        if not self.redo_stack:
            self.toast("Nothing to redo")
            self.update_history_buttons()
            return

        self.undo_stack.append(self.make_history_state())
        state = self.redo_stack.pop()
        self.restore_history_state(state)
        self.toast("Redo")


    def save_as(self):
        entry = Gtk.Entry(
            placeholder_text="new-theme-name",
            activates_default=True,
        )
        current = Gtk.Label(
            label=f"Source theme: {self.theme_name}",
            xalign=0,
        )
        current.add_css_class("dim-label")

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
            margin_top=8,
        )
        content.append(current)
        content.append(entry)

        dialog = Adw.AlertDialog(
            heading="Save theme as",
            body=(
                "Create a new editable theme from the current theme, "
                "including YAML, images, fonts, preview, and local assets."
            ),
        )
        dialog.set_extra_child(content)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Create theme")
        dialog.set_response_appearance(
            "save",
            Adw.ResponseAppearance.SUGGESTED,
        )
        dialog.set_default_response("save")
        dialog.set_close_response("cancel")

        def response(_dialog, response_id):
            if response_id != "save":
                return

            name = entry.get_text().strip()
            if not name:
                self.error_dialog("Invalid theme name", "Enter a theme name.")
                return
            allowed = (
                "abcdefghijklmnopqrstuvwxyz"
                "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                "0123456789._-"
            )
            if name in {".", ".."} or any(ch not in allowed for ch in name):
                self.error_dialog(
                    "Invalid theme name",
                    "Use only letters, numbers, dots, underscores, and hyphens.",
                )
                return

            destination = THEMES_DIR / name
            if destination.exists():
                self.error_dialog(
                    "Theme already exists",
                    f"A theme named '{name}' already exists.",
                )
                return

            try:
                save_yaml_atomic(self.theme_file, self.theme_data)
                shutil.copytree(self.theme_dir, destination)
                save_yaml_atomic(
                    destination / "theme.yaml",
                    copy.deepcopy(self.theme_data),
                )
            except Exception as exc:
                if destination.exists():
                    shutil.rmtree(destination, ignore_errors=True)
                self.error_dialog("Could not create theme", str(exc))
                return

            self.switch_theme(name)

        dialog.connect("response", response)
        dialog.present(self)

    def save(self):
        save_yaml_atomic(self.theme_file, self.theme_data)
        self.toast("Theme saved")

    def refresh_preview(self):
        self.preview_generation += 1
        generation = self.preview_generation
        self.preview_status.set_label("Rendering preview…")

        def worker():
            script = f"""
import sys
from pathlib import Path
root = Path({str(ROOT)!r})
sys.path.insert(0, str(root))
from library import config
config.CONFIG_DATA["config"]["HW_SENSORS"] = "STATIC"
config.CONFIG_DATA["config"]["THEME"] = {self.theme_name!r}
config.load_theme()
config.CONFIG_DATA["display"]["REVISION"] = "SIMU"
from library.display import display
display.initialize_display()
from PIL import Image
video = config.THEME_DATA.get("video", {{}})
bg = video.get("PREVIEW_BACKGROUND", "background.png")
bg_path = Path(config.THEME_DATA["PATH"]) / bg
if bg_path.is_file():
    image = Image.open(bg_path).convert("RGB").resize(
        (display.lcd.get_width(), display.lcd.get_height())
    )
    display.lcd.screen_image = image
display.display_static_images()
display.display_static_text()
import library.stats as stats
callbacks = [
    (("STATS","CPU","PERCENTAGE"), stats.CPU.percentage),
    (("STATS","CPU","FREQUENCY"), stats.CPU.frequency),
    (("STATS","CPU","LOAD"), stats.CPU.load),
    (("STATS","CPU","TEMPERATURE"), stats.CPU.temperature),
    (("STATS","CPU","FAN_SPEED"), stats.CPU.fan_speed),
    (("STATS","GPU"), stats.Gpu.stats),
    (("STATS","MEMORY"), stats.Memory.stats),
    (("STATS","DISK"), stats.Disk.stats),
    (("STATS","NET"), stats.Net.stats),
    (("STATS","DATE"), stats.Date.stats),
    (("STATS","UPTIME"), stats.SystemUptime.stats),
    (("STATS","CUSTOM"), stats.Custom.stats),
    (("STATS","WEATHER"), stats.Weather.stats),
    (("STATS","PING"), stats.Ping.stats),
]
for path, callback in callbacks:
    node = config.THEME_DATA
    try:
        for part in path:
            node = node[part]
        if isinstance(node, dict) and node.get("INTERVAL", 0) > 0:
            callback()
    except Exception:
        pass
display.lcd.screen_image.save({str(self.preview_file)!r}, "PNG")
"""
            result = subprocess.run(
                [project_python(), "-c", script],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
                check=False,
            )
            GLib.idle_add(
                self.finish_preview,
                generation,
                result.returncode,
                result.stdout,
                result.stderr,
            )

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def finish_preview(self, generation, returncode, stdout, stderr):
        # Ignore an older render that completed after a newer Undo/Redo action.
        if generation != self.preview_generation:
            return False

        if returncode != 0:
            self.preview_status.set_label(
                (stderr or stdout or "Preview failed").strip()[-1000:]
            )
            return False

        try:
            texture = Gdk.Texture.new_from_filename(str(self.preview_file))
            self.preview_picture.set_paintable(texture)
            self.preview_status.set_label(str(self.preview_file))
        except GLib.Error as exc:
            self.preview_status.set_label(str(exc))
        return False

    def on_video_tools_clicked(self, *_args):
        try:
            self.open_video_tools()
        except Exception as exc:
            self.error_dialog("Could not open video and background tools", str(exc))

    def on_text_effects_clicked(self, *_args):
        try:
            self.open_text_effects()
        except Exception as exc:
            self.error_dialog("Could not open text effects", str(exc))

    def open_text_effects(self):
        if self.selected_path is None:
            self.toast("Select a text element first")
            return

        node = self.node_at_path(self.selected_path)

        if not is_text_style_node(node):
            self.toast("The selected element is not rendered as text")
            return

        effects = copy.deepcopy(node.get("EFFECTS", {}))
        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
            margin_top=8,
            margin_bottom=8,
            margin_start=8,
            margin_end=8,
        )

        def add_color_row(group, title, value):
            row = Adw.ActionRow(title=title)
            selector = self.create_color_selector(
                value,
                force_alpha=True,
            )
            row.add_suffix(selector)
            group.add(row)
            return selector

        def add_spin_row(
            group,
            title,
            value,
            lower,
            upper,
            step=1,
            digits=0,
        ):
            row = Adw.ActionRow(title=title)
            spin = Gtk.SpinButton.new_with_range(lower, upper, step)
            spin.set_digits(digits)
            spin.set_value(float(value))
            spin.set_valign(Gtk.Align.CENTER)
            spin.set_size_request(120, -1)
            row.add_suffix(spin)
            group.add(row)
            return spin

        effect_labels = ["Choose a preset…"] + text_effect_preset_names()
        effect_dropdown = Gtk.DropDown.new_from_strings(effect_labels)
        effect_dropdown.set_size_request(250, -1)
        effect_dropdown.set_valign(Gtk.Align.CENTER)
        effect_dropdown.set_tooltip_text("Fill effect controls")
        effect_dropdown._theme_resetting_effect_preset = False
        effect_group = Adw.PreferencesGroup(
            title="Effect preset",
            description="Fill effect controls without applying them.",
        )
        effect_row = Adw.ActionRow(title="Preset")
        effect_row.add_suffix(effect_dropdown)
        effect_group.add(effect_row)
        content.append(effect_group)

        shadow_group = Adw.PreferencesGroup(
            title="Shadow",
            description="Draw a blurred copy behind the text.",
        )
        shadow_switch = Adw.SwitchRow(title="Enabled")
        shadow_switch.set_active(
            bool(effects.get("SHADOW", {}).get("ENABLED", False))
        )
        shadow_group.add(shadow_switch)
        shadow_color = add_color_row(
            shadow_group,
            "Color",
            effects.get("SHADOW", {}).get(
                "COLOR",
                [0, 0, 0, 180],
            ),
        )
        shadow_x = add_spin_row(
            shadow_group,
            "Horizontal offset",
            effects.get("SHADOW", {}).get("OFFSET_X", 3),
            -40,
            40,
        )
        shadow_y = add_spin_row(
            shadow_group,
            "Vertical offset",
            effects.get("SHADOW", {}).get("OFFSET_Y", 3),
            -40,
            40,
        )
        shadow_blur = add_spin_row(
            shadow_group,
            "Blur radius",
            effects.get("SHADOW", {}).get("BLUR_RADIUS", 4),
            0,
            40,
            0.5,
            1,
        )
        content.append(shadow_group)

        glow_group = Adw.PreferencesGroup(
            title="Glow",
            description="Draw a colored blurred halo around the text.",
        )
        glow_switch = Adw.SwitchRow(title="Enabled")
        glow_switch.set_active(
            bool(effects.get("GLOW", {}).get("ENABLED", False))
        )
        glow_group.add(glow_switch)
        glow_color = add_color_row(
            glow_group,
            "Color",
            effects.get("GLOW", {}).get(
                "COLOR",
                [255, 255, 255, 160],
            ),
        )
        glow_blur = add_spin_row(
            glow_group,
            "Blur radius",
            effects.get("GLOW", {}).get("BLUR_RADIUS", 8),
            0,
            40,
            0.5,
            1,
        )
        glow_intensity = add_spin_row(
            glow_group,
            "Intensity",
            effects.get("GLOW", {}).get("INTENSITY", 1),
            1,
            4,
        )
        content.append(glow_group)

        outline_group = Adw.PreferencesGroup(
            title="Outline",
            description="Draw a solid stroke around the glyphs.",
        )
        outline_switch = Adw.SwitchRow(title="Enabled")
        outline_switch.set_active(
            bool(effects.get("OUTLINE", {}).get("ENABLED", False))
        )
        outline_group.add(outline_switch)
        outline_color = add_color_row(
            outline_group,
            "Color",
            effects.get("OUTLINE", {}).get(
                "COLOR",
                [0, 0, 0, 255],
            ),
        )
        outline_width = add_spin_row(
            outline_group,
            "Width",
            effects.get("OUTLINE", {}).get("WIDTH", 2),
            0,
            20,
        )
        content.append(outline_group)

        def set_spin_value(spin, value):
            spin.set_value(float(value))

        def set_switch_value(switch, value):
            switch.set_active(bool(value))

        effect_controls = {
            "SHADOW": {
                "ENABLED": shadow_switch,
                "COLOR": shadow_color,
                "OFFSET_X": shadow_x,
                "OFFSET_Y": shadow_y,
                "BLUR_RADIUS": shadow_blur,
            },
            "GLOW": {
                "ENABLED": glow_switch,
                "COLOR": glow_color,
                "BLUR_RADIUS": glow_blur,
                "INTENSITY": glow_intensity,
            },
            "OUTLINE": {
                "ENABLED": outline_switch,
                "COLOR": outline_color,
                "WIDTH": outline_width,
            },
        }

        def load_effect_controls(preset):
            for section, values in preset.items():
                controls = effect_controls[section]
                set_switch_value(controls["ENABLED"], values["ENABLED"])
                self.set_color_selector_value(controls["COLOR"], values["COLOR"])
                for key, control in controls.items():
                    if key in ("ENABLED", "COLOR"):
                        continue
                    set_spin_value(control, values[key])

        def effect_preset_changed(widget, _param):
            if getattr(widget, "_theme_resetting_effect_preset", False):
                return
            index = widget.get_selected()
            if index in (0, Gtk.INVALID_LIST_POSITION):
                return
            names = text_effect_preset_names()
            if index - 1 >= len(names):
                return

            load_effect_controls(text_effect_preset(names[index - 1]))
            widget._theme_resetting_effect_preset = True
            widget.set_selected(0)
            widget._theme_resetting_effect_preset = False

        effect_dropdown.connect("notify::selected", effect_preset_changed)

        scroll = Gtk.ScrolledWindow(
            min_content_width=720,
            min_content_height=620,
            propagate_natural_width=True,
            propagate_natural_height=True,
        )
        scroll.set_policy(
            Gtk.PolicyType.NEVER,
            Gtk.PolicyType.AUTOMATIC,
        )
        scroll.set_child(content)

        dialog = Adw.AlertDialog(
            heading="Text effects",
            body=(
                "Configure shadow, glow, and outline. "
                "Changes are rendered in the preview after applying."
            ),
        )
        dialog.set_extra_child(scroll)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("reset", "Reset effects")
        dialog.add_response("apply", "Apply")
        dialog.set_response_appearance(
            "reset",
            Adw.ResponseAppearance.DESTRUCTIVE,
        )
        dialog.set_response_appearance(
            "apply",
            Adw.ResponseAppearance.SUGGESTED,
        )
        dialog.set_default_response("apply")
        dialog.set_close_response("cancel")

        def response(_dialog, response_id):
            if response_id == "cancel":
                return

            self.push_undo()

            if response_id == "reset":
                node.pop("EFFECTS", None)
            elif response_id == "apply":
                updated = {
                    "SHADOW": {
                        "ENABLED": shadow_switch.get_active(),
                        "COLOR": self.color_selector_value(
                            shadow_color,
                            4,
                        ),
                        "OFFSET_X": int(shadow_x.get_value()),
                        "OFFSET_Y": int(shadow_y.get_value()),
                        "BLUR_RADIUS": float(
                            shadow_blur.get_value()
                        ),
                    },
                    "GLOW": {
                        "ENABLED": glow_switch.get_active(),
                        "COLOR": self.color_selector_value(
                            glow_color,
                            4,
                        ),
                        "BLUR_RADIUS": float(
                            glow_blur.get_value()
                        ),
                        "INTENSITY": int(
                            glow_intensity.get_value()
                        ),
                    },
                    "OUTLINE": {
                        "ENABLED": outline_switch.get_active(),
                        "COLOR": self.color_selector_value(
                            outline_color,
                            4,
                        ),
                        "WIDTH": int(outline_width.get_value()),
                    },
                }

                if any(
                    section["ENABLED"]
                    for section in updated.values()
                ):
                    node["EFFECTS"] = updated
                else:
                    node.pop("EFFECTS", None)
            else:
                return

            save_yaml_atomic(self.theme_file, self.theme_data)
            self.build_property_rows()
            self.refresh_preview()
            self.toast("Text effects updated")

        dialog.connect("response", response)
        dialog.present(self)

    def video_node(self):
        node = self.theme_data.setdefault("video", {})
        if not isinstance(node, dict):
            raise TypeError("The theme video section must be a mapping.")
        return node

    def current_video_path(self):
        value = self.video_node().get("PATH", "")
        return str(value or "")

    def switch_theme(self, theme_name: str):
        theme_name = str(theme_name or "").strip()
        if not theme_name:
            self.toast("Choose a theme first")
            return False
        if theme_name == self.theme_name:
            self.toast(f"{theme_name} is already open")
            return False

        theme_dir = THEMES_DIR / theme_name
        theme_file = theme_dir / "theme.yaml"
        if not theme_file.is_file():
            self.error_dialog(
                "Could not change theme",
                f"{theme_file} was not found.",
            )
            return False

        try:
            theme_data = load_yaml(theme_file)
            write_current_theme(theme_name)
        except Exception as exc:
            self.error_dialog("Could not change theme", str(exc))
            return False

        self.theme_name = theme_name
        self.theme_dir = theme_dir
        self.theme_file = theme_file
        self.preview_file = theme_dir / "preview.png"
        self.theme_data = theme_data
        self.session_original = copy.deepcopy(theme_data)
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.selected_path = None
        self.property_widgets.clear()
        self.clear_property_group()
        self.path_label.set_label("Select an element")

        self.set_title(f"Theme Editor — {theme_name}")
        self.window_title.set_title(theme_name)
        app = self.get_application()
        if app is not None:
            app.theme_name = theme_name

        self.populate_elements()
        self.update_history_buttons()
        self.refresh_preview()
        self.toast(f"Theme changed to {theme_name}")
        return True

    def apply_video_path(self, path):
        path = str(path).strip()
        if not path:
            self.toast("Choose a video first")
            return

        node = self.video_node()
        old_value = str(node.get("PATH", "") or "")
        if old_value == path:
            self.toast("This video is already selected")
            return

        self.push_undo()
        node["PATH"] = path
        node.setdefault("INTERVAL", 0)
        save_yaml_atomic(self.theme_file, self.theme_data)

        self.populate_elements()
        self.selected_path = ("video",)
        GLib.idle_add(self.restore_tree_selection, self.selected_path)
        self.build_property_rows()
        self.refresh_preview()
        self.toast(f"Theme video selected: {Path(path).name}")

    def open_video_tools(self):
        theme_names = available_themes()
        theme_dropdown = Gtk.DropDown.new_from_strings(
            theme_names or ("No themes found",)
        )
        theme_dropdown.set_sensitive(bool(theme_names))
        if self.theme_name in theme_names:
            theme_dropdown.set_selected(theme_names.index(self.theme_name))
        change_theme = Gtk.Button(
            label="Change",
            icon_name="view-refresh-symbolic",
            tooltip_text="Set the selected theme as active and open it here",
        )
        change_theme.set_sensitive(bool(theme_names))

        theme_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )
        theme_dropdown.set_hexpand(True)
        theme_box.append(theme_dropdown)
        theme_box.append(change_theme)

        source_labels = (
            "Local file",
            "Display SD card",
            "Display internal memory",
        )
        source_dropdown = Gtk.DropDown.new_from_strings(source_labels)
        source_dropdown.set_selected(0)

        selected_path = Gtk.Entry(
            placeholder_text="Choose a local file or load display videos"
        )
        selected_path.set_text(self.current_video_path())

        choose_local = Gtk.Button(label="Choose local video…")
        load_remote = Gtk.Button(label="Load videos from display")
        remote_dropdown = Gtk.DropDown.new_from_strings(
            ("No display videos loaded",)
        )
        remote_dropdown.set_sensitive(False)

        timestamp = Gtk.SpinButton.new_with_range(0.0, 86400.0, 0.1)
        timestamp.set_digits(1)
        timestamp.set_value(0.0)

        output_name = Gtk.Entry()
        output_name.set_text(
            str(
                self.video_node().get(
                    "PREVIEW_BACKGROUND",
                    "background.png",
                )
            )
        )

        set_preview = Gtk.Switch()
        set_preview.set_active(True)

        grid = Gtk.Grid(
            row_spacing=10,
            column_spacing=10,
            margin_top=8,
        )

        def add_row(row, label, widget):
            title = Gtk.Label(label=label, xalign=0)
            title.add_css_class("dim-label")
            grid.attach(title, 0, row, 1, 1)
            grid.attach(widget, 1, row, 1, 1)

        add_row(0, "Theme", theme_box)
        add_row(1, "Source", source_dropdown)
        add_row(2, "Selected video", selected_path)
        add_row(3, "", choose_local)
        add_row(4, "", load_remote)
        add_row(5, "Display videos", remote_dropdown)
        add_row(6, "Frame time (seconds)", timestamp)
        add_row(7, "Background filename", output_name)
        add_row(8, "Set as preview background", set_preview)

        help_label = Gtk.Label(
            label=(
                "Videos stored on the display can be selected, played, and "
                "used by the theme. The editor automatically searches the "
                "media-preparation cache for the converted local copy. If it "
                "is unavailable, choose the original file manually."
            ),
            xalign=0,
            wrap=True,
        )
        help_label.add_css_class("dim-label")
        grid.attach(help_label, 0, 9, 2, 1)

        state = {
            "remote_paths": [],
            "local_path": None,
            "loading": False,
        }

        dialog = Adw.AlertDialog(
            heading="Video and background",
            body=(
                "Choose the video used by this theme, preview a display "
                "video, or extract a local frame as the theme background."
            ),
        )
        dialog.set_extra_child(grid)
        dialog.add_response("close", "Close")
        dialog.add_response("stop", "Stop display video")
        dialog.add_response("play", "Play on display")
        dialog.add_response("use", "Use in theme")
        dialog.add_response("generate", "Generate background")
        dialog.set_response_appearance(
            "generate",
            Adw.ResponseAppearance.SUGGESTED,
        )
        dialog.set_default_response("generate")
        dialog.set_close_response("close")

        def choose_local_video(*_args):
            chooser = Gtk.FileDialog(
                title="Choose a GIF or video",
                modal=True,
            )
            media_filter = Gtk.FileFilter()
            media_filter.set_name("GIF and video files")
            for mime in (
                "image/gif",
                "video/mp4",
                "video/webm",
                "video/x-matroska",
                "video/quicktime",
            ):
                media_filter.add_mime_type(mime)
            filters = Gio.ListStore.new(Gtk.FileFilter)
            filters.append(media_filter)
            chooser.set_filters(filters)

            def selected(chooser, result):
                try:
                    file = chooser.open_finish(result)
                except GLib.Error:
                    return
                path = Path(file.get_path())
                if not path.is_file():
                    self.toast("Selected video is not available")
                    return
                state["local_path"] = path
                source_dropdown.set_selected(0)
                selected_path.set_text(str(path))

            chooser.open(self, None, selected)

        choose_local.connect("clicked", choose_local_video)

        def selected_remote_path():
            index = remote_dropdown.get_selected()
            paths = state["remote_paths"]
            if index < 0 or index >= len(paths):
                return None
            return paths[index]

        def remote_changed(_dropdown, _param):
            path = selected_remote_path()
            if not path:
                return
            selected_path.set_text(path)
            local_copy = find_prepared_local_video(path)
            state["local_path"] = local_copy
            if local_copy is not None:
                self.toast(
                    f"Local prepared copy found: {local_copy.name}"
                )

        remote_dropdown.connect("notify::selected", remote_changed)

        def finish_remote_load(paths, error):
            state["loading"] = False
            load_remote.set_sensitive(True)
            if error:
                self.error_dialog("Could not list display videos", error)
                return False
            state["remote_paths"] = list(paths)
            names = tuple(Path(path).name for path in paths)
            model = Gtk.StringList.new(
                names or ("No videos found in this storage",)
            )
            remote_dropdown.set_model(model)
            remote_dropdown.set_sensitive(bool(paths))
            if paths:
                remote_dropdown.set_selected(0)
                selected_path.set_text(paths[0])
            return False

        def load_display_videos(*_args):
            if state["loading"]:
                return
            source_index = source_dropdown.get_selected()
            if source_index == 0:
                self.toast("Choose SD card or internal memory first")
                return

            internal = source_index == 2
            state["local_path"] = None
            state["loading"] = True
            load_remote.set_sensitive(False)
            load_remote.set_label("Loading…")

            def worker():
                manager = None
                try:
                    manager = VideoManager()
                    _directories, files = manager.list_videos(
                        internal=internal
                    )
                    paths = [
                        display_video_path(name, internal=internal)
                        for name in files
                    ]
                    error = None
                except Exception as exc:
                    paths = []
                    error = str(exc)
                finally:
                    if manager is not None:
                        manager.close()

                def finish():
                    load_remote.set_label("Load videos from display")
                    return finish_remote_load(paths, error)

                GLib.idle_add(finish)

            threading.Thread(target=worker, daemon=True).start()

        load_remote.connect("clicked", load_display_videos)

        def run_remote_action(action, path):
            def worker():
                manager = None
                try:
                    manager = VideoManager()
                    if action == "play":
                        manager.play(path)
                        message = f"Playing {Path(path).name}"
                    else:
                        manager.stop()
                        message = "Display video stopped"
                    error = None
                except Exception as exc:
                    message = ""
                    error = str(exc)
                finally:
                    if manager is not None:
                        manager.close()

                def finish():
                    if error:
                        self.error_dialog("Display video", error)
                    else:
                        self.toast(message)
                    return False

                GLib.idle_add(finish)

            threading.Thread(target=worker, daemon=True).start()

        def generate_selected_background():
            source = state["local_path"]
            if source is None:
                raw_path = selected_path.get_text().strip()
                candidate = Path(raw_path).expanduser()
                if candidate.is_file():
                    source = candidate

            if source is None or not Path(source).is_file():
                self.error_dialog(
                    "Local video required",
                    (
                        "No matching prepared copy was found in the local "
                        "media cache. Choose the original local file before "
                        "generating a background."
                    ),
                )
                return

            name = Path(output_name.get_text().strip()).name
            if not name:
                name = "background.png"
            if Path(name).suffix.lower() != ".png":
                name = f"{Path(name).stem}.png"
            destination = self.theme_dir / name
            frame_time = timestamp.get_value()
            dialog.set_response_enabled("generate", False)

            def worker():
                try:
                    generate_background(
                        Path(source),
                        destination,
                        timestamp=frame_time,
                        width=480,
                        height=480,
                    )
                    error = None
                except Exception as exc:
                    error = str(exc)

                def finish():
                    dialog.set_response_enabled("generate", True)
                    if error:
                        self.error_dialog(
                            "Could not generate background",
                            error,
                        )
                        return False

                    if set_preview.get_active():
                        self.push_undo()
                        self.video_node()["PREVIEW_BACKGROUND"] = name
                        save_yaml_atomic(self.theme_file, self.theme_data)
                    self.refresh_preview()
                    self.toast(f"Background generated: {name}")
                    return False

                GLib.idle_add(finish)

            threading.Thread(target=worker, daemon=True).start()

        def change_selected_theme(*_args):
            index = theme_dropdown.get_selected()
            if index < 0 or index >= len(theme_names):
                self.toast("Choose a theme first")
                return
            self.switch_theme(theme_names[index])

        change_theme.connect("clicked", change_selected_theme)

        def response(_dialog, response_id):
            if response_id == "use":
                self.apply_video_path(selected_path.get_text())
                dialog.present(self)
            elif response_id == "generate":
                generate_selected_background()
                dialog.present(self)
            elif response_id == "play":
                path = selected_path.get_text().strip()
                if not path.startswith(("/mnt/SDCARD/video/", "/root/video/")):
                    self.toast("Choose a video stored on the display")
                    dialog.present(self)
                    return
                run_remote_action("play", path)
                dialog.present(self)
            elif response_id == "stop":
                run_remote_action("stop", "")
                dialog.present(self)

        dialog.connect("response", response)
        dialog.present(self)

    def shared_background_name(self):
        return self.theme_data.get("video", {}).get(
            "PREVIEW_BACKGROUND",
            "background.png",
        )

    @staticmethod
    def unique_mapping_key(mapping, base):
        candidate = base
        counter = 2
        while candidate in mapping:
            candidate = f"{base}_{counter}"
            counter += 1
        return candidate

    @staticmethod
    def deep_merge_missing(target, source):
        if not isinstance(target, dict) or not isinstance(source, dict):
            return target
        for key, value in source.items():
            if key not in target:
                target[key] = copy.deepcopy(value)
            elif isinstance(target[key], dict) and isinstance(value, dict):
                ThemeEditorWindow.deep_merge_missing(target[key], value)
        return target

    @staticmethod
    def normalize_color_values(node):
        color_keys = {
            "FONT_COLOR", "BACKGROUND_COLOR", "BAR_COLOR",
            "BAR_BACKGROUND_COLOR", "LINE_COLOR", "AXIS_COLOR",
        }
        if isinstance(node, dict):
            for key, value in list(node.items()):
                if key in color_keys and isinstance(value, str):
                    try:
                        node[key] = [
                            int(part.strip())
                            for part in value.split(",")
                        ]
                    except Exception:
                        pass
                elif isinstance(value, (dict, list)):
                    ThemeEditorWindow.normalize_color_values(value)
        elif isinstance(node, list):
            for value in node:
                if isinstance(value, (dict, list)):
                    ThemeEditorWindow.normalize_color_values(value)

    def normalize_component_template(self, node):
        self.normalize_color_values(node)
        background = self.shared_background_name()

        def visit(value):
            if isinstance(value, dict):
                if "SHOW" in value:
                    value["SHOW"] = False
                if value.get("BACKGROUND_IMAGE"):
                    value["BACKGROUND_IMAGE"] = background
                    value.pop("BACKGROUND_COLOR", None)
                for child in value.values():
                    if isinstance(child, (dict, list)):
                        visit(child)
            elif isinstance(value, list):
                for child in value:
                    if isinstance(child, (dict, list)):
                        visit(child)

        visit(node)
        return node

    def load_official_templates(self):
        if not DEFAULT_TEMPLATE_FILE.is_file():
            raise FileNotFoundError(DEFAULT_TEMPLATE_FILE)
        if not EXAMPLE_TEMPLATE_FILE.is_file():
            raise FileNotFoundError(EXAMPLE_TEMPLATE_FILE)
        return load_yaml(DEFAULT_TEMPLATE_FILE), load_yaml(EXAMPLE_TEMPLATE_FILE)

    def ensure_official_sensor_tree(self, top_key):
        default_data, example_data = self.load_official_templates()
        default_stats = default_data.get("STATS", {})
        example_stats = example_data.get("STATS", {})

        if top_key not in default_stats and top_key not in example_stats:
            raise KeyError(f"Unknown sensor template: {top_key}")

        source = copy.deepcopy(example_stats.get(top_key, {}))
        self.normalize_component_template(source)
        self.deep_merge_missing(
            source,
            copy.deepcopy(default_stats.get(top_key, {})),
        )

        stats = self.theme_data.setdefault("STATS", {})
        if top_key not in stats:
            stats[top_key] = source
        else:
            self.deep_merge_missing(stats[top_key], source)

        self.normalize_component_template(stats[top_key])
        return stats[top_key]

    @staticmethod
    def set_show(node, value=True):
        if isinstance(node, dict):
            node["SHOW"] = bool(value)

    @staticmethod
    def ensure_interval(node, fallback):
        if isinstance(node, dict):
            current = int(node.get("INTERVAL", 0) or 0)
            node["INTERVAL"] = max(current, fallback)

    def show_add_component_dialog(self):
        labels = list(COMPONENT_PRESETS.keys())
        dropdown = Gtk.DropDown.new_from_strings(labels)
        dropdown.set_selected(0)

        extra = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
            margin_top=8,
        )
        description = Gtk.Label(
            label=(
                "Sensor components use the official default.yaml and "
                "theme_example.yaml structures."
            ),
            xalign=0,
            wrap=True,
        )
        description.add_css_class("dim-label")
        extra.append(description)
        extra.append(dropdown)

        dialog = Adw.AlertDialog(
            heading="Add component",
            body="Choose the component to add to this theme.",
        )
        dialog.set_extra_child(extra)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("add", "Add")
        dialog.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("add")
        dialog.set_close_response("cancel")

        def response(_dialog, response_id):
            if response_id != "add":
                return
            index = dropdown.get_selected()
            if index < 0 or index >= len(labels):
                return
            label = labels[index]
            kind, component_id = COMPONENT_PRESETS[label]
            if kind == "custom" and component_id == "text":
                self.add_custom_text()
            elif kind == "custom" and component_id == "image":
                self.choose_static_image()
            else:
                self.add_sensor_component(component_id)

        dialog.connect("response", response)
        dialog.present(self)

    def add_custom_text(self):
        self.push_undo()
        container = self.theme_data.setdefault("static_text", {})
        key = self.unique_mapping_key(container, "custom_text")
        container[key] = {
            "TEXT": "New text",
            "X": 240,
            "Y": 240,
            "WIDTH": 240,
            "HEIGHT": 50,
            "FONT": "roboto-mono/RobotoMono-Regular.ttf",
            "FONT_SIZE": 24,
            "FONT_COLOR": [255, 255, 255],
            "BACKGROUND_IMAGE": self.shared_background_name(),
            "ALIGN": "center",
            "ANCHOR": "mm",
        }
        self.finish_structure_change(
            ("static_text", key),
            "Custom text added",
        )

    def choose_static_image(self):
        dialog = Gtk.FileDialog(
            title="Choose a static image",
            modal=True,
        )
        image_filter = Gtk.FileFilter()
        image_filter.set_name("Image files")
        for mime in (
            "image/png", "image/jpeg", "image/webp", "image/bmp",
        ):
            image_filter.add_mime_type(mime)

        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(image_filter)
        dialog.set_filters(filters)
        dialog.open(self, None, self.on_static_image_chosen)

    def on_static_image_chosen(self, dialog, result):
        try:
            file = dialog.open_finish(result)
        except GLib.Error:
            return

        source = Path(file.get_path())
        if not source.is_file():
            self.toast("Selected image is not available")
            return

        destination = self.theme_dir / source.name
        if destination.exists() and source.resolve() != destination.resolve():
            stem = self.unique_mapping_key(
                {path.stem: True for path in self.theme_dir.iterdir()},
                source.stem,
            )
            destination = self.theme_dir / f"{stem}{source.suffix}"

        try:
            if source.resolve() != destination.resolve():
                import shutil
                shutil.copy2(source, destination)
        except Exception as exc:
            self.error_dialog("Could not add image", str(exc))
            return

        self.push_undo()
        container = self.theme_data.setdefault("static_images", {})
        key = self.unique_mapping_key(container, "custom_image")
        container[key] = {
            "PATH": destination.name,
            "X": 180,
            "Y": 180,
            "WIDTH": 120,
            "HEIGHT": 120,
        }
        self.finish_structure_change(
            ("static_images", key),
            "Static image added",
        )

    def add_sensor_component(self, component_id):
        self.push_undo()
        selected_path = None

        try:
            if component_id == "CPU.PERCENTAGE":
                cpu = self.ensure_official_sensor_tree("CPU")
                group = cpu["PERCENTAGE"]
                self.ensure_interval(group, 1)
                self.set_show(group["TEXT"])
                self.set_show(group["GRAPH"])
                selected_path = ("STATS", "CPU", "PERCENTAGE", "TEXT")

            elif component_id == "CPU.TEMPERATURE":
                cpu = self.ensure_official_sensor_tree("CPU")
                group = cpu["TEMPERATURE"]
                self.ensure_interval(group, 1)
                self.set_show(group["TEXT"])
                self.set_show(group["GRAPH"])
                selected_path = ("STATS", "CPU", "TEMPERATURE", "TEXT")

            elif component_id == "MEMORY":
                memory = self.ensure_official_sensor_tree("MEMORY")
                self.ensure_interval(memory, 5)
                self.set_show(memory["VIRTUAL"]["PERCENT_TEXT"])
                self.set_show(memory["VIRTUAL"]["GRAPH"])
                selected_path = (
                    "STATS", "MEMORY", "VIRTUAL", "PERCENT_TEXT"
                )

            elif component_id.startswith("GPU."):
                gpu = self.ensure_official_sensor_tree("GPU")
                self.ensure_interval(gpu, 1)
                key = component_id.split(".", 1)[1]
                self.set_show(gpu[key]["TEXT"])
                if "GRAPH" in gpu[key]:
                    self.set_show(gpu[key]["GRAPH"])
                selected_path = ("STATS", "GPU", key, "TEXT")

            elif component_id.startswith("NET."):
                net = self.ensure_official_sensor_tree("NET")
                self.ensure_interval(net, 5)
                _, interface, direction = component_id.split(".")
                self.set_show(net[interface][direction]["TEXT"])
                selected_path = (
                    "STATS", "NET", interface, direction, "TEXT"
                )

            elif component_id == "WEATHER":
                weather = self.ensure_official_sensor_tree("WEATHER")
                self.ensure_interval(weather, 300)
                self.set_show(weather["TEMPERATURE"]["TEXT"])
                self.set_show(weather["WEATHER_DESCRIPTION"]["TEXT"])
                selected_path = (
                    "STATS", "WEATHER", "TEMPERATURE", "TEXT"
                )

            elif component_id == "DISK":
                disk = self.ensure_official_sensor_tree("DISK")
                self.ensure_interval(disk, 10)
                self.set_show(disk["USED"]["PERCENT_TEXT"])
                self.set_show(disk["USED"]["GRAPH"])
                selected_path = (
                    "STATS", "DISK", "USED", "PERCENT_TEXT"
                )

            elif component_id == "PING":
                ping = self.ensure_official_sensor_tree("PING")
                self.ensure_interval(ping, 10)
                self.set_show(ping["TEXT"])
                selected_path = ("STATS", "PING", "TEXT")

            elif component_id == "UPTIME":
                uptime = self.ensure_official_sensor_tree("UPTIME")
                self.ensure_interval(uptime, 1)
                self.set_show(uptime["FORMATTED"]["TEXT"])
                selected_path = (
                    "STATS", "UPTIME", "FORMATTED", "TEXT"
                )

            elif component_id in ("DATE.DAY", "DATE.HOUR"):
                date = self.ensure_official_sensor_tree("DATE")
                self.ensure_interval(date, 1)
                key = component_id.split(".", 1)[1]
                self.set_show(date[key]["TEXT"])
                selected_path = ("STATS", "DATE", key, "TEXT")

            else:
                raise KeyError(component_id)

        except Exception as exc:
            if self.undo_stack:
                self.undo_stack.pop()
            self.error_dialog("Could not add component", str(exc))
            return

        self.finish_structure_change(
            selected_path,
            f"Component added: {component_id}",
        )

    def finish_structure_change(self, selected_path, message):
        save_yaml_atomic(self.theme_file, self.theme_data)
        self.populate_elements()
        self.selected_path = selected_path
        if selected_path is not None:
            try:
                self.build_property_rows()
            except Exception:
                pass
        self.refresh_preview()
        self.toast(message)

    @staticmethod
    def recursively_set_enabled(node, enabled):
        changed = False
        if isinstance(node, dict):
            if "SHOW" in node and node["SHOW"] != enabled:
                node["SHOW"] = enabled
                changed = True
            if "INTERVAL" in node:
                new_value = (
                    max(1, int(node.get("INTERVAL", 0) or 0))
                    if enabled else 0
                )
                if node["INTERVAL"] != new_value:
                    node["INTERVAL"] = new_value
                    changed = True
            for value in node.values():
                if isinstance(value, (dict, list)):
                    changed = (
                        ThemeEditorWindow.recursively_set_enabled(
                            value,
                            enabled,
                        )
                        or changed
                    )
        elif isinstance(node, list):
            for value in node:
                if isinstance(value, (dict, list)):
                    changed = (
                        ThemeEditorWindow.recursively_set_enabled(
                            value,
                            enabled,
                        )
                        or changed
                    )
        return changed

    def enable_selected(self):
        if self.selected_path is None:
            self.toast("Select a component first")
            return
        node = self.node_at_path(self.selected_path)
        self.push_undo()
        changed = self.recursively_set_enabled(node, True)
        if (
            isinstance(node, dict)
            and "INTERVAL" not in node
            and self.selected_path[:1] == ("STATS",)
        ):
            node["INTERVAL"] = 1
            changed = True
        if not changed:
            self.undo_stack.pop()
            self.toast("Component is already enabled")
            return
        self.finish_structure_change(
            self.selected_path,
            "Component enabled",
        )

    def disable_selected(self):
        if self.selected_path is None:
            self.toast("Select a component first")
            return

        if self.selected_path[0] in ("static_text", "static_images"):
            self.toast("Use Delete for static text and images")
            return

        node = self.node_at_path(self.selected_path)
        self.push_undo()
        changed = self.recursively_set_enabled(node, False)
        if isinstance(node, dict) and "INTERVAL" not in node:
            node["INTERVAL"] = 0
            changed = True
        if not changed:
            self.undo_stack.pop()
            self.toast("Component is already disabled")
            return
        self.finish_structure_change(
            self.selected_path,
            "Component disabled",
        )

    @staticmethod
    def offset_coordinates(node, amount=10):
        if isinstance(node, dict):
            if "X" in node:
                try:
                    node["X"] = int(node["X"]) + amount
                except Exception:
                    pass
            if "Y" in node:
                try:
                    node["Y"] = int(node["Y"]) + amount
                except Exception:
                    pass
            for value in node.values():
                if isinstance(value, (dict, list)):
                    ThemeEditorWindow.offset_coordinates(value, amount)
        elif isinstance(node, list):
            for value in node:
                if isinstance(value, (dict, list)):
                    ThemeEditorWindow.offset_coordinates(value, amount)

    def duplicate_selected(self):
        if self.selected_path is None:
            self.toast("Select an element first")
            return

        if self.selected_path[0] not in ("static_text", "static_images"):
            self.toast("Only custom text and static images can be duplicated")
            return

        parent = self.theme_data
        for part in self.selected_path[:-1]:
            parent = parent[part]

        if not isinstance(parent, dict):
            self.toast("This element cannot be duplicated")
            return

        key = self.selected_path[-1]
        self.push_undo()
        new_key = self.unique_mapping_key(parent, f"{key}_copy")
        parent[new_key] = copy.deepcopy(parent[key])
        self.offset_coordinates(parent[new_key], 10)
        new_path = self.selected_path[:-1] + (new_key,)
        self.finish_structure_change(new_path, "Element duplicated")

    def delete_selected(self):
        if self.selected_path is None:
            self.toast("Select an element first")
            return

        if self.selected_path[0] not in ("static_text", "static_images"):
            dialog = Adw.AlertDialog(
                heading="Disable sensor component?",
                body=(
                    "Sensor structures are kept because stats.py expects "
                    "their YAML keys. The selected component will be disabled."
                ),
            )
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("disable", "Disable")
            dialog.set_response_appearance(
                "disable",
                Adw.ResponseAppearance.DESTRUCTIVE,
            )
            dialog.connect(
                "response",
                lambda _dialog, response: self.disable_selected()
                if response == "disable" else None,
            )
            dialog.present(self)
            return

        label = " / ".join(str(part) for part in self.selected_path)
        dialog = Adw.AlertDialog(
            heading="Delete element?",
            body=f"{label} will be removed from the theme.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance(
            "delete",
            Adw.ResponseAppearance.DESTRUCTIVE,
        )

        def response(_dialog, response_id):
            if response_id != "delete":
                return

            parent = self.theme_data
            for part in self.selected_path[:-1]:
                parent = parent[part]

            self.push_undo()
            del parent[self.selected_path[-1]]

            if (
                isinstance(parent, dict)
                and not parent
                and len(self.selected_path) == 2
                and self.selected_path[0]
                in ("static_text", "static_images")
            ):
                self.theme_data.pop(self.selected_path[0], None)

            self.selected_path = None
            save_yaml_atomic(self.theme_file, self.theme_data)
            self.populate_elements()
            self.clear_property_group()
            self.refresh_preview()
            self.toast("Element deleted")

        dialog.connect("response", response)
        dialog.present(self)

    def open_classic_editor(self):
        try:
            subprocess.Popen(
                [project_python(), str(CLASSIC_EDITOR), self.theme_name],
                cwd=str(ROOT),
                start_new_session=True,
            )
        except Exception as exc:
            self.toast(f"Could not open classic editor: {exc}")

    def error_dialog(self, heading, body):
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("close", "Close")
        dialog.present(self)

    def toast(self, text):
        self.toast_overlay.add_toast(Adw.Toast(title=text, timeout=3))





class ThemeEditorApplication(Adw.Application):
    def __init__(self, theme_name: str):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.NON_UNIQUE,
        )
        self.theme_name = theme_name

    def do_activate(self):
        window = ThemeEditorWindow(self, self.theme_name)
        window.present()


def main():
    if len(sys.argv) != 2:
        print("Usage: theme-editor-gtk.py THEME_NAME", file=sys.stderr)
        return 2
    return ThemeEditorApplication(sys.argv[1]).run(sys.argv[:1])


if __name__ == "__main__":
    raise SystemExit(main())
