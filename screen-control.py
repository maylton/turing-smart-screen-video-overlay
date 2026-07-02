#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import sys
import time
from pathlib import Path

from library.runtime import DeviceBusyError, DeviceLock

ROOT = Path(__file__).resolve().parent


def run_power_command(command: str) -> None:
    # Import only after acquiring the lease because library.display creates the
    # display communication object at module import time.
    from library.display import display

    lcd = display.lcd
    if lcd is None:
        raise RuntimeError("The configured display revision is unknown")

    lcd.update_queue = None
    lcd.InitializeComm()
    try:
        if command == "off":
            try:
                lcd.SetBrightness(0)
            except Exception:
                pass
            display.turn_off()
        else:
            display.turn_on()
        time.sleep(0.25)
    finally:
        try:
            lcd.closeSerial()
        except Exception:
            pass


def main() -> int:
    command = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    if command not in {"off", "on"}:
        print("Usage: screen-control.py off|on", file=sys.stderr)
        return 2

    try:
        with DeviceLock(role="screen-control", root=ROOT):
            run_power_command(command)
        return 0
    except DeviceBusyError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"Display power command failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
