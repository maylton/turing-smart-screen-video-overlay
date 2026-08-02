#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Preflight and run a status-observable Rev. C HTML theme diagnostic."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

from library.atomic_regions import AtomicRegion
from library.dirty_region_optimizer import optimize_frame_analysis
from library.frame_pipeline import FramePipeline
from library.rev_c_live_sink import (
    LIVE_CONFIRMATION_TEXT,
    GuardedRevCLiveSession,
    LiveWriteRefused,
)
from library.rev_c_production_parity import compare_with_production_driver
from library.rev_c_protocol_simulator import RevCProtocolSimulator
from library.simulated_display_transport import (
    SimulatedDisplayTransport,
    get_transport_profile,
)
from library.theme_engine import ThemeManifest, ThemeValidationError


ROOT = Path(__file__).resolve().parent
DEFAULT_THEME = ROOT / "res" / "themes" / "html-demo"
DEFAULT_STATUS_LOG = Path("/tmp/turing-html-physical-status.jsonl")
PLANNING_MAX_REGIONS = 64


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("/tmp/turing-html-frames"),
    )
    parser.add_argument(
        "--theme",
        type=Path,
        default=DEFAULT_THEME,
        help="HTML theme whose manifest defines atomic widget regions.",
    )
    parser.add_argument("--port", default="")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Open the explicit port after preflight and run a bounded session.",
    )
    parser.add_argument("--monitor-stopped", action="store_true")
    parser.add_argument(
        "--confirm",
        default="",
        help=f"Required live confirmation token: {LIVE_CONFIRMATION_TEXT}",
    )
    parser.add_argument("--max-frames", type=int, default=5)
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--poll-interval", type=float, default=0.10)
    parser.add_argument("--stale-after", type=float, default=10.0)
    parser.add_argument(
        "--max-regions",
        type=int,
        default=8,
        help="Maximum UPDATE_BITMAP transactions in one physical batch.",
    )
    parser.add_argument(
        "--max-total-regions",
        type=int,
        default=32,
        help=(
            "Maximum tight regions in one logical update before refusing it; "
            "regions are never merged merely to fit --max-regions."
        ),
    )
    parser.add_argument("--max-wire-bytes", type=int, default=300_000)
    parser.add_argument(
        "--region-pacing",
        type=float,
        default=0.25,
        help="Seconds to wait between regions inside one physical batch.",
    )
    parser.add_argument(
        "--batch-pacing",
        type=float,
        default=0.35,
        help="Seconds to wait at boundaries between physical region batches.",
    )
    parser.add_argument(
        "--status-min-bytes",
        type=int,
        default=1,
        help="Stop if a requested hardware status read returns fewer bytes.",
    )
    parser.add_argument(
        "--status-log",
        type=Path,
        default=DEFAULT_STATUS_LOG,
        help="JSONL file containing complete captured status responses.",
    )
    return parser.parse_args(argv)


def load_coherent_frame(
    directory: Path,
) -> Optional[Tuple[Image.Image, int]]:
    root = Path(directory).expanduser().resolve()
    image_path = root / "latest.png"
    metrics_path = root / "metrics.json"
    try:
        image_before = image_path.stat()
        metrics_before = metrics_path.stat()
    except OSError:
        return None

    if image_before.st_mtime_ns > metrics_before.st_mtime_ns:
        return None

    try:
        payload = json.loads(metrics_path.read_text(encoding="utf-8"))
        with Image.open(image_path) as opened:
            frame = opened.convert("RGBA")
            frame.load()
        image_after = image_path.stat()
        metrics_after = metrics_path.stat()
    except (OSError, ValueError, json.JSONDecodeError):
        return None

    if (
        image_before.st_mtime_ns != image_after.st_mtime_ns
        or metrics_before.st_mtime_ns != metrics_after.st_mtime_ns
    ):
        return None
    if frame.size != (int(payload["width"]), int(payload["height"])):
        return None
    return frame, int(payload["sequence"])


def build_engines(frame: Image.Image):
    # Keep component discovery generous. Planning remains independent from the
    # much smaller number of physical exchanges permitted in each batch.
    pipeline = FramePipeline(
        tile_size=16,
        pixel_threshold=0,
        full_refresh_ratio=0.45,
        max_regions=PLANNING_MAX_REGIONS,
    )
    transport = SimulatedDisplayTransport(
        get_transport_profile("rev-c-2inch")
    )
    protocol = RevCProtocolSimulator(display_stride=frame.height)
    return pipeline, transport, protocol


