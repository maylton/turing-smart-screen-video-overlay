# SPDX-License-Identifier: GPL-3.0-or-later
"""Targeted startup hooks for local GTK entry points.

Python imports ``usercustomize`` automatically during startup when this checkout
is on ``sys.path``. Keep these hooks narrowly scoped so normal project imports
and monitor runtime entry points are not affected.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


_THEME_EDITOR_ENTRY_POINTS = {
    "theme-editor-gtk.py",
}

_MAIN_APP_ENTRY_POINTS = {
    "configure-gtk.py",
}

_MAIN_APP_HOOK_INSTALLED = False


def _entry_point_name() -> str:
    return Path(sys.argv[0]).name


def _should_patch_theme_editor() -> bool:
    return _entry_point_name() in _THEME_EDITOR_ENTRY_POINTS


def _should_patch_main_app() -> bool:
    return _entry_point_name() in _MAIN_APP_ENTRY_POINTS


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


def _wrap_runtime_patches_for_diagnostics() -> None:
    main_module = sys.modules.get("__main__")
    runtime_patches = getattr(main_module, "install_runtime_patches", None)
    if runtime_patches is None or getattr(runtime_patches, "_diagnostics_integration_wrapper", False):
        return

    def install_runtime_patches_with_diagnostics(app, *args, **kwargs):
        result = runtime_patches(app, *args, **kwargs)
        try:
            from library.main_app_diagnostics_integration import (
                install_main_app_diagnostics_integration,
            )

            install_main_app_diagnostics_integration(app)
        except Exception as exc:  # pragma: no cover - defensive startup guard
            print(
                f"[main-app-diagnostics] could not install after runtime patches: {exc}",
                file=sys.stderr,
                flush=True,
            )
        return result

    install_runtime_patches_with_diagnostics._diagnostics_integration_wrapper = True
    main_module.install_runtime_patches = install_runtime_patches_with_diagnostics


def _install_main_app_diagnostics_hook() -> None:
    global _MAIN_APP_HOOK_INSTALLED
    if _MAIN_APP_HOOK_INSTALLED or not _should_patch_main_app():
        return

    original_spec_from_file_location = importlib.util.spec_from_file_location

    def spec_from_file_location(name, location, *args, **kwargs):
        spec = original_spec_from_file_location(name, location, *args, **kwargs)
        if spec is None or spec.loader is None:
            return spec

        try:
            path = Path(location)
        except TypeError:
            return spec

        if name != "turing_smart_screen_gtk_app" or path.name != "configure_gtk_app.py":
            return spec

        loader = spec.loader
        original_exec_module = loader.exec_module

        def exec_module(module) -> None:
            original_exec_module(module)
            _wrap_runtime_patches_for_diagnostics()

        loader.exec_module = exec_module
        return spec

    importlib.util.spec_from_file_location = spec_from_file_location
    _MAIN_APP_HOOK_INSTALLED = True


_install_theme_editor_patches()
_install_main_app_diagnostics_hook()
