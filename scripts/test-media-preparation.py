#!/usr/bin/env python3
"""End-to-end FFmpeg validation for media preparation without USB hardware."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from library.media_preparation import ConversionSettings, convert_media, create_preview


def run(command):
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())


def assert_output(data, fps):
    output = data["output"]
    assert output["codec"] == "h264", output
    assert (output["width"], output["height"]) == (480, 480), output
    assert output["pixel_format"] in {"yuv420p", "yuvj420p"}, output
    assert output["has_audio"] is False, output
    assert abs(float(output["fps"]) - fps) < 0.2, output


def main() -> int:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise SystemExit("ffmpeg and ffprobe are required")
    with tempfile.TemporaryDirectory(prefix="turing-media-test-") as temp:
        directory = Path(temp)
        video = directory / "wide-source.mp4"
        gif = directory / "animated-source.gif"
        run([
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30",
            "-t", "1.4", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(video),
        ])
        run([
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=size=320x240:rate=12",
            "-t", "1.0", "-vf", "fps=12", str(gif),
        ])

        preview = directory / "preview.png"
        create_preview(
            video,
            preview,
            ConversionSettings(mode="fill", zoom=1.1, offset_x=8, offset_y=-6, fps=30),
        )
        assert preview.is_file() and preview.stat().st_size > 0

        fit_output = directory / "fit.mp4"
        fit_data = convert_media(
            video,
            fit_output,
            ConversionSettings(mode="fit", fps=24, end=1.0),
        )
        assert_output(fit_data, 24)

        gif_output = directory / "gif.mp4"
        gif_data = convert_media(
            gif,
            gif_output,
            ConversionSettings(mode="stretch", fps=30, end=0.8),
        )
        assert_output(gif_data, 30)

        print("Media preparation integration test passed.")
        print(f"Preview: {preview.stat().st_size} bytes")
        print(f"Fit MP4: {fit_output.stat().st_size} bytes")
        print(f"GIF MP4: {gif_output.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
