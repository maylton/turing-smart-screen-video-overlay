#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Developer-only simulator for experimental HTML themes."""

from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

from library.html_theme_engine import HtmlThemeEngine, WebKitUnavailableError
from library.sensor_snapshot import SensorSnapshotCollector
from library.theme_engine import ThemeManifest, ThemeValidationError


ROOT = Path(__file__).resolve().parent
DEFAULT_THEME = ROOT / "res" / "themes" / "html-demo"


def demo_readers():
    started = time.monotonic()

    def phase():
        return time.monotonic() - started

    return {
        "cpu": lambda: {
            "usage": round(52 + 35 * math.sin(phase() * 0.8), 1),
            "temperature": round(61 + 7 * math.sin(phase() * 0.45), 1),
            "frequency": round(4.5 + 0.4 * math.sin(phase() * 0.3), 2),
        },
        "gpu": lambda: {
            "name": "AMD Radeon RX 9070 XT",
            "usage": round(68 + 24 * math.sin(phase() * 0.55 + 1.2), 1),
            "temperature": round(64 + 6 * math.sin(phase() * 0.35), 1),
            "vramUsed": round(8.2 + 1.8 * math.sin(phase() * 0.2), 1),
            "vramTotal": 16,
        },
        "memory": lambda: {
            "usage": round(47 + 9 * math.sin(phase() * 0.18), 1),
            "used": 15.4,
            "total": 32,
        },
        "network": lambda: {
            "upload": round(2.4 + 1.2 * abs(math.sin(phase() * 0.9)), 1),
            "download": round(18 + 12 * abs(math.sin(phase() * 0.42)), 1),
        },
        "system": lambda: {
            "hostname": "html-theme-preview",
            "time": time.strftime("%H:%M:%S"),
        },
    }


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme", type=Path, default=DEFAULT_THEME)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def validate(args):
    manifest = ThemeManifest.load(args.theme)
    if manifest.engine != "html":
        raise ThemeValidationError("The preview command requires an HTML theme")
    return manifest


def run_check(manifest):
    print(f"HTML theme manifest: OK ({manifest.name})")
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("WebKit", "6.0")
        from gi.repository import Gtk, WebKit  # noqa: F401
    except Exception as exc:
        print(f"WebKitGTK: unavailable — {exc}")
        return 2
    print("WebKitGTK: available")
    return 0


def run_preview(manifest, snapshot_path=None):
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import GLib, Gtk
    except Exception as exc:
        raise WebKitUnavailableError("GTK4 GI bindings are required") from exc

    collector = SensorSnapshotCollector(demo_readers())
    engine = HtmlThemeEngine()

    class PreviewApplication(Gtk.Application):
        def __init__(self):
            super().__init__(
                application_id="io.github.turing.HtmlThemePreview"
            )
            self.window = None
            self._snapshot_scheduled = False

        def do_activate(self):
            if self.window is not None:
                self.window.present()
                return
            engine.load(manifest)
            self.window = Gtk.ApplicationWindow(application=self)
            self.window.set_title(f"HTML Theme Preview — {manifest.name}")
            self.window.set_default_size(manifest.width, manifest.height)
            self.window.set_resizable(False)
            self.window.set_child(engine.render())
            self.window.present()

            interval_ms = max(
                100,
                int(round(1000 / manifest.refresh_rate)),
            )

            def update_theme():
                engine.update(collector.collect())
                if snapshot_path and not self._snapshot_scheduled:
                    self._snapshot_scheduled = True

                    def export_snapshot():
                        def finished(error):
                            if error:
                                print(
                                    f"Snapshot failed: {error}",
                                    file=sys.stderr,
                                )
                            else:
                                print(f"Snapshot written to {snapshot_path}")

                        engine.snapshot_png(snapshot_path, finished)
                        return False

                    GLib.timeout_add(1200, export_snapshot)
                return True

            update_theme()
            GLib.timeout_add(interval_ms, update_theme)

        def do_shutdown(self):
            engine.close()
            Gtk.Application.do_shutdown(self)

    return PreviewApplication().run([])


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    try:
        manifest = validate(args)
        if args.check:
            return run_check(manifest)
        return run_preview(manifest, args.snapshot)
    except (ThemeValidationError, WebKitUnavailableError) as exc:
        print(f"HTML theme preview error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
