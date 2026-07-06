# SPDX-License-Identifier: GPL-3.0-or-later
"""Improve GTK Theme Editor live-preview interactions.

This patch keeps the preview geometry stable when status text changes and lets
users select draggable elements directly from the preview instead of selecting
those elements in the tree first.
"""

from __future__ import annotations

import threading
from typing import Any


_INSTALLED = False
_PATCH_ATTEMPTS = 0
_MAX_PATCH_ATTEMPTS = 100


def _main_module() -> Any | None:
    try:
        return __import__("__main__")
    except Exception:
        return None


def _canvas_dimensions(editor: Any) -> tuple[int, int]:
    main = _main_module()
    if main is not None:
        theme_canvas_dimensions = getattr(main, "theme_canvas_dimensions", None)
        if theme_canvas_dimensions is not None:
            try:
                width, height = theme_canvas_dimensions(editor.theme_data)
                return max(1, int(width)), max(1, int(height))
            except Exception:
                pass
    return 480, 480


def _preview_point_to_display(editor: Any, x: float, y: float) -> tuple[float, float] | None:
    picture = getattr(editor, "preview_picture", None)
    if picture is None:
        return None

    allocated_width = max(1, int(picture.get_allocated_width()))
    allocated_height = max(1, int(picture.get_allocated_height()))
    canvas_width, canvas_height = _canvas_dimensions(editor)

    scale = min(
        allocated_width / canvas_width,
        allocated_height / canvas_height,
    )
    if scale <= 0:
        return None

    rendered_width = canvas_width * scale
    rendered_height = canvas_height * scale
    offset_x = (allocated_width - rendered_width) / 2
    offset_y = (allocated_height - rendered_height) / 2

    display_x = (x - offset_x) / scale
    display_y = (y - offset_y) / scale
    if display_x < 0 or display_y < 0:
        return None
    if display_x > canvas_width or display_y > canvas_height:
        return None
    return display_x, display_y


def _anchor_factor(anchor: str) -> tuple[float, float]:
    anchor = str(anchor or "lt").lower()
    horizontal = anchor[0] if len(anchor) >= 1 else "l"
    vertical = anchor[1] if len(anchor) >= 2 else "t"

    x_factor = {"l": 0.0, "m": 0.5, "c": 0.5, "r": 1.0}.get(horizontal, 0.0)
    y_factor = {"t": 0.0, "m": 0.5, "c": 0.5, "b": 1.0}.get(vertical, 0.0)
    return x_factor, y_factor


def _node_bounds(node: dict[str, Any]) -> tuple[float, float, float, float] | None:
    if "X" not in node or "Y" not in node:
        return None

    try:
        x = float(node.get("X") or 0)
        y = float(node.get("Y") or 0)
    except (TypeError, ValueError):
        return None

    try:
        width = float(node.get("WIDTH") or node.get("RADIUS") or 24)
        height = float(node.get("HEIGHT") or node.get("RADIUS") or 24)
    except (TypeError, ValueError):
        width = height = 24

    width = max(8.0, width)
    height = max(8.0, height)

    x_factor, y_factor = _anchor_factor(str(node.get("ANCHOR", "lt") or "lt"))
    left = x - width * x_factor
    top = y - height * y_factor
    return left, top, width, height


def _is_preview_selectable(node: dict[str, Any]) -> bool:
    if not isinstance(node, dict):
        return False
    if "X" not in node or "Y" not in node:
        return False
    if node.get("SHOW") is False:
        return False
    if node.get("ENABLED") is False:
        return False
    return True


def _path_is_image(path: tuple[Any, ...], node: dict[str, Any]) -> bool:
    if path and path[0] == "static_images":
        return True
    if "PATH" in node and "FONT" not in node:
        return True
    if "BACKGROUND_IMAGE" in node and "FONT" not in node and "TEXT" not in node:
        return True
    return False


def _path_is_text_overlay(path: tuple[Any, ...], node: dict[str, Any]) -> bool:
    if path and path[0] == "static_text":
        return True
    if "FONT" in node or "TEXT" in node or "FORMAT" in node:
        return True
    return False


