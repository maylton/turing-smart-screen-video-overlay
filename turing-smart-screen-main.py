#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Main GTK app launcher with stacked runtime integrations."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIGURE_GTK = ROOT / "configure-gtk.py"


def load_configure_launcher():
    spec = importlib.util.spec_from_file_location(
        "turing_smart_screen_configure_launcher",
        CONFIGURE_GTK,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {CONFIGURE_GTK.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    launcher = load_configure_launcher()
    app = launcher.load_app_module()
    launcher.install_runtime_patches(app)

    from library.embedded_theme_editor_runtime import install_embedded_theme_editor_patches
    from library.embedded_video_manager_runtime import install_embedded_video_manager_patches

    install_embedded_theme_editor_patches(app, root=ROOT)
    install_embedded_video_manager_patches(app, root=ROOT)
    return app.main()


if __name__ == "__main__":
    raise SystemExit(main())
