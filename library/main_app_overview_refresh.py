# SPDX-License-Identifier: GPL-3.0-or-later
"""Automatic refresh of the Overview Theme, Monitor and Display cards."""

from __future__ import annotations

from typing import Any

from gi.repository import GLib


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
        except Exception as exc:
            toast = getattr(window, "toast", None)
            if callable(toast):
                try:
                    toast(f"Could not refresh Overview status: {exc}")
                except Exception:
                    pass


class OverviewRefreshMixin:
    """Keep the Overview status cards fresh without a manual Refresh."""

    def __init__(self, application):
        super().__init__(application)
        try:
            GLib.timeout_add_seconds(REFRESH_INTERVAL_SECONDS, self.refresh_overview_status_timer)
        except Exception:
            pass

    def refresh_overview_status_timer(self) -> bool:
        # Do not fight longer-running Apply + Sync + Start status messages.
        if bool(getattr(self, "_apply_sync_status_active", False)):
            return True
        if _overview_is_visible(self):
            _safe_refresh_overview(self)
        return True
