# SPDX-License-Identifier: GPL-3.0-or-later
"""Narrow test hooks for the GTK launcher.

Python imports ``usercustomize`` after ``sitecustomize`` when it is present on
``sys.path``. Keep this file guarded by entry point so the diagnostics-page test
branch can wire new UI into ``configure-gtk.py`` without touching production
launcher code yet.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_DIAGNOSTICS_HOOK_INSTALLED = False


def _entry_point_name() -> str:
    return Path(sys.argv[0]).name


def _should_patch_main_app() -> bool:
    return _entry_point_name() == "configure-gtk.py"


def _install_diagnostics_import_hook() -> None:
    global _DIAGNOSTICS_HOOK_INSTALLED
    if _DIAGNOSTICS_HOOK_INSTALLED or not _should_patch_main_app():
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
            try:
                from library.main_app_diagnostics_integration import (
                    install_main_app_diagnostics_integration,
                )

                install_main_app_diagnostics_integration(module)
            except Exception as exc:  # pragma: no cover - defensive startup guard
                print(
                    f"[diagnostics] could not install main app integration: {exc}",
                    file=sys.stderr,
                    flush=True,
                )

        loader.exec_module = exec_module
        return spec

    importlib.util.spec_from_file_location = spec_from_file_location
    _DIAGNOSTICS_HOOK_INSTALLED = True


try:
    _install_diagnostics_import_hook()
except Exception as exc:  # pragma: no cover - defensive startup guard
    print(
        f"[diagnostics] could not install import hook: {exc}",
        file=sys.stderr,
        flush=True,
    )
