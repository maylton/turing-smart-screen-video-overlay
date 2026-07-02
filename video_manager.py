#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime-safe entry point for the native video manager backend."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from library.runtime import DeviceBusyError, DeviceLock

ROOT = Path(__file__).resolve().parent
BACKEND_MODULE = ROOT / "video_manager_backend.py"


def load_backend():
    spec = importlib.util.spec_from_file_location(
        "turing_video_manager_backend", BACKEND_MODULE
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {BACKEND_MODULE.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    backend = load_backend()

    # Probe is read-only and never opens the display connection.
    if "probe" in sys.argv[1:]:
        return backend.cli()

    try:
        with DeviceLock(role="video-manager", root=ROOT):
            # The lease is now the source of truth. Disable the legacy pgrep
            # heuristic so unrelated main.py processes cannot cause a false hit.
            backend.main_program_running = lambda: False
            return backend.cli()
    except DeviceBusyError as exc:
        print(str(exc), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
