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
import tempfile
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
from library.theme_video_inspector import (
    VideoThemeUpdate,
    build_video_section,
    convert_media_atomic,
    create_preview_atomic,
    live_preview_settings,
    prepared_output_path,
    preview_background_path,
    resolve_local_video_source,
)
from library.theme_element_catalog import (
    STATE_ACTIVE,
    STATE_INACTIVE,
    STATE_MIXED,
    STATE_STRUCTURAL,
    catalog_entries,
    catalog_presence,
    catalog_preferred_path,
    element_icon_name,
    humanize_element_label,
    theme_state_summary,
    tree_state,
)
from library.theme_layer_order import (
    BRING_TO_FRONT,
    MOVE_BACKWARD,
    MOVE_FORWARD,
    SEND_TO_BACK,
    LayerOrderError,
    is_reorderable_layer,
    layer_action_state,
    layer_info,
    layer_position_label,
    move_layer,
)
from library.theme_media_layout import (
    ALIGN_X,
    ALIGN_Y,
    MODE_CUSTOM,
    MODE_FILL,
    MODE_FIT,
    MODE_ORIGINAL,
    MODE_STRETCH,
    ImageLayoutSettings,
    ThemeMediaLayoutError,
    compute_image_layout,
    image_dimensions,
    infer_layout_mode,
    layout_summary,
    render_image_layout_preview,
    resolve_theme_image_path,
    theme_canvas_dimensions,
)
from library.media_preparation import (
    ConversionSettings,
    alignment_offsets,
    cache_directory,
    probe_source,
)
from library.theme_generated_media import (
    GeneratedMediaStatus,
    inspect_generated_media,
    remove_unused_managed_asset,
)
from library.theme_media_transform import (
    ROTATION_0,
    ROTATION_90,
    ROTATION_180,
    ROTATION_270,
    ImageTransformSettings,
    ThemeMediaTransformError,
    is_identity_transform,
    prepare_transform_asset,
    render_transform_preview_asset,
    resolve_transform_source,
    transformed_dimensions,
    uncropped_transformed_dimensions,
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


def find_theme_file(theme_dir: Path) -> Path | None:
    """Return the supported YAML file for a theme directory."""
    for filename in ("theme.yaml", "theme.yml"):
        candidate = theme_dir / filename
        if candidate.is_file():
            return candidate
    return None


def available_themes() -> list[str]:
    if not THEMES_DIR.exists():
        return []

    themes = []
    try:
        for path in THEMES_DIR.iterdir():
            if path.is_dir() and find_theme_file(path) is not None:
                themes.append(path.name)
    except OSError:
        return []
    return sorted(themes, key=str.casefold)


def validate_theme_name(name: str) -> str:
    """Return a stripped valid theme directory name or raise ValueError."""
    name = str(name or "").strip()
    if not name:
        raise ValueError("Enter a theme name.")
    allowed = (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789._-"
    )
    if name in {".", ".."} or any(ch not in allowed for ch in name):
        raise ValueError("Use only letters, numbers, dots, underscores, and hyphens.")
    return name


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

    def __init__(
        self,
        label: str,
        path: tuple,
        node=None,
        display_label: str | None = None,
        icon_name: str = "applications-system-symbolic",
        status: str = "structural",
        status_label: str = "Configuration",
        active_count: int = 0,
        inactive_count: int = 0,
        layer_label: str = "",
    ):
        super().__init__()
        self.label = label
        self.path = path
        self.path_text = " / ".join(str(part) for part in path)
        self.node = node
        self.display_label = display_label or label
        self.icon_name = icon_name
        self.status = status
        self.status_label = status_label
        self.active_count = active_count
        self.inactive_count = inactive_count
        self.layer_label = layer_label
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
        theme_file = find_theme_file(self.theme_dir)
        if theme_file is None:
            raise FileNotFoundError(
                f"No theme.yaml or theme.yml found in {self.theme_dir}"
            )
        self.theme_file = theme_file
        self.preview_file = self.theme_dir / "preview.png"

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

        refresh_btn = Gtk.Button(
            icon_name="view-refresh-symbolic",
            tooltip_text="Render and refresh the theme preview",
        )
        refresh_btn.connect("clicked", lambda *_: self.refresh_preview())
        header.pack_end(refresh_btn)

        save_btn = Gtk.Button(
            label="Save",
            tooltip_text="Save the current theme YAML",
        )
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", lambda *_: self.save())
        header.pack_end(save_btn)

        def popover_action_button(label, icon_name, callback, popover):
            button = Gtk.Button()
            button.add_css_class("flat")
            button.set_halign(Gtk.Align.FILL)
            content = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=10,
                margin_top=4,
                margin_bottom=4,
                margin_start=4,
                margin_end=4,
            )
            content.append(Gtk.Image.new_from_icon_name(icon_name))
            text = Gtk.Label(label=label, xalign=0)
            text.set_hexpand(True)
            content.append(text)
            button.set_child(content)

            def activate(*_args):
                popover.popdown()
                callback()

            button.connect("clicked", activate)
            return button

        tools_popover = Gtk.Popover()
        tools_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            margin_top=10,
            margin_bottom=10,
            margin_start=10,
            margin_end=10,
        )
        tools_box.set_size_request(260, -1)
        media_heading = Gtk.Label(label="Media", xalign=0)
        media_heading.add_css_class("heading")
        tools_box.append(media_heading)
        tools_box.append(
            popover_action_button(
                "Video Inspector",
                "media-playback-start-symbolic",
                self.open_video_inspector,
                tools_popover,
            )
        )
        tools_box.append(
            popover_action_button(
                "Video and Background",
                "video-x-generic-symbolic",
                self.open_video_tools,
                tools_popover,
            )
        )
        tools_box.append(
            popover_action_button(
                "Generated Media",
                "folder-pictures-symbolic",
                self.open_generated_media_manager,
                tools_popover,
            )
        )
        tools_popover.set_child(tools_box)

        tools_button = Gtk.MenuButton(label="Tools")
        tools_button.set_tooltip_text("Open theme editing tools")
        tools_button.set_popover(tools_popover)
        header.pack_end(tools_button)

        overflow_popover = Gtk.Popover()
        overflow_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            margin_top=10,
            margin_bottom=10,
            margin_start=10,
            margin_end=10,
        )
        overflow_box.set_size_request(240, -1)
        overflow_box.append(
            popover_action_button(
                "Save As…",
                "document-save-as-symbolic",
                self.save_as,
                overflow_popover,
            )
        )
        overflow_box.append(
            popover_action_button(
                "Rename Theme…",
                "document-edit-symbolic",
                self.rename_theme,
                overflow_popover,
            )
        )
        overflow_box.append(
            popover_action_button(
                "Open Theme Folder",
                "folder-open-symbolic",
                lambda: self.reveal_generated_media(self.theme_dir),
                overflow_popover,
            )
        )
        overflow_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        overflow_box.append(
            popover_action_button(
                "Open Classic Editor",
                "applications-system-symbolic",
                self.open_classic_editor,
                overflow_popover,
            )
        )
        overflow_popover.set_child(overflow_box)

        overflow_button = Gtk.MenuButton(icon_name="open-menu-symbolic")
        overflow_button.set_tooltip_text("More theme actions")
        overflow_button.set_popover(overflow_popover)
        header.pack_end(overflow_button)

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

        self.elements_summary_label = Gtk.Label(label="", xalign=0)
        self.elements_summary_label.add_css_class("dim-label")
        box.append(self.elements_summary_label)

        add_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.catalog_entries = catalog_entries()
        self.catalog_labels = [
            f"{entry['category']} — {entry['label']}"
            for entry in self.catalog_entries
        ]
        self.add_element_dropdown = Gtk.DropDown.new_from_strings(
            self.catalog_labels
        )
        self.add_element_dropdown.set_hexpand(True)
        self.add_element_dropdown.connect(
            "notify::selected",
            self.on_catalog_selection_changed,
        )
        add_row.append(self.add_element_dropdown)
        self.add_element_button = Gtk.Button(
            label="Add",
            icon_name="list-add-symbolic",
            tooltip_text="Add or select the chosen catalog element",
        )
        self.add_element_button.add_css_class("suggested-action")
        self.add_element_button.connect("clicked", self.on_add_element_clicked)
        add_row.append(self.add_element_button)
        box.append(add_row)

        self.catalog_status_label = Gtk.Label(label="", xalign=0)
        self.catalog_status_label.add_css_class("dim-label")
        box.append(self.catalog_status_label)

        self.search_entry = Gtk.SearchEntry(placeholder_text="Search elements")
        self.search_entry.connect("search-changed", self.on_search_changed)
        box.append(self.search_entry)

        self.state_filter_labels = [
            "All elements",
            "Visible",
            "Hidden",
            "Mixed",
            "Structure",
        ]
        self.state_filter_dropdown = Gtk.DropDown.new_from_strings(
            self.state_filter_labels
        )
        self.state_filter_dropdown.set_selected(0)
        self.state_filter_dropdown.connect(
            "notify::selected",
            self.on_state_filter_changed,
        )
        box.append(self.state_filter_dropdown)

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

        actions_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.actions_button = Gtk.MenuButton(label="Actions")
        actions_popover = Gtk.Popover()
        actions_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
            margin_top=8,
            margin_bottom=8,
            margin_start=8,
            margin_end=8,
        )
        self.show_action_button = Gtk.Button(label="Show / Enable")
        self.show_action_button.set_tooltip_text(
            "Show static elements or enable sensor/video components"
        )
        self.show_action_button.connect("clicked", self.on_show_action_clicked)
        actions_box.append(self.show_action_button)
        self.hide_action_button = Gtk.Button(label="Hide / Disable")
        self.hide_action_button.set_tooltip_text(
            "Hide static elements or disable sensor/video components"
        )
        self.hide_action_button.connect("clicked", self.on_hide_action_clicked)
        actions_box.append(self.hide_action_button)
        self.adjust_image_layout_button = Gtk.Button(
            label="Adjust image layout…",
            icon_name="image-x-generic-symbolic",
        )
        self.adjust_image_layout_button.set_tooltip_text(
            "Open the non-destructive static image layout inspector"
        )
        self.adjust_image_layout_button.connect(
            "clicked",
            self.on_adjust_image_layout_clicked,
        )
        actions_box.append(self.adjust_image_layout_button)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        actions_box.append(separator)
        layer_title = Gtk.Label(label="Layer order", xalign=0)
        layer_title.add_css_class("dim-label")
        actions_box.append(layer_title)

        self.move_backward_button = Gtk.Button(
            label="Move backward",
            icon_name="go-up-symbolic",
        )
        self.move_backward_button.set_tooltip_text(
            "Move this layer one position toward the start of its group, drawing below its previous neighbor"
        )
        self.move_backward_button.connect(
            "clicked",
            lambda *_: self.move_selected_layer(MOVE_BACKWARD),
        )
        actions_box.append(self.move_backward_button)

        self.move_forward_button = Gtk.Button(
            label="Move forward",
            icon_name="go-down-symbolic",
        )
        self.move_forward_button.set_tooltip_text(
            "Move this layer one position toward the end of its group, drawing above its next neighbor"
        )
        self.move_forward_button.connect(
            "clicked",
            lambda *_: self.move_selected_layer(MOVE_FORWARD),
        )
        actions_box.append(self.move_forward_button)

        self.send_to_back_button = Gtk.Button(
            label="Send to back",
            icon_name="go-top-symbolic",
        )
        self.send_to_back_button.set_tooltip_text(
            "Move this layer to the first position of its text or image group"
        )
        self.send_to_back_button.connect(
            "clicked",
            lambda *_: self.move_selected_layer(SEND_TO_BACK),
        )
        actions_box.append(self.send_to_back_button)

        self.bring_to_front_button = Gtk.Button(
            label="Bring to front",
            icon_name="go-bottom-symbolic",
        )
        self.bring_to_front_button.set_tooltip_text(
            "Move this layer to the last position of its text or image group"
        )
        self.bring_to_front_button.connect(
            "clicked",
            lambda *_: self.move_selected_layer(BRING_TO_FRONT),
        )
        actions_box.append(self.bring_to_front_button)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        actions_box.append(separator)

        self.duplicate_action_button = Gtk.Button(label="Duplicate")
        self.duplicate_action_button.set_tooltip_text(
            "Duplicate the selected custom text or static image"
        )
        self.duplicate_action_button.connect(
            "clicked",
            self.on_duplicate_action_clicked,
        )
        actions_box.append(self.duplicate_action_button)
        self.delete_action_button = Gtk.Button(label="Delete")
        self.delete_action_button.add_css_class("destructive-action")
        self.delete_action_button.set_tooltip_text(
            "Delete custom elements; sensors are disabled after confirmation"
        )
        self.delete_action_button.connect("clicked", self.on_delete_action_clicked)
        actions_box.append(self.delete_action_button)
        actions_popover.set_child(actions_box)
        self.actions_button.set_popover(actions_popover)
        actions_row.append(self.actions_button)
        box.append(actions_row)

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
        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row_box.set_margin_top(6)
        row_box.set_margin_bottom(6)

        icon = Gtk.Image(icon_name="applications-system-symbolic")
        icon.set_pixel_size(18)
        row_box.append(icon)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_box.set_hexpand(True)
        title = Gtk.Label(xalign=0)
        title.set_hexpand(True)
        title.set_ellipsize(3)
        subtitle = Gtk.Label(xalign=0)
        subtitle.add_css_class("dim-label")
        subtitle.set_ellipsize(3)
        text_box.append(title)
        text_box.append(subtitle)
        row_box.append(text_box)

        state = Gtk.Label(xalign=1)
        state.add_css_class("dim-label")
        row_box.append(state)

        expander.set_child(row_box)
        list_item.set_child(expander)

    def bind_tree_item(self, _factory, list_item):
        row = list_item.get_item()
        expander = list_item.get_child()
        expander.set_list_row(row)

        item = row.get_item()
        row_box = expander.get_child()
        icon = row_box.get_first_child()
        text_box = icon.get_next_sibling()
        title = text_box.get_first_child()
        subtitle = title.get_next_sibling()
        state = text_box.get_next_sibling()

        icon.set_from_icon_name(item.icon_name or "applications-system-symbolic")
        title.set_label(item.display_label)
        subtitle.set_label(self.element_summary_text(item))
        subtitle.set_visible(bool(subtitle.get_label()))
        state.set_label(item.status_label)
        row_box.set_tooltip_text(item.path_text or item.label)

        for widget in (title, icon, state):
            if item.status == STATE_INACTIVE:
                widget.add_css_class("dim-label")
            else:
                widget.remove_css_class("dim-label")

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

    def inherited_enabled_for_path(self, path):
        node = self.theme_data
        enabled = True
        for part in path[:-1]:
            if not isinstance(node, dict) or part not in node:
                return enabled
            node = node[part]
            if isinstance(node, dict) and "INTERVAL" in node:
                try:
                    enabled = enabled and int(node.get("INTERVAL", 0) or 0) > 0
                except (TypeError, ValueError):
                    enabled = False
        return enabled

    def status_label_for_state(self, status, item=None):
        if status == STATE_ACTIVE:
            return "Visible"
        if status == STATE_INACTIVE:
            return "Hidden"
        if status == STATE_MIXED:
            return "Mixed"
        if item is not None and item.has_children():
            return "Group"
        return "Configuration"

    def element_counts(self, path, node):
        state = tree_state(
            path,
            node,
            inherited_enabled=self.inherited_enabled_for_path(path),
        )
        if state == STATE_ACTIVE:
            return 1, 0
        if state == STATE_INACTIVE:
            return 0, 1
        active = 0
        inactive = 0
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, dict):
                    child_active, child_inactive = self.element_counts(
                        path + (key,),
                        value,
                    )
                    active += child_active
                    inactive += child_inactive
        return active, inactive

    def element_summary_text(self, item):
        parts = []
        if item.status == STATE_STRUCTURAL:
            if item.layer_label:
                parts.append(item.layer_label)
            return " · ".join(parts)
        if item.has_children() and item.active_count:
            parts.append(f"{item.active_count} visible")
        if item.has_children() and item.inactive_count:
            parts.append(f"{item.inactive_count} hidden")
        if item.layer_label:
            parts.append(item.layer_label)
        return " · ".join(parts)

    def make_element_item(self, key, path, node):
        status = tree_state(
            path,
            node,
            inherited_enabled=self.inherited_enabled_for_path(path),
        )
        active_count, inactive_count = self.element_counts(path, node)
        item = ElementItem(
            str(key),
            path,
            node,
            display_label=humanize_element_label(key),
            icon_name=element_icon_name(path, node),
            status=status,
            status_label=self.status_label_for_state(status),
            active_count=active_count,
            inactive_count=inactive_count,
            layer_label=layer_position_label(self.theme_data, path),
        )
        return item

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

        def ordered_items(mapping, prefix):
            items = list(mapping.items())
            if not prefix:
                order = {
                    "display": 0,
                    "video": 1,
                    "static_text": 2,
                    "static_images": 3,
                    "STATS": 4,
                }
                items.sort(key=lambda pair: order.get(str(pair[0]), 99))
            return items

        def build_store(mapping, prefix=()):
            store = Gio.ListStore.new(ElementItem)
            for key, payload in ordered_items(mapping, prefix):
                path = prefix + (key,)
                node = payload.get("__node__")
                if node is None:
                    try:
                        node = self.node_at_path(path)
                    except Exception:
                        node = None
                item = self.make_element_item(key, path, node)
                children = build_store(payload.get("__children__", {}), path)
                for index in range(children.get_n_items()):
                    item.children.append(children.get_item(index))
                item.status_label = self.status_label_for_state(item.status, item)
                store.append(item)
            return store

        return build_store(root)

    def state_filter_key(self):
        index = getattr(self, "state_filter_dropdown", None)
        if index is None:
            return "all"
        selected = self.state_filter_dropdown.get_selected()
        labels = {
            1: STATE_ACTIVE,
            2: STATE_INACTIVE,
            3: STATE_MIXED,
            4: STATE_STRUCTURAL,
        }
        return labels.get(selected, "all")

    def item_matches_filters(self, item, query, state_filter):
        text_match = (
            not query
            or query in item.label.casefold()
            or query in item.display_label.casefold()
            or query in item.path_text.casefold()
        )
        state_match = state_filter == "all" or item.status == state_filter
        return text_match and state_match

    def populate_elements(self, search_text=None):
        self.root_items.remove_all()
        if search_text is None and hasattr(self, "search_entry"):
            search_text = self.search_entry.get_text()
        if search_text is None:
            search_text = ""
        query = search_text.strip().casefold()
        state_filter = self.state_filter_key()

        full_tree = self.build_element_tree()

        def clone_filtered(item):
            child_clones = []
            for index in range(item.children.get_n_items()):
                clone = clone_filtered(item.children.get_item(index))
                if clone is not None:
                    child_clones.append(clone)

            own_match = self.item_matches_filters(item, query, state_filter)
            if not own_match and not child_clones:
                return None

            clone = ElementItem(
                item.label,
                item.path,
                item.node,
                display_label=item.display_label,
                icon_name=item.icon_name,
                status=item.status,
                status_label=item.status_label,
                active_count=item.active_count,
                inactive_count=item.inactive_count,
                layer_label=item.layer_label,
            )
            for child in child_clones:
                clone.children.append(child)
            clone.status_label = self.status_label_for_state(clone.status, clone)
            return clone

        for index in range(full_tree.get_n_items()):
            clone = clone_filtered(full_tree.get_item(index))
            if clone is not None:
                self.root_items.append(clone)

        self.update_elements_summary()
        self.update_catalog_status()
        self.update_actions_sensitivity()

        if query or state_filter != "all":
            GLib.idle_add(lambda: (self.set_all_expanded(True), False)[1])

    def on_search_changed(self, entry):
        self.populate_elements(entry.get_text())

    def on_state_filter_changed(self, *_args):
        self.populate_elements()

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
            self.update_actions_sensitivity()
            return

        self.build_property_rows()
        self.update_actions_sensitivity()

    def update_elements_summary(self):
        summary = theme_state_summary(self.theme_data)
        parts = [
            f"{summary[STATE_ACTIVE]} visible",
            f"{summary[STATE_INACTIVE]} hidden",
        ]
        if summary[STATE_MIXED]:
            parts.append(f"{summary[STATE_MIXED]} mixed")
        self.elements_summary_label.set_label(" · ".join(parts))

    def selected_tree_status(self):
        if self.selected_path is None:
            return None
        try:
            node = self.node_at_path(self.selected_path)
        except Exception:
            return None
        return tree_state(
            self.selected_path,
            node,
            inherited_enabled=self.inherited_enabled_for_path(self.selected_path),
        )

    def selected_contains_state(self, desired_state):
        if self.selected_path is None:
            return False
        try:
            node = self.node_at_path(self.selected_path)
        except Exception:
            return False
        return self.node_contains_state(self.selected_path, node, desired_state)

    def node_contains_state(self, path, node, desired_state):
        state = tree_state(
            path,
            node,
            inherited_enabled=self.inherited_enabled_for_path(path),
        )
        if state == desired_state:
            return True
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, dict) and self.node_contains_state(
                    path + (key,),
                    value,
                    desired_state,
                ):
                    return True
        return False

    def update_actions_sensitivity(self):
        has_selection = self.selected_path is not None
        status = self.selected_tree_status()
        can_show = has_selection and (
            status in {STATE_INACTIVE, STATE_MIXED}
            or self.selected_contains_state(STATE_INACTIVE)
        )
        can_hide = has_selection and (
            status in {STATE_ACTIVE, STATE_MIXED}
            or self.selected_contains_state(STATE_ACTIVE)
        )
        can_duplicate = (
            has_selection
            and len(self.selected_path) == 2
            and self.selected_path[0] in ("static_text", "static_images")
        )
        can_delete = has_selection and len(self.selected_path) > 1
        if has_selection and self.selected_path[0] in ("static_text", "static_images"):
            can_delete = len(self.selected_path) == 2

        self.show_action_button.set_sensitive(bool(can_show))
        self.hide_action_button.set_sensitive(bool(can_hide))
        self.duplicate_action_button.set_sensitive(bool(can_duplicate))
        self.delete_action_button.set_sensitive(bool(can_delete))
        layer_state = (
            layer_action_state(self.theme_data, self.selected_path)
            if has_selection else {}
        )
        self.move_backward_button.set_sensitive(
            bool(layer_state.get(MOVE_BACKWARD, False))
        )
        self.move_forward_button.set_sensitive(
            bool(layer_state.get(MOVE_FORWARD, False))
        )
        self.send_to_back_button.set_sensitive(
            bool(layer_state.get(SEND_TO_BACK, False))
        )
        self.bring_to_front_button.set_sensitive(
            bool(layer_state.get(BRING_TO_FRONT, False))
        )
        self.adjust_image_layout_button.set_sensitive(
            self.selected_static_image(show_errors=False) is not None
        )

    def selected_static_image(self, show_errors=True):
        if (
            self.selected_path is None
            or len(self.selected_path) != 2
            or self.selected_path[0] != "static_images"
        ):
            if show_errors:
                self.toast("Select a static image first")
            return None
        try:
            node = self.node_at_path(self.selected_path)
            source_path = resolve_theme_image_path(self.theme_dir, node)
        except Exception as exc:
            if show_errors:
                self.error_dialog("Static image unavailable", str(exc))
            return None
        if not isinstance(node, dict):
            if show_errors:
                self.toast("Select a static image first")
            return None
        return tuple(self.selected_path), node, source_path

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

    def create_image_layout_row(self, node):
        selected = self.selected_static_image(show_errors=False)
        if selected is None:
            return None
        _path, _node, _source_path = selected
        try:
            transform_source = resolve_transform_source(
                self.theme_dir,
                str(node.get("PATH") or ""),
            )
            source_size = image_dimensions(transform_source.source_path)
            transformed_size = transformed_dimensions(
                source_size,
                transform_source.current_settings,
            )
            canvas_size = theme_canvas_dimensions(self.theme_data)
            mode = infer_layout_mode(transformed_size, canvas_size, node)
        except Exception:
            transform_source = None
            mode = MODE_CUSTOM
        mode_labels = {
            MODE_ORIGINAL: "Original",
            MODE_FIT: "Fit",
            MODE_FILL: "Fill",
            MODE_STRETCH: "Stretch",
            MODE_CUSTOM: "Custom",
        }
        width = int(node.get("WIDTH", 0) or 0)
        height = int(node.get("HEIGHT", 0) or 0)
        x = int(node.get("X", 0) or 0)
        y = int(node.get("Y", 0) or 0)
        parts = [f"{mode_labels.get(mode, 'Custom')} · {width}×{height} at {x},{y}"]
        if transform_source is not None:
            transform_label = self.transform_summary_label(
                transform_source.current_settings,
            )
            if transform_label:
                parts.append(transform_label)
            if transform_source.is_managed_asset:
                parts.append("Managed transformed asset")
        row = Adw.ActionRow(
            title="Image layout",
            subtitle=" · ".join(parts),
        )
        button = Gtk.Button(label="Adjust…", valign=Gtk.Align.CENTER)
        button.set_tooltip_text("Open the static image layout inspector")
        button.connect("clicked", self.on_adjust_image_layout_clicked)
        row.add_suffix(button)
        return row

    @staticmethod
    def transform_summary_label(settings):
        parts = []
        if settings.rotation == ROTATION_90:
            parts.append("90° clockwise")
        elif settings.rotation == ROTATION_180:
            parts.append("180°")
        elif settings.rotation == ROTATION_270:
            parts.append("270° clockwise")
        if settings.flip_horizontal:
            parts.append("mirrored horizontally")
        if settings.flip_vertical:
            parts.append("mirrored vertically")
        if settings.crop_box is not None:
            x, y, width, height = settings.crop_box
            parts.append(f"crop {width}×{height} at {x},{y}")
        return " · ".join(parts)

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

        if self.selected_path == ("video",):
            tools_row = Adw.ActionRow(
                title="Video tools",
                subtitle="Preview, prepare, or manage the theme video.",
            )
            inspector_button = Gtk.Button(
                label="Inspector",
                icon_name="media-playback-start-symbolic",
                valign=Gtk.Align.CENTER,
            )
            inspector_button.connect("clicked", self.on_video_inspector_clicked)
            background_button = Gtk.Button(
                label="Background",
                icon_name="video-x-generic-symbolic",
                valign=Gtk.Align.CENTER,
            )
            background_button.connect("clicked", self.on_video_tools_clicked)
            tools_row.add_suffix(inspector_button)
            tools_row.add_suffix(background_button)
            self.dynamic_group.add(tools_row)
            self.property_rows.append(tools_row)

        image_layout_row = self.create_image_layout_row(node)
        if image_layout_row is not None:
            self.dynamic_group.add(image_layout_row)
            self.property_rows.append(image_layout_row)

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
        self.update_elements_summary()
        self.update_catalog_status()
        self.update_actions_sensitivity()
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
        self.populate_elements()
        GLib.idle_add(self.restore_tree_selection, self.selected_path)
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
        self.populate_elements()
        GLib.idle_add(self.restore_tree_selection, self.selected_path)
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

            try:
                name = validate_theme_name(entry.get_text())
            except ValueError as exc:
                self.error_dialog(
                    "Invalid theme name",
                    str(exc),
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
                    destination / self.theme_file.name,
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

    def rename_theme(self):
        entry = Gtk.Entry(
            text=self.theme_name,
            activates_default=True,
        )
        current = Gtk.Label(
            label=f"Current theme: {self.theme_name}",
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
            heading="Rename theme",
            body=(
                "Rename the current theme folder and keep all local YAML, "
                "preview, generated media, and assets in place."
            ),
        )
        dialog.set_extra_child(content)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("rename", "Rename theme")
        dialog.set_response_appearance(
            "rename",
            Adw.ResponseAppearance.SUGGESTED,
        )
        dialog.set_default_response("rename")
        dialog.set_close_response("cancel")

        def response(_dialog, response_id):
            if response_id != "rename":
                return

            try:
                name = validate_theme_name(entry.get_text())
            except ValueError as exc:
                self.error_dialog("Invalid theme name", str(exc))
                return

            if name == self.theme_name:
                self.toast(f"{name} is already the current theme name")
                return

            destination = THEMES_DIR / name
            if destination.exists():
                self.error_dialog(
                    "Theme already exists",
                    f"A theme named '{name}' already exists.",
                )
                return

            old_name = self.theme_name
            old_dir = self.theme_dir
            old_file_name = self.theme_file.name
            try:
                save_yaml_atomic(self.theme_file, self.theme_data)
                old_dir.rename(destination)
                write_current_theme(name)
            except Exception as exc:
                if destination.exists() and not old_dir.exists():
                    try:
                        destination.rename(old_dir)
                    except Exception:
                        pass
                try:
                    write_current_theme(old_name)
                except Exception:
                    pass
                self.error_dialog("Could not rename theme", str(exc))
                return

            self.theme_name = name
            self.theme_dir = destination
            self.theme_file = destination / old_file_name
            self.preview_file = destination / "preview.png"
            app = self.get_application()
            if app is not None:
                app.theme_name = name

            self.set_title(f"Theme Editor — {name}")
            self.window_title.set_title(name)
            self.populate_elements()
            self.update_catalog_status()
            self.refresh_preview()
            self.toast(f"Theme renamed to {name}")

        dialog.connect("response", response)
        dialog.present(self)

    def reveal_generated_media(self, path: Path):
        target = path if path.exists() else path.parent
        directory = target.parent if target.is_file() else target
        try:
            subprocess.Popen(
                ["gio", "open", str(directory)],
                start_new_session=True,
            )
        except Exception as exc:
            self.error_dialog("Could not open file manager", str(exc))

    def open_generated_media_manager(self):
        dialog = Adw.PreferencesDialog()
        dialog.set_title("Generated Media")
        dialog.set_content_width(820)
        dialog.set_content_height(680)

        page = Adw.PreferencesPage(
            title="Generated Media",
            icon_name="folder-pictures-symbolic",
        )
        dialog.add(page)

        summary_group = Adw.PreferencesGroup(title="Manifest")
        assets_group = Adw.PreferencesGroup(title="Assets")
        page.add(summary_group)
        page.add(assets_group)
        visible_rows = {"summary": [], "assets": []}

        def replace_rows(group, key, rows):
            for previous in visible_rows[key]:
                group.remove(previous)
            visible_rows[key] = list(rows)
            for row in visible_rows[key]:
                group.add(row)

        def status_label(status):
            return {
                GeneratedMediaStatus.IN_USE: "In use",
                GeneratedMediaStatus.UNUSED: "Unused",
                GeneratedMediaStatus.ORPHANED: "Orphaned",
                GeneratedMediaStatus.UNMANAGED: "Unmanaged",
            }[status]

        def transform_summary(record):
            settings = record.settings
            if settings is None:
                return "Transform unavailable"
            parts = [f"rotation {settings.rotation}°"]
            if settings.flip_horizontal:
                parts.append("horizontal flip")
            if settings.flip_vertical:
                parts.append("vertical flip")
            if settings.crop_box is not None:
                x, y, width, height = settings.crop_box
                parts.append(f"crop {width}×{height} at {x},{y}")
            else:
                parts.append("no crop")
            return " · ".join(parts)

        def confirm_remove(record):
            confirm = Adw.AlertDialog(
                heading="Remove unused generated asset?",
                body=(
                    f"{record.reference}\n\n"
                    "Only the generated file and its manifest entry will be removed."
                ),
            )
            confirm.add_response("cancel", "Cancel")
            confirm.add_response("remove", "Remove")
            confirm.set_response_appearance(
                "remove", Adw.ResponseAppearance.DESTRUCTIVE
            )
            confirm.set_close_response("cancel")

            def response(_dialog, response_id):
                if response_id != "remove":
                    return
                try:
                    remove_unused_managed_asset(
                        self.theme_dir,
                        self.theme_data,
                        record.reference,
                    )
                except Exception as exc:
                    self.error_dialog("Could not remove generated asset", str(exc))
                    return
                self.toast(f"Removed {Path(record.reference).name}")
                populate()

            confirm.connect("response", response)
            confirm.present(dialog)

        def populate():
            report = inspect_generated_media(self.theme_dir, self.theme_data)
            summary_rows = []
            asset_rows = []

            manifest_row = Adw.ActionRow(
                title="transform-manifest.json",
                subtitle=(
                    str(report.manifest_path)
                    if report.manifest_valid
                    else report.manifest_error or "Invalid manifest"
                ),
            )
            manifest_row.add_prefix(
                Gtk.Image.new_from_icon_name(
                    "emblem-ok-symbolic"
                    if report.manifest_valid
                    else "dialog-error-symbolic"
                )
            )
            reveal_manifest = Gtk.Button(
                icon_name="folder-open-symbolic",
                tooltip_text="Open manifest location",
                valign=Gtk.Align.CENTER,
            )
            reveal_manifest.connect(
                "clicked",
                lambda *_: self.reveal_generated_media(report.manifest_path),
            )
            manifest_row.add_suffix(reveal_manifest)
            summary_rows.append(manifest_row)

            if report.manifest_valid and not report.records:
                asset_rows.append(
                    Adw.ActionRow(
                        title="No generated assets",
                        subtitle="The manifest and generated-media directory are empty.",
                    )
                )

            if report.manifest_valid:
                for record in report.records:
                    details = [status_label(record.status)]
                    if record.source_reference:
                        details.append(f"source: {record.source_reference}")
                    details.append(transform_summary(record))
                    if record.issues:
                        details.append("; ".join(record.issues))
                    row = Adw.ActionRow(
                        title=Path(record.reference).name,
                        subtitle="\n".join(details),
                    )

                    if record.exists:
                        preview = Gtk.Picture.new_for_filename(str(record.path))
                        preview.set_size_request(96, 64)
                        preview.set_content_fit(Gtk.ContentFit.CONTAIN)
                        row.add_prefix(preview)
                    else:
                        row.add_prefix(
                            Gtk.Image.new_from_icon_name("image-missing-symbolic")
                        )

                    reveal = Gtk.Button(
                        icon_name="folder-open-symbolic",
                        tooltip_text="Reveal in file manager",
                        valign=Gtk.Align.CENTER,
                    )
                    reveal.connect(
                        "clicked",
                        lambda _button, item=record: self.reveal_generated_media(
                            item.path
                        ),
                    )
                    row.add_suffix(reveal)

                    remove = Gtk.Button(
                        icon_name="user-trash-symbolic",
                        tooltip_text=(
                            "Remove unused managed asset"
                            if record.removable
                            else "This asset cannot be safely removed"
                        ),
                        valign=Gtk.Align.CENTER,
                        sensitive=record.removable,
                    )
                    remove.add_css_class("destructive-action")
                    remove.connect(
                        "clicked",
                        lambda _button, item=record: confirm_remove(item),
                    )
                    row.add_suffix(remove)
                    asset_rows.append(row)

            replace_rows(summary_group, "summary", summary_rows)
            replace_rows(assets_group, "assets", asset_rows)

        populate()
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
from library.theme_video_background import theme_uses_video_overlay
if theme_uses_video_overlay(config.THEME_DATA):
    display.lcd.video_overlay_enabled = True
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

    def on_video_inspector_clicked(self, *_args):
        try:
            self.open_video_inspector()
        except Exception as exc:
            self.error_dialog("Could not open video inspector", str(exc))

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
        theme_file = find_theme_file(theme_dir)
        if theme_file is None:
            self.error_dialog(
                "Could not change theme",
                f"No theme.yaml or theme.yml was found in {theme_dir}.",
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

    def open_video_inspector(self):
        current_video = self.theme_data.get("video", {})
        if not isinstance(current_video, dict):
            current_video = {}
        target_width, target_height = theme_canvas_dimensions(self.theme_data)

        dialog = Adw.PreferencesDialog()
        dialog.set_title("Video Inspector")
        dialog.set_content_width(920)
        dialog.set_content_height(760)

        page = Adw.PreferencesPage(
            title="Video Inspector",
            icon_name="media-playback-start-symbolic",
        )
        dialog.add(page)

        source_group = Adw.PreferencesGroup(
            title="Source",
            description="Choose and inspect a local GIF or video before changing the theme.",
        )
        preview_group = Adw.PreferencesGroup(title="Preview")
        framing_group = Adw.PreferencesGroup(
            title="Framing",
            description=f"Prepared output: {target_width}×{target_height} H.264/yuv420p.",
        )
        crop_group = Adw.PreferencesGroup(title="Crop and rotation")
        output_group = Adw.PreferencesGroup(title="Output and theme")
        page.add(source_group)
        page.add(preview_group)
        page.add(framing_group)
        page.add(crop_group)
        page.add(output_group)

        source_row = Adw.ActionRow(
            title="No local video selected",
            subtitle="Choose a supported GIF, MP4, MKV, WebM, MOV, or AVI file.",
        )
        choose_source = Gtk.Button(
            label="Choose…",
            icon_name="document-open-symbolic",
            valign=Gtk.Align.CENTER,
        )
        source_row.add_suffix(choose_source)
        source_group.add(source_row)

        metadata_row = Adw.ActionRow(
            title="Media information",
            subtitle="No source has been analyzed.",
        )
        source_group.add(metadata_row)

        preview_video = Gtk.Video()
        preview_video.set_size_request(480, 360)
        preview_video.set_hexpand(True)
        preview_video.set_vexpand(True)
        preview_video.set_autoplay(True)
        preview_video.set_loop(True)

        play_pause_button = Gtk.Button(
            icon_name="media-playback-start-symbolic",
            tooltip_text="Play or pause the preview",
            sensitive=False,
        )
        restart_button = Gtk.Button(
            icon_name="media-skip-backward-symbolic",
            tooltip_text="Restart the preview",
            sensitive=False,
        )
        timeline = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL,
            0.0,
            1.0,
            0.01,
        )
        timeline.set_draw_value(False)
        timeline.set_hexpand(True)
        timeline.set_sensitive(False)
        time_label = Gtk.Label(label="00:00 / 00:00")
        time_label.add_css_class("numeric")
        loop_toggle = Gtk.CheckButton(label="Loop")
        loop_toggle.set_active(True)

        playback_controls = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )
        playback_controls.append(play_pause_button)
        playback_controls.append(restart_button)
        playback_controls.append(timeline)
        playback_controls.append(time_label)
        playback_controls.append(loop_toggle)

        preview_status = Gtk.Label(
            label="Choose a source to start the automatic preview.",
            xalign=0,
            wrap=True,
        )
        preview_status.add_css_class("dim-label")
        preview_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
        )
        preview_box.append(preview_video)
        preview_box.append(playback_controls)
        preview_box.append(preview_status)
        preview_group.add(preview_box)

        mode_ids = ("fit", "fill", "stretch", "original", "custom")
        mode_row = Adw.ComboRow(
            title="Mode",
            model=Gtk.StringList.new(("Fit", "Fill", "Stretch", "Original", "Custom")),
        )
        mode_row.set_selected(0)
        framing_group.add(mode_row)

        def add_spin(group, title, value, lower, upper, step=1.0, digits=0):
            row = Adw.ActionRow(title=title)
            spin = Gtk.SpinButton.new_with_range(lower, upper, step)
            spin.set_digits(digits)
            spin.set_value(float(value))
            spin.set_size_request(130, -1)
            spin.set_valign(Gtk.Align.CENTER)
            row.add_suffix(spin)
            group.add(row)
            return spin

        zoom_spin = add_spin(framing_group, "Zoom", 1.0, 0.25, 4.0, 0.05, 2)
        custom_width_spin = add_spin(
            framing_group,
            "Custom width",
            target_width,
            2,
            4096,
        )
        custom_height_spin = add_spin(
            framing_group,
            "Custom height",
            target_height,
            2,
            4096,
        )

        align_x_ids = ("left", "center", "right")
        align_x_row = Adw.ComboRow(
            title="Horizontal alignment",
            model=Gtk.StringList.new(("Left", "Center", "Right")),
        )
        align_x_row.set_selected(1)
        framing_group.add(align_x_row)

        align_y_ids = ("top", "center", "bottom")
        align_y_row = Adw.ComboRow(
            title="Vertical alignment",
            model=Gtk.StringList.new(("Top", "Center", "Bottom")),
        )
        align_y_row.set_selected(1)
        framing_group.add(align_y_row)

        rotation_ids = (0, 90, 180, 270)
        rotation_row = Adw.ComboRow(
            title="Rotation",
            model=Gtk.StringList.new(("0°", "90°", "180°", "270°")),
        )
        rotation_row.set_selected(0)
        crop_group.add(rotation_row)

        crop_left_spin = add_spin(crop_group, "Crop left", 0, 0, 4096)
        crop_right_spin = add_spin(crop_group, "Crop right", 0, 0, 4096)
        crop_top_spin = add_spin(crop_group, "Crop top", 0, 0, 4096)
        crop_bottom_spin = add_spin(crop_group, "Crop bottom", 0, 0, 4096)

        fps_ids = (24, 30)
        fps_row = Adw.ComboRow(
            title="Output FPS",
            model=Gtk.StringList.new(("24 FPS", "30 FPS")),
        )
        fps_row.set_selected(1)
        output_group.add(fps_row)
        crf_spin = add_spin(output_group, "Quality (CRF)", 20, 0, 51)

        output_name_row = Adw.EntryRow(title="Prepared video filename")
        output_name_row.set_text(str(current_video.get("LOCAL_PATH") or ""))
        output_group.add(output_name_row)

        storage_row = Adw.ComboRow(
            title="Display storage",
            model=Gtk.StringList.new(("SD card", "Internal memory")),
        )
        if str(current_video.get("PATH") or "").startswith("/root/video/"):
            storage_row.set_selected(1)
        output_group.add(storage_row)

        preview_name_row = Adw.EntryRow(title="Theme preview background")
        preview_name_row.set_text(
            str(current_video.get("PREVIEW_BACKGROUND") or "video-preview.png")
        )
        output_group.add(preview_name_row)

        overlay_row = Adw.SwitchRow(
            title="Transparent video overlay",
            subtitle="Render widgets over the video on supported displays.",
        )
        overlay_row.set_active(bool(current_video.get("OVERLAY", True)))
        output_group.add(overlay_row)

        preview_button = Gtk.Button(
            label="Refresh preview",
            icon_name="view-refresh-symbolic",
            sensitive=False,
        )
        apply_button = Gtk.Button(
            label="Convert and apply",
            icon_name="media-record-symbolic",
            sensitive=False,
        )
        apply_button.add_css_class("suggested-action")
        close_button = Gtk.Button(label="Close")
        actions = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            halign=Gtk.Align.END,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
        )
        actions.append(close_button)
        actions.append(preview_button)
        actions.append(apply_button)
        output_group.add(actions)

        state = {
            "source_path": None,
            "source_media": None,
            "probe_generation": 0,
            "preview_generation": 0,
            "preview_path": None,
            "preview_debounce_id": 0,
            "timeline_timer_id": 0,
            "updating_timeline": False,
            "closed": False,
            "busy": False,
        }

        def set_busy(busy):
            state["busy"] = bool(busy)
            choose_source.set_sensitive(not busy)
            preview_button.set_sensitive(not busy and state["source_media"] is not None)
            apply_button.set_sensitive(not busy and state["source_media"] is not None)

        def update_custom_sensitivity(*_args):
            custom = mode_row.get_selected() == mode_ids.index("custom")
            custom_width_spin.set_sensitive(custom)
            custom_height_spin.set_sensitive(custom)

        mode_row.connect("notify::selected", update_custom_sensitivity)
        update_custom_sensitivity()

        def selected_settings():
            media = state["source_media"]
            if media is None:
                raise ValueError("Choose and analyze a local source first.")
            mode_index = mode_row.get_selected()
            rotation_index = rotation_row.get_selected()
            fps_index = fps_row.get_selected()
            values = {
                "mode": mode_ids[mode_index] if mode_index < len(mode_ids) else "fit",
                "zoom": zoom_spin.get_value(),
                "target_width": target_width,
                "target_height": target_height,
                "profile_id": f"theme:{self.theme_name}",
                "custom_width": int(custom_width_spin.get_value()),
                "custom_height": int(custom_height_spin.get_value()),
                "crop_left": int(crop_left_spin.get_value()),
                "crop_right": int(crop_right_spin.get_value()),
                "crop_top": int(crop_top_spin.get_value()),
                "crop_bottom": int(crop_bottom_spin.get_value()),
                "rotation": rotation_ids[rotation_index]
                if rotation_index < len(rotation_ids)
                else 0,
                "fps": fps_ids[fps_index] if fps_index < len(fps_ids) else 30,
                "crf": int(crf_spin.get_value()),
            }
            base = ConversionSettings(**values)
            horizontal_index = align_x_row.get_selected()
            vertical_index = align_y_row.get_selected()
            horizontal = align_x_ids[horizontal_index]
            vertical = align_y_ids[vertical_index]
            offset_x, offset_y = alignment_offsets(
                media.width,
                media.height,
                base,
                horizontal,
                vertical,
            )
            values["offset_x"] = offset_x
            values["offset_y"] = offset_y
            return ConversionSettings(**values).validated(
                duration=media.duration,
                source_width=media.width,
                source_height=media.height,
            )

        def finish_probe(generation, path, media, error):
            if state["closed"] or generation != state["probe_generation"]:
                return False
            set_busy(False)
            if error:
                state["source_path"] = None
                state["source_media"] = None
                source_row.set_title("Could not analyze source")
                source_row.set_subtitle(str(path))
                metadata_row.set_subtitle(error)
                preview_status.set_label(error)
                return False

            state["source_path"] = Path(path)
            state["source_media"] = media
            source_row.set_title(media.filename)
            source_row.set_subtitle(media.path)
            fps_text = f"{media.fps:.2f}" if media.fps is not None else "unknown"
            metadata_row.set_subtitle(
                f"{media.width}×{media.height} · {media.codec} · {media.pixel_format or 'unknown'} · "
                f"{fps_text} FPS · {media.duration:.2f} s · {media.size_bytes} bytes"
            )
            crop_left_spin.set_range(0, max(0, media.width - 1))
            crop_right_spin.set_range(0, max(0, media.width - 1))
            crop_top_spin.set_range(0, max(0, media.height - 1))
            crop_bottom_spin.set_range(0, max(0, media.height - 1))
            if not output_name_row.get_text().strip():
                output_name_row.set_text(
                    prepared_output_path(cache_directory(), media.filename).name
                )
            schedule_preview()
            return False

        def start_probe(path):
            path = Path(path).expanduser().resolve()
            state["probe_generation"] += 1
            generation = state["probe_generation"]
            state["preview_generation"] += 1
            set_busy(True)
            source_row.set_title("Analyzing source…")
            source_row.set_subtitle(str(path))
            metadata_row.set_subtitle("Running FFprobe…")

            def worker():
                try:
                    media = probe_source(path)
                    error = None
                except Exception as exc:
                    media = None
                    error = str(exc)
                GLib.idle_add(finish_probe, generation, path, media, error)

            threading.Thread(target=worker, daemon=True).start()

        def choose_local_source(*_args):
            chooser = Gtk.FileDialog(title="Choose a GIF or video", modal=True)
            media_filter = Gtk.FileFilter()
            media_filter.set_name("GIF and video files")
            for pattern in ("*.gif", "*.mp4", "*.mkv", "*.webm", "*.mov", "*.avi"):
                media_filter.add_pattern(pattern)
            filters = Gio.ListStore.new(Gtk.FileFilter)
            filters.append(media_filter)
            chooser.set_filters(filters)

            def selected(chooser, result):
                try:
                    file = chooser.open_finish(result)
                except GLib.Error:
                    return
                path = file.get_path()
                if path:
                    start_probe(path)

            chooser.open(self, None, selected)

        choose_source.connect("clicked", choose_local_source)

        def format_media_time(seconds):
            seconds = max(0, int(seconds or 0))
            minutes, seconds = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            if hours:
                return f"{hours:d}:{minutes:02d}:{seconds:02d}"
            return f"{minutes:02d}:{seconds:02d}"

        def playback_stream():
            return preview_video.get_media_stream()

        def update_playback_controls():
            if state["closed"]:
                return False
            stream = playback_stream()
            if stream is None:
                return True
            duration_us = max(0, int(stream.get_duration()))
            timestamp_us = max(0, int(stream.get_timestamp()))
            duration = duration_us / 1_000_000
            timestamp = timestamp_us / 1_000_000
            state["updating_timeline"] = True
            try:
                timeline.set_range(0.0, max(duration, 0.01))
                timeline.set_value(min(timestamp, max(duration, 0.01)))
            finally:
                state["updating_timeline"] = False
            time_label.set_label(
                f"{format_media_time(timestamp)} / {format_media_time(duration)}"
            )
            play_pause_button.set_icon_name(
                "media-playback-pause-symbolic"
                if stream.get_playing()
                else "media-playback-start-symbolic"
            )
            return True

        def seek_preview(scale):
            if state["updating_timeline"]:
                return
            stream = playback_stream()
            if stream is not None and stream.get_seekable():
                stream.seek(int(scale.get_value() * 1_000_000))

        timeline.connect("value-changed", seek_preview)

        def toggle_playback(*_args):
            stream = playback_stream()
            if stream is None:
                return
            if stream.get_playing():
                stream.pause()
            else:
                stream.play()
            update_playback_controls()

        def restart_playback(*_args):
            stream = playback_stream()
            if stream is None:
                return
            if stream.get_seekable():
                stream.seek(0)
            stream.play()
            update_playback_controls()

        def update_loop(*_args):
            preview_video.set_loop(loop_toggle.get_active())

        play_pause_button.connect("clicked", toggle_playback)
        restart_button.connect("clicked", restart_playback)
        loop_toggle.connect("toggled", update_loop)

        def finish_preview(generation, output, error):
            if state["closed"] or generation != state["preview_generation"]:
                Path(output).unlink(missing_ok=True)
                return False
            set_busy(False)
            if error:
                preview_status.set_label(error)
                return False
            previous_stream = playback_stream()
            resume_timestamp = 0
            if previous_stream is not None:
                resume_timestamp = max(0, int(previous_stream.get_timestamp()))
            old_output = state.get("preview_path")
            state["preview_path"] = Path(output)
            preview_video.set_file(Gio.File.new_for_path(str(output)))
            preview_video.set_loop(loop_toggle.get_active())
            preview_video.set_autoplay(True)
            play_pause_button.set_sensitive(True)
            restart_button.set_sensitive(True)
            timeline.set_sensitive(True)
            preview_status.set_label(
                "Playing an automatic 8-second transformed preview. "
                "Controls update it after a short pause."
            )

            def resume_playback():
                stream = playback_stream()
                if stream is None:
                    return False
                duration = max(0, int(stream.get_duration()))
                target = resume_timestamp
                if duration > 0:
                    target %= duration
                if target > 0 and stream.get_seekable():
                    stream.seek(target)
                stream.play()
                update_playback_controls()
                return False

            GLib.timeout_add(150, resume_playback)
            if old_output is not None and Path(old_output) != Path(output):
                GLib.timeout_add(
                    1000,
                    lambda path=Path(old_output): (
                        path.unlink(missing_ok=True),
                        False,
                    )[1],
                )
            return False

        def queue_preview(*_args):
            source = state["source_path"]
            media = state["source_media"]
            if source is None or media is None:
                return False
            try:
                settings = live_preview_settings(
                    selected_settings(),
                    media.duration,
                )
            except Exception as exc:
                preview_status.set_label(str(exc))
                return False
            state["preview_generation"] += 1
            generation = state["preview_generation"]
            output = (
                cache_directory()
                / f"theme-editor-live-preview-{os.getpid()}-{generation}.mp4"
            )
            set_busy(True)
            preview_status.set_label("Updating the live preview…")

            def worker():
                try:
                    convert_media_atomic(source, output, settings)
                    error = None
                except Exception as exc:
                    error = str(exc)
                GLib.idle_add(finish_preview, generation, output, error)

            threading.Thread(target=worker, daemon=True).start()
            return False

        def schedule_preview(*_args):
            if state["source_media"] is None:
                return
            debounce_id = state.get("preview_debounce_id", 0)
            if debounce_id:
                GLib.source_remove(debounce_id)
            preview_status.set_label("Settings changed — preview update queued…")

            def run_preview():
                state["preview_debounce_id"] = 0
                return queue_preview()

            state["preview_debounce_id"] = GLib.timeout_add(450, run_preview)

        preview_button.connect("clicked", queue_preview)
        for spin in (
            zoom_spin,
            custom_width_spin,
            custom_height_spin,
            crop_left_spin,
            crop_right_spin,
            crop_top_spin,
            crop_bottom_spin,
            crf_spin,
        ):
            spin.connect("value-changed", schedule_preview)
        for combo in (
            mode_row,
            align_x_row,
            align_y_row,
            rotation_row,
            fps_row,
        ):
            combo.connect("notify::selected", schedule_preview)

        state["timeline_timer_id"] = GLib.timeout_add(
            200,
            update_playback_controls,
        )

        def finish_conversion(output, preview_destination, update, error):
            if state["closed"]:
                return False
            set_busy(False)
            if error:
                self.error_dialog("Could not prepare video", error)
                return False
            try:
                self.push_undo()
                existing = self.theme_data.get("video", {})
                self.theme_data["video"] = build_video_section(existing, update)
                save_yaml_atomic(self.theme_file, self.theme_data)
            except Exception as exc:
                self.error_dialog("Could not apply video to theme", str(exc))
                return False

            self.populate_elements()
            self.selected_path = ("video",)
            GLib.idle_add(self.restore_tree_selection, self.selected_path)
            self.build_property_rows()
            self.refresh_preview()
            self.toast(f"Prepared and applied {Path(output).name}")
            preview_status.set_label(
                f"Prepared: {output}\nTheme background: {preview_destination}"
            )
            return False

        def begin_conversion(output, preview_destination, settings, update):
            source = state["source_path"]
            set_busy(True)
            preview_status.set_label("Converting video and generating theme background…")

            def worker():
                try:
                    convert_media_atomic(source, output, settings)
                    create_preview_atomic(source, preview_destination, settings)
                    error = None
                except Exception as exc:
                    error = str(exc)
                GLib.idle_add(
                    finish_conversion,
                    output,
                    preview_destination,
                    update,
                    error,
                )

            threading.Thread(target=worker, daemon=True).start()

        def convert_and_apply(*_args):
            if state["source_path"] is None or state["source_media"] is None:
                self.toast("Choose a local source first")
                return
            try:
                settings = selected_settings()
                output = prepared_output_path(
                    cache_directory(),
                    output_name_row.get_text() or state["source_media"].filename,
                )
                preview_destination = preview_background_path(
                    self.theme_dir,
                    preview_name_row.get_text(),
                )
                remote_path = display_video_path(
                    output.name,
                    internal=storage_row.get_selected() == 1,
                )
                update = VideoThemeUpdate(
                    local_filename=output.name,
                    remote_path=remote_path,
                    preview_background=preview_destination.name,
                    background_frame_time=0.0,
                    overlay=overlay_row.get_active(),
                )
            except Exception as exc:
                self.error_dialog("Invalid video settings", str(exc))
                return

            if not output.exists():
                begin_conversion(output, preview_destination, settings, update)
                return

            confirm = Adw.AlertDialog(
                heading="Replace prepared video?",
                body=(
                    f"{output.name} already exists in the media-preparation cache. "
                    "The existing prepared copy will be replaced only after a successful conversion."
                ),
            )
            confirm.add_response("cancel", "Cancel")
            confirm.add_response("replace", "Replace")
            confirm.set_response_appearance(
                "replace",
                Adw.ResponseAppearance.DESTRUCTIVE,
            )
            confirm.set_close_response("cancel")

            def response(_confirm, response_id):
                if response_id == "replace":
                    begin_conversion(output, preview_destination, settings, update)

            confirm.connect("response", response)
            confirm.present(dialog)

        apply_button.connect("clicked", convert_and_apply)
        close_button.connect("clicked", lambda *_: dialog.close())

        def closed(*_args):
            state["closed"] = True
            state["probe_generation"] += 1
            state["preview_generation"] += 1
            debounce_id = state.get("preview_debounce_id", 0)
            if debounce_id:
                GLib.source_remove(debounce_id)
            timer_id = state.get("timeline_timer_id", 0)
            if timer_id:
                GLib.source_remove(timer_id)
            preview_video.set_file(None)
            preview_path = state.get("preview_path")
            if preview_path is not None:
                Path(preview_path).unlink(missing_ok=True)

        dialog.connect("closed", closed)
        dialog.present(self)

        initial_source = resolve_local_video_source(self.theme_dir, current_video)
        if initial_source is None:
            initial_source = find_prepared_local_video(
                str(current_video.get("PATH") or "")
            )
        if initial_source is not None:
            start_probe(initial_source)

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
            if self.switch_theme(theme_names[index]):
                dialog.close()

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

    def selected_catalog_entry(self):
        index = self.add_element_dropdown.get_selected()
        if index < 0 or index >= len(self.catalog_entries):
            return None
        return self.catalog_entries[index]

    def catalog_action(self, entry):
        presence = catalog_presence(self.theme_data, entry["id"])
        if entry["repeatable"] and presence["count"] > 0:
            return "add_another"
        if not presence["present"]:
            return "add"
        if presence["state"] == STATE_INACTIVE:
            return "enable"
        return "select"

    def update_catalog_status(self):
        if not hasattr(self, "add_element_dropdown"):
            return
        entry = self.selected_catalog_entry()
        if entry is None:
            return
        presence = catalog_presence(self.theme_data, entry["id"])
        action = self.catalog_action(entry)
        if action == "add_another":
            status_text = f"{presence['count']} existing items"
            button_label = "Add another"
        elif action == "add":
            status_text = "Available to add"
            button_label = "Add"
        elif action == "enable":
            status_text = "Currently hidden"
            button_label = "Enable"
        else:
            status_text = (
                "Already visible"
                if presence["state"] == STATE_ACTIVE
                else "Mixed visibility"
            )
            button_label = "Select"
        self.catalog_status_label.set_label(status_text)
        self.add_element_button.set_label(button_label)

    def on_catalog_selection_changed(self, *_args):
        self.update_catalog_status()

    def on_add_element_clicked(self, *_args):
        entry = self.selected_catalog_entry()
        if entry is None:
            return
        action = self.catalog_action(entry)
        if entry["component_id"] == "text" and action in {"add", "add_another"}:
            self.add_custom_text()
            return
        if entry["component_id"] == "image" and action in {"add", "add_another"}:
            self.choose_static_image()
            return
        if action == "add":
            self.add_sensor_component(entry["component_id"])
            return
        path = catalog_preferred_path(self.theme_data, entry["id"])
        if path is None:
            self.toast("Element is not available in this theme")
            return
        if action == "enable":
            self.enable_path(path)
            return
        self.selected_path = path
        GLib.idle_add(self.restore_tree_selection, path)

    def add_custom_text(self):
        self.push_undo()
        container = self.theme_data.setdefault("static_text", {})
        key = self.unique_mapping_key(container, "custom_text")
        container[key] = {
            "SHOW": True,
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
            "SHOW": True,
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
        GLib.idle_add(self.restore_tree_selection, selected_path)
        if selected_path is not None:
            try:
                self.build_property_rows()
            except Exception:
                pass
        else:
            self.clear_property_group()
        self.update_elements_summary()
        self.update_catalog_status()
        self.update_actions_sensitivity()
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

    def set_static_path_visible(self, path, visible):
        node = self.node_at_path(path)
        changed = False
        if len(path) == 1 and path[0] in ("static_text", "static_images"):
            if isinstance(node, dict):
                for child in node.values():
                    if isinstance(child, dict) and child.get("SHOW", True) != visible:
                        child["SHOW"] = bool(visible)
                        changed = True
        elif len(path) == 2 and path[0] in ("static_text", "static_images"):
            if isinstance(node, dict) and node.get("SHOW", True) != visible:
                node["SHOW"] = bool(visible)
                changed = True
        return changed

    def apply_enabled_to_path(self, path, enabled):
        node = self.node_at_path(path)
        if path and path[0] in ("static_text", "static_images"):
            return self.set_static_path_visible(path, enabled)
        if path == ("video",) and isinstance(node, dict):
            if node.get("ENABLED", False) != enabled:
                node["ENABLED"] = bool(enabled)
                return True
            return False

        changed = self.recursively_set_enabled(node, enabled)
        if isinstance(node, dict) and "INTERVAL" not in node and path[:1] == ("STATS",):
            node["INTERVAL"] = 1 if enabled else 0
            changed = True
        return changed

    def enable_path(self, path):
        self.push_undo()
        changed = self.apply_enabled_to_path(path, True)
        if not changed:
            self.undo_stack.pop()
            self.toast("Component is already enabled")
            return
        self.finish_structure_change(path, "Component enabled")

    def disable_path(self, path):
        self.push_undo()
        changed = self.apply_enabled_to_path(path, False)
        if not changed:
            self.undo_stack.pop()
            self.toast("Component is already disabled")
            return
        self.finish_structure_change(path, "Component disabled")

    def enable_selected(self):
        if self.selected_path is None:
            self.toast("Select a component first")
            return
        self.enable_path(self.selected_path)

    def disable_selected(self):
        if self.selected_path is None:
            self.toast("Select a component first")
            return
        self.disable_path(self.selected_path)

    def on_show_action_clicked(self, *_args):
        self.actions_button.popdown()
        self.enable_selected()

    def on_hide_action_clicked(self, *_args):
        self.actions_button.popdown()
        self.disable_selected()

    def on_adjust_image_layout_clicked(self, *_args):
        self.actions_button.popdown()
        self.open_image_layout_inspector()

    def open_image_layout_inspector(self):
        selected = self.selected_static_image()
        if selected is None:
            return
        selected_path, node, _current_path = selected
        try:
            transform_source = resolve_transform_source(
                self.theme_dir,
                str(node.get("PATH") or ""),
            )
            source_size = image_dimensions(transform_source.source_path)
            current_transform = transform_source.current_settings
            current_uncropped_size = uncropped_transformed_dimensions(
                source_size,
                current_transform,
            )
            current_transformed_size = transformed_dimensions(
                source_size,
                current_transform,
            )
            canvas_size = theme_canvas_dimensions(self.theme_data)
        except Exception as exc:
            self.error_dialog("Could not inspect image", str(exc))
            return

        current_geometry = {
            "X": int(node.get("X", 0) or 0),
            "Y": int(node.get("Y", 0) or 0),
            "WIDTH": int(node.get("WIDTH", source_size[0]) or source_size[0]),
            "HEIGHT": int(node.get("HEIGHT", source_size[1]) or source_size[1]),
        }
        inferred_mode = infer_layout_mode(
            current_transformed_size,
            canvas_size,
            current_geometry,
        )
        mode_ids = [
            MODE_ORIGINAL,
            MODE_FIT,
            MODE_FILL,
            MODE_STRETCH,
            MODE_CUSTOM,
        ]
        mode_labels = [
            "Original size",
            "Fit",
            "Fill",
            "Stretch",
            "Custom size",
        ]
        rotation_ids = [
            ROTATION_0,
            ROTATION_90,
            ROTATION_180,
            ROTATION_270,
        ]
        rotation_labels = [
            "0°",
            "90° clockwise",
            "180°",
            "270° clockwise",
        ]
        crop_preset_ids = ["free", "square", "canvas", "source"]
        crop_preset_labels = ["Free", "Square", "Canvas ratio", "Source ratio"]

        dialog = Adw.Window(
            title="Image layout",
            transient_for=self,
            modal=True,
        )
        dialog.set_default_size(1000, 720)

        root = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=16,
            margin_top=16,
            margin_bottom=16,
            margin_start=16,
            margin_end=16,
        )
        dialog.set_content(root)

        controls_scroll = Gtk.ScrolledWindow()
        controls_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        controls_scroll.set_size_request(360, -1)
        controls = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        controls_scroll.set_child(controls)
        root.append(controls_scroll)

        info_group = Adw.PreferencesGroup(title="Image")
        info_group.add(
            Adw.ActionRow(
                title="Original source",
                subtitle=transform_source.source_reference,
            )
        )
        info_group.add(
            Adw.ActionRow(
                title="Current asset",
                subtitle=transform_source.current_asset_reference,
            )
        )
        info_group.add(
            Adw.ActionRow(
                title="Source dimensions",
                subtitle=f"{source_size[0]}×{source_size[1]}",
            )
        )
        transformed_row = Adw.ActionRow(
            title="Transformed dimensions",
            subtitle=f"{current_transformed_size[0]}×{current_transformed_size[1]}",
        )
        info_group.add(transformed_row)
        info_group.add(
            Adw.ActionRow(
                title="Canvas dimensions",
                subtitle=f"{canvas_size[0]}×{canvas_size[1]}",
            )
        )
        info_group.add(
            Adw.ActionRow(
                title="Current geometry",
                subtitle=(
                    f"{current_geometry['WIDTH']}×{current_geometry['HEIGHT']} "
                    f"at {current_geometry['X']},{current_geometry['Y']}"
                ),
            )
        )
        controls.append(info_group)

        transform_group = Adw.PreferencesGroup(title="Transform")
        rotation_model = Gtk.StringList.new(rotation_labels)
        rotation_row = Adw.ComboRow(title="Rotation", model=rotation_model)
        rotation_row.set_selected(rotation_ids.index(current_transform.rotation))
        transform_group.add(rotation_row)
        flip_h_row = Adw.SwitchRow(title="Mirror horizontally")
        flip_h_row.set_active(current_transform.flip_horizontal)
        transform_group.add(flip_h_row)
        flip_v_row = Adw.SwitchRow(title="Mirror vertically")
        flip_v_row.set_active(current_transform.flip_vertical)
        transform_group.add(flip_v_row)
        reset_transform_row = Adw.ActionRow(title="Reset transform")
        reset_transform_btn = Gtk.Button(
            label="Reset rotation and mirrors",
            tooltip_text="Reset transform controls without changing YAML until Apply",
            valign=Gtk.Align.CENTER,
        )
        reset_transform_row.add_suffix(reset_transform_btn)
        transform_group.add(reset_transform_row)
        controls.append(transform_group)

        current_crop = current_transform.crop_box
        crop_group = Adw.PreferencesGroup(title="Crop")
        crop_enabled_row = Adw.SwitchRow(title="Enable crop")
        crop_enabled_row.set_active(current_crop is not None)
        crop_group.add(crop_enabled_row)

        crop_preset_model = Gtk.StringList.new(crop_preset_labels)
        crop_preset_row = Adw.ComboRow(title="Preset", model=crop_preset_model)
        crop_preset_row.set_selected(0)
        crop_group.add(crop_preset_row)

        crop_x_row = Adw.ActionRow(title="Crop X")
        crop_x_spin = Gtk.SpinButton.new_with_range(0, 4096, 1)
        crop_x_spin.set_valign(Gtk.Align.CENTER)
        crop_x_spin.set_size_request(110, -1)
        crop_x_row.add_suffix(crop_x_spin)
        crop_group.add(crop_x_row)

        crop_y_row = Adw.ActionRow(title="Crop Y")
        crop_y_spin = Gtk.SpinButton.new_with_range(0, 4096, 1)
        crop_y_spin.set_valign(Gtk.Align.CENTER)
        crop_y_spin.set_size_request(110, -1)
        crop_y_row.add_suffix(crop_y_spin)
        crop_group.add(crop_y_row)

        crop_width_row = Adw.ActionRow(title="Crop width")
        crop_width_spin = Gtk.SpinButton.new_with_range(1, 4096, 1)
        crop_width_spin.set_valign(Gtk.Align.CENTER)
        crop_width_spin.set_size_request(110, -1)
        crop_width_row.add_suffix(crop_width_spin)
        crop_group.add(crop_width_row)

        crop_height_row = Adw.ActionRow(title="Crop height")
        crop_height_spin = Gtk.SpinButton.new_with_range(1, 4096, 1)
        crop_height_spin.set_valign(Gtk.Align.CENTER)
        crop_height_spin.set_size_request(110, -1)
        crop_height_row.add_suffix(crop_height_spin)
        crop_group.add(crop_height_row)

        crop_size_row = Adw.ActionRow(
            title="Crop source",
            subtitle=f"{current_uncropped_size[0]}×{current_uncropped_size[1]}",
        )
        crop_group.add(crop_size_row)

        reset_crop_row = Adw.ActionRow(title="Reset crop")
        reset_crop_btn = Gtk.Button(
            label="Use full image",
            tooltip_text="Disable crop without changing YAML until Apply",
            valign=Gtk.Align.CENTER,
        )
        reset_crop_row.add_suffix(reset_crop_btn)
        crop_group.add(reset_crop_row)
        controls.append(crop_group)

        layout_group = Adw.PreferencesGroup(title="Layout")
        mode_model = Gtk.StringList.new(mode_labels)
        mode_row = Adw.ComboRow(title="Mode", model=mode_model)
        mode_row.set_selected(mode_ids.index(inferred_mode))
        layout_group.add(mode_row)

        zoom_row = Adw.ActionRow(title="Zoom")
        zoom_spin = Gtk.SpinButton.new_with_range(0.25, 4.0, 0.05)
        zoom_spin.set_digits(2)
        zoom_spin.set_value(1.0)
        zoom_spin.set_valign(Gtk.Align.CENTER)
        zoom_spin.set_size_request(110, -1)
        zoom_row.add_suffix(zoom_spin)
        layout_group.add(zoom_row)

        custom_width_row = Adw.ActionRow(title="Custom width")
        custom_width_spin = Gtk.SpinButton.new_with_range(1, 4096, 1)
        custom_width_spin.set_value(float(current_geometry["WIDTH"]))
        custom_width_spin.set_valign(Gtk.Align.CENTER)
        custom_width_spin.set_size_request(110, -1)
        custom_width_row.add_suffix(custom_width_spin)
        layout_group.add(custom_width_row)

        custom_height_row = Adw.ActionRow(title="Custom height")
        custom_height_spin = Gtk.SpinButton.new_with_range(1, 4096, 1)
        custom_height_spin.set_value(float(current_geometry["HEIGHT"]))
        custom_height_spin.set_valign(Gtk.Align.CENTER)
        custom_height_spin.set_size_request(110, -1)
        custom_height_row.add_suffix(custom_height_spin)
        layout_group.add(custom_height_row)

        align_row = Adw.ActionRow(title="Alignment")
        align_grid = Gtk.Grid(column_spacing=4, row_spacing=4)
        alignment_buttons = {}
        alignment_state = {"x": "center", "y": "center"}
        for row_index, align_y in enumerate(ALIGN_Y):
            for col_index, align_x in enumerate(ALIGN_X):
                button = Gtk.ToggleButton()
                button.set_size_request(34, 28)
                button.set_tooltip_text(f"{align_x} / {align_y}")
                button.set_label("•")
                alignment_buttons[(align_x, align_y)] = button
                align_grid.attach(button, col_index, row_index, 1, 1)
        align_row.add_suffix(align_grid)
        layout_group.add(align_row)

        geometry_row = Adw.ActionRow(title="Calculated geometry")
        layout_group.add(geometry_row)
        controls.append(layout_group)

        button_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda *_: dialog.close())
        apply_btn = Gtk.Button(label="Apply")
        apply_btn.add_css_class("suggested-action")
        button_row.append(cancel_btn)
        button_row.append(apply_btn)
        controls.append(button_row)

        preview_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        preview_box.set_hexpand(True)
        preview_box.set_vexpand(True)
        preview_label = Gtk.Label(label="Rendering preview…", xalign=0)
        preview_label.add_css_class("dim-label")
        preview_box.append(preview_label)
        aspect = Gtk.AspectFrame()
        aspect.set_ratio(canvas_size[0] / canvas_size[1])
        aspect.set_obey_child(False)
        aspect.set_hexpand(True)
        aspect.set_vexpand(True)
        picture = Gtk.Picture()
        picture.set_can_shrink(True)
        if hasattr(Gtk, "ContentFit"):
            picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        aspect.set_child(picture)
        preview_box.append(aspect)
        root.append(preview_box)

        preview_state = {"generation": 0, "source": 0, "closed": False}
        cache_dir = Path(tempfile.gettempdir()) / "turing-theme-editor-layout-preview"

        def base_transform_settings():
            rotation_index = rotation_row.get_selected()
            if rotation_index < 0 or rotation_index >= len(rotation_ids):
                rotation_index = 0
            return ImageTransformSettings(
                rotation=rotation_ids[rotation_index],
                flip_horizontal=flip_h_row.get_active(),
                flip_vertical=flip_v_row.get_active(),
            )

        def crop_source_size():
            return uncropped_transformed_dimensions(
                source_size,
                base_transform_settings(),
            )

        def set_crop_ranges(width, height):
            crop_x_spin.set_range(0, max(0, width - 1))
            crop_y_spin.set_range(0, max(0, height - 1))
            crop_width_spin.set_range(1, max(1, width))
            crop_height_spin.set_range(1, max(1, height))

        def set_crop_box(crop_box, *, enable=True):
            width, height = crop_source_size()
            set_crop_ranges(width, height)
            if crop_box is None:
                x, y, crop_width, crop_height = 0, 0, width, height
                enable = False
            else:
                x, y, crop_width, crop_height = crop_box
                x = max(0, min(int(x), max(0, width - 1)))
                y = max(0, min(int(y), max(0, height - 1)))
                crop_width = max(1, min(int(crop_width), width - x))
                crop_height = max(1, min(int(crop_height), height - y))
            crop_enabled_row.set_active(enable)
            crop_x_spin.set_value(float(x))
            crop_y_spin.set_value(float(y))
            crop_width_spin.set_value(float(crop_width))
            crop_height_spin.set_value(float(crop_height))
            crop_size_row.set_subtitle(f"{width}×{height}")

        def selected_crop_box():
            if not crop_enabled_row.get_active():
                return None
            width, height = crop_source_size()
            x = int(crop_x_spin.get_value())
            y = int(crop_y_spin.get_value())
            crop_width = int(crop_width_spin.get_value())
            crop_height = int(crop_height_spin.get_value())
            x = max(0, min(x, max(0, width - 1)))
            y = max(0, min(y, max(0, height - 1)))
            crop_width = max(1, min(crop_width, width - x))
            crop_height = max(1, min(crop_height, height - y))
            return (x, y, crop_width, crop_height)

        def apply_crop_preset(*_args):
            width, height = crop_source_size()
            preset_index = crop_preset_row.get_selected()
            if preset_index < 0 or preset_index >= len(crop_preset_ids):
                preset_index = 0
            preset = crop_preset_ids[preset_index]
            if preset == "free":
                return
            if preset == "square":
                crop_width = crop_height = min(width, height)
            else:
                if preset == "canvas":
                    ratio_width, ratio_height = canvas_size
                else:
                    ratio_width, ratio_height = source_size
                ratio = ratio_width / ratio_height
                crop_width = width
                crop_height = int(round(crop_width / ratio))
                if crop_height > height:
                    crop_height = height
                    crop_width = int(round(crop_height * ratio))
                crop_width = max(1, min(width, crop_width))
                crop_height = max(1, min(height, crop_height))
            x = max(0, (width - crop_width) // 2)
            y = max(0, (height - crop_height) // 2)
            set_crop_box((x, y, crop_width, crop_height), enable=True)
            queue_preview()

        def selected_layout_settings():
            mode_index = mode_row.get_selected()
            if mode_index < 0 or mode_index >= len(mode_ids):
                mode_index = mode_ids.index(MODE_CUSTOM)
            return ImageLayoutSettings(
                mode=mode_ids[mode_index],
                zoom=float(zoom_spin.get_value()),
                align_x=alignment_state["x"],
                align_y=alignment_state["y"],
                custom_width=int(custom_width_spin.get_value()),
                custom_height=int(custom_height_spin.get_value()),
            )

        def selected_transform_settings():
            base = base_transform_settings()
            return ImageTransformSettings(
                rotation=base.rotation,
                flip_horizontal=base.flip_horizontal,
                flip_vertical=base.flip_vertical,
                crop_box=selected_crop_box(),
            )

        def calculated_layout():
            transform_settings = selected_transform_settings()
            layout_settings = selected_layout_settings()
            transformed_size = transformed_dimensions(
                source_size,
                transform_settings,
            )
            layout = compute_image_layout(
                transformed_size[0],
                transformed_size[1],
                canvas_size[0],
                canvas_size[1],
                layout_settings,
            )
            return transform_settings, layout_settings, transformed_size, layout

        def set_alignment(align_x, align_y):
            alignment_state["x"] = align_x
            alignment_state["y"] = align_y
            for key, button in alignment_buttons.items():
                button.set_active(key == (align_x, align_y))
            queue_preview()

        for (align_x, align_y), button in alignment_buttons.items():
            button.connect(
                "clicked",
                lambda widget, x=align_x, y=align_y: set_alignment(x, y)
                if widget.get_active() else None,
            )

        def update_custom_sensitivity():
            mode_index = mode_row.get_selected()
            is_custom = (
                0 <= mode_index < len(mode_ids)
                and mode_ids[mode_index] == MODE_CUSTOM
            )
            custom_width_spin.set_sensitive(is_custom)
            custom_height_spin.set_sensitive(is_custom)

        def update_crop_sensitivity():
            active = crop_enabled_row.get_active()
            crop_preset_row.set_sensitive(active)
            crop_x_spin.set_sensitive(active)
            crop_y_spin.set_sensitive(active)
            crop_width_spin.set_sensitive(active)
            crop_height_spin.set_sensitive(active)

        def clamp_crop_to_source():
            set_crop_box(selected_crop_box(), enable=crop_enabled_row.get_active())

        def render_preview(transform_settings, layout, generation):
            transformed_path = cache_dir / (
                f"layout-transform-{os.getpid()}-{generation}.png"
            )
            output_path = cache_dir / f"layout-preview-{os.getpid()}-{generation}.png"
            try:
                render_transform_preview_asset(
                    transform_source.source_path,
                    transformed_path,
                    transform_settings,
                )
                rendered = render_image_layout_preview(
                    transformed_path,
                    output_path,
                    canvas_size=canvas_size,
                    layout=layout,
                )
                error = None
            except Exception as exc:
                rendered = None
                error = str(exc)

            def finish():
                if preview_state["closed"] or generation != preview_state["generation"]:
                    return False
                if error:
                    preview_label.set_label("Could not render preview")
                    picture.set_paintable(None)
                    return False
                picture.set_filename(str(rendered))
                preview_label.set_label("Preview ready")
                return False

            GLib.idle_add(finish)

        def refresh_layout_preview():
            preview_state["source"] = 0
            try:
                (
                    transform_settings,
                    layout_settings,
                    transformed_size,
                    layout,
                ) = calculated_layout()
            except Exception as exc:
                geometry_row.set_subtitle(str(exc))
                transformed_row.set_subtitle("Unavailable")
                preview_label.set_label("Could not render preview")
                picture.set_paintable(None)
                return False

            transformed_row.set_subtitle(
                f"{transformed_size[0]}×{transformed_size[1]}"
            )
            summary = layout_summary(layout, layout_settings)
            transform_label = self.transform_summary_label(transform_settings)
            if transform_label:
                summary = f"{summary} · {transform_label}"
            geometry_row.set_subtitle(summary)
            preview_state["generation"] += 1
            generation = preview_state["generation"]
            preview_label.set_label("Rendering preview…")
            threading.Thread(
                target=render_preview,
                args=(transform_settings, layout, generation),
                daemon=True,
            ).start()
            return False

        def queue_preview(*_args):
            preview_state["source"] += 1
            source = preview_state["source"]

            def maybe_refresh():
                if source != preview_state["source"]:
                    return False
                return refresh_layout_preview()

            GLib.timeout_add(250, maybe_refresh)

        def mode_changed(*_args):
            update_custom_sensitivity()
            queue_preview()

        def transform_changed(*_args):
            clamp_crop_to_source()
            queue_preview()

        def crop_changed(*_args):
            update_crop_sensitivity()
            queue_preview()

        def reset_transform(*_args):
            rotation_row.set_selected(0)
            flip_h_row.set_active(False)
            flip_v_row.set_active(False)
            queue_preview()

        def reset_crop(*_args):
            set_crop_box(None)
            update_crop_sensitivity()
            queue_preview()

        def on_close(*_args):
            preview_state["closed"] = True
            preview_state["generation"] += 1
            return False

        dialog.connect("close-request", on_close)
        mode_row.connect("notify::selected", mode_changed)
        zoom_spin.connect("value-changed", queue_preview)
        custom_width_spin.connect("value-changed", queue_preview)
        custom_height_spin.connect("value-changed", queue_preview)
        rotation_row.connect("notify::selected", transform_changed)
        flip_h_row.connect("notify::active", transform_changed)
        flip_v_row.connect("notify::active", transform_changed)
        reset_transform_btn.connect("clicked", reset_transform)
        crop_enabled_row.connect("notify::active", crop_changed)
        crop_preset_row.connect("notify::selected", apply_crop_preset)
        crop_x_spin.connect("value-changed", queue_preview)
        crop_y_spin.connect("value-changed", queue_preview)
        crop_width_spin.connect("value-changed", queue_preview)
        crop_height_spin.connect("value-changed", queue_preview)
        reset_crop_btn.connect("clicked", reset_crop)

        def apply_layout(*_args):
            selected_now = self.selected_static_image()
            if selected_now is None:
                return
            current_path, current_node, _current_source = selected_now
            if current_path != selected_path:
                self.toast("Image selection changed")
                return
            try:
                transform_settings = selected_transform_settings()
                layout_settings = selected_layout_settings()
                prepared = prepare_transform_asset(
                    self.theme_dir,
                    str(current_node.get("PATH") or ""),
                    transform_settings,
                )
                layout = compute_image_layout(
                    prepared.output_size[0],
                    prepared.output_size[1],
                    canvas_size[0],
                    canvas_size[1],
                    layout_settings,
                )
            except Exception as exc:
                self.error_dialog("Could not apply layout", str(exc))
                return

            keys = ("PATH", "X", "Y", "WIDTH", "HEIGHT")
            final_values = {
                "PATH": prepared.output_reference,
                "X": int(layout["X"]),
                "Y": int(layout["Y"]),
                "WIDTH": int(layout["WIDTH"]),
                "HEIGHT": int(layout["HEIGHT"]),
            }
            changed = str(current_node.get("PATH") or "") != final_values["PATH"]
            changed = changed or any(
                int(current_node.get(key, 0) or 0) != final_values[key]
                for key in ("X", "Y", "WIDTH", "HEIGHT")
            )
            if not changed:
                self.toast("No image changes")
                return

            old_values = {key: current_node.get(key) for key in keys}
            pushed = self.push_undo()
            try:
                for key, value in final_values.items():
                    current_node[key] = value
                save_yaml_atomic(self.theme_file, self.theme_data)
            except Exception as exc:
                for key, value in old_values.items():
                    current_node[key] = value
                if pushed and self.undo_stack:
                    self.undo_stack.pop()
                    self.update_history_buttons()
                self.error_dialog("Could not apply layout", str(exc))
                return

            self.populate_elements()
            self.selected_path = selected_path
            GLib.idle_add(self.restore_tree_selection, selected_path)
            self.build_property_rows()
            self.update_elements_summary()
            self.update_catalog_status()
            self.update_actions_sensitivity()
            self.refresh_preview()
            self.toast("Image transform and layout updated")
            dialog.close()

        apply_btn.connect("clicked", apply_layout)
        set_crop_box(current_crop, enable=current_crop is not None)
        set_alignment("center", "center")
        update_custom_sensitivity()
        update_crop_sensitivity()
        queue_preview()
        dialog.present()

    def move_selected_layer(self, action):
        self.actions_button.popdown()
        if self.selected_path is None:
            self.toast("Select a layer first")
            return
        selected_path = tuple(self.selected_path)
        if not is_reorderable_layer(self.theme_data, selected_path):
            self.toast("Only static text and image items can be reordered")
            return

        info = layer_info(self.theme_data, selected_path)
        if not info.get("actions", {}).get(action, False):
            self.toast("Layer is already at that position")
            self.update_actions_sensitivity()
            return

        messages = {
            MOVE_BACKWARD: "Moved backward",
            MOVE_FORWARD: "Moved forward",
            SEND_TO_BACK: "Sent to back",
            BRING_TO_FRONT: "Brought to front",
        }
        self.push_undo()
        try:
            self.theme_data = move_layer(self.theme_data, selected_path, action)
        except LayerOrderError as exc:
            if self.undo_stack:
                self.undo_stack.pop()
                self.update_history_buttons()
            self.toast(str(exc))
            return
        except Exception as exc:
            if self.undo_stack:
                self.undo_stack.pop()
                self.update_history_buttons()
            self.error_dialog("Could not move layer", str(exc))
            return

        save_yaml_atomic(self.theme_file, self.theme_data)
        self.populate_elements()
        self.selected_path = selected_path
        # Filters may hide the selected item; keep the logical selection and
        # let restore_tree_selection select it visually only when still shown.
        GLib.idle_add(self.restore_tree_selection, selected_path)
        try:
            self.build_property_rows()
        except Exception:
            self.clear_property_group()
        self.update_elements_summary()
        self.update_catalog_status()
        self.update_actions_sensitivity()
        self.refresh_preview()
        self.toast(messages.get(action, "Layer moved"))

    def on_duplicate_action_clicked(self, *_args):
        self.actions_button.popdown()
        self.duplicate_selected()

    def on_delete_action_clicked(self, *_args):
        self.actions_button.popdown()
        self.delete_selected()

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
            self.update_elements_summary()
            self.update_catalog_status()
            self.update_actions_sensitivity()
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
