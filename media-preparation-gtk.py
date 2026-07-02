#!/usr/bin/env python3
"""GTK launcher for the media preparation editor."""

from __future__ import annotations

import sys

from media_preparation_gtk_app import MediaPreparationApplication


if __name__ == "__main__":
    raise SystemExit(MediaPreparationApplication().run(sys.argv))
