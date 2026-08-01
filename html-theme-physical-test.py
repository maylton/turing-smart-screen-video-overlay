#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Preflight and guarded one-shot physical test for HTML themes on Rev. C."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

from library.frame_pipeline import FrameAnalysis, FrameRegion
from library.rev_c_physical_sink import (
    CONFIRMATION_TEXT,
    PhysicalWriteRefused,
    write_full_frame_once,
)
from library.rev_c_production_parity import compare_with_production_driver
from library.rev_c_protocol_simulator import RevCProtocolSimulator
from library.simulated_display_transport import (
    SimulatedDisplayTransport,
    get_transport_profile,
)


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("/tmp/turing-html-frames"),
        help="Directory produced by html-theme-preview-gtk.py --inspect-frames.",
    )
    parser.add_argument(
        "--port",
        default="",
        help="Explicit Rev. C serial device, for example /dev/ttyACM0.",
    )
    parser.add_argument(
        "--write-once",
        action="store_true",
        help="After all preflight checks pass, write exactly one full frame.",
    )
    parser.add_argument(
        "--monitor-stopped",
        action="store_true",
        help="Acknowledge that the normal monitor process is stopped.",
    )
    parser.add_argument(
        "--confirm",
        default="",
        help=f"Required write confirmation token: {CONFIRMATION_TEXT}",
    )
    return parser.parse_args(argv)


def load_coherent_frame(directory: Path) -> Optional[Tuple[Image.Image, int]]:
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


def build_full_parity(frame: Image.Image, sequence: int):
    width, height = frame.size
    region = FrameRegion(0, 0, width, height)
    analysis = FrameAnalysis(
        sequence=sequence,
        width=width,
        height=height,
        changed_pixels=width * height,
        total_pixels=width * height,
        change_ratio=1.0,
        regions=(region,),
        full_refresh=True,
    )
    transport_engine = SimulatedDisplayTransport(
        get_transport_profile("rev-c-2inch")
    )
    transport = transport_engine.submit(frame, analysis)
    protocol = RevCProtocolSimulator(display_stride=height).submit(transport)
    parity = compare_with_production_driver(frame, transport, protocol)
    return transport, protocol, parity


def run(args) -> int:
    loaded = load_coherent_frame(args.input)
    if loaded is None:
        print(
            "No coherent HTML frame bundle is available. Produce one with "
            "html-theme-preview-gtk.py --inspect-frames first.",
            file=sys.stderr,
        )
        return 2

    frame, sequence = loaded
    if frame.size != (480, 480):
        print(
            f"Physical Rev. C test requires 480x480; received {frame.size}",
            file=sys.stderr,
        )
        return 2

    try:
        transport, protocol, parity = build_full_parity(frame, sequence)
    except Exception as exc:
        print(f"Preflight serializer validation failed: {exc}", file=sys.stderr)
        return 3

    print(f"Frame: {frame.width}x{frame.height} sequence={sequence}")
    print(f"Transport roundtrip: {'ok' if transport.roundtrip_matches else 'FAILED'}")
    print(f"Rev. C framing: {'ok' if protocol.valid else 'FAILED'}")
    print(f"Production parity: {'ok' if parity.valid else 'FAILED'}")
    print(f"Wire bytes: {len(parity.production_wire)}")
    print("Physical I/O: disabled during preflight")

    if not (
        transport.roundtrip_matches
        and protocol.valid
        and parity.valid
    ):
        return 3

    if not args.write_once:
        print("Preflight passed. No serial device was opened.")
        return 0

    try:
        result = write_full_frame_once(
            frame,
            parity,
            port=args.port,
            confirmation=args.confirm,
            monitor_stopped=args.monitor_stopped,
        )
    except PhysicalWriteRefused as exc:
        print(f"Physical write refused: {exc}", file=sys.stderr)
        return 4
    except Exception as exc:
        print(f"Physical write failed: {exc}", file=sys.stderr)
        return 5

    print(
        "Physical write completed: "
        f"port={result.port} frame={result.width}x{result.height} "
        f"closed={'yes' if result.serial_closed else 'no'}"
    )
    return 0


def main(argv=None) -> int:
    return run(parse_args(argv or sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
