# SPDX-License-Identifier: GPL-3.0-or-later
"""GTK-main-loop worker for the experimental integrated HTML renderer."""

from __future__ import annotations

import argparse
import os
import signal
import sys
from pathlib import Path

import yaml

from library.budgeted_frame_planner import BudgetedFramePlanner
from library.frame_pipeline import FramePipeline, decode_png_frame, write_frame_artifacts
from library.html_theme_engine import HtmlThemeEngine, WebKitGtkBackend
from library.real_sensor_source import RealSensorSource
from library.rev_c_integrated_sink import (
    MAX_REGIONS_PER_CYCLE,
    MAX_WIRE_BYTES_PER_CYCLE,
    IntegratedRevCSink,
)
from library.rev_c_production_parity import compare_with_production_driver
from library.rev_c_protocol_simulator import RevCProtocolSimulator
from library.sensor_snapshot import SensorSnapshotCollector
from library.simulated_display_transport import SimulatedDisplayTransport, get_transport_profile
from library.theme_engine import ThemeManifest, ThemeValidationError


ROOT = Path(__file__).resolve().parents[1]


def _args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--theme", type=Path, required=True)
    return parser.parse_args(argv)


def _safe_engine(webkit):
    def factory(manifest):
        backend = WebKitGtkBackend(manifest)
        settings = backend.view.get_settings()
        policy = getattr(getattr(webkit, "HardwareAccelerationPolicy", None), "NEVER", None)
        setter = getattr(settings, "set_hardware_acceleration_policy", None)
        if callable(setter) and policy is not None:
            setter(policy)
        for name in ("set_enable_webgl", "set_enable_accelerated_2d_canvas"):
            disable = getattr(settings, name, None)
            if callable(disable):
                disable(False)
        return backend
    return HtmlThemeEngine(factory)


def run(theme: Path) -> int:
    manifest = ThemeManifest.load(theme)
    if manifest.engine != "html" or manifest.network or "sensors" not in manifest.permissions:
        raise ThemeValidationError("unsafe or non-HTML theme selected")
    if (manifest.width, manifest.height) != (480, 480):
        raise ThemeValidationError("integrated Rev. C HTML themes must be 480x480")

    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8")) or {}
    display = config.get("display", {})
    if str(display.get("REVISION", "")) != "C":
        raise ThemeValidationError("integrated HTML transport currently supports Rev. C only")
    port = str(config.get("config", {}).get("COM_PORT") or "AUTO")
    network_interface = str(config.get("config", {}).get("ETH") or "")

    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("WebKit", "6.0")
    from gi.repository import GLib, Gtk, WebKit

    collector = SensorSnapshotCollector(RealSensorSource(network_interface=network_interface).readers())
    engine = _safe_engine(WebKit)
    transport_engine = SimulatedDisplayTransport(get_transport_profile("rev-c-2inch"))
    protocol_engine = RevCProtocolSimulator(display_stride=480)
    diagnostic_dir = os.environ.get("TURING_HTML_FRAME_ARTIFACTS", "").strip()

    class Worker(Gtk.Application):
        def __init__(self):
            super().__init__(application_id="io.github.turing.HtmlRendererWorker")
            self.window = None
            self.sink = None
            self.planner = None
            self.capture_busy = False
            self.closing = False
            self.source_ids = set()

        def stop(self, *_args):
            if self.closing:
                return False
            self.closing = True
            for source_id in tuple(self.source_ids):
                try: GLib.source_remove(source_id)
                except Exception: pass
            self.source_ids.clear()
            try:
                if self.sink is not None: self.sink.close()
            finally:
                self.sink = None
                engine.close()
                self.quit()
            return False

        def capture(self):
            if self.closing or self.capture_busy:
                return not self.closing
            self.capture_busy = True

            def finished(payload, error):
                self.capture_busy = False
                if self.closing:
                    return
                if error is not None or payload is None:
                    print(f"HTML frame capture failed: {error}", file=sys.stderr, flush=True)
                    self.stop()
                    return
                try:
                    frame = decode_png_frame(payload, (480, 480))
                    if self.sink is None:
                        pipeline = FramePipeline(pixel_threshold=0)
                        analysis = pipeline.process(frame)
                        transport = transport_engine.submit(frame, analysis)
                        protocol = protocol_engine.submit(transport)
                        parity = compare_with_production_driver(frame, transport, protocol)
                        self.sink = IntegratedRevCSink(frame, protocol, parity, port=port)
                        self.planner = BudgetedFramePlanner(
                            frame,
                            atomic_regions=manifest.atomic_regions,
                            initial_sequence=analysis.sequence,
                            pixel_threshold=4,
                        )
                    else:
                        plan = self.planner.plan(
                            frame,
                            max_regions=MAX_REGIONS_PER_CYCLE,
                            max_wire_bytes=MAX_WIRE_BYTES_PER_CYCLE,
                        )
                        transport = transport_engine.submit(frame, plan.analysis)
                        protocol = protocol_engine.submit(transport)
                        parity = compare_with_production_driver(frame, transport, protocol)
                        self.sink.submit(frame, transport, protocol, parity)
                        self.planner.commit(frame, plan)
                    if diagnostic_dir:
                        write_frame_artifacts(Path(diagnostic_dir), frame, plan.analysis if self.planner and 'plan' in locals() else analysis)
                except Exception as exc:
                    print(f"HTML renderer stopped safely: {exc}", file=sys.stderr, flush=True)
                    self.stop()

            engine.snapshot_png_bytes(finished)
            return True

        def do_activate(self):
            engine.load(manifest)
            self.window = Gtk.ApplicationWindow(application=self)
            self.window.set_default_size(480, 480)
            self.window.set_resizable(False)
            self.window.set_child(engine.render())
            self.window.connect("close-request", self.stop)
            self.window.present()
            engine.update(collector.collect())
            interval = max(500, int(round(1000 / manifest.refresh_rate)))

            def tick():
                if self.closing: return False
                engine.update(collector.collect())
                return self.capture()
            source_id = GLib.timeout_add(interval, tick)
            self.source_ids.add(source_id)
            def first_capture():
                self.capture()
                return False
            self.source_ids.add(GLib.timeout_add(1200, first_capture))
            if hasattr(GLib, "unix_signal_add"):
                for signum in (signal.SIGINT, signal.SIGTERM):
                    self.source_ids.add(GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signum, self.stop))

    return int(Worker().run([]))


def main(argv=None) -> int:
    try:
        return run(_args(sys.argv[1:] if argv is None else argv).theme)
    except Exception as exc:
        print(f"HTML renderer startup failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
