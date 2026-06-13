#!/usr/bin/env python3
"""Small command-line controller for the configured Turing display."""

from __future__ import annotations

import sys
import time

from library.display import display


def main() -> int:
    command = sys.argv[1].lower() if len(sys.argv) > 1 else ""

    if command not in {"off", "on"}:
        print("Usage: screen-control.py off|on", file=sys.stderr)
        return 2

    if display.lcd is None:
        print("The configured display revision is unknown.", file=sys.stderr)
        return 1

    try:
        # Initialize communication without resetting or redrawing the screen.
        display.lcd.InitializeComm()

        if command == "off":
            display.turn_off()
        else:
            display.turn_on()

        # Give queued USB/serial commands a moment to leave the process.
        time.sleep(0.5)
        return 0
    except Exception as exc:
        print(f"Display power command failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
