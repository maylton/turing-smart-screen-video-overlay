# SPDX-License-Identifier: GPL-3.0-or-later
"""Automatic Overview status refresh for the GTK main app."""

from __future__ import annotations

from typing import Any


REFRESH_INTERVAL_SECONDS = 2


def _overview_is_visible(window: Any) -> bool:
    stack = getattr(window, "stack", None)
    getter = getattr(stack, "get_visible_child_name", None)
    if not callable(getter):
        return True
    try:
        return getter() == "overview"
    except Exception:
        return True


def _safe_refresh_overview(window: Any) -> None:
    refresher = getattr(window, "refresh_overview", None)
    if callable(refresher):
        try:
            refresher()
        except Exception:
            pass


def install_main_app_overview_auto_refresh(app: Any) -> None:
    """Install a lightweight timer that keeps Overview status cards fresh."""

    window_class = getattr(app, "SmartScreenWindow", None)
    if window_class is None or getattr(window_class, "_overview_auto_refresh_installed", False):
        return

    original_init = window_class.__init__

    def refresh_overview_status_timer(self) -> bool:
        # Do not fight longer-running Apply + Sync + Start status messages.
        if bool(getattr(self, "_apply_sync_status_active", False)):
            return True
        if _overview_is_visible(self):
            _safe_refresh_overview(self)
        return True

    def patched_init(self, application):
        original_init(self, application)
        try:
            app.GLib.timeout_add_seconds(
                REFRESH_INTERVAL_SECONDS,
                self.refresh_overview_status_timer,
            )
        except Exception:
            pass

    window_class.refresh_overview_status_timer = refresh_overview_status_timer
    window_class.__init__ = patched_init
    window_class._overview_auto_refresh_installed = True
