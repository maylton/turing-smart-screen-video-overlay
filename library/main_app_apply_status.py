# SPDX-License-Identifier: GPL-3.0-or-later
"""User-facing Apply + Sync + Start progress messages for the GTK app.

This module patches only main-app status messages. It does not open serial
ports, sync videos, start/stop processes, or change runtime behavior by itself;
those operations remain owned by the existing runtime/video code.
"""

from __future__ import annotations

from typing import Any, Callable


APPLY_STEPS: tuple[tuple[int, str, str], ...] = (
    (0, "Preparing Apply + Sync + Start…", "Updating the active theme and preparing the display."),
    (1200, "Stopping monitor…", "Releasing the display before video sync."),
    (3200, "Waiting for display…", "Waiting for the real ttyACM display to settle."),
    (5600, "Syncing theme video…", "Uploading or replacing the display-side video."),
    (9000, "Cleaning old video…", "Keeping the display in single-video mode."),
    (12500, "Waiting for wake-up…", "UsbMonitor may appear briefly while the display restarts."),
    (16500, "Starting monitor…", "The monitor will restart after the display is stable."),
)


def _call_later(app: Any, milliseconds: int, callback: Callable[[], bool]) -> None:
    try:
        app.GLib.timeout_add(milliseconds, callback)
    except Exception:
        pass


def _toast(window: Any, message: str) -> None:
    try:
        window.toast(message)
    except Exception:
        pass


def _set_row_subtitle(row: Any, subtitle: str) -> bool:
    setter = getattr(row, "set_subtitle", None)
    if not callable(setter):
        return False
    try:
        setter(subtitle)
        return True
    except Exception:
        return False


def _set_label_text(widget: Any, text: str) -> bool:
    setter = getattr(widget, "set_label", None)
    if not callable(setter):
        return False
    try:
        setter(text)
        return True
    except Exception:
        return False


def _update_known_status_widgets(window: Any, title: str, detail: str) -> None:
    """Best-effort persistent status update for old and polished Overview builds."""

    subtitle = f"{title} · {detail}" if detail else title

    # Older Overview status rows.
    for attr in (
        "process_status_row",
        "runtime_status_row",
        "monitor_status_row",
    ):
        row = getattr(window, attr, None)
        if row is not None:
            _set_row_subtitle(row, subtitle)

    # Polished dashboard builds use labels/cards. Keep this broad enough to work
    # across the test branches, but scoped to monitor/apply/status-like names.
    title_tokens = ("monitor", "runtime", "operation", "apply", "sync", "status")

    for name, widget in vars(window).items():
        lowered = name.casefold()
        if not any(token in lowered for token in title_tokens):
            continue
        if "button" in lowered or "action" in lowered:
            continue

        if any(token in lowered for token in ("detail", "subtitle", "description")):
            _set_label_text(widget, detail or title)
        elif any(token in lowered for token in ("label", "title", "value")):
            _set_label_text(widget, title)


def _set_operation_status(
    window: Any,
    title: str,
    detail: str = "",
    *,
    toast: bool = False,
) -> None:
    window._apply_sync_status_title = title
    window._apply_sync_status_detail = detail
    _update_known_status_widgets(window, title, detail)
    if toast:
        _toast(window, title)


def _restore_operation_status(window: Any) -> None:
    title = getattr(window, "_apply_sync_status_title", "")
    detail = getattr(window, "_apply_sync_status_detail", "")
    active = bool(getattr(window, "_apply_sync_status_active", False))
    if active and title:
        _update_known_status_widgets(window, title, detail)


def _end_operation_status(app: Any, window: Any, *, delay_ms: int = 2400) -> None:
    def finish() -> bool:
        window._apply_sync_status_active = False
        try:
            window.refresh_overview()
        except Exception:
            pass
        return False

    _call_later(app, delay_ms, finish)


def _begin_apply_progress(app: Any, window: Any) -> None:
    window._apply_sync_status_active = True
    window._apply_sync_status_generation = getattr(
        window,
        "_apply_sync_status_generation",
        0,
    ) + 1
    generation = window._apply_sync_status_generation

    for delay, title, detail in APPLY_STEPS:
        def show_step(
            title: str = title,
            detail: str = detail,
            generation: int = generation,
        ) -> bool:
            if getattr(window, "_apply_sync_status_generation", None) != generation:
                return False
            if not bool(getattr(window, "_apply_sync_status_active", False)):
                return False
            _set_operation_status(window, title, detail)
            return False

        _call_later(app, delay, show_step)

    _set_operation_status(
        window,
        APPLY_STEPS[0][1],
        APPLY_STEPS[0][2],
        toast=True,
    )


