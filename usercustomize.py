# SPDX-License-Identifier: GPL-3.0-or-later
"""Targeted startup hooks for local GTK theme editor entry points.

Python imports ``usercustomize`` automatically during startup when this checkout
is on ``sys.path``. Keep this file narrowly scoped so normal project imports and
monitor runtime entry points are not affected.
"""

from __future__ import annotations

import sys
from pathlib import Path


_THEME_EDITOR_ENTRY_POINTS = {
    "theme-editor-gtk.py",
}


def _entry_point_name() -> str:
    return Path(sys.argv[0]).name


def _should_patch_theme_editor() -> bool:
    return _entry_point_name() in _THEME_EDITOR_ENTRY_POINTS


def _install_theme_editor_patches() -> None:
    if not _should_patch_theme_editor():
        return

    try:
        from library.weather_runtime_patch import install as install_weather_runtime_patch
        from library.weather_hidden_defaults import install as install_weather_hidden_defaults
        from library.theme_editor_tree_state_patch import install as install_tree_state_patch
        from library.theme_editor_preview_interaction_patch import install as install_preview_interaction_patch
        from library.theme_editor_preview_drag_fix import install as install_preview_drag_fix

        install_weather_runtime_patch()
        install_weather_hidden_defaults()
        install_tree_state_patch()
        install_preview_interaction_patch()
        install_preview_drag_fix()
    except Exception as exc:  # pragma: no cover - defensive startup guard
        print(
            f"[theme-editor] could not install runtime patches: {exc}",
            file=sys.stderr,
            flush=True,
        )


_install_theme_editor_patches()
