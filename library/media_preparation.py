"""Media probing, framing, preview, and conversion for native display video."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import unicodedata
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

TARGET_WIDTH = 480
TARGET_HEIGHT = 480
SUPPORTED_INPUT_SUFFIXES = {".gif", ".mp4", ".mkv", ".webm", ".mov", ".avi"}
FRAME_MODES = {"fit", "fill", "stretch"}
FPS_PRESETS = {24, 30}


class MediaPreparationError(RuntimeError):
    """Base error for source analysis and FFmpeg preparation."""


class UnsupportedMediaError(MediaPreparationError):
    """Raised when the selected local input type is unsupported."""


class InvalidSettingsError(MediaPreparationError):
    """Raised when framing or trim settings are inconsistent."""


class MediaCommandError(MediaPreparationError):
    """Raised when FFprobe or FFmpeg fails."""

    def __init__(self, message: str, *, command: list[str], stderr: str = ""):
        super().__init__(message)
        self.command = command
        self.stderr = stderr


@dataclass(frozen=True)
class SourceMedia:
    path: str
    filename: str
    suffix: str
    codec: str
    width: int
    height: int
    pixel_format: str | None
    fps: float | None
    duration: float
    container: str | None
    has_audio: bool
    size_bytes: int

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height if self.height else 0.0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["aspect_ratio"] = self.aspect_ratio
        return data


@dataclass(frozen=True)
class ConversionSettings:
    mode: str = "fit"
    zoom: float = 1.0
    offset_x: int = 0
    offset_y: int = 0
    start: float = 0.0
    end: float | None = None
    fps: int = 30
    background: str = "000000"
    crf: int = 20

    def validated(self, *, duration: float | None = None) -> "ConversionSettings":
        mode = self.mode.lower().strip()
        if mode not in FRAME_MODES:
            raise InvalidSettingsError(f"Unsupported framing mode: {self.mode}")
        if not math.isfinite(self.zoom) or not 0.25 <= self.zoom <= 4.0:
            raise InvalidSettingsError("Zoom must be between 0.25 and 4.0.")
        if self.fps not in FPS_PRESETS:
            raise InvalidSettingsError("Output FPS must be 24 or 30.")
        if self.start < 0 or not math.isfinite(self.start):
            raise InvalidSettingsError("Trim start must be zero or greater.")
        if self.end is not None:
            if not math.isfinite(self.end) or self.end <= self.start:
                raise InvalidSettingsError("Trim end must be greater than trim start.")
            if duration is not None and self.end > duration + 0.05:
                raise InvalidSettingsError("Trim end exceeds the source duration.")
        if duration is not None and self.start >= duration:
            raise InvalidSettingsError("Trim start must be before the source ends.")
        background = self.background.removeprefix("#")
        if not re.fullmatch(r"[0-9A-Fa-f]{6}", background):
            raise InvalidSettingsError("Background must be a six-digit RGB color.")
        if not 0 <= self.crf <= 51:
            raise InvalidSettingsError("CRF must be between 0 and 51.")
        return ConversionSettings(
            mode=mode,
            zoom=float(self.zoom),
            offset_x=int(self.offset_x),
            offset_y=int(self.offset_y),
            start=float(self.start),
            end=float(self.end) if self.end is not None else None,
            fps=int(self.fps),
            background=background.lower(),
            crf=int(self.crf),
        )


def _require_command(name: str) -> str:
    command = shutil.which(name)
    if not command:
        raise MediaPreparationError(f"Required command was not found: {name}")
    return command


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "Unknown media error").strip()
        raise MediaCommandError(
            stderr.splitlines()[-1] if stderr else "Media command failed.",
            command=command,
            stderr=stderr,
        )
    return completed


def _parse_rate(value: str | None) -> float | None:
    if not value or value in {"0/0", "N/A"}:
        return None
    try:
        rate = float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return None
    return rate if math.isfinite(rate) and rate > 0 else None


def _parse_duration(*values: Any) -> float:
    for value in values:
        try:
            duration = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(duration) and duration > 0:
            return duration
    raise MediaPreparationError("Could not determine the source duration.")


def validate_source(path: str | os.PathLike[str]) -> Path:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Local media file was not found: {source}")
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_INPUT_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_INPUT_SUFFIXES))
        raise UnsupportedMediaError(
            f"Unsupported input type {suffix or '(none)'}. Supported: {supported}"
        )
    return source


def probe_source(path: str | os.PathLike[str]) -> SourceMedia:
    source = validate_source(path)
    command = [
        _require_command("ffprobe"),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(source),
    ]
    payload = json.loads(_run(command).stdout)
    streams = payload.get("streams") or []
    video = next(
        (stream for stream in streams if stream.get("codec_type") == "video"),
        None,
    )
    if not video:
        raise MediaPreparationError("The selected file does not contain a video stream.")
    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)
    if width <= 0 or height <= 0:
        raise MediaPreparationError("The source video dimensions are invalid.")
    format_data = payload.get("format") or {}
    duration = _parse_duration(video.get("duration"), format_data.get("duration"))
    return SourceMedia(
        path=str(source),
        filename=source.name,
        suffix=source.suffix.lower(),
        codec=str(video.get("codec_name") or "unknown"),
        width=width,
        height=height,
        pixel_format=video.get("pix_fmt"),
        fps=_parse_rate(video.get("avg_frame_rate") or video.get("r_frame_rate")),
        duration=duration,
        container=format_data.get("format_name"),
        has_audio=any(stream.get("codec_type") == "audio" for stream in streams),
        size_bytes=source.stat().st_size,
    )


def cache_directory() -> Path:
    base = Path(
        os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
    ).expanduser()
    target = base / "turing-smart-screen" / "media-preparation"
    target.mkdir(parents=True, exist_ok=True)
    return target


def safe_output_name(value: str) -> str:
    stem = Path(value).stem
    ascii_stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    ascii_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", ascii_stem).strip("-._")
    if not ascii_stem:
        ascii_stem = "prepared-video"
    return f"{ascii_stem[:100]}.mp4"


def _scale_filter(mode: str) -> str:
    if mode == "fit":
        return (
            f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:"
            "force_original_aspect_ratio=decrease"
        )
    if mode == "fill":
        return (
            f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:"
            "force_original_aspect_ratio=increase"
        )
    return f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}"


def build_filter(settings: ConversionSettings, *, preview: bool = False) -> str:
    settings = settings.validated()
    zoom = f"{settings.zoom:.6f}".rstrip("0").rstrip(".")
    scale = _scale_filter(settings.mode)
    zoom_filter = (
        f"scale='max(2,trunc(iw*{zoom}/2)*2)':"
        f"'max(2,trunc(ih*{zoom}/2)*2)'"
    )
    x_term = f"{settings.offset_x:+d}"
    y_term = f"{settings.offset_y:+d}"
    final_format = "format=rgba" if preview else f"fps={settings.fps},format=yuv420p"
    return (
        f"color=c=0x{settings.background}:s={TARGET_WIDTH}x{TARGET_HEIGHT}:"
        f"r={settings.fps}[bg];"
        f"[0:v]{scale},{zoom_filter},setsar=1[fg];"
        f"[bg][fg]overlay=x='(W-w)/2{x_term}':y='(H-h)/2{y_term}':"
        f"shortest=1,{final_format}[out]"
    )


def _trim_arguments(settings: ConversionSettings) -> list[str]:
    args: list[str] = []
    if settings.start > 0:
        args.extend(["-ss", f"{settings.start:.3f}"])
    if settings.end is not None:
        args.extend(["-t", f"{settings.end - settings.start:.3f}"])
    return args


def build_preview_command(
    source: Path,
    output: Path,
    settings: ConversionSettings,
) -> list[str]:
    return [
        _require_command("ffmpeg"),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        *_trim_arguments(settings),
        "-i",
        str(source),
        "-filter_complex",
        build_filter(settings, preview=True),
        "-map",
        "[out]",
        "-frames:v",
        "1",
        str(output),
    ]


def build_conversion_command(
    source: Path,
    output: Path,
    settings: ConversionSettings,
) -> list[str]:
    return [
        _require_command("ffmpeg"),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        *_trim_arguments(settings),
        "-i",
        str(source),
        "-filter_complex",
        build_filter(settings, preview=False),
        "-map",
        "[out]",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        str(settings.crf),
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output),
    ]


def create_preview(
    source_path: str | os.PathLike[str],
    output_path: str | os.PathLike[str],
    settings: ConversionSettings,
) -> Path:
    source_media = probe_source(source_path)
    source = Path(source_media.path)
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    settings = settings.validated(duration=source_media.duration)
    _run(build_preview_command(source, output, settings))
    if not output.is_file() or output.stat().st_size <= 0:
        raise MediaPreparationError("FFmpeg did not create the preview image.")
    return output


def convert_media(
    source_path: str | os.PathLike[str],
    output_path: str | os.PathLike[str],
    settings: ConversionSettings,
) -> dict[str, Any]:
    source_media = probe_source(source_path)
    source = Path(source_media.path)
    output = Path(output_path).expanduser().resolve()
    if output.suffix.lower() != ".mp4":
        raise InvalidSettingsError("Prepared output must use the .mp4 extension.")
    output.parent.mkdir(parents=True, exist_ok=True)
    settings = settings.validated(duration=source_media.duration)
    _run(build_conversion_command(source, output, settings))
    prepared = probe_source(output)
    issues: list[str] = []
    if prepared.codec != "h264":
        issues.append(f"codec is {prepared.codec}, expected h264")
    if (prepared.width, prepared.height) != (TARGET_WIDTH, TARGET_HEIGHT):
        issues.append(
            f"resolution is {prepared.width}x{prepared.height}, "
            f"expected {TARGET_WIDTH}x{TARGET_HEIGHT}"
        )
    if prepared.pixel_format not in {"yuv420p", "yuvj420p"}:
        issues.append(
            f"pixel format is {prepared.pixel_format}, expected yuv420p"
        )
    if prepared.has_audio:
        issues.append("audio stream was not removed")
    if issues:
        raise MediaPreparationError(
            "Prepared output failed compatibility validation: " + "; ".join(issues)
        )
    return {
        "source": source_media.to_dict(),
        "output": prepared.to_dict(),
        "settings": asdict(settings),
    }
