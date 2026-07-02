#!/usr/bin/env python3
"""Exercise advanced media conversion with real FFmpeg inputs."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from library.media_preparation import ConversionSettings, convert_media, create_preview


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="turing-advanced-media-") as temp:
        root = Path(temp)
        source = root / "source.mp4"
        background = root / "background.png"
        blurred = root / "blurred.mp4"
        custom = root / "custom.mp4"
        preview = root / "preview.png"

        run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30",
                "-t", "2.5", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                str(source),
            ]
        )
        run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "color=c=blue:s=800x600",
                "-frames:v", "1", str(background),
            ]
        )

        blurred_result = convert_media(
            source,
            blurred,
            ConversionSettings(
                mode="original",
                crop_left=40,
                crop_right=20,
                crop_top=10,
                crop_bottom=30,
                rotation=90,
                zoom=0.7,
                background_mode="blur",
                blur_strength=28,
                speed=1.5,
                start=0.2,
                end=2.0,
            ),
        )
        custom_result = convert_media(
            source,
            custom,
            ConversionSettings(
                mode="custom",
                custom_width=300,
                custom_height=180,
                offset_x=60,
                offset_y=-80,
                background_mode="image",
                background_image=str(background),
                loop_count=1,
                end=4.0,
            ),
        )
        create_preview(
            source,
            preview,
            ConversionSettings(
                mode="fill",
                rotation=270,
                background_mode="image",
                background_image=str(background),
            ),
        )

        for path in (blurred, custom, preview):
            if not path.is_file() or path.stat().st_size <= 0:
                raise RuntimeError(f"Expected output was not created: {path}")

        print(json.dumps(
            {
                "blurred": blurred_result["output"],
                "custom": custom_result["output"],
                "preview": str(preview),
            },
            indent=2,
        ))
    print("Advanced media preparation integration test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
