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

yaml = ruamel.yaml.YAML()
yaml.preserve_quotes = True


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        return yaml.load(stream)


def save_yaml(path: Path, data):
    with path.open("w", encoding="utf-8") as stream:
        yaml.dump(data, stream)


def refresh_simulated_theme():
    config.load_theme()
    display.initialize_display()
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
        ttk.Button(action_frame, text="Reset selected element", command=self.reset_selected).pack(fill="x", pady=5)

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
