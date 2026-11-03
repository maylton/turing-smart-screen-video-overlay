# SPDX-License-Identifier: GPL-3.0-or-later
"""Register UNIX signal handlers on the GLib main loop."""

from __future__ import annotations

from typing import Callable, Optional


def unix_signal_add(priority: int, signum: int, callback: Callable[[], bool]) -> Optional[int]:
    """Return a GLib source id, or None when the platform has no support.

    PyGObject 3.52+ moved the API to ``GLibUnix.signal_add`` and warns on
    every call to the old ``GLib.unix_signal_add``.
    """
    try:
        import gi

        gi.require_version("GLibUnix", "2.0")
        from gi.repository import GLibUnix

        return GLibUnix.signal_add(priority, signum, callback)
    except (ImportError, ValueError, AttributeError):
        pass

    from gi.repository import GLib

    legacy = getattr(GLib, "unix_signal_add", None)
    if not callable(legacy):
        return None
    return legacy(priority, signum, callback)
