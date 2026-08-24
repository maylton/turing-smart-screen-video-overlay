# SPDX-License-Identifier: GPL-3.0-or-later
"""Native Rev. C video plus atomic transparent HTML overlay ownership."""

from __future__ import annotations

import time
from typing import Callable, Optional

from PIL import Image

from library.display_shutdown import power_off_and_close_display
from library.theme_engine import NativeVideoOverlay, ThemeValidationError


def _default_driver_factory(port: str):
    from library.lcd.lcd_comm_rev_c import LcdCommRevC
    return LcdCommRevC(com_port=port, display_width=480, display_height=480)


class HtmlNativeVideoSink:
    """Open serial once, start native video, and retain only the latest overlay."""

    MINIMUM_TRANSPARENT_RATIO = 0.10

    def __init__(
        self,
        initial_overlay: Image.Image,
        spec: NativeVideoOverlay,
        *,
        port: str,
        brightness: int = 20,
        refresh_interval: float = 1.0,
        driver_factory: Optional[Callable[[str], object]] = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._driver = None
        self._closed = False
        self._sleeper = sleeper
        self._validate_overlay(initial_overlay)
        try:
            from library.lcd.lcd_comm import Orientation

            driver = (driver_factory or _default_driver_factory)(port)
            self._driver = driver
            driver.InitializeComm()
            screen_on = getattr(driver, "ScreenOn", None)
            if callable(screen_on):
                screen_on()
            set_brightness = getattr(driver, "SetBrightness", None)
            if callable(set_brightness):
                set_brightness(max(0, min(100, int(brightness))))
            driver.SetOrientation(Orientation.LANDSCAPE)
            driver.StartVideoOverlay(
                spec.device_path,
                refresh_interval=max(0.25, float(refresh_interval)),
            )
            self.submit(initial_overlay)
        except Exception:
            try:
                self.close()
            except Exception:
                pass
            raise

    @staticmethod
    def _validate_overlay(image: Image.Image) -> None:
        frame = image.convert("RGBA")
        frame.load()
        if frame.size != (480, 480):
            raise ThemeValidationError(
                f"native HTML overlay must be 480x480; received {frame.size}"
            )
        minimum, maximum = frame.getchannel("A").getextrema()
        if minimum > 0:
            raise ThemeValidationError(
                "native HTML overlay is fully opaque and would cover the video"
            )
        if maximum == 0:
            raise ThemeValidationError(
                "native HTML overlay is fully transparent and contains no live data"
            )
        transparent = frame.getchannel("A").histogram()[0]
        if transparent < int(
            frame.width * frame.height * HtmlNativeVideoSink.MINIMUM_TRANSPARENT_RATIO
        ):
            raise ThemeValidationError(
                "native HTML overlay must leave at least 10% of the video visible"
            )

    def check_health(self) -> None:
        if self._closed or self._driver is None:
            raise RuntimeError("native HTML video sink is closed")
        error = getattr(self._driver, "video_overlay_error", None)
        if error is not None:
            raise RuntimeError(f"native video overlay transport failed: {error}") from error
        if not bool(getattr(self._driver, "video_overlay_enabled", False)):
            raise RuntimeError("native video overlay stopped unexpectedly")

    def submit(self, overlay: Image.Image) -> None:
        self.check_health()
        self._validate_overlay(overlay)
        self._driver.DisplayPILImageOnVideoOverlay(
            overlay.convert("RGBA"),
            x=0,
            y=0,
            image_width=480,
            image_height=480,
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        driver, self._driver = self._driver, None
        power_off_and_close_display(driver, sleeper=self._sleeper)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
        return False
