# SPDX-License-Identifier: GPL-3.0-or-later
"""Native Rev. C video plus atomic transparent HTML overlay ownership."""

from __future__ import annotations

import time
from typing import Callable, Optional

from PIL import Image

from library.log import logger
from library import display_health
from library.display_shutdown import power_off_and_close_display
from library.theme_engine import NativeVideoOverlay, ThemeValidationError

def _default_driver_factory(port: str):
    from library.lcd.lcd_comm_rev_c import LcdCommRevC

    return LcdCommRevC(com_port=port, display_width=480, display_height=480)


class HtmlNativeVideoSink:
    """Open serial once, start native video, and retain only the latest overlay."""

    MINIMUM_TRANSPARENT_RATIO = 0.10
    MINIMUM_PHYSICAL_REFRESH_INTERVAL_SECONDS = 1.0
    START_ATTEMPTS = 10
    START_RETRY_DELAY_SECONDS = 3.0
    FIRST_FRAME_TIMEOUT_SECONDS = 12.0

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
        self._brightness = brightness
        self._refresh_interval = refresh_interval
        self._driver_factory = driver_factory
        self._port = port
        self._spec = spec
        display_health.clear()
        last_error: Optional[Exception] = None
        for attempt in range(1, self.START_ATTEMPTS + 1):
            try:
                self._start_once(initial_overlay)
                return
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Native video start attempt %d/%d failed: %s",
                    attempt,
                    self.START_ATTEMPTS,
                    exc,
                )
                self._closed = False
                try:
                    self.close()
                except Exception:
                    pass
                self._closed = False
                if attempt < self.START_ATTEMPTS:
                    # The display may still be mounting its SD card after a
                    # cold boot; give it time and redo HELLO + video start.
                    self._sleeper(self.START_RETRY_DELAY_SECONDS)
        self._closed = True
        raise last_error

    def _start_once(self, initial_overlay: Image.Image) -> None:
        try:
            from library.lcd.lcd_comm import Orientation

            driver = (self._driver_factory or _default_driver_factory)(self._port)
            self._driver = driver
            driver.InitializeComm()
            screen_on = getattr(driver, "ScreenOn", None)
            if callable(screen_on):
                screen_on()
            set_brightness = getattr(driver, "SetBrightness", None)
            if callable(set_brightness):
                set_brightness(max(0, min(100, int(self._brightness))))
            driver.SetOrientation(Orientation.LANDSCAPE)
            driver.StartVideoOverlay(
                self._spec.device_path,
                refresh_interval=max(
                    self.MINIMUM_PHYSICAL_REFRESH_INTERVAL_SECONDS,
                    float(self._refresh_interval),
                ),
            )
            self.submit(initial_overlay)
            self._wait_first_frame_acknowledged()
        except Exception:
            try:
                self.close()
            except Exception:
                pass
            raise

    def _wait_first_frame_acknowledged(self) -> None:
        """Block until the display has ACKed the first overlay frame.

        A responding serial port (HELLO) does not prove that the firmware has
        entered video mode; right after a cold boot the process can look
        healthy while the screen stays frozen.
        """
        driver = self._driver
        if not hasattr(driver, "_video_overlay_last_sent"):
            return
        deadline = time.monotonic() + self.FIRST_FRAME_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            self.check_health()
            if getattr(driver, "_video_overlay_last_sent", 0.0) > 0.0:
                logger.info("Native video overlay: first frame acknowledged")
                return
            self._sleeper(0.1)
        raise RuntimeError("display did not acknowledge the first overlay frame")

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

    def last_frame_ack_age(self) -> Optional[float]:
        """Seconds since the display acknowledged an overlay frame, or None."""
        last_sent = getattr(self._driver, "_video_overlay_last_sent", 0.0)
        if not last_sent:
            return None
        return max(0.0, time.monotonic() - last_sent)

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
        display_health.clear()
        driver, self._driver = self._driver, None
        power_off_and_close_display(driver, sleeper=self._sleeper)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
        return False
