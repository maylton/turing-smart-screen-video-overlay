#!/usr/bin/env python3
"""GTK launcher for the media preparation editor."""

from __future__ import annotations

import sys

import media_preparation_gtk_app as app


def install_i18n() -> None:
    try:
        from library.media_preparation_i18n import install_media_preparation_i18n

        install_media_preparation_i18n(app)
    except Exception as exc:  # pragma: no cover - defensive startup guard
        print(
            f"[media-preparation-i18n] could not install: {exc}",
            file=sys.stderr,
            flush=True,
        )


if __name__ == "__main__":
    install_i18n()
    raise SystemExit(app.MediaPreparationApplication().run(sys.argv))