def _hit_test_priority(
    path: tuple[Any, ...],
    node: dict[str, Any],
    area: float,
    index: int,
) -> tuple[int, float, int, int]:
    """Sort candidates so overlays win over full-screen image backgrounds."""

    if _path_is_text_overlay(path, node):
        kind_priority = 0
    elif _path_is_image(path, node):
        kind_priority = 2
    else:
        kind_priority = 1

    # Smaller boxes are more likely to be intentional click targets. Full-screen
    # images still remain selectable when no overlay hits that point, but they
    # no longer steal drag selection from text/metric overlays.
    return (kind_priority, area, -len(path), -index)


def _hit_test_preview(editor: Any, preview_x: float, preview_y: float) -> tuple[Any, ...] | None:
    point = _preview_point_to_display(editor, preview_x, preview_y)
    if point is None:
        return None
    display_x, display_y = point

    candidates: list[tuple[tuple[int, float, int, int], tuple[Any, ...]]] = []
    try:
        nodes = list(editor.iter_editable_nodes())
    except Exception:
        return None

    for index, (path, node) in enumerate(nodes):
        path = tuple(path)
        if not _is_preview_selectable(node):
            continue
        bounds = _node_bounds(node)
        if bounds is None:
            continue
        left, top, width, height = bounds
        if left <= display_x <= left + width and top <= display_y <= top + height:
            area = width * height
            candidates.append((_hit_test_priority(path, node, area, index), path))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _select_path_from_preview(editor: Any, path: tuple[Any, ...]) -> None:
    editor.selected_path = tuple(path)
    try:
        editor.populate_elements()
    except Exception:
        pass
    try:
        editor.build_property_rows()
    except Exception:
        pass
    try:
        editor.update_actions_sensitivity()
    except Exception:
        pass

    main = _main_module()
    glib = getattr(main, "GLib", None) if main is not None else None
    if glib is not None:
        glib.idle_add(editor.restore_tree_selection, tuple(path))
    else:
        try:
            editor.restore_tree_selection(tuple(path))
        except Exception:
            pass


def _stabilize_status_label(label: Any) -> None:
    try:
        label.set_wrap(False)
    except Exception:
        pass
    try:
        label.set_lines(1)
    except Exception:
        pass
    try:
        label.set_ellipsize(3)
    except Exception:
        pass
    try:
        label.set_size_request(-1, 36)
    except Exception:
        pass
    try:
        label.set_tooltip_text("Live preview status")
    except Exception:
        pass


def _patch_window(window_class: type) -> bool:
    if getattr(window_class, "_preview_interaction_patch", False):
        return True

    build_preview_panel = getattr(window_class, "build_preview_panel", None)
    drag_begin = getattr(window_class, "on_preview_drag_begin", None)
    finish_preview = getattr(window_class, "finish_preview", None)
    if build_preview_panel is None or drag_begin is None or finish_preview is None:
        return False

    def build_preview_panel_patched(self):
        panel = build_preview_panel(self)
        status = getattr(self, "preview_status", None)
        if status is not None:
            _stabilize_status_label(status)
        return panel

    def on_preview_drag_begin_patched(self, gesture, start_x, start_y):
        target_path = _hit_test_preview(self, start_x, start_y)
        if target_path is not None:
            _select_path_from_preview(self, target_path)
            try:
                label = " / ".join(str(part) for part in target_path)
                self.preview_status.set_label(f"Selected: {label}")
            except Exception:
                pass
        return drag_begin(self, gesture, start_x, start_y)

    def finish_preview_patched(self, generation, returncode, stdout, stderr):
        result = finish_preview(self, generation, returncode, stdout, stderr)
        status = getattr(self, "preview_status", None)
        if status is not None:
            _stabilize_status_label(status)
            if returncode == 0 and generation == getattr(self, "preview_generation", None):
                try:
                    status.set_label("Preview updated")
                    status.set_tooltip_text(str(getattr(self, "preview_file", "")))
                except Exception:
                    pass
        return result

    window_class.build_preview_panel = build_preview_panel_patched
    window_class.on_preview_drag_begin = on_preview_drag_begin_patched
    window_class.finish_preview = finish_preview_patched
    window_class._preview_interaction_patch = True
    return True


def _patch_when_ready() -> None:
    global _PATCH_ATTEMPTS
    _PATCH_ATTEMPTS += 1

    main = _main_module()
    window_class = getattr(main, "ThemeEditorWindow", None) if main is not None else None
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
