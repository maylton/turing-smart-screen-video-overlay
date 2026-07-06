# SPDX-License-Identifier: GPL-3.0-or-later
"""Narrow compatibility hook for the GTK test launcher.

The validated Main App / Diagnostics behavior now lives in
``library.main_app_diagnostics_integration``. This file remains only as a small
compatibility bridge for installed draft builds whose launcher has not yet been
updated to call the consolidated integration directly.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HOOK_INSTALLED = False


def _entry_point_name() -> str:
    return Path(sys.argv[0]).name


def _should_patch_main_app() -> bool:
    return _entry_point_name() == "configure-gtk.py"


def _install_consolidated_integration_after_runtime_patches() -> None:
    main_module = sys.modules.get("__main__")
    runtime_patches = getattr(main_module, "install_runtime_patches", None)
    if runtime_patches is None or getattr(
        runtime_patches,
        "_consolidated_main_app_integration_wrapper",
        False,
    ):
        return

    def install_runtime_patches_with_consolidated_integration(app, *args, **kwargs):
        result = runtime_patches(app, *args, **kwargs)
        try:
            from library.main_app_diagnostics_integration import (
                install_main_app_diagnostics_integration,
            )

            install_main_app_diagnostics_integration(app)
        except Exception as exc:  # pragma: no cover - defensive startup guard
            print(
                f"[main-app-integration] could not install after runtime patches: {exc}",
                file=sys.stderr,
                flush=True,
            )
        return result

    install_runtime_patches_with_consolidated_integration._consolidated_main_app_integration_wrapper = True
    main_module.install_runtime_patches = install_runtime_patches_with_consolidated_integration


def _install_import_hook() -> None:
    global _HOOK_INSTALLED
    if _HOOK_INSTALLED or not _should_patch_main_app():
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
            _install_consolidated_integration_after_runtime_patches()

        loader.exec_module = exec_module
        return spec

    importlib.util.spec_from_file_location = spec_from_file_location
    _HOOK_INSTALLED = True


try:
    _install_import_hook()
except Exception as exc:  # pragma: no cover - defensive startup guard
    print(
        f"[main-app-integration] could not install import hook: {exc}",
        file=sys.stderr,
        flush=True,
    )
