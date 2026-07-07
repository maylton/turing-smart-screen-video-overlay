#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Developer entry point for the reusable GTK theme gallery surface.

Long term, the gallery should be opened from the main application shell. This
script remains useful during the migration because it lets us test the gallery
surface independently.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# GTK comes from the system Python on Arch/CachyOS, while the project
# dependencies may live in the virtual environment.
for site_dir in (
    ROOT / "venv" / "lib",
    ROOT / ".venv" / "lib",
):
    if site_dir.is_dir():
        for candidate in site_dir.glob("python*/site-packages"):
            sys.path.insert(0, str(candidate))

from library.theme_gallery import main
from library.theme_gallery_i18n import install_theme_gallery_i18n


if __name__ == "__main__":
    install_theme_gallery_i18n()
    raise SystemExit(main(sys.argv))
