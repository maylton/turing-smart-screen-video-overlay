#!/usr/bin/env python3
"""Bootstrap the installed GTK application with project startup hooks enabled."""

from __future__ import annotations

import importlib
import os
import runpy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ENTRY_POINT = ROOT / "configure-gtk.py"


def main() -> int:
    os.environ.setdefault("TURING_SMART_SCREEN_HOME", str(ROOT))

    root_text = str(ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

    # Startup hooks inspect argv[0] to decide which narrowly scoped patches to
    # install. Present the real GTK entry point before importing them.
    forwarded_args = sys.argv[1:]
    sys.argv = [str(ENTRY_POINT), *forwarded_args]

    for module_name in ("sitecustomize", "usercustomize"):
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            if exc.name == module_name:
                continue
            raise

    runpy.run_path(str(ENTRY_POINT), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
