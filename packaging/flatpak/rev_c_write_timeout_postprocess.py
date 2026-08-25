#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Apply a bounded serial write timeout to Rev. C in the Flatpak payload."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: rev_c_write_timeout_postprocess.py PAYLOAD_ROOT")

    root = Path(sys.argv[1]).resolve()
    path = root / "library/lcd/lcd_comm_rev_c.py"
    source = path.read_text(encoding="utf-8")

    old = '''class LcdCommRevC(LcdComm):
    def __init__(self, com_port: str = "AUTO", display_width: int = 480, display_height: int = 800,
'''
    new = '''class LcdCommRevC(LcdComm):
    SERIAL_WRITE_TIMEOUT_SECONDS = 2.0

    def openSerial(self):
        super().openSerial()
        if self.lcd_serial is not None:
            self.lcd_serial.write_timeout = self.SERIAL_WRITE_TIMEOUT_SECONDS

    def __init__(self, com_port: str = "AUTO", display_width: int = 480, display_height: int = 800,
'''

    if old not in source:
        raise AssertionError("Flatpak Rev. C write-timeout hook not found")

    path.write_text(source.replace(old, new, 1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
