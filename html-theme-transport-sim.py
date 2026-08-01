#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Watch HTML frame artifacts and simulate display pixel transport."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

from library.frame_pipeline import FrameAnalysis, FrameRegion
from library.rev_c_protocol_simulator import (
    RevCProtocolSimulator,
    write_rev_c_protocol_artifacts,
)
from library.simulated_display_transport import (
    PROFILES,
    SimulatedDisplayTransport,
    get_transport_profile,
    write_transport_artifacts,
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
        "--output",
        type=Path,
        default=Path("/tmp/turing-html-transport"),
        help="Directory for virtual framebuffer and transport metrics.",
    )
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        default="rev-c-2inch",
        help="Display pixel profile to simulate.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.20,
        help="Polling interval in seconds.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process one coherent frame and exit.",
    )
    parser.add_argument(
        "--rev-c-framing",
        action="store_true",
        help=(
            "Wrap rev-c-2inch packets in exact in-memory 250-byte protocol "
            "blocks and validate them without opening a serial port."
        ),
    )
    return parser.parse_args(argv)


def analysis_from_payload(payload) -> FrameAnalysis:
    regions = tuple(
        FrameRegion(
            x=int(region["x"]),
            y=int(region["y"]),
            width=int(region["width"]),
            height=int(region["height"]),
        )
        for region in payload.get("regions", ())
    )
    return FrameAnalysis(
        sequence=int(payload["sequence"]),
        width=int(payload["width"]),
        height=int(payload["height"]),
        changed_pixels=int(payload.get("changedPixels", 0)),
        total_pixels=int(
            payload.get(
                "totalPixels",
                int(payload["width"]) * int(payload["height"]),
            )
        ),
        change_ratio=float(payload.get("changeRatio", 0.0)),
        regions=regions,
        full_refresh=bool(payload.get("fullRefresh", False)),
    )


def load_coherent_frame(
    directory: Path,
) -> Optional[Tuple[Image.Image, FrameAnalysis]]:
    """Read artifacts only after metrics have caught up with the PNG."""
    root = Path(directory).expanduser().resolve()
    image_path = root / "latest.png"
    metrics_path = root / "metrics.json"
    try:
        image_before = image_path.stat()
        metrics_before = metrics_path.stat()
    except OSError:
        return None

    # write_frame_artifacts publishes metrics last. A newer PNG means the next
    # bundle is still being written, so wait for its metrics instead of mixing
    # two sequences.
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

    analysis = analysis_from_payload(payload)
    if frame.size != (analysis.width, analysis.height):
        return None
    return frame, analysis


def _initial_full_analysis(analysis: FrameAnalysis) -> FrameAnalysis:
    region = FrameRegion(0, 0, analysis.width, analysis.height)
    return replace(
        analysis,
        changed_pixels=analysis.width * analysis.height,
        total_pixels=analysis.width * analysis.height,
        change_ratio=1.0,
        regions=(region,),
        full_refresh=True,
    )


def run(args) -> int:
    if args.interval <= 0:
        print("--interval must be greater than zero", file=sys.stderr)
        return 2
    if args.rev_c_framing and args.profile != "rev-c-2inch":
        print(
            "--rev-c-framing requires --profile rev-c-2inch",
            file=sys.stderr,
        )
        return 2

    profile = get_transport_profile(args.profile)
    transport = SimulatedDisplayTransport(profile)
    protocol = RevCProtocolSimulator() if args.rev_c_framing else None
    last_sequence = None
    processed = 0

    print(f"Transport profile: {profile.name}")
    print(f"  full:    {profile.full_encoding}")
    print(f"  partial: {profile.partial_encoding}")
    print("Physical I/O: disabled")
    print(
        "Rev. C framing: "
        + ("enabled (memory/files only)" if protocol else "disabled")
    )

    try:
        while True:
            loaded = load_coherent_frame(args.input)
            if loaded is None:
                if args.once:
                    print(
                        "No coherent frame bundle is available yet",
                        file=sys.stderr,
                    )
                    return 2
                time.sleep(args.interval)
                continue

            frame, analysis = loaded
            if analysis.sequence == last_sequence:
                if args.once and processed:
                    return 0
                time.sleep(args.interval)
                continue

            if (
                last_sequence is None
                or analysis.sequence < last_sequence
                or transport.framebuffer is None
            ):
                transport.reset()
                if protocol is not None:
                    protocol.reset()
                analysis = _initial_full_analysis(analysis)

            result = transport.submit(frame, analysis)
            framebuffer = transport.framebuffer
            assert framebuffer is not None
            output = write_transport_artifacts(
                args.output,
                frame,
                framebuffer,
                result,
            )

            protocol_suffix = ""
            protocol_valid = True
            if protocol is not None:
                protocol_result = protocol.submit(result)
                write_rev_c_protocol_artifacts(
                    args.output,
                    protocol_result,
                )
                protocol_valid = protocol_result.valid
                protocol_suffix = (
                    f" wire={protocol_result.wire_bytes:7d} "
                    f"framing={'ok' if protocol_valid else 'FAILED'} "
                    f"wire-saved="
                    f"{protocol_result.wire_savings_ratio * 100:5.1f}%"
                )

            mode = "full" if result.full_refresh else "partial"
            print(
                f"TRANSPORT {result.sequence:04d} "
                f"profile={result.profile} "
                f"encoding={result.encoding} "
                f"mode={mode} "
                f"packets={len(result.packets):02d} "
                f"bytes={result.simulated_bytes:7d} "
                f"saved={result.savings_ratio * 100:5.1f}% "
                f"roundtrip={'ok' if result.roundtrip_matches else 'FAILED'}"
                f"{protocol_suffix} "
                f"output={output}",
                flush=True,
            )
            last_sequence = result.sequence
            processed += 1
            if not protocol_valid:
                return 3
            if args.once:
                return 0
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 130


def main(argv=None) -> int:
    return run(parse_args(argv or sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