def install_main_app_apply_status(app: Any) -> None:
    """Install user-facing progress messages after runtime patches are present."""

    window_class = getattr(app, "SmartScreenWindow", None)
    if window_class is None or getattr(window_class, "_apply_status_installed", False):
        return

    original_update_runtime_status = getattr(window_class, "update_runtime_status", None)
    original_refresh_overview = getattr(window_class, "refresh_overview", None)
    original_apply = getattr(window_class, "apply_set_current_theme_from_gallery", None)
    original_sync = getattr(window_class, "sync_theme_video_from_gallery", None)
    original_finish_sync = getattr(window_class, "finish_sync_theme_video", None)
    original_finish_apply = getattr(window_class, "finish_used_theme_video_and_start", None)
    original_start_monitor = getattr(window_class, "start_monitor", None)
    original_finish_start = getattr(window_class, "finish_monitor_start", None)
    original_stop_monitor = getattr(window_class, "stop_monitor", None)
    original_finish_stop = getattr(window_class, "finish_monitor_stop", None)

    if callable(original_update_runtime_status):
        def update_runtime_status_with_operation(self, *args, **kwargs):
            result = original_update_runtime_status(self, *args, **kwargs)
            _restore_operation_status(self)
            return result

        window_class.update_runtime_status = update_runtime_status_with_operation

    if callable(original_refresh_overview):
        def refresh_overview_with_operation(self, *args, **kwargs):
            result = original_refresh_overview(self, *args, **kwargs)
            _restore_operation_status(self)
            return result

        window_class.refresh_overview = refresh_overview_with_operation

    if callable(original_apply):
        def apply_set_current_theme_from_gallery_with_status(self, record, *args, **kwargs):
            _begin_apply_progress(app, self)
            return original_apply(self, record, *args, **kwargs)

        window_class.apply_set_current_theme_from_gallery = apply_set_current_theme_from_gallery_with_status

    if callable(original_sync):
        def sync_theme_video_from_gallery_with_status(self, record, *args, **kwargs):
            self._apply_sync_status_active = True
            _set_operation_status(
                self,
                "Syncing theme video…",
                f"Preparing video sync for {getattr(record, 'name', 'selected theme')}.",
                toast=True,
            )
            return original_sync(self, record, *args, **kwargs)

        window_class.sync_theme_video_from_gallery = sync_theme_video_from_gallery_with_status

    if callable(original_finish_sync):
        def finish_sync_theme_video_with_status(self, theme_name: str, message: str, error: str, *args, **kwargs):
            if error:
                _set_operation_status(
                    self,
                    "Video sync failed",
                    str(error),
                    toast=True,
                )
            else:
                _set_operation_status(
                    self,
                    "Video synced",
                    message or f"Video synced for {theme_name}.",
                    toast=True,
                )
            result = original_finish_sync(self, theme_name, message, error, *args, **kwargs)
            _end_operation_status(app, self)
            return result

        window_class.finish_sync_theme_video = finish_sync_theme_video_with_status

    if callable(original_finish_apply):
        def finish_used_theme_video_and_start_with_status(
            self,
            new_theme: str,
            message: str,
            error: str,
            *args,
            **kwargs,
        ):
            if error:
                _set_operation_status(
                    self,
                    "Video sync failed; starting monitor…",
                    str(error),
                    toast=True,
                )
            else:
                _set_operation_status(
                    self,
                    "Video sync complete; starting monitor…",
                    message or f"{new_theme} is ready.",
                    toast=True,
                )
            return original_finish_apply(self, new_theme, message, error, *args, **kwargs)

        window_class.finish_used_theme_video_and_start = finish_used_theme_video_and_start_with_status

    if callable(original_start_monitor):
        def start_monitor_with_status(self, *args, **kwargs):
            self._apply_sync_status_active = True
            _set_operation_status(
                self,
                "Starting monitor…",
                "Launching main.py with the selected theme.",
            )
            return original_start_monitor(self, *args, **kwargs)

        window_class.start_monitor = start_monitor_with_status

    if callable(original_finish_start):
        def finish_monitor_start_with_status(self, *args, **kwargs):
            result = original_finish_start(self, *args, **kwargs)
            process = getattr(self, "monitor_process", None)
            if process is not None and process.poll() is None:
                _set_operation_status(
                    self,
                    "Monitor started",
                    f"PID {process.pid}" if getattr(process, "pid", None) else "Monitor is running.",
                    toast=True,
                )
            else:
                _set_operation_status(
                    self,
                    "Monitor did not stay running",
                    "Check Diagnostics for the last runtime state.",
                    toast=True,
                )
            _end_operation_status(app, self)
            return result

        window_class.finish_monitor_start = finish_monitor_start_with_status

    if callable(original_stop_monitor):
        def stop_monitor_with_status(self, *args, **kwargs):
            self._apply_sync_status_active = True
            _set_operation_status(
                self,
                "Stopping monitor…",
                "Waiting for the display connection to be released.",
                toast=True,
            )
            return original_stop_monitor(self, *args, **kwargs)

        window_class.stop_monitor = stop_monitor_with_status

    if callable(original_finish_stop):
        def finish_monitor_stop_with_status(self, result, error, *args, **kwargs):
            output = original_finish_stop(self, result, error, *args, **kwargs)
            if error:
                _set_operation_status(
                    self,
                    "Could not stop monitor",
                    str(error),
                    toast=True,
                )
            else:
                detail = getattr(result, "message", "") or "Display connection released."
                _set_operation_status(self, "Monitor stopped", detail)
            _end_operation_status(app, self)
            return output

        window_class.finish_monitor_stop = finish_monitor_stop_with_status

    window_class._apply_status_installed = True
