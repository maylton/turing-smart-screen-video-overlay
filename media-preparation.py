#!/usr/bin/env python3
"""Structured command-line backend for the media preparation editor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from library.media_preparation import (
    ConversionSettings,
    MediaCommandError,
    cache_directory,
    convert_media,
    create_preview,
    probe_source,
    safe_output_name,
)


def settings_from_args(args: argparse.Namespace) -> ConversionSettings:
    return ConversionSettings(
        mode=args.mode,
        zoom=args.zoom,
        offset_x=args.x,
        offset_y=args.y,
        start=args.start,
        end=args.end,
        fps=args.fps,
        background=args.background,
        crf=getattr(args, "crf", 20),
    )


def add_settings(parser: argparse.ArgumentParser, *, include_crf: bool) -> None:
    parser.add_argument("--mode", choices=("fit", "fill", "stretch"), default="fit")
    parser.add_argument("--zoom", type=float, default=1.0)
    parser.add_argument("--x", type=int, default=0)
    parser.add_argument("--y", type=int, default=0)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--end", type=float)
    parser.add_argument("--fps", type=int, choices=(24, 30), default=30)
    parser.add_argument("--background", default="000000")
    if include_crf:
        parser.add_argument("--crf", type=int, default=20)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Return structured JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)

    probe = subparsers.add_parser("probe", help="Analyze a source GIF or video")
    probe.add_argument("source")

    preview = subparsers.add_parser("preview", help="Render one transformed preview frame")
    preview.add_argument("source")
    preview.add_argument("--output")
    add_settings(preview, include_crf=False)

    convert = subparsers.add_parser("convert", help="Prepare a display-compatible MP4")
    convert.add_argument("source")
    convert.add_argument("--output")
    convert.add_argument("--name")
    add_settings(convert, include_crf=True)
    return parser


def success(command: str, data: dict) -> dict:
    return {"ok": True, "command": command, "data": data}


def failure(command: str | None, exc: Exception) -> dict:
    error = {"type": type(exc).__name__, "message": str(exc)}
    if isinstance(exc, MediaCommandError):
        error["stderr"] = exc.stderr[-3000:]
        error["command"] = exc.command
    return {"ok": False, "command": command, "error": error}


def execute(args: argparse.Namespace) -> dict:
    if args.command == "probe":
        return success("probe", probe_source(args.source).to_dict())
    settings = settings_from_args(args)
    if args.command == "preview":
        output = Path(args.output) if args.output else cache_directory() / "preview.png"
        result = create_preview(args.source, output, settings)
        return success("preview", {"output": str(result), "settings": settings.__dict__})
    if args.command == "convert":
        if args.output:
            output = Path(args.output)
        else:
            name = safe_output_name(args.name or Path(args.source).name)
            output = cache_directory() / name
        data = convert_media(args.source, output, settings)
        data["path"] = str(output.resolve())
        return success("convert", data)
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