def validate_frame(
    frame: Image.Image,
    pipeline: FramePipeline,
    transport_engine: SimulatedDisplayTransport,
    protocol_engine: RevCProtocolSimulator,
    *,
    atomic_regions: Tuple[AtomicRegion, ...] = (),
):
    previous = pipeline.previous
    analysis = pipeline.process(frame)
    analysis = optimize_frame_analysis(
        previous,
        frame,
        analysis,
        tile_size=pipeline.tile_size,
        pixel_threshold=pipeline.pixel_threshold,
        max_regions=PLANNING_MAX_REGIONS,
        full_refresh_ratio=pipeline.full_refresh_ratio,
        atomic_regions=atomic_regions,
    )
    transport = transport_engine.submit(frame, analysis)
    protocol = protocol_engine.submit(transport)
    parity = compare_with_production_driver(frame, transport, protocol)
    return analysis, transport, protocol, parity


def status_summary(batch) -> str:
    return (
        f"status={len(batch.samples):02d} "
        f"bytes={batch.minimum_received_bytes}-"
        f"{batch.maximum_received_bytes} "
        f"nonzero={batch.total_nonzero_bytes} "
        f"sha={batch.fingerprint} "
        f"io={batch.elapsed_ms:.1f}ms"
    )


def write_status_record(
    path: Path,
    *,
    kind: str,
    source_sequence: int,
    validated_sequence: int,
    batch,
    reset: bool = False,
) -> Path:
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "recordedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "kind": kind,
        "sourceSequence": int(source_sequence),
        "validatedSequence": int(validated_sequence),
        "status": batch.as_dict(),
    }
    mode = "w" if reset else "a"
    with destination.open(mode, encoding="utf-8") as output:
        output.write(json.dumps(record, sort_keys=True) + "\n")
        output.flush()
    return destination


def load_theme_manifest(theme: Path) -> ThemeManifest:
    manifest = ThemeManifest.load(theme)
    if manifest.engine != "html":
        raise ThemeValidationError(
            "the physical HTML diagnostic requires an HTML theme"
        )
    if (manifest.width, manifest.height) != (480, 480):
        raise ThemeValidationError(
            "the Rev. C physical diagnostic requires a 480x480 theme"
        )
    return manifest


