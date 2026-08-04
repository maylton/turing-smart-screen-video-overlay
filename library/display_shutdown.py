# SPDX-License-Identifier: GPL-3.0-or-later
"""Best-effort physical display power-off before releasing its transport."""

from __future__ import annotations

import time
from typing import Callable


DISPLAY_MEDIA_STOP_SETTLE_SECONDS = 0.15
DISPLAY_POWER_OFF_SETTLE_SECONDS = 0.35


def _disable_async_queue(driver: object) -> None:
    """Ensure final power commands are written synchronously when supported."""
    try:
        setattr(driver, "update_queue", None)
    except Exception:
        pass


def _set_brightness_zero(driver: object) -> None:
    callback = getattr(driver, "SetBrightness", None)
    if callable(callback):
        callback(0)


def _turn_off_backplate(driver: object) -> None:
    callback = getattr(driver, "SetBackplateLedColor", None)
    if not callable(callback):
        return
    try:
        callback(led_color=(0, 0, 0))
    except TypeError:
        callback((0, 0, 0))


def _remember_first_error(
    current: Exception | None,
    candidate: Exception,
) -> Exception:
    return current if current is not None else candidate


def power_off_and_close_display(
    driver: object | None,
    *,
    sleeper: Callable[[float], None] = time.sleep,
    media_stop_settle_seconds: float = DISPLAY_MEDIA_STOP_SETTLE_SECONDS,
    settle_seconds: float = DISPLAY_POWER_OFF_SETTLE_SECONDS,
) -> None:
    """Stop native media, power the LCD down, then close the transport.

    Rev. C firmware retains its last frame after serial disconnect. Native
    video also needs a short mode-transition interval: sending ``TURNOFF``
    immediately after ``STOP_MEDIA`` can leave the background frozen while the
    live HTML overlay disappears.

    The shutdown sequence is therefore synchronous and deliberately ordered:
    stop the native overlay worker/media, wait for the firmware transition,
    force brightness zero as a visual safety net, call ``ScreenOff()``, wait for
    the power command, and only then release the serial connection.
    """
    if driver is None:
        return

    _disable_async_queue(driver)
    power_error: Exception | None = None
    video_was_active = bool(getattr(driver, "video_overlay_enabled", False))
    stop_video = getattr(driver, "StopVideoOverlay", None)

    if video_was_active and callable(stop_video):
        try:
            stop_video()
        except Exception as exc:
            power_error = _remember_first_error(power_error, exc)
        try:
            sleeper(max(0.0, float(media_stop_settle_seconds)))
        except Exception as exc:
            power_error = _remember_first_error(power_error, exc)

    # Brightness zero is intentional even when ScreenOff is available. It
    # prevents a visible frozen frame if a firmware revision accepts the stop
    # commands but ignores or delays TURNOFF. Startup restores configured
    # brightness before rendering the next theme.
    try:
        _set_brightness_zero(driver)
    except Exception as exc:
        power_error = _remember_first_error(power_error, exc)

    screen_off = getattr(driver, "ScreenOff", None)
    if callable(screen_off):
        try:
            # After StopVideoOverlay(), Rev. C ScreenOff follows its non-video
            # path, which sends STOP_MEDIA with a status read before TURNOFF.
            screen_off()
        except Exception as exc:
            power_error = _remember_first_error(power_error, exc)
    elif not video_was_active and callable(stop_video):
        try:
            stop_video()
        except Exception as exc:
            power_error = _remember_first_error(power_error, exc)

    try:
        _turn_off_backplate(driver)
    except Exception:
        # Backplate LEDs are optional and must not prevent serial cleanup.
        pass

    settle_error: Exception | None = None
    close_error: Exception | None = None
    try:
        sleeper(max(0.0, float(settle_seconds)))
    except Exception as exc:
        settle_error = exc
    finally:
        close = getattr(driver, "closeSerial", None)
        if callable(close):
            try:
                close()
            except Exception as exc:
                close_error = exc

    if power_error is not None:
        raise power_error
    if settle_error is not None:
        raise settle_error
    if close_error is not None:
        raise close_error
