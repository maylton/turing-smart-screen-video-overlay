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
from library.html_theme_engine import HtmlThemeEngine, WebKitGtk3OffscreenBackend
from library.html_hybrid import (
    OVERLAY_SELECTOR,
    overlay_frames_equal,
    overlay_layer_script,
    validate_native_video,
)
from library.html_native_video_sink import HtmlNativeVideoSink
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
SUPPORTED_NATIVE_VIDEO_SIZES = {'2.1"', '2.8"'}


def schedule_once(glib, delay_ms, callback, source_ids) -> int:
    """Schedule a GTK callback once, even when the callback returns True."""
    holder = {}

    def invoke():
        source_ids.discard(holder.get("source_id"))
        callback()
        return False

    source_id = glib.timeout_add(delay_ms, invoke)
    holder["source_id"] = source_id
    source_ids.add(source_id)
    return source_id


def configured_display_size(config: dict, root: Path = ROOT) -> str:
    """Use the preserved YAML theme as the Rev. C physical-size safety hint."""
    legacy = config.get("config", {})
    legacy = legacy if isinstance(legacy, dict) else {}
    theme_name = str(legacy.get("THEME") or "").strip()
    themes_root = (Path(root) / "res" / "themes").resolve()
    theme_dir = (themes_root / theme_name).resolve()
    try:
        theme_dir.relative_to(themes_root)
    except ValueError:
        return ""
    theme_file = theme_dir / "theme.yaml"
    try:
        payload = yaml.safe_load(theme_file.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return ""
    display = payload.get("display", {})
    if not isinstance(display, dict):
        return ""
    return str(display.get("DISPLAY_SIZE") or "").strip()


def _args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--theme", type=Path, required=True)
    return parser.parse_args(argv)


def _safe_engine(webkit):
    def factory(manifest):
        return WebKitGtk3OffscreenBackend(manifest)
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
    brightness = int(display.get("BRIGHTNESS", 20))
    hybrid_spec = manifest.native_video_overlay
    if hybrid_spec is not None:
        display_size = configured_display_size(config)
        if display_size not in SUPPORTED_NATIVE_VIDEO_SIZES:
            raise ThemeValidationError(
                "native HTML video currently requires a configured Rev. C "
                "2.1/2.8-inch display hint"
            )
        # Local codec/size/profile validation happens before the driver factory
        # can construct LcdCommRevC (whose constructor opens serial).
        validate_native_video(manifest)

    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    legacy_config = config.get("config", {})
    legacy_config = legacy_config if isinstance(legacy_config, dict) else {}
    collector = SensorSnapshotCollector(
        RealSensorSource(
            network_interface=network_interface,
            weather_settings=legacy_config,
            hardware_sensors=str(legacy_config.get("HW_SENSORS") or "AUTO"),
        ).readers()
    )
    engine = _safe_engine(WebKit2)
    transport_engine = (
        None
        if hybrid_spec is not None
        else SimulatedDisplayTransport(get_transport_profile("rev-c-2inch"))
    )
    protocol_engine = (
        None if hybrid_spec is not None else RevCProtocolSimulator(display_stride=480)
    )
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
            self.last_overlay = None
            self.diagnostic_pipeline = FramePipeline(pixel_threshold=4)
            self._application_held = True
            self.hold()

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
                if self._application_held:
                    self._application_held = False
                    self.release()
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
                    if hybrid_spec is not None:
                        if self.sink is not None:
                            self.sink.check_health()
                        if (
                            self.last_overlay is not None
                            and overlay_frames_equal(self.last_overlay, frame)
                        ):
                            return
                        if self.sink is None:
                            self.sink = HtmlNativeVideoSink(
                                frame,
                                hybrid_spec,
                                port=port,
                                brightness=brightness,
                                refresh_interval=1.0 / manifest.refresh_rate,
                            )
                        else:
                            self.sink.submit(frame)
                        self.last_overlay = frame.copy()
                        if diagnostic_dir:
                            analysis = self.diagnostic_pipeline.process(frame)
                            write_frame_artifacts(Path(diagnostic_dir), frame, analysis)
                    elif self.sink is None:
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
                    if diagnostic_dir and hybrid_spec is None:
                        write_frame_artifacts(Path(diagnostic_dir), frame, plan.analysis if self.planner and 'plan' in locals() else analysis)
                except Exception as exc:
                    print(f"HTML renderer stopped safely: {exc}", file=sys.stderr, flush=True)
                    self.stop()

            engine.snapshot_png_bytes(finished)
            return True

        def update_and_capture(self):
            if self.closing or self.capture_busy:
                return not self.closing

            def updated(error):
                if self.closing:
                    return
                if error is not None:
                    print(f"HTML update failed: {error}", file=sys.stderr, flush=True)
                    self.stop()
                    return
                # Wait one paint turn after JavaScript has completed before
                # asking WebKit for a texture.
                schedule_once(GLib, 12, self.capture, self.source_ids)

            engine.update_async(collector.collect(), updated)
            return True

        def start_updates(self, error=None):
            if error is not None:
                print(f"HTML layer configuration failed: {error}", file=sys.stderr, flush=True)
                self.stop()
                return
            interval = max(500, int(round(1000 / manifest.refresh_rate)))
            self.update_and_capture()
            source_id = GLib.timeout_add(interval, self.update_and_capture)
            self.source_ids.add(source_id)

        def do_activate(self):
            engine.load(manifest)
            if hybrid_spec is not None:
                engine.set_transparent_background()
                engine.evaluate(
                    overlay_layer_script(OVERLAY_SELECTOR),
                    self.start_updates,
                )
            else:
                # evaluate() queues until LOAD_FINISHED, replacing the old
                # fixed 1.2-second startup sleep with an explicit barrier.
                engine.evaluate("true", self.start_updates)
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
