"""Test package.

library.display builds the display driver when it is imported (directly or
through library.stats/library.scheduler), and with the real config.yaml that
opens the physical serial port. Tests must never talk to a connected screen:
it would steal replies from a running monitor. Force the simulated display
before any test module is imported, without its preview web server (a
non-daemon thread on port 5678 that would keep the test process alive).
"""

import library.config as _config
import library.lcd.lcd_simulated as _simulated


class _NoWebServer:
    def __init__(self, *_args, **_kwargs):
        pass

    def serve_forever(self):
        pass

    def shutdown(self):
        pass


_config.CONFIG_DATA.setdefault("display", {})["REVISION"] = "SIMU"
_simulated.HTTPServer = _NoWebServer
