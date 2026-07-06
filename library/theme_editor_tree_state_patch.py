# SPDX-License-Identifier: GPL-3.0-or-later
"""Preserve GTK Theme Editor tree expansion across property updates.

The editor rebuilds the tree after saves, presets, Undo/Redo, and preview
updates. Without preserving the expansion state, editing a nested component feels
like the hierarchy collapses after every action.
"""

from __future__ import annotations

import threading
from typing import Any


_INSTALLED = False
_PATCH_ATTEMPTS = 0
_MAX_PATCH_ATTEMPTS = 100


def _collect_expanded_paths(editor: Any) -> set[tuple[Any, ...]]:
    paths: set[tuple[Any, ...]] = set()
    try:
        model = editor.tree_model
    except Exception:
        return paths

    try:
        count = model.get_n_items()
    except Exception:
        return paths

    for index in range(count):
        try:
            row = model.get_item(index)
            if row is None or not row.get_expanded():
                continue
            item = row.get_item()
            if item is not None:
                paths.add(tuple(item.path))
        except Exception:
            continue
    return paths


def _is_selected_ancestor(path: tuple[Any, ...], selected_path: tuple[Any, ...] | None) -> bool:
    if not selected_path:
        return False
    return len(path) < len(selected_path) and selected_path[: len(path)] == path


def _restore_tree_state(
    editor: Any,
    expanded_paths: set[tuple[Any, ...]],
    selected_path: tuple[Any, ...] | None,
) -> bool:
    try:
        model = editor.tree_model
    except Exception:
        return False

    # Expanding a row may reveal more children, so run a few passes until the
    # desired expanded descendants and selected path are visible.
    for _round in range(8):
        changed = False
        try:
            count = model.get_n_items()
        except Exception:
            break

        for index in range(count):
            try:
                row = model.get_item(index)
                if row is None:
                    continue
                item = row.get_item()
                if item is None:
                    continue
                path = tuple(item.path)
                should_expand = path in expanded_paths or _is_selected_ancestor(
                    path,
                    selected_path,
                )
                if should_expand and row.is_expandable() and not row.get_expanded():
                    row.set_expanded(True)
                    changed = True
            except Exception:
                continue

        if not changed:
            break

    if selected_path is not None:
        try:
            editor.restore_tree_selection(selected_path)
        except Exception:
            pass
    return False


def _patch_window(window_class: type) -> bool:
    if getattr(window_class, "_tree_state_preserve_patch", False):
        return True

    original_populate_elements = getattr(window_class, "populate_elements", None)
    if original_populate_elements is None:
        return False

    def populate_elements(self, *args, **kwargs):
        expanded_paths = _collect_expanded_paths(self)
        selected_path = getattr(self, "selected_path", None)
        if selected_path is not None:
            selected_path = tuple(selected_path)

        result = original_populate_elements(self, *args, **kwargs)

        try:
            main = __import__("__main__")
            glib = getattr(main, "GLib", None)
            if glib is not None:
                glib.idle_add(_restore_tree_state, self, expanded_paths, selected_path)
            else:
                _restore_tree_state(self, expanded_paths, selected_path)
        except Exception:
            pass
        return result

    window_class.populate_elements = populate_elements
    window_class._tree_state_preserve_patch = True
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
