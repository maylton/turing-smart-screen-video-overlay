# SPDX-License-Identifier: GPL-3.0-or-later
"""Make direct preview selection immediately draggable.

The first preview interaction patch selected the element under the cursor, but
then delegated to the original drag-begin handler. In some GTK selection timing
paths that handler still saw no movable selected node. This patch owns the drag
lifecycle for preview-selected elements so the same click that selects an item
can also move it.
"""

from __future__ import annotations

import threading
from typing import Any

from library.theme_editor_preview_interaction_patch import (
    _canvas_dimensions,
    _hit_test_preview,
    _select_path_from_preview,
)


_INSTALLED = False
_PATCH_ATTEMPTS = 0
_MAX_PATCH_ATTEMPTS = 100


def _node_for_path(editor: Any, path: tuple[Any, ...] | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        node = editor.node_at_path(path)
    except Exception:
        return None
    if not isinstance(node, dict):
        return None
    if "X" not in node or "Y" not in node:
        return None
    return node


def _selected_movable_path(editor: Any) -> tuple[Any, ...] | None:
    selected_path = getattr(editor, "selected_path", None)
    if selected_path is None:
        return None
    path = tuple(selected_path)
    if _node_for_path(editor, path) is None:
        return None
    return path


def _set_property_text(editor: Any, key: str, value: Any) -> None:
    try:
        widget = editor.property_widgets.get(key)
    except Exception:
        widget = None
    if widget is not None and hasattr(widget, "set_text"):
        try:
            widget.set_text(str(value))
        except Exception:
            pass


def _patch_window(window_class: type) -> bool:
    if getattr(window_class, "_preview_direct_drag_fix_patch", False):
        return True

    def on_preview_drag_begin(self, _gesture, start_x, start_y):
        self.drag_start_pointer = None
        self.drag_start_element = None
        self.drag_dirty = False
        self.drag_history_pushed = False
        self.drag_target_path = None

        target_path = _hit_test_preview(self, start_x, start_y)
        if target_path is not None:
            self.selected_path = tuple(target_path)
            _select_path_from_preview(self, tuple(target_path))
        else:
            target_path = _selected_movable_path(self)

        node = _node_for_path(self, tuple(target_path) if target_path else None)
        if node is None:
            self.toast("Select an element with X and Y first")
            return

        self.selected_path = tuple(target_path)
        self.drag_target_path = tuple(target_path)
        self.drag_history_pushed = self.push_undo()
        self.drag_start_pointer = (start_x, start_y)
        self.drag_start_element = (int(node["X"]), int(node["Y"]))
        self.drag_dirty = False

        try:
            label = " / ".join(str(part) for part in self.drag_target_path)
            self.preview_status.set_label(f"Dragging: {label}")
        except Exception:
            pass

    def on_preview_drag_update(self, _gesture, offset_x, offset_y):
        target_path = getattr(self, "drag_target_path", None) or _selected_movable_path(self)
        node = _node_for_path(self, tuple(target_path) if target_path else None)
        if node is None or self.drag_start_element is None:
            return

        scale = self.preview_to_display_scale()
        new_x = round(self.drag_start_element[0] + offset_x * scale)
        new_y = round(self.drag_start_element[1] + offset_y * scale)
        canvas_width, canvas_height = _canvas_dimensions(self)

        node["X"] = max(0, min(canvas_width, new_x))
        node["Y"] = max(0, min(canvas_height, new_y))
        self.drag_dirty = True

        _set_property_text(self, "X", node["X"])
        _set_property_text(self, "Y", node["Y"])

        try:
            self.preview_status.set_label(
                f"Position: X={node['X']}, Y={node['Y']} — release to render"
            )
        except Exception:
            pass

    def on_preview_drag_end(self, _gesture, _offset_x, _offset_y):
        if self.drag_start_element is None:
            return

        self.drag_start_pointer = None
        self.drag_start_element = None
        self.drag_target_path = None

        if not self.drag_dirty:
            if getattr(self, "drag_history_pushed", False) and self.undo_stack:
                self.undo_stack.pop()
                self.update_history_buttons()
            self.drag_history_pushed = False
            return

        if not self.save_theme_data():
            return
        self.refresh_preview()
        self.drag_dirty = False
        self.drag_history_pushed = False
        self.update_history_buttons()

    window_class.on_preview_drag_begin = on_preview_drag_begin
    window_class.on_preview_drag_update = on_preview_drag_update
    window_class.on_preview_drag_end = on_preview_drag_end
    window_class._preview_direct_drag_fix_patch = True
    return True


def _patch_when_ready() -> None:
    global _PATCH_ATTEMPTS
    _PATCH_ATTEMPTS += 1

    try:
        main = __import__("__main__")
        window_class = getattr(main, "ThemeEditorWindow", None)
    except Exception:
        window_class = None

    if isinstance(window_class, type) and _patch_window(window_class):
        return

    if _PATCH_ATTEMPTS < _MAX_PATCH_ATTEMPTS:
        timer = threading.Timer(0.05, _patch_when_ready)
        timer.daemon = True
        timer.start()


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    _patch_when_ready()
