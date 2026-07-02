#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure validation helpers for native smart-screen video operations."""

from __future__ import annotations

import json
import posixpath
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

DISPLAY_WIDTH = 480
DISPLAY_HEIGHT = 480
DEFAULT_SD_VIDEO_DIR = "/mnt/SDCARD/video/"
DEFAULT_INTERNAL_VIDEO_DIR = "/root/video/"
_ALLOWED_ROOTS = (
    DEFAULT_SD_VIDEO_DIR.rstrip("/"),
    DEFAULT_INTERNAL_VIDEO_DIR.rstrip("/"),
)


class RemotePathError(ValueError):
    """Raised when a remote display path escapes the supported video roots."""


class MediaProbeError(RuntimeError):
    """Raised when ffprobe cannot inspect a local media file."""


class IncompatibleMediaError(ValueError):
    def __init__(self, probe: "VideoProbe"):
        self.probe = probe
        details = "; ".join(probe.issues) or "unknown incompatibility"
        super().__init__(f"Video is not compatible with the display: {details}")


def _ascii_bytes(value: str) -> bytes:
    try:
        return value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise RemotePathError(
            "Remote video names currently support ASCII characters only."
        ) from exc


def normalize_remote_path(remote_path: str, allow_directory: bool = False) -> str:
    """Return a canonical safe path under one of the display video roots.

    Files are intentionally restricted to direct children of the supported
    video directories. This matches the current UI and prevents traversal,
    ambiguous nested paths, and accidental access to other firmware files.
    """
    if not isinstance(remote_path, str) or not remote_path.strip():
        raise RemotePathError("Remote path must be a non-empty string.")

    raw = remote_path.strip()
    if "\x00" in raw or "\\" in raw:
        raise RemotePathError("Remote path contains unsupported characters.")
    if not raw.startswith("/"):
        raise RemotePathError("Remote path must be absolute.")

    raw_parts = [part for part in raw.split("/") if part]
    if any(part in {".", ".."} for part in raw_parts):
        raise RemotePathError("Remote path traversal is not allowed.")

    normalized = posixpath.normpath(raw)
    path = PurePosixPath(normalized)

    matched_root = None
    for root_text in _ALLOWED_ROOTS:
        root = PurePosixPath(root_text)
        if path == root or root in path.parents:
            matched_root = root
            break

    if matched_root is None:
        raise RemotePathError(
            "Remote path must stay under "
            f"{DEFAULT_SD_VIDEO_DIR} or {DEFAULT_INTERNAL_VIDEO_DIR}."
        )

    relative = path.relative_to(matched_root)
    if allow_directory:
        if relative.parts:
            raise RemotePathError("Only the root video directories are supported.")
        canonical = matched_root.as_posix() + "/"
    else:
        if len(relative.parts) != 1:
            raise RemotePathError(
                "Remote video files must be direct children of the video directory."
            )
        filename = relative.name
        if not filename or filename in {".", ".."}:
            raise RemotePathError("Remote path must include a file name.")
        if any(ord(character) < 32 for character in filename):
            raise RemotePathError("Remote file name contains control characters.")
        canonical = (matched_root / filename).as_posix()

    encoded = _ascii_bytes(canonical)
    if len(encoded) > 255:
        raise RemotePathError("Remote path cannot exceed 255 bytes.")
    return canonical


def remote_path_for_local(local_path: Path, internal: bool = False) -> str:
    directory = DEFAULT_INTERNAL_VIDEO_DIR if internal else DEFAULT_SD_VIDEO_DIR
    return normalize_remote_path(directory + local_path.name)


def parse_rate(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text or text in {"0/0", "N/A"}:
        return None
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        try:
            denominator_value = float(denominator)
            return float(numerator) / denominator_value if denominator_value else None
        except ValueError:
            return None
    try:
        return float(text)
    except ValueError:
        return None


@dataclass(frozen=True)
class VideoProbe:
    path: str
    codec: str | None
    width: int | None
    height: int | None
    pixel_format: str | None
    fps: float | None
    duration: float | None
    container: str | None
    has_audio: bool
    compatible: bool
    issues: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["issues"] = list(self.issues)
        return data


def evaluate_probe(path: Path, payload: dict[str, Any]) -> VideoProbe:
    streams = payload.get("streams")
    if not isinstance(streams, list):
        streams = []

    video_stream = next(
        (stream for stream in streams if stream.get("codec_type") == "video"),
        None,
    )
    if video_stream is None:
        raise MediaProbeError("No video stream was found in the selected file.")

    audio_stream = next(
        (stream for stream in streams if stream.get("codec_type") == "audio"),
        None,
    )
    format_data = payload.get("format")
    if not isinstance(format_data, dict):
        format_data = {}

    codec = video_stream.get("codec_name")
    width = video_stream.get("width")
    height = video_stream.get("height")
    pixel_format = video_stream.get("pix_fmt")
    fps = parse_rate(
        video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")
    )

    try:
        duration = float(
            video_stream.get("duration") or format_data.get("duration")
        )
    except (TypeError, ValueError):
        duration = None

    issues: list[str] = []
    if codec != "h264":
        issues.append("codec must be H.264")
    if (width, height) != (DISPLAY_WIDTH, DISPLAY_HEIGHT):
        issues.append(f"resolution must be {DISPLAY_WIDTH}x{DISPLAY_HEIGHT}")
    if pixel_format not in {"yuv420p", "yuvj420p"}:
        issues.append("pixel format must be yuv420p")

    return VideoProbe(
        path=str(path),
        codec=str(codec) if codec is not None else None,
        width=int(width) if isinstance(width, int) else None,
        height=int(height) if isinstance(height, int) else None,
        pixel_format=(
            str(pixel_format) if pixel_format is not None else None
        ),
        fps=fps,
        duration=duration,
        container=(
            str(format_data.get("format_name"))
            if format_data.get("format_name") is not None
            else None
        ),
        has_audio=audio_stream is not None,
        compatible=not issues,
        issues=tuple(issues),
    )


def probe_video(path: Path) -> VideoProbe:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Local media file was not found: {path}")

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise MediaProbeError(
            "ffprobe is required to validate videos before upload."
        )

    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            (
                "stream=codec_type,codec_name,width,height,pix_fmt,"
                "avg_frame_rate,r_frame_rate,duration:"
                "format=format_name,duration"
            ),
            "-of",
            "json",
            str(path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "ffprobe failed").strip()
        raise MediaProbeError(detail)

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MediaProbeError("ffprobe returned invalid JSON.") from exc
    return evaluate_probe(path, payload)