def run(args) -> int:
    if args.poll_interval <= 0:
        print("--poll-interval must be greater than zero", file=sys.stderr)
        return 2
    if args.stale_after <= 0:
        print("--stale-after must be greater than zero", file=sys.stderr)
        return 2

    try:
        manifest = load_theme_manifest(args.theme)
    except ThemeValidationError as exc:
        print(f"HTML theme validation failed: {exc}", file=sys.stderr)
        return 2

    loaded = load_coherent_frame(args.input)
    if loaded is None:
        print("No coherent HTML frame bundle is available", file=sys.stderr)
        return 2
    initial_frame, source_sequence = loaded
    if initial_frame.size != (480, 480):
        print(
            f"Rev. C live test requires 480x480; received {initial_frame.size}",
            file=sys.stderr,
        )
        return 2

    pipeline, transport_engine, protocol_engine = build_engines(initial_frame)
    try:
        _analysis, initial_transport, initial_protocol, initial_parity = (
            validate_frame(
                initial_frame,
                pipeline,
                transport_engine,
                protocol_engine,
                atomic_regions=manifest.atomic_regions,
            )
        )
    except Exception as exc:
        print(f"Initial preflight failed: {exc}", file=sys.stderr)
        return 3

    print(f"HTML theme: {manifest.name}")
    print(f"Atomic widget regions: {len(manifest.atomic_regions)}")
    print(f"Initial frame: 480x480 source-sequence={source_sequence}")
    print(
        "Transport roundtrip: "
        + ("ok" if initial_transport.roundtrip_matches else "FAILED")
    )
    print(
        "Rev. C framing: " + ("ok" if initial_protocol.valid else "FAILED")
    )
    print(
        "Production parity: " + ("ok" if initial_parity.valid else "FAILED")
    )
    print(f"Initial wire bytes: {initial_protocol.wire_bytes}")
    print(
        "Diagnostic limits: "
        f"frames={args.max_frames} "
        f"regions-per-batch={args.max_regions} "
        f"total-regions={args.max_total_regions} "
        f"interval={args.interval:.2f}s "
        f"region-pacing={args.region_pacing:.2f}s "
        f"batch-pacing={args.batch_pacing:.2f}s"
    )

    if not (
        initial_transport.roundtrip_matches
        and initial_protocol.valid
        and initial_parity.valid
    ):
        return 3

    if not args.live:
        print("Preflight passed. No serial device was opened.")
        return 0

    try:
        session = GuardedRevCLiveSession(
            initial_frame,
            initial_protocol,
            initial_parity,
            port=args.port,
            confirmation=args.confirm,
            monitor_stopped=args.monitor_stopped,
            max_partial_frames=args.max_frames,
            max_duration=args.duration,
            min_interval=args.interval,
            max_regions=args.max_total_regions,
            batch_regions=args.max_regions,
            max_wire_bytes=args.max_wire_bytes,
            region_pacing=args.region_pacing,
            batch_pacing=args.batch_pacing,
            minimum_status_bytes=args.status_min_bytes,
        )
    except LiveWriteRefused as exc:
        print(f"Live session refused: {exc}", file=sys.stderr)
        return 4
    except Exception as exc:
        print(f"Live session failed to start: {exc}", file=sys.stderr)
        return 5

    initial_status = session.initial_status_batch
    status_log = write_status_record(
        args.status_log,
        kind="initial-full",
        source_sequence=source_sequence,
        validated_sequence=initial_transport.sequence,
        batch=initial_status,
        reset=True,
    )
    print("Initial physical frame written with observable status reads.")
    print(f"INITIAL {status_summary(initial_status)}")
    print(f"Status log: {status_log}")

    last_source_sequence = source_sequence
    last_new_frame_at = time.monotonic()

    try:
        with session:
            while session.can_continue:
                loaded = load_coherent_frame(args.input)
                if loaded is None:
                    if (
                        time.monotonic() - last_new_frame_at
                        >= args.stale_after
                    ):
                        print(
                            "Producer artifacts became stale; stopping safely."
                        )
                        break
                    time.sleep(args.poll_interval)
                    continue

                frame, current_source_sequence = loaded
                if current_source_sequence < last_source_sequence:
                    print(
                        "Producer sequence moved backwards; stopping safely.",
                        file=sys.stderr,
                    )
                    return 6
                if current_source_sequence == last_source_sequence:
                    if (
                        time.monotonic() - last_new_frame_at
                        >= args.stale_after
                    ):
                        print("Producer became stale; stopping safely.")
                        break
                    time.sleep(args.poll_interval)
                    continue

                wait = session.seconds_until_next_write
                if wait > 0:
                    time.sleep(min(args.poll_interval, wait))
                    continue

                try:
                    analysis, transport, protocol, parity = validate_frame(
                        frame,
                        pipeline,
                        transport_engine,
                        protocol_engine,
                        atomic_regions=manifest.atomic_regions,
                    )
                except Exception as exc:
                    print(
                        f"Live frame validation failed: {exc}",
                        file=sys.stderr,
                    )
                    return 6

                if analysis.full_refresh:
                    print(
                        "A later frame requires a full refresh; "
                        "stopping instead of writing it.",
                        file=sys.stderr,
                    )
                    return 6

                try:
                    update = session.submit_partial(
                        frame,
                        transport,
                        protocol,
                        parity,
                    )
                except LiveWriteRefused as exc:
                    print(f"Live update refused: {exc}", file=sys.stderr)
                    return 6
                except Exception as exc:
                    print(f"Live update failed: {exc}", file=sys.stderr)
                    return 7

                write_status_record(
                    args.status_log,
                    kind="partial",
                    source_sequence=current_source_sequence,
                    validated_sequence=update.sequence,
                    batch=update.status_batch,
                )
                print(
                    f"LIVE source={current_source_sequence:04d} "
                    f"validated={update.sequence:04d} "
                    f"regions={update.region_count:02d} "
                    f"batches={update.batch_count:02d} "
                    f"wire={update.wire_bytes:7d} "
                    f"frame={update.partial_frame_number:02d}/"
                    f"{session.max_partial_frames} "
                    f"{status_summary(update.status_batch)} "
                    "roundtrip=ok framing=ok production=ok",
                    flush=True,
                )
                last_source_sequence = current_source_sequence
                last_new_frame_at = time.monotonic()

            summary = session.close()
            print(
                "Live diagnostic completed: "
                f"partial-frames={summary.partial_frames_written} "
                f"status-responses={summary.status_responses} "
                f"serial-closed={'yes' if summary.serial_closed else 'no'}"
            )
            return 0
    except KeyboardInterrupt:
        summary = session.close()
        print(
            "\nLive diagnostic interrupted: "
            f"partial-frames={summary.partial_frames_written} "
            f"status-responses={summary.status_responses} "
            f"serial-closed={'yes' if summary.serial_closed else 'no'}"
        )
        return 130


def main(argv=None) -> int:
    return run(parse_args(argv or sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
