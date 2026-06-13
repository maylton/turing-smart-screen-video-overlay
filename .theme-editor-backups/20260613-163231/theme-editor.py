#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Advanced visual theme editor for turing-smart-screen-python.

Features:
- Simulated live preview
- Generic element/property editor
- Drag selected elements on the preview
- Undo / Redo
- Restore session start
- Save as copy
- Apply to display only when requested
"""

from __future__ import annotations

from library.pythoncheck import check_python_version
check_python_version()

import copy
import locale
import logging
import os
import shutil
import subprocess
import sys
import time
import tempfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from PIL import Image, ImageTk
import ruamel.yaml

if len(sys.argv) != 2:
    print("Usage: theme-editor.py theme-name")
    raise SystemExit(2)

import library.log
library.log.logger.setLevel(logging.NOTSET)

logger = logging.getLogger("turing-editor")
logger.setLevel(logging.DEBUG)

from library import config

THEME_NAME = sys.argv[1]
MAIN_DIRECTORY = Path(__file__).resolve().parent
THEME_DIR = MAIN_DIRECTORY / "res" / "themes" / THEME_NAME
THEME_FILE = THEME_DIR / "theme.yaml"
BACKUP_FILE = THEME_DIR / "theme.yaml.editor-backup"
PREVIEW_FILE = THEME_DIR / "preview.png"

if not THEME_FILE.is_file():
    raise SystemExit(f"Theme file not found: {THEME_FILE}")

config.CONFIG_DATA["config"]["HW_SENSORS"] = "STATIC"
config.CONFIG_DATA["config"]["THEME"] = THEME_NAME
config.load_theme()
config.CONFIG_DATA["display"]["REVISION"] = "SIMU"

from library.display import display

EDITABLE_KEYS = (
    "X", "Y", "WIDTH", "HEIGHT",
    "FONT_SIZE", "FONT_COLOR", "BACKGROUND_COLOR",
    "ALIGN", "ANCHOR", "TEXT", "SHOW", "INTERVAL", "PATH"
)

NUMERIC_KEYS = {"X", "Y", "WIDTH", "HEIGHT", "FONT_SIZE", "INTERVAL"}
BOOLEAN_KEYS = {"SHOW"}


COMPONENT_PRESETS = {
    "Custom text": ("static_text",),
    "Static image": ("static_images",),
    "CPU usage": (("STATS", "CPU", "PERCENTAGE"),),
    "CPU temperature": (("STATS", "CPU", "TEMPERATURE"),),
    "CPU frequency": (("STATS", "CPU", "FREQUENCY"),),
    "CPU load": (("STATS", "CPU", "LOAD"),),
    "CPU fan speed": (("STATS", "CPU", "FAN_SPEED"),),
    "RAM usage": (("STATS", "MEMORY"),),
    "GPU usage": (
        ("STATS", "GPU", "PERCENTAGE"),
        ("STATS", "GPU"),
    ),
    "GPU temperature": (
        ("STATS", "GPU", "TEMPERATURE"),
        ("STATS", "GPU"),
    ),
    "Date": (
        ("STATS", "DATE", "DATE"),
        ("STATS", "DATE"),
    ),
    "Time": (
        ("STATS", "DATE", "HOUR"),
        ("STATS", "DATE"),
    ),
    "Disk usage": (("STATS", "DISK"),),
    "Network": (("STATS", "NET"),),
    "Weather": (("STATS", "WEATHER"),),
    "Ping": (("STATS", "PING"),),
    "System uptime": (("STATS", "UPTIME"),),
    "Custom sensor": (("STATS", "CUSTOM"),),
}

yaml = ruamel.yaml.YAML()
yaml.preserve_quotes = True


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        return yaml.load(stream)


def save_yaml(path: Path, data):
    """Write YAML atomically and validate it before replacing the real file."""
    temporary = path.with_suffix(path.suffix + ".tmp")

    try:
        with temporary.open("w", encoding="utf-8") as stream:
            yaml.dump(data, stream)

        # Validate the generated YAML before touching the working theme.
        with temporary.open("r", encoding="utf-8") as stream:
            yaml.load(stream)

        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)


def refresh_simulated_theme():
    config.load_theme()
    display.initialize_display()

    # Editor-only preview base for video themes. This does not add a full-screen
    # static image to the real theme, so it will not cover the native video.
    video_config = config.THEME_DATA.get("video", {})
    preview_background = video_config.get("PREVIEW_BACKGROUND", "background.png")
    preview_background_path = Path(config.THEME_DATA["PATH"]) / preview_background

    if preview_background_path.is_file():
        try:
            background = Image.open(preview_background_path).convert("RGB")
            background = background.resize(
                (display.lcd.get_width(), display.lcd.get_height()),
                Image.Resampling.LANCZOS,
            )
            display.lcd.screen_image = background
        except Exception as exc:
            logger.warning("Could not load preview background: %s", exc)

    display.display_static_images()
    display.display_static_text()

    import library.stats as stats

    stats_map = [
        (("STATS", "CPU", "PERCENTAGE"), stats.CPU.percentage),
        (("STATS", "CPU", "FREQUENCY"), stats.CPU.frequency),
        (("STATS", "CPU", "LOAD"), stats.CPU.load),
        (("STATS", "CPU", "TEMPERATURE"), stats.CPU.temperature),
        (("STATS", "CPU", "FAN_SPEED"), stats.CPU.fan_speed),
        (("STATS", "GPU"), stats.Gpu.stats),
        (("STATS", "MEMORY"), stats.Memory.stats),
        (("STATS", "DISK"), stats.Disk.stats),
        (("STATS", "NET"), stats.Net.stats),
        (("STATS", "DATE"), stats.Date.stats),
        (("STATS", "UPTIME"), stats.SystemUptime.stats),
        (("STATS", "CUSTOM"), stats.Custom.stats),
        (("STATS", "WEATHER"), stats.Weather.stats),
        (("STATS", "PING"), stats.Ping.stats),
    ]

    for path, callback in stats_map:
        node = config.THEME_DATA
        try:
            for part in path:
                node = node[part]
            if isinstance(node, dict) and node.get("INTERVAL", 0) > 0:
                callback()
        except Exception:
            pass

    display.lcd.screen_image.save(PREVIEW_FILE, "PNG")
    return display.lcd.screen_image.copy()


class ThemeEditorApp:
    def __init__(self):
        locale.setlocale(locale.LC_ALL, "")
        self.root = tk.Tk()
        self.root.title(f"Turing Theme Editor — {THEME_NAME}")
        self.root.geometry("1280x760")
        self.root.minsize(1080, 680)

        icon = MAIN_DIRECTORY / "res/icons/monitor-icon-17865/64.png"
        if icon.is_file():
            self.root.iconphoto(True, tk.PhotoImage(file=str(icon)))

        self.theme_data = load_yaml(THEME_FILE)
        self.session_original = copy.deepcopy(self.theme_data)
        self.undo_stack = []
        self.redo_stack = []

        if not BACKUP_FILE.exists():
            shutil.copy2(THEME_FILE, BACKUP_FILE)

        self.selected_path = None
        self.preview_image_tk = None
        self.preview_scale = 1.0
        self.drag_origin = None
        self.drag_element_origin = None
        self.field_vars = {}
        self._refresh_job = None
        self._building_fields = False

        self.build_ui()
        self.populate_tree()
        self.refresh_preview()
        self.bind_shortcuts()

    def build_ui(self):
        toolbar = ttk.Frame(self.root, padding=8)
        toolbar.pack(fill="x")

        ttk.Button(toolbar, text="↶ Undo", command=self.undo).pack(side="left", padx=3)
        ttk.Button(toolbar, text="↷ Redo", command=self.redo).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Restore session", command=self.restore_session).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Save", command=self.save_current).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Save as copy", command=self.save_as_copy).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Apply to display", command=self.apply_to_display).pack(side="left", padx=12)
        ttk.Button(toolbar, text="Open YAML", command=self.open_yaml).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Video background", command=self.open_video_background_dialog).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Refresh preview", command=self.refresh_preview).pack(side="left", padx=3)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(toolbar, textvariable=self.status_var).pack(side="right", padx=8)

        body = ttk.Panedwindow(self.root, orient="horizontal")
        body.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        left = ttk.Frame(body, padding=6)
        center = ttk.Frame(body, padding=6)
        right = ttk.Frame(body, padding=6)
        body.add(left, weight=1)
        body.add(center, weight=3)
        body.add(right, weight=2)

        ttk.Label(left, text="Theme elements", font="bold").pack(anchor="w")

        component_actions = ttk.Frame(left)
        component_actions.pack(fill="x", pady=(6, 2))
        ttk.Button(component_actions, text="+ Add", command=self.add_component).pack(side="left", padx=(0, 3))
        ttk.Button(component_actions, text="⧉ Duplicate", command=self.duplicate_selected).pack(side="left", padx=3)
        ttk.Button(component_actions, text="Disable", command=self.disable_selected).pack(side="left", padx=3)
        ttk.Button(component_actions, text="Delete", command=self.delete_selected).pack(side="left", padx=3)

        self.tree = ttk.Treeview(left, show="tree")
        tree_scroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side="left", fill="both", expand=True, pady=(6, 0))
        tree_scroll.pack(side="right", fill="y", pady=(6, 0))
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        ttk.Label(center, text="Live preview", font="bold").pack(anchor="w")
        preview_wrap = ttk.Frame(center)
        preview_wrap.pack(fill="both", expand=True, pady=(6, 0))

        self.canvas = tk.Canvas(preview_wrap, background="#202020", highlightthickness=0)
        xscroll = ttk.Scrollbar(preview_wrap, orient="horizontal", command=self.canvas.xview)
        yscroll = ttk.Scrollbar(preview_wrap, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=xscroll.set, yscrollcommand=yscroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        preview_wrap.rowconfigure(0, weight=1)
        preview_wrap.columnconfigure(0, weight=1)

        self.canvas.bind("<ButtonPress-1>", self.on_preview_press)
        self.canvas.bind("<B1-Motion>", self.on_preview_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_preview_release)

        zoom_bar = ttk.Frame(center)
        zoom_bar.pack(fill="x", pady=6)
        ttk.Button(zoom_bar, text="Zoom −", command=lambda: self.change_zoom(-0.1)).pack(side="left")
        ttk.Button(zoom_bar, text="Zoom +", command=lambda: self.change_zoom(0.1)).pack(side="left", padx=5)
        ttk.Label(
            zoom_bar,
            text="Tip: select an element with X/Y, then drag it on the preview."
        ).pack(side="left", padx=12)

        ttk.Label(right, text="Properties", font="bold").pack(anchor="w")
        self.properties_container = ttk.Frame(right)
        self.properties_container.pack(fill="both", expand=True, pady=(6, 0))

        self.fields_frame = ttk.Frame(self.properties_container)
        self.fields_frame.pack(fill="x")

        action_frame = ttk.Frame(right)
        action_frame.pack(fill="x", pady=8)
        ttk.Button(action_frame, text="Apply property changes", command=self.apply_fields).pack(fill="x")
        ttk.Button(action_frame, text="Enable selected component", command=self.enable_selected).pack(fill="x", pady=(5, 0))
        ttk.Button(action_frame, text="Disable selected component", command=self.disable_selected).pack(fill="x", pady=5)
        ttk.Button(action_frame, text="Reset selected element", command=self.reset_selected).pack(fill="x")

    def bind_shortcuts(self):
        self.root.bind_all("<Control-z>", lambda _e: self.undo())
        self.root.bind_all("<Control-y>", lambda _e: self.redo())
        self.root.bind_all("<Control-s>", lambda _e: self.save_current())

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

    def original_node_at_path(self, path):
        node = self.session_original
        for part in path:
            node = node[part]
        return node

    def display_name(self, path):
        if not path:
            return "Theme"
        return " / ".join(str(part) for part in path)

    def populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.path_by_item = {}

        groups = {}
        for path, _node in self.iter_editable_nodes():
            parent = ""
            partial = ()
            for part in path:
                partial += (part,)
                if partial not in groups:
                    item = self.tree.insert(parent, "end", text=str(part), open=len(partial) <= 2)
                    groups[partial] = item
                parent = groups[partial]
            if path:
                self.path_by_item[parent] = path

    def on_tree_select(self, _event=None):
        selected = self.tree.selection()
        if not selected:
            return
        item = selected[0]
        path = self.path_by_item.get(item)
        if path is None:
            return
        self.selected_path = path
        self.build_property_fields()

    def build_property_fields(self):
        for child in self.fields_frame.winfo_children():
            child.destroy()
        self.field_vars.clear()

        if self.selected_path is None:
            return

        node = self.node_at_path(self.selected_path)
        ttk.Label(
            self.fields_frame,
            text=self.display_name(self.selected_path),
            wraplength=300
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        row = 1
        self._building_fields = True
        for key in EDITABLE_KEYS:
            if key not in node:
                continue

            ttk.Label(self.fields_frame, text=key).grid(
                row=row, column=0, sticky="w", padx=(0, 8), pady=3
            )

            value = node[key]
            if key in BOOLEAN_KEYS:
                var = tk.BooleanVar(value=bool(value))
                widget = ttk.Checkbutton(self.fields_frame, variable=var)
            else:
                var = tk.StringVar(value=self.value_to_text(value))
                widget = ttk.Entry(self.fields_frame, textvariable=var)

            widget.grid(row=row, column=1, sticky="ew", pady=3)
            self.field_vars[key] = var
            row += 1

        self.fields_frame.columnconfigure(1, weight=1)
        self._building_fields = False

    @staticmethod
    def value_to_text(value):
        if isinstance(value, (list, tuple)):
            return ", ".join(str(item) for item in value)
        return str(value)

    def parse_value(self, key, text, old_value):
        if key in NUMERIC_KEYS:
            return int(float(text))
        if key in BOOLEAN_KEYS:
            return bool(text)
        if isinstance(old_value, (list, tuple)):
            parts = [part.strip() for part in str(text).split(",")]
            values = [int(part) for part in parts]
            return values
        return text

    def push_undo(self):
        self.undo_stack.append(copy.deepcopy(self.theme_data))
        if len(self.undo_stack) > 100:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def apply_fields(self):
        if self.selected_path is None:
            return

        node = self.node_at_path(self.selected_path)
        changed = False
        updated = {}

        try:
            for key, var in self.field_vars.items():
                old = node[key]
                raw = var.get()
                new = self.parse_value(key, raw, old)
                updated[key] = new
                if new != old:
                    changed = True
        except Exception as exc:
            messagebox.showerror("Invalid value", str(exc))
            return

        if not changed:
            return

        self.push_undo()
        for key, value in updated.items():
            node[key] = value

        self.write_and_refresh("Properties updated")


    def path_exists(self, path):
        try:
            self.node_at_path(path)
            return True
        except Exception:
            return False

    def first_existing_path(self, candidates):
        for path in candidates:
            if self.path_exists(path):
                return path
        return None

    @staticmethod
    def recursively_set_enabled(node, enabled):
        changed = False

        if isinstance(node, dict):
            if "SHOW" in node and node["SHOW"] != enabled:
                node["SHOW"] = enabled
                changed = True

            if "INTERVAL" in node:
                new_value = max(1, int(node.get("INTERVAL", 0) or 0)) if enabled else 0
                if node["INTERVAL"] != new_value:
                    node["INTERVAL"] = new_value
                    changed = True

            for value in node.values():
                if isinstance(value, (dict, list)):
                    changed = ThemeEditorApp.recursively_set_enabled(value, enabled) or changed

        elif isinstance(node, list):
            for value in node:
                if isinstance(value, (dict, list)):
                    changed = ThemeEditorApp.recursively_set_enabled(value, enabled) or changed

        return changed

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
                    ThemeEditorApp.offset_coordinates(value, amount)
        elif isinstance(node, list):
            for value in node:
                if isinstance(value, (dict, list)):
                    ThemeEditorApp.offset_coordinates(value, amount)

    @staticmethod
    def unique_mapping_key(mapping, base):
        candidate = base
        counter = 2
        while candidate in mapping:
            candidate = f"{base}_{counter}"
            counter += 1
        return candidate

    def select_path(self, target_path):
        for item, path in self.path_by_item.items():
            if path == target_path:
                self.tree.selection_set(item)
                self.tree.focus(item)
                self.tree.see(item)
                self.selected_path = path
                self.build_property_fields()
                return

    def add_component(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add component")
        dialog.geometry("390x430")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Choose a component", font="bold").pack(anchor="w", padx=12, pady=(12, 6))

        listbox = tk.Listbox(dialog, exportselection=False)
        for label in COMPONENT_PRESETS:
            listbox.insert(tk.END, label)
        listbox.pack(fill="both", expand=True, padx=12, pady=6)
        listbox.selection_set(0)

        def confirm():
            selection = listbox.curselection()
            if not selection:
                return

            label = listbox.get(selection[0])
            dialog.destroy()

            if label == "Custom text":
                self.add_custom_text()
                return
            if label == "Static image":
                self.add_static_image()
                return

            candidates = COMPONENT_PRESETS[label]
            path = self.first_existing_path(candidates)
            if path is None:
                messagebox.showwarning(
                    "Add component",
                    f"The current theme does not contain a compatible block for “{label}”.\n\n"
                    "This first editor version can enable existing sensor blocks, but it does not "
                    "invent a complete sensor schema when the theme has none."
                )
                return

            self.push_undo()
            node = self.node_at_path(path)
            changed = self.recursively_set_enabled(node, True)

            if isinstance(node, dict) and "INTERVAL" not in node:
                node["INTERVAL"] = 1
                changed = True

            self.populate_tree()
            self.select_path(path)
            self.write_and_refresh(f"Enabled component: {label}")

        button_bar = ttk.Frame(dialog)
        button_bar.pack(fill="x", padx=12, pady=12)
        ttk.Button(button_bar, text="Cancel", command=dialog.destroy).pack(side="right")
        ttk.Button(button_bar, text="Add", command=confirm).pack(side="right", padx=6)
        listbox.bind("<Double-Button-1>", lambda _event: confirm())

    def add_custom_text(self):
        self.push_undo()

        container = self.theme_data.setdefault("static_text", {})
        key = self.unique_mapping_key(container, "custom_text")
        container[key] = {
            "TEXT": "New text",
            "X": 120,
            "Y": 120,
            "WIDTH": 240,
            "HEIGHT": 50,
            "FONT": "roboto-mono/RobotoMono-Regular.ttf",
            "FONT_SIZE": 24,
            "FONT_COLOR": [255, 255, 255],
            "BACKGROUND_COLOR": [0, 0, 0, 0],
            "ALIGN": "center",
            "ANCHOR": "mm",
        }

        path = ("static_text", key)
        self.populate_tree()
        self.select_path(path)
        self.write_and_refresh("Custom text added")

    def add_static_image(self):
        filename = filedialog.askopenfilename(
            parent=self.root,
            title="Choose an image",
            filetypes=(
                ("Image files", "*.png *.jpg *.jpeg *.webp *.bmp"),
                ("All files", "*.*"),
            )
        )
        if not filename:
            return

        source = Path(filename)
        destination_name = source.name
        destination = THEME_DIR / destination_name

        if destination.exists() and source.resolve() != destination.resolve():
            destination_name = self.unique_mapping_key(
                {path.name: True for path in THEME_DIR.iterdir()},
                source.stem
            ) + source.suffix
            destination = THEME_DIR / destination_name

        try:
            if source.resolve() != destination.resolve():
                shutil.copy2(source, destination)
        except Exception as exc:
            messagebox.showerror("Add image", str(exc))
            return

        self.push_undo()

        container = self.theme_data.setdefault("static_images", {})
        key = self.unique_mapping_key(container, "custom_image")
        container[key] = {
            "PATH": destination_name,
            "X": 120,
            "Y": 120,
            "WIDTH": 120,
            "HEIGHT": 120,
        }

        path = ("static_images", key)
        self.populate_tree()
        self.select_path(path)
        self.write_and_refresh("Static image added")

    def duplicate_selected(self):
        if self.selected_path is None:
            messagebox.showwarning("Duplicate", "Select an element first.")
            return

        if not self.selected_path or self.selected_path[0] not in ("static_text", "static_images"):
            messagebox.showwarning(
                "Duplicate",
                "In this first version, only custom/static text and image elements can be duplicated.\n\n"
                "Sensor blocks have fixed names used by the scheduler, so duplicating them would not "
                "create a second working sensor."
            )
            return

        parent = self.theme_data
        for part in self.selected_path[:-1]:
            parent = parent[part]

        key = self.selected_path[-1]
        if not isinstance(parent, dict):
            messagebox.showwarning("Duplicate", "This element cannot be duplicated safely.")
            return

        self.push_undo()

        new_key = self.unique_mapping_key(parent, f"{key}_copy")
        parent[new_key] = copy.deepcopy(parent[key])
        self.offset_coordinates(parent[new_key], 10)

        new_path = self.selected_path[:-1] + (new_key,)
        self.populate_tree()
        self.select_path(new_path)
        self.write_and_refresh("Element duplicated")

    def enable_selected(self):
        if self.selected_path is None:
            messagebox.showwarning("Enable", "Select a component first.")
            return

        self.push_undo()
        node = self.node_at_path(self.selected_path)
        changed = self.recursively_set_enabled(node, True)

        if isinstance(node, dict) and "INTERVAL" not in node and self.selected_path[:1] == ("STATS",):
            node["INTERVAL"] = 1
            changed = True

        if not changed:
            self.undo_stack.pop()
            self.status_var.set("Selected component is already enabled")
            return

        self.build_property_fields()
        self.write_and_refresh("Component enabled")

    def disable_selected(self):
        if self.selected_path is None:
            messagebox.showwarning("Disable", "Select a component first.")
            return

        if self.selected_path[0] in ("static_text", "static_images"):
            messagebox.showinfo(
                "Disable",
                "Static text and image entries do not have a universal enable flag.\n"
                "Use Delete to remove them, or Undo to bring them back."
            )
            return

        self.push_undo()
        node = self.node_at_path(self.selected_path)
        changed = self.recursively_set_enabled(node, False)

        if isinstance(node, dict) and "INTERVAL" not in node:
            node["INTERVAL"] = 0
            changed = True

        if not changed:
            self.undo_stack.pop()
            self.status_var.set("Selected component is already disabled")
            return

        self.build_property_fields()
        self.write_and_refresh("Component disabled")

    def delete_selected(self):
        if self.selected_path is None:
            messagebox.showwarning("Delete", "Select an element first.")
            return

        if self.selected_path[0] not in ("static_text", "static_images"):
            messagebox.showinfo(
                "Delete",
                "Sensor sections are not deleted because the project may expect their YAML keys to exist.\n\n"
                "The selected sensor will be disabled instead."
            )
            self.disable_selected()
            return

        if not messagebox.askyesno(
            "Delete element",
            f"Delete this theme element?\n\n{self.display_name(self.selected_path)}"
        ):
            return

        parent = self.theme_data
        for part in self.selected_path[:-1]:
            parent = parent[part]

        self.push_undo()
        deleted_key = self.selected_path[-1]
        del parent[deleted_key]

        # Never leave an empty top-level static_images/static_text mapping.
        # Some round-trip YAML layouts can serialize an empty mapping as:
        #
        # static_images:
        # {}
        #
        # which is invalid YAML because the empty mapping loses indentation.
        if (
            isinstance(parent, dict)
            and not parent
            and len(self.selected_path) == 2
            and self.selected_path[0] in ("static_text", "static_images")
        ):
            self.theme_data.pop(self.selected_path[0], None)

        self.selected_path = None
        self.populate_tree()
        self.build_property_fields()
        self.write_and_refresh("Element deleted")

    def reset_selected(self):
        if self.selected_path is None:
            return

        try:
            original = copy.deepcopy(self.original_node_at_path(self.selected_path))
        except Exception:
            messagebox.showerror("Reset", "The selected element did not exist when the editor opened.")
            return

        self.push_undo()

        parent = self.theme_data
        for part in self.selected_path[:-1]:
            parent = parent[part]
        parent[self.selected_path[-1]] = original

        self.build_property_fields()
        self.write_and_refresh("Selected element restored")

    def undo(self):
        if not self.undo_stack:
            self.status_var.set("Nothing to undo")
            return
        self.redo_stack.append(copy.deepcopy(self.theme_data))
        self.theme_data = self.undo_stack.pop()
        self.populate_tree()
        self.selected_path = None
        self.build_property_fields()
        self.write_and_refresh("Undo")

    def redo(self):
        if not self.redo_stack:
            self.status_var.set("Nothing to redo")
            return
        self.undo_stack.append(copy.deepcopy(self.theme_data))
        self.theme_data = self.redo_stack.pop()
        self.populate_tree()
        self.selected_path = None
        self.build_property_fields()
        self.write_and_refresh("Redo")

    def restore_session(self):
        if not messagebox.askyesno(
            "Restore session",
            "Discard every change made since this editor was opened?"
        ):
            return

        self.push_undo()
        self.theme_data = copy.deepcopy(self.session_original)
        self.populate_tree()
        self.selected_path = None
        self.build_property_fields()
        self.write_and_refresh("Session restored")

    def save_current(self):
        save_yaml(THEME_FILE, self.theme_data)
        self.status_var.set("Theme saved")
        messagebox.showinfo("Theme editor", f"Saved:\n{THEME_FILE}")

    def save_as_copy(self):
        name = simpledialog.askstring(
            "Save as copy",
            "New theme folder name:",
            initialvalue=f"{THEME_NAME}_custom",
            parent=self.root
        )
        if not name:
            return

        if any(char in name for char in ("/", "\\", "..")):
            messagebox.showerror("Save as copy", "Invalid folder name.")
            return

        destination = MAIN_DIRECTORY / "res" / "themes" / name
        if destination.exists():
            messagebox.showerror("Save as copy", "That theme folder already exists.")
            return

        shutil.copytree(THEME_DIR, destination)
        save_yaml(destination / "theme.yaml", self.theme_data)
        messagebox.showinfo("Save as copy", f"Theme copy created:\n{destination}")


    @staticmethod
    def is_text_render_node(node):
        if not isinstance(node, dict):
            return False

        has_geometry = all(key in node for key in ("X", "Y", "WIDTH", "HEIGHT"))
        has_text_style = any(
            key in node
            for key in ("FONT", "FONT_SIZE", "FONT_COLOR", "TEXT", "ALIGN", "ANCHOR")
        )
        return has_geometry and has_text_style

    @classmethod
    def apply_background_to_text_nodes(cls, node, filename):
        changed = 0

        if isinstance(node, dict):
            if cls.is_text_render_node(node):
                if node.get("BACKGROUND_IMAGE") != filename:
                    node["BACKGROUND_IMAGE"] = filename
                    changed += 1

                # Avoid the renderer falling back to an opaque white box.
                # Keep this value for compatibility, but the background image
                # is the source actually used for the text region.
                if "BACKGROUND_COLOR" not in node:
                    node["BACKGROUND_COLOR"] = [0, 0, 0, 0]

            for value in node.values():
                if isinstance(value, (dict, list)):
                    changed += cls.apply_background_to_text_nodes(value, filename)

        elif isinstance(node, list):
            for value in node:
                if isinstance(value, (dict, list)):
                    changed += cls.apply_background_to_text_nodes(value, filename)

        return changed

    def open_video_background_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Generate background from video")
        dialog.geometry("620x500")
        dialog.minsize(620, 500)
        dialog.transient(self.root)
        dialog.grab_set()

        video_path = tk.StringVar()
        timestamp = tk.StringVar(value="1.0")
        output_name = tk.StringVar(value="background.png")
        apply_to_all = tk.BooleanVar(value=True)

        ttk.Label(
            dialog,
            text="Extract one full-screen frame and use it as the shared BACKGROUND_IMAGE.",
            font="bold",
            wraplength=570,
        ).pack(anchor="w", padx=16, pady=(16, 8))

        ttk.Label(
            dialog,
            text=(
                "The generated image is used by the editor as the preview base and by "
                "text/sensor elements as a shared background. It is not added as a "
                "full-screen static image, so it will not cover the native video."
            ),
            wraplength=570,
        ).pack(anchor="w", padx=16, pady=(0, 14))

        form = ttk.Frame(dialog)
        form.pack(fill="x", padx=16)

        ttk.Label(form, text="Local video").grid(row=0, column=0, sticky="w", pady=5)
        video_entry = ttk.Entry(form, textvariable=video_path)
        video_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=5)

        def browse_video():
            selected = filedialog.askopenfilename(
                parent=dialog,
                title="Select the local copy of the theme video",
                filetypes=(
                    ("Video files", "*.mp4 *.mov *.mkv *.avi *.webm"),
                    ("All files", "*.*"),
                ),
            )
            if selected:
                video_path.set(selected)

        ttk.Button(form, text="Browse…", command=browse_video).grid(
            row=0, column=2, pady=5
        )

        ttk.Label(form, text="Frame time (seconds)").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(form, textvariable=timestamp, width=16).grid(
            row=1, column=1, sticky="w", padx=8, pady=5
        )

        ttk.Label(form, text="Output file").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(form, textvariable=output_name, width=30).grid(
            row=2, column=1, sticky="w", padx=8, pady=5
        )

        ttk.Checkbutton(
            form,
            text="Apply BACKGROUND_IMAGE to all text and sensor value elements",
            variable=apply_to_all,
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(12, 5))

        form.columnconfigure(1, weight=1)

        status = tk.StringVar(value="")
        ttk.Label(dialog, textvariable=status, wraplength=570).pack(
            anchor="w", padx=16, pady=12
        )

        def generate():
            source = Path(video_path.get()).expanduser()
            if not source.is_file():
                messagebox.showerror("Video background", "Select a valid local video file.")
                return

            try:
                seconds = float(timestamp.get())
                if seconds < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror(
                    "Video background",
                    "Frame time must be a non-negative number."
                )
                return

            filename = output_name.get().strip()
            if not filename:
                filename = "background.png"
            if "/" in filename or "\\" in filename:
                messagebox.showerror(
                    "Video background",
                    "Output file must be a filename only."
                )
                return
            if not filename.lower().endswith(".png"):
                filename += ".png"

            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                messagebox.showerror(
                    "Video background",
                    "ffmpeg is required but was not found in PATH."
                )
                return

            destination = THEME_DIR / filename
            temporary = destination.with_suffix(".tmp.png")
            status.set("Extracting video frame…")
            dialog.update_idletasks()

            command = [
                ffmpeg,
                "-y",
                "-ss", str(seconds),
                "-i", str(source),
                "-frames:v", "1",
                "-vf",
                (
                    f"scale={display.lcd.get_width()}:{display.lcd.get_height()}:"
                    "force_original_aspect_ratio=increase,"
                    f"crop={display.lcd.get_width()}:{display.lcd.get_height()}"
                ),
                str(temporary),
            ]

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0 or not temporary.is_file():
                temporary.unlink(missing_ok=True)
                messagebox.showerror(
                    "Video background",
                    result.stderr.strip() or "ffmpeg could not extract the frame."
                )
                status.set("Failed")
                return

            try:
                # Normalize image mode and dimensions before replacing the real file.
                frame = Image.open(temporary).convert("RGB")
                frame = frame.resize(
                    (display.lcd.get_width(), display.lcd.get_height()),
                    Image.Resampling.LANCZOS,
                )
                frame.save(destination, "PNG")
            finally:
                temporary.unlink(missing_ok=True)

            self.push_undo()

            video_config = self.theme_data.setdefault("video", {})
            video_config["LOCAL_PATH"] = source.name
            video_config["PREVIEW_BACKGROUND"] = filename
            video_config["BACKGROUND_FRAME_TIME"] = seconds

            changed = 0
            if apply_to_all.get():
                changed = self.apply_background_to_text_nodes(
                    self.theme_data,
                    filename,
                )

            save_yaml(THEME_FILE, self.theme_data)
            self.populate_tree()
            self.refresh_preview()

            status.set(
                f"Generated {filename}; updated {changed} text/sensor element(s)."
            )
            messagebox.showinfo(
                "Video background",
                (
                    f"Generated:\n{destination}\n\n"
                    f"BACKGROUND_IMAGE applied to {changed} element(s)."
                ),
            )

        buttons = ttk.Frame(dialog)
        buttons.pack(side="bottom", fill="x", padx=16, pady=16)

        generate_btn = ttk.Button(
            buttons,
            text="Generate background",
            command=generate,
        )
        generate_btn.pack(side="right", padx=(8, 0), ipadx=10, ipady=6)

        close_btn = ttk.Button(
            buttons,
            text="Close",
            command=dialog.destroy,
        )
        close_btn.pack(side="right", ipadx=10, ipady=6)

        # Make Enter activate generation and Escape close the dialog.
        dialog.bind("<Return>", lambda _event: generate())
        dialog.bind("<Escape>", lambda _event: dialog.destroy())

    def open_yaml(self):
        if sys.platform == "win32":
            os.startfile(THEME_FILE)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(THEME_FILE)])
        else:
            subprocess.Popen(["xdg-open", str(THEME_FILE)])

    def apply_to_display(self):
        save_yaml(THEME_FILE, self.theme_data)

        if not messagebox.askyesno(
            "Apply to display",
            "This will stop the current main.py process and start it again with the edited theme.\n\nContinue?"
        ):
            return

        try:
            subprocess.run(
                ["pkill", "-f", "python3 main.py"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(2)
            subprocess.Popen([sys.executable, str(MAIN_DIRECTORY / "main.py")])
            self.status_var.set("Applied to display")
        except Exception as exc:
            messagebox.showerror("Apply to display", str(exc))

    def write_and_refresh(self, status):
        save_yaml(THEME_FILE, self.theme_data)
        self.status_var.set(status)
        self.schedule_preview_refresh()

    def schedule_preview_refresh(self):
        if self._refresh_job is not None:
            self.root.after_cancel(self._refresh_job)
        self._refresh_job = self.root.after(180, self.refresh_preview)

    def refresh_preview(self):
        self._refresh_job = None
        try:
            screen = refresh_simulated_theme()
            theme_data = load_yaml(THEME_FILE)

            if theme_data.get("display", {}).get("DISPLAY_SIZE") == '2.1"':
                mask_path = MAIN_DIRECTORY / "res/backgrounds/circular-mask.png"
                if mask_path.is_file():
                    mask = Image.open(mask_path).convert("RGBA")
                    screen = screen.convert("RGBA")
                    screen.alpha_composite(mask)

            width = max(1, int(screen.width * self.preview_scale))
            height = max(1, int(screen.height * self.preview_scale))
            resized = screen.resize((width, height), Image.Resampling.LANCZOS)

            self.preview_image_tk = ImageTk.PhotoImage(resized)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, image=self.preview_image_tk, anchor="nw", tags="preview")
            self.canvas.configure(scrollregion=(0, 0, width, height))
            self.draw_selected_outline()
            self.status_var.set("Preview updated")
        except Exception as exc:
            self.status_var.set("Preview error")
            self.canvas.delete("all")
            self.canvas.create_text(
                20, 20,
                text=f"Error rendering theme:\n{exc}",
                fill="white",
                anchor="nw",
                width=500
            )

    def draw_selected_outline(self):
        if self.selected_path is None:
            return
        try:
            node = self.node_at_path(self.selected_path)
            x = int(node["X"]) * self.preview_scale
            y = int(node["Y"]) * self.preview_scale
            width = int(node.get("WIDTH", 40)) * self.preview_scale
            height = int(node.get("HEIGHT", 20)) * self.preview_scale
        except Exception:
            return

        self.canvas.create_rectangle(
            x, y, x + width, y + height,
            outline="#ffcc00",
            width=2,
            dash=(5, 3),
            tags="selection"
        )

    def change_zoom(self, delta):
        self.preview_scale = min(2.0, max(0.3, self.preview_scale + delta))
        self.refresh_preview()

    def on_preview_press(self, event):
        if self.selected_path is None:
            return
        try:
            node = self.node_at_path(self.selected_path)
            x = int(node["X"])
            y = int(node["Y"])
        except Exception:
            return

        self.drag_origin = (
            self.canvas.canvasx(event.x),
            self.canvas.canvasy(event.y)
        )
        self.drag_element_origin = (x, y)

    def on_preview_drag(self, event):
        if self.drag_origin is None or self.drag_element_origin is None:
            return

        current_x = self.canvas.canvasx(event.x)
        current_y = self.canvas.canvasy(event.y)
        dx = (current_x - self.drag_origin[0]) / self.preview_scale
        dy = (current_y - self.drag_origin[1]) / self.preview_scale

        node = self.node_at_path(self.selected_path)
        node["X"] = int(round(self.drag_element_origin[0] + dx))
        node["Y"] = int(round(self.drag_element_origin[1] + dy))

        self.canvas.delete("selection")
        self.draw_selected_outline()

    def on_preview_release(self, _event):
        if self.drag_origin is None:
            return

        node = self.node_at_path(self.selected_path)
        new_position = (node.get("X"), node.get("Y"))

        if new_position != self.drag_element_origin:
            # Rebuild the undo snapshot with the original coordinates.
            snapshot = copy.deepcopy(self.theme_data)
            snapshot_node = snapshot
            for part in self.selected_path:
                snapshot_node = snapshot_node[part]
            snapshot_node["X"], snapshot_node["Y"] = self.drag_element_origin
            self.undo_stack.append(snapshot)
            self.redo_stack.clear()

            self.build_property_fields()
            self.write_and_refresh("Element moved")

        self.drag_origin = None
        self.drag_element_origin = None

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    def on_close(self):
        if self.theme_data != self.session_original:
            choice = messagebox.askyesnocancel(
                "Close editor",
                "Save the current theme before closing?\n\n"
                "Yes: save and close\n"
                "No: restore the theme from when this session opened\n"
                "Cancel: keep editing"
            )
            if choice is None:
                return
            if choice:
                save_yaml(THEME_FILE, self.theme_data)
            else:
                save_yaml(THEME_FILE, self.session_original)

        self.root.destroy()


if __name__ == "__main__":
    ThemeEditorApp().run()
