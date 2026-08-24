# SPDX-License-Identifier: GPL-3.0-or-later
"""Long-lived, status-observable Rev. C sink for the integrated HTML runner."""

from __future__ import annotations

import time
from typing import Callable, Optional

from PIL import Image

from library.display_shutdown import power_off_and_close_display
from library.rev_c_live_sink import LiveWriteRefused, _validate_protocol_parity
from library.rev_c_physical_sink import _validate_parity
from library.rev_c_status_transport import send_protocol_with_status


MAX_REGIONS_PER_CYCLE = 8
MAX_WIRE_BYTES_PER_CYCLE = 300_000
REGION_PACING_SECONDS = 0.10
MINIMUM_STATUS_BYTES = 1


def _default_driver_factory(port: str):
    from library.rev_c_recovery import RecoveringLcdCommRevC

    return RecoveringLcdCommRevC(
        com_port=port,
        display_width=480,
        display_height=480,
    )


class IntegratedRevCSink:
    """Own one serial driver until close; every exchange is status checked."""

    def __init__(
        self,
        initial_frame: Image.Image,
        initial_protocol,
        initial_parity,
        *,
        port: str,
        driver_factory: Optional[Callable[[str], object]] = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        frame = initial_frame.convert("RGBA")
        frame.load()
        if frame.size != (480, 480):
            raise LiveWriteRefused("integrated HTML renderer requires 480x480")
        _validate_parity(initial_parity)
        _validate_protocol_parity(initial_protocol, initial_parity, "full")
        self._driver = None
        self._closed = False
        self._sleeper = sleeper
        self._sequence = int(initial_parity.sequence)
        try:
            from library.lcd.lcd_comm import Orientation

            self._driver = (driver_factory or _default_driver_factory)(port)
            self._driver.InitializeComm()
            self._driver.SetOrientation(Orientation.LANDSCAPE)
            send_protocol_with_status(
                self._driver,
                initial_protocol,
                minimum_status_bytes=MINIMUM_STATUS_BYTES,
                inter_exchange_delay=0.0,
                exchange_batch_size=1,
                inter_batch_delay=0.0,
                sleeper=sleeper,
            )
        except Exception:
            try:
                self.close()
            except Exception:
                pass
            raise

    def submit(self, frame, transport, protocol, parity) -> None:
        if self._closed or self._driver is None:
            raise LiveWriteRefused("integrated Rev. C sink is closed")
        packets = tuple(getattr(transport, "packets", ()))
        if len(packets) > MAX_REGIONS_PER_CYCLE:
            raise LiveWriteRefused("physical cycle exceeds 8 regions")
        if int(getattr(protocol, "wire_bytes", 0)) > MAX_WIRE_BYTES_PER_CYCLE:
            raise LiveWriteRefused("physical cycle exceeds 300000 bytes")
        mode = "partial" if packets else "noop"
        _validate_protocol_parity(protocol, parity, mode)
        sequence = int(getattr(parity, "sequence", 0))
        if sequence <= self._sequence:
            raise LiveWriteRefused("physical sequence did not increase")
        send_protocol_with_status(
            self._driver,
            protocol,
            minimum_status_bytes=MINIMUM_STATUS_BYTES,
            inter_exchange_delay=REGION_PACING_SECONDS,
            exchange_batch_size=MAX_REGIONS_PER_CYCLE,
            inter_batch_delay=0.0,
            sleeper=self._sleeper,
        )
        self._sequence = sequence

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
