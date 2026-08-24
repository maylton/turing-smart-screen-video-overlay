# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded Rev. C handshake with USB-level recovery for wedged displays."""

from __future__ import annotations

import string
import time

import serial

from library.lcd.lcd_comm_rev_c import Command, LcdCommRevC, SubRevision
from library.log import logger


HELLO_ATTEMPTS = 3
POST_RESET_HELLO_ATTEMPTS = 3
SERIAL_WRITE_TIMEOUT_SECONDS = 3
USB_SETTLE_SECONDS = 1.0

# Prefer the awake CDC endpoint when both identities are visible. Resetting one
# physical endpoint is enough; resetting every matching USB node while a device
# is re-enumerating creates avoidable disconnect races.
AWAKE_USB_IDS = (
    (0x1D6B, 0x0121),
    (0x1D6B, 0x0106),
    (0x0525, 0xA4A7),
)
SLEEPING_USB_IDS = (
    (0x1A86, 0xCA21),
)


class RevCRecoveryError(RuntimeError):
    """Raised when a Rev. C display cannot be recovered automatically."""


class RecoveringLcdCommRevC(LcdCommRevC):
    """Rev. C driver that never loops forever on a dead HELLO exchange."""

    def openSerial(self):
        super().openSerial()
        if self.lcd_serial is not None:
            # pyserial's default write_timeout=None can block indefinitely when
            # hardware flow control is asserted and the display firmware wedges.
            self.lcd_serial.write_timeout = SERIAL_WRITE_TIMEOUT_SECONDS

    def _hello_exchange(self) -> str:
        self.sub_revision = self._get_sub_revision()
        self.serial_flush_input()
        try:
            self._send_command(Command.HELLO, bypass_queue=True)
        except serial.SerialTimeoutException:
            logger.warning("Rev. C HELLO write timed out")
            return ""
        except serial.SerialException as exc:
            logger.warning("Rev. C HELLO write failed: %s", exc)
            return ""

        try:
            payload = self.serial_read(23)
        except serial.SerialException as exc:
            logger.warning("Rev. C HELLO read failed: %s", exc)
            return ""
        finally:
            try:
                self.serial_flush_input()
            except Exception:
                pass

        response = "".join(
            character
            for character in payload.decode(errors="ignore")
            if character in set(string.printable)
        )
        logger.debug("Display ID returned: %s", response)
        return response

    def _finish_hello(self, response: str) -> None:
        # IDs are unreliable for physical size on some Rev. C models, so width
        # and height remain the authoritative sub-revision hint.
        self.sub_revision = self._get_sub_revision()
        if self.sub_revision == SubRevision.UNKNOWN:
            logger.error(
                "Unsupported resolution %dx%d for revision C",
                self.display_width,
                self.display_height,
            )

        try:
            self.rom_version = int(response.split(".")[2])
            if self.rom_version < 80 or self.rom_version > 100:
                logger.warning(
                    "ROM version %d may be invalid, use default ROM version 87",
                    self.rom_version,
                )
                self.rom_version = 87
        except Exception:
            logger.warning(
                "Display returned invalid ROM version, use default ROM version 87"
            )
            self.rom_version = 87

        logger.debug(
            "HW sub-revision detected: %s, ROM version: %d",
            str(self.sub_revision),
            self.rom_version,
        )

    def _try_hello(self, attempts: int) -> str:
        for attempt in range(1, attempts + 1):
            logger.debug("Rev. C HELLO attempt %d/%d", attempt, attempts)
            response = self._hello_exchange()
            if response.startswith("chs_"):
                return response
            if attempt < attempts:
                logger.warning(
                    "Display returned invalid or empty ID; retrying in 1 second"
                )
                time.sleep(1)
        return ""

    @staticmethod
    def _matching_usb_device():
        try:
            import usb.core
        except Exception as exc:
            raise RevCRecoveryError(
                "pyusb is required for Rev. C USB recovery"
            ) from exc

        devices = list(usb.core.find(find_all=True) or [])
        by_id = {(dev.idVendor, dev.idProduct): dev for dev in devices}
        for identity in AWAKE_USB_IDS + SLEEPING_USB_IDS:
            device = by_id.get(identity)
            if device is not None:
                return device
        return None

    def _usb_reset_and_reopen(self) -> None:
        try:
            self.closeSerial()
        except Exception:
            pass

        device = self._matching_usb_device()
        if device is None:
            raise RevCRecoveryError("no Rev. C USB endpoint is available for reset")

        identity = (device.idVendor, device.idProduct)
        logger.warning(
            "Rev. C serial handshake is unresponsive; resetting USB endpoint %04x:%04x",
            identity[0],
            identity[1],
        )
        try:
            device.reset()
        except Exception as exc:
            raise RevCRecoveryError(
                "USB reset failed; verify the Rev. C raw USB udev permissions"
            ) from exc
        finally:
            try:
                import usb.util
                usb.util.dispose_resources(device)
            except Exception:
                pass

        time.sleep(USB_SETTLE_SECONDS)

        # The reset commonly leaves only the CT21INCH/ca21 sleeping endpoint.
        # AUTO detection knows how to touch that endpoint until the awake CDC
        # endpoint reappears, and it also handles a changed ttyACM number.
        self.com_port = "AUTO"
        self.openSerial()

    def _hello(self):
        response = self._try_hello(HELLO_ATTEMPTS)
        if response.startswith("chs_"):
            self._finish_hello(response)
            return

        self._usb_reset_and_reopen()
        response = self._try_hello(POST_RESET_HELLO_ATTEMPTS)
        if not response.startswith("chs_"):
            raise RevCRecoveryError(
                "Rev. C display did not answer HELLO after USB recovery"
            )
        self._finish_hello(response)
