# SPDX-License-Identifier: GPL-3.0-or-later
"""Best-effort physical display power-off before releasing its transport."""

from __future__ import annotations

import time
from typing import Callable


DISPLAY_POWER_OFF_SETTLE_SECONDS = 0.35


def _disable_async_queue(driver: object) -> None:
    """Ensure final power commands are written synchronously when supported."""
    try:
        setattr(driver, "update_queue", None)
    except Exception:
        pass


def _turn_off_backplate(driver: object) -> None:
    callback = getattr(driver, "SetBackplateLedColor", None)
    if not callable(callback):
        return
    try:
        callback(led_color=(0, 0, 0))
    except TypeError:
        callback((0, 0, 0))


def power_off_and_close_display(
    driver: object | None,
    *,
    sleeper: Callable[[float], None] = time.sleep,
    settle_seconds: float = DISPLAY_POWER_OFF_SETTLE_SECONDS,
) -> None:
    """Power the screen down, wait for firmware, then close the transport.

    Rev. C displays retain their last frame after the serial process exits. A
    plain ``closeSerial()`` therefore does not represent a visual shutdown.
    ``ScreenOff()`` must be delivered while the transport is still open.

    The first power-off error is re-raised only after the serial connection has
    been released. A brightness-zero fallback is attempted when the firmware
    rejects ``ScreenOff()`` so a partial shutdown does not leave a bright frozen
    frame behind.
    """
    if driver is None:
        return

    _disable_async_queue(driver)
    power_error: Exception | None = None

    screen_off = getattr(driver, "ScreenOff", None)
    if callable(screen_off):
        try:
            screen_off()
        except Exception as exc:
            power_error = exc
            set_brightness = getattr(driver, "SetBrightness", None)
            if callable(set_brightness):
                try:
                    set_brightness(0)
                except Exception:
                    pass
    else:
        stop_video = getattr(driver, "StopVideoOverlay", None)
        if callable(stop_video) and bool(
            getattr(driver, "video_overlay_enabled", False)
        ):
            try:
                stop_video()
            except Exception as exc:
                power_error = exc

    try:
        _turn_off_backplate(driver)
    except Exception:
        # Backplate LEDs are optional and must not prevent serial cleanup.
        pass

    try:
        sleeper(max(0.0, float(settle_seconds)))
    finally:
        close = getattr(driver, "closeSerial", None)
        if callable(close):
            close()

    if power_error is not None:
        raise power_error
