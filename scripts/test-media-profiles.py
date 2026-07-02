#!/usr/bin/env python3
"""Validate profile-aware rectangular output with real FFmpeg."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from library.media_preparation import ConversionSettings, convert_media


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="turing-media-profile-") as temp:
        root = Path(temp)
        source = root / "source.mp4"
        portrait = root / "portrait.mp4"
        landscape = root / "landscape.mp4"

        run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=640x360:rate=30",
                "-t",
                "1.5",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(source),
            ]
        )

        portrait_result = convert_media(
            source,
            portrait,
            ConversionSettings(
                target_width=320,
                target_height=480,
                profile_id="portrait-320x480-preview",
                mode="fit",
            ),
        )
        landscape_result = convert_media(
            source,
            landscape,
            ConversionSettings(
                target_width=800,
                target_height=480,
                profile_id="landscape-800x480-preview",
                mode="fill",
            ),
        )

        if (
            portrait_result["output"]["width"],
            portrait_result["output"]["height"],
        ) != (320, 480):
            raise RuntimeError("Portrait profile dimensions were not preserved.")
        if (
            landscape_result["output"]["width"],
            landscape_result["output"]["height"],
        ) != (800, 480):
            raise RuntimeError("Landscape profile dimensions were not preserved.")

    print("Profile-aware FFmpeg integration test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
