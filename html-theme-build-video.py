#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile an opt-in HTML theme base layer into native display video."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("GSK_RENDERER", "gl")
os.environ.setdefault("WEBKIT_DISABLE_DMABUF_RENDERER", "1")

from library.html_hybrid import validate_native_video
from library.html_theme_video_builder import build_native_video, frame_count
from library.theme_engine import ThemeManifest


ROOT = Path(__file__).resolve().parent
DEFAULT_THEME = ROOT / "res" / "themes" / "html-aio-material-expressive"


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme", type=Path, default=DEFAULT_THEME)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        manifest = ThemeManifest.load(args.theme)
        spec = manifest.native_video_overlay
        if spec is None:
            raise ValueError("theme does not enable nativeVideoOverlay")
        if args.check:
            probe = validate_native_video(manifest)
            print(
                f"Native HTML video: {manifest.name}; "
                f"frames={frame_count(manifest)} fps={spec.fps} "
                f"duration={spec.duration:.3f}s profile={probe.profile} "
                f"level={probe.level}"
            )
            return 0
        video, preview = build_native_video(
            manifest,
            destination=args.output,
            preview=args.preview,
        )
        print(f"Native HTML video written to {video}")
        print(f"Background preview written to {preview}")
        return 0
    except Exception as exc:
        print(f"Native HTML video build failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
