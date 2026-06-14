#!/usr/bin/env python3
from __future__ import annotations

import sys
import time

from library.display import display


def power_off() -> None:
    lcd = display.lcd
    if lcd is None:
        raise RuntimeError("The configured display revision is unknown")

    # This helper runs without main.py's scheduler, so queued commands would
    # never be sent. Force synchronous USB/serial writes.
    lcd.update_queue = None
    lcd.InitializeComm()

    try:
        lcd.SetBrightness(0)
    except Exception:
        pass

    display.turn_off()
    time.sleep(0.25)

    try:
        display.turn_off()
    except Exception:
        pass

    time.sleep(0.25)

    try:
        lcd.closeSerial()
    except Exception:
        pass


def power_on() -> None:
    lcd = display.lcd
    if lcd is None:
        raise RuntimeError("The configured display revision is unknown")

    lcd.update_queue = None
    lcd.InitializeComm()
    display.turn_on()
    time.sleep(0.25)

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
        power_off() if command == "off" else power_on()
        return 0
    except Exception as exc:
        print(f"Display power command failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
