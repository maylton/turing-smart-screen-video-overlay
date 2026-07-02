#!/usr/bin/env python3
"""Structured command-line backend for profile-aware media preparation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from library.media_preparation import (
    ConversionSettings,
    MediaCommandError,
    alignment_offsets,
    cache_directory,
    convert_media,
    create_preview,
    effective_duration,
    probe_source,
    safe_output_name,
)
from library.media_profiles import (
    estimate_output_size,
    format_bytes,
    get_profile,
    list_profiles,
)

ROOT = Path(__file__).resolve().parent


def profile_from_args(args: argparse.Namespace):
    return get_profile(getattr(args, "profile", "active-theme"), ROOT)


def settings_from_args(args: argparse.Namespace) -> ConversionSettings:
    profile = profile_from_args(args)
    return ConversionSettings(
        target_width=profile.width,
        target_height=profile.height,
        profile_id=profile.id,
        encoder=profile.encoder,
        codec=profile.codec,
        pixel_format=profile.pixel_format,
        mode=args.mode,
        zoom=args.zoom,
        offset_x=args.x,
        offset_y=args.y,
        custom_width=args.width,
        custom_height=args.height,
        crop_left=args.crop_left,
        crop_right=args.crop_right,
        crop_top=args.crop_top,
        crop_bottom=args.crop_bottom,
        rotation=args.rotation,
        start=args.start,
        end=args.end,
        fps=args.fps,
        speed=args.speed,
        loop_count=args.loop_count,
        background_mode=args.background_mode,
        background=args.background,
        background_image=args.background_image,
        blur_strength=args.blur,
        crf=getattr(args, "crf", 20),
    )


def add_settings(parser: argparse.ArgumentParser, *, include_crf: bool) -> None:
    parser.add_argument("--profile", default="active-theme")
    parser.add_argument(
        "--mode",
        choices=("fit", "fill", "stretch", "original", "custom"),
        default="fit",
    )
    parser.add_argument("--zoom", type=float, default=1.0)
    parser.add_argument("--x", type=int, default=0)
    parser.add_argument("--y", type=int, default=0)
    parser.add_argument("--width", type=int, default=480)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--crop-left", type=int, default=0)
    parser.add_argument("--crop-right", type=int, default=0)
    parser.add_argument("--crop-top", type=int, default=0)
    parser.add_argument("--crop-bottom", type=int, default=0)
    parser.add_argument("--rotation", type=int, choices=(0, 90, 180, 270), default=0)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--end", type=float)
    parser.add_argument("--fps", type=int, choices=(24, 30), default=30)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--loop-count", type=int, default=0)
    parser.add_argument(
        "--background-mode",
        choices=("solid", "blur", "image"),
        default="solid",
    )
    parser.add_argument("--background", default="000000")
    parser.add_argument("--background-image")
    parser.add_argument("--blur", type=float, default=24.0)
    if include_crf:
        parser.add_argument("--crf", type=int, default=20)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Return structured JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("profiles", help="List active and reusable display profiles")

    probe = subparsers.add_parser("probe", help="Analyze a source GIF or video")
    probe.add_argument("source")

    preview = subparsers.add_parser("preview", help="Render one transformed preview frame")
    preview.add_argument("source")
    preview.add_argument("--output")
    add_settings(preview, include_crf=False)

    convert = subparsers.add_parser("convert", help="Prepare a profile-compatible MP4")
    convert.add_argument("source")
    convert.add_argument("--output")
    convert.add_argument("--name")
    add_settings(convert, include_crf=True)

    estimate = subparsers.add_parser(
        "estimate",
        help="Estimate duration and output storage before conversion",
    )
    estimate.add_argument("source")
    add_settings(estimate, include_crf=True)

    align = subparsers.add_parser("align", help="Calculate offsets for a canvas edge")
    align.add_argument("source")
    align.add_argument("--horizontal", choices=("left", "center", "right"), required=True)
    align.add_argument("--vertical", choices=("top", "center", "bottom"), required=True)
    add_settings(align, include_crf=False)
    return parser


def success(command: str, data: dict) -> dict:
    return {"ok": True, "command": command, "data": data}


def failure(command: str | None, exc: Exception) -> dict:
    error = {"type": type(exc).__name__, "message": str(exc)}
    if isinstance(exc, MediaCommandError):
        error["stderr"] = exc.stderr[-3000:]
        error["command"] = exc.command
    return {"ok": False, "command": command, "error": error}


def estimate_payload(args: argparse.Namespace) -> dict:
    source = probe_source(args.source)
    profile = profile_from_args(args)
    settings = settings_from_args(args).validated(
        duration=effective_duration(source.duration, args.loop_count),
        source_width=source.width,
        source_height=source.height,
    )
    available = effective_duration(source.duration, settings.loop_count)
    end = settings.end if settings.end is not None else available
    selected = max(0.0, end - settings.start)
    output_duration = selected / settings.speed
    estimate = estimate_output_size(
        profile,
        output_duration,
        settings.fps,
        settings.crf,
    )
    estimate["low"] = format_bytes(estimate["low_bytes"])
    estimate["estimated"] = format_bytes(estimate["estimated_bytes"])
    estimate["high"] = format_bytes(estimate["high_bytes"])
    estimate["profile"] = profile.to_dict()
    estimate["source_duration"] = source.duration
    estimate["available_duration"] = available
    estimate["selected_input_duration"] = selected
    return estimate


def execute(args: argparse.Namespace) -> dict:
    if args.command == "profiles":
        profiles = [profile.to_dict() for profile in list_profiles(ROOT)]
        return success(
            "profiles",
            {
                "default_profile_id": "active-theme",
                "profiles": profiles,
            },
        )
    if args.command == "probe":
        return success("probe", probe_source(args.source).to_dict())
    settings = settings_from_args(args)
    if args.command == "preview":
        output = Path(args.output) if args.output else cache_directory() / "preview.png"
        result = create_preview(args.source, output, settings)
        return success(
            "preview",
            {
                "output": str(result),
                "settings": settings.__dict__,
                "profile": profile_from_args(args).to_dict(),
            },
        )
    if args.command == "convert":
        if args.output:
            output = Path(args.output)
        else:
            name = safe_output_name(args.name or Path(args.source).name)
            output = cache_directory() / name
        data = convert_media(args.source, output, settings)
        data["path"] = str(output.resolve())
        data["profile"] = profile_from_args(args).to_dict()
        data["estimate"] = estimate_payload(args)
        return success("convert", data)
    if args.command == "estimate":
        return success("estimate", estimate_payload(args))
    if args.command == "align":
        source = probe_source(args.source)
        x, y = alignment_offsets(
            source.width,
            source.height,
            settings,
            args.horizontal,
            args.vertical,
        )
        return success(
            "align",
            {
                "x": x,
                "y": y,
                "profile": profile_from_args(args).to_dict(),
            },
        )
    raise RuntimeError(f"Unknown command: {args.command}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        payload = execute(args)
        status = 0
    except Exception as exc:
        payload = failure(getattr(args, "command", None), exc)
        status = 1
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    elif payload.get("ok"):
        print(json.dumps(payload["data"], indent=2, ensure_ascii=False))
    else:
        print(payload["error"]["message"], file=sys.stderr)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
