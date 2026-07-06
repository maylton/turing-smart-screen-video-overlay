# SPDX-License-Identifier: GPL-3.0-or-later
"""Filter noisy native-video overlay frame refresh debug logs.

The Rev. C native-video overlay worker may emit one DEBUG record for every
latest-frame refresh. That was useful while validating the worker, but it makes
the normal monitor terminal output unreadable. Keep warnings/errors and startup
logs visible; drop only the repetitive successful frame-refresh DEBUG line.
"""

from __future__ import annotations

import logging


class QuietVideoOverlayFrameFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True

        return "Video overlay latest frame sent in" not in message


_FILTER = QuietVideoOverlayFrameFilter()
_INSTALLED = False


def install_quiet_video_overlay_logs() -> None:
    """Install the frame-refresh filter on the project logger once."""

    global _INSTALLED
    if _INSTALLED:
        return

    from library.log import logger

    logger.addFilter(_FILTER)
    for handler in logger.handlers:
        handler.addFilter(_FILTER)

    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(_FILTER)

    _INSTALLED = True
