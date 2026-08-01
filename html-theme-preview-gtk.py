#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Developer-only simulator for experimental HTML themes."""

from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

from library.frame_pipeline import FramePipeline, write_frame_artifacts
from library.html_theme_engine import HtmlThemeEngine, WebKitUnavailableError
from library.real_sensor_source import RealSensorSource
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
    parser.add_argument(
        "--real-sensors",
        action="store_true",
        help="Use the existing Python hardware sensor backend.",
    )
    parser.add_argument(
        "--network-interface",
        default="",
        help="Optional interface used by real network metrics.",
    )
    parser.add_argument(
        "--inspect-frames",
        type=Path,
        help=(
            "Capture rendered frames in memory, calculate dirty regions, and "
            "write latest.png, latest-diff.png, and metrics.json here."
        ),
    )
    parser.add_argument(
        "--frame-interval",
        type=float,
        default=1.0,
        help="Seconds between simulator frame inspections (minimum 0.25).",
    )
    parser.add_argument(
        "--frame-threshold",
        type=int,
        default=4,
        help="Ignore per-channel pixel changes at or below this value.",
    )
    return parser.parse_args(argv)


def validate(args):
    manifest = ThemeManifest.load(args.theme)
    if manifest.engine != "html":
        raise ThemeValidationError("The preview command requires an HTML theme")
    if args.frame_interval <= 0:
        raise ThemeValidationError("--frame-interval must be greater than zero")
    if not 0 <= args.frame_threshold <= 255:
        raise ThemeValidationError("--frame-threshold must be between 0 and 255")
    return manifest


def build_collector(args):
    if args.real_sensors:
        source = RealSensorSource(
            network_interface=args.network_interface,
        )
        return SensorSnapshotCollector(source.readers()), "real"
    return SensorSnapshotCollector(demo_readers()), "synthetic"


def run_check(manifest, args):
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

    try:
        from PIL import Image  # noqa: F401
    except Exception as exc:
        print(f"Frame pipeline: unavailable — {exc}")
        return 2
    print("Frame pipeline: available")

    if args.real_sensors:
        try:
            collector, _source_name = build_collector(args)
            snapshot = collector.collect()
            sections = ", ".join(sorted(snapshot.data))
            print(f"Real sensor adapter: available ({sections})")
            if snapshot.errors:
                print(
                    "Real sensor warnings: "
                    + "; ".join(
                        f"{name}={message}"
                        for name, message in snapshot.errors.items()
                    )
                )
        except Exception as exc:
            print(f"Real sensor adapter: unavailable — {exc}")
            return 2
    return 0


def run_preview(manifest, args):
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import GLib, Gtk
    except Exception as exc:
        raise WebKitUnavailableError("GTK4 GI bindings are required") from exc

    collector, source_name = build_collector(args)
    engine = HtmlThemeEngine()
    frame_pipeline = FramePipeline(
        pixel_threshold=args.frame_threshold,
    )

    class PreviewApplication(Gtk.Application):
        def __init__(self):
            super().__init__(
                application_id="io.github.turing.HtmlThemePreview"
            )
            self.window = None
            self._snapshot_scheduled = False
            self._frame_capture_busy = False

        def do_activate(self):
            if self.window is not None:
                self.window.present()
                return
            engine.load(manifest)
            self.window = Gtk.ApplicationWindow(application=self)
            self.window.set_title(
                f"HTML Theme Preview — {manifest.name} — {source_name}"
            )
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
                if args.snapshot and not self._snapshot_scheduled:
                    self._snapshot_scheduled = True

                    def export_snapshot():
                        def finished(error):
                            if error:
                                print(
                                    f"Snapshot failed: {error}",
                                    file=sys.stderr,
                                )
                            else:
                                print(
                                    f"Snapshot written to {args.snapshot}"
                                )

                        engine.snapshot_png(args.snapshot, finished)
                        return False

                    GLib.timeout_add(1200, export_snapshot)
                return True

            update_theme()
            GLib.timeout_add(interval_ms, update_theme)

            if args.inspect_frames:
                frame_interval_ms = max(
                    250,
                    int(round(args.frame_interval * 1000)),
                )

                def inspect_frame():
                    if self._frame_capture_busy:
                        return True
                    self._frame_capture_busy = True
                    started = time.monotonic()

                    def finished(payload, error):
                        self._frame_capture_busy = False
                        if error is not None or payload is None:
                            print(
                                f"Frame inspection failed: {error}",
                                file=sys.stderr,
                            )
                            return
                        try:
                            frame, analysis = frame_pipeline.process_png(
                                payload
                            )
                            output = write_frame_artifacts(
                                args.inspect_frames,
                                frame,
                                analysis,
                            )
                            elapsed_ms = (
                                time.monotonic() - started
                            ) * 1000.0
                            mode = (
                                "full"
                                if analysis.full_refresh
                                else "partial"
                            )
                            message = (
                                f"FRAME {analysis.sequence:04d} "
                                f"changed={analysis.change_ratio * 100:5.1f}% "
                                f"regions={len(analysis.regions):02d} "
                                f"mode={mode} capture={elapsed_ms:5.1f}ms "
                                f"output={output}"
                            )
                            print(message)
                            if self.window is not None:
                                self.window.set_title(
                                    f"HTML Theme Preview — {manifest.name} — "
                                    f"{source_name} — "
                                    f"{analysis.change_ratio * 100:.1f}% / "
                                    f"{len(analysis.regions)} region(s)"
                                )
                        except Exception as exc:
                            print(
                                f"Frame pipeline failed: {exc}",
                                file=sys.stderr,
                            )

                    engine.snapshot_png_bytes(finished)
                    return True

                def start_frame_inspector():
                    inspect_frame()
                    GLib.timeout_add(frame_interval_ms, inspect_frame)
                    return False

                GLib.timeout_add(1400, start_frame_inspector)

        def do_shutdown(self):
            engine.close()
            Gtk.Application.do_shutdown(self)

    return PreviewApplication().run([])


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    try:
        manifest = validate(args)
        if args.check:
            return run_check(manifest, args)
        return run_preview(manifest, args)
    except (ThemeValidationError, WebKitUnavailableError, ValueError) as exc:
        print(f"HTML theme preview error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
