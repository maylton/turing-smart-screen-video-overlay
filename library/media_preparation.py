"""Advanced media probing, framing, preview, and conversion for display video."""

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
FRAME_MODES = {"fit", "fill", "stretch", "original", "custom"}
FPS_PRESETS = {24, 30}
ROTATIONS = {0, 90, 180, 270}
BACKGROUND_MODES = {"solid", "blur", "image"}
ALIGN_X = {"left", "center", "right"}
ALIGN_Y = {"top", "center", "bottom"}


class MediaPreparationError(RuntimeError):
    """Base error for source analysis and FFmpeg preparation."""


class UnsupportedMediaError(MediaPreparationError):
    """Raised when the selected local input type is unsupported."""


class InvalidSettingsError(MediaPreparationError):
    """Raised when framing, crop, background, or timing settings are invalid."""


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
    target_width: int = TARGET_WIDTH
    target_height: int = TARGET_HEIGHT
    profile_id: str = "active-theme"
    encoder: str = "libx264"
    codec: str = "h264"
    pixel_format: str = "yuv420p"
    custom_width: int = TARGET_WIDTH
    custom_height: int = TARGET_HEIGHT
    crop_left: int = 0
    crop_right: int = 0
    crop_top: int = 0
    crop_bottom: int = 0
    rotation: int = 0
    flip_horizontal: bool = False
    flip_vertical: bool = False
    start: float = 0.0
    end: float | None = None
    fps: int = 24
    speed: float = 1.0
    loop_count: int = 0
    background_mode: str = "solid"
    background: str = "000000"
    background_image: str | None = None
    blur_strength: float = 24.0
    crf: int = 20

    def validated(
        self,
        *,
        duration: float | None = None,
        source_width: int | None = None,
        source_height: int | None = None,
    ) -> "ConversionSettings":
        mode = self.mode.lower().strip()
        if mode not in FRAME_MODES:
            raise InvalidSettingsError(f"Unsupported framing mode: {self.mode}")
        if not math.isfinite(self.zoom) or not 0.25 <= self.zoom <= 4.0:
            raise InvalidSettingsError("Zoom must be between 0.25 and 4.0.")
        if self.fps not in FPS_PRESETS:
            raise InvalidSettingsError("Output FPS must be 24 or 30.")
        if self.rotation not in ROTATIONS:
            raise InvalidSettingsError("Rotation must be 0, 90, 180, or 270 degrees.")
        if not math.isfinite(self.speed) or not 0.25 <= self.speed <= 4.0:
            raise InvalidSettingsError("Playback speed must be between 0.25 and 4.0.")
        if not 0 <= int(self.loop_count) <= 20:
            raise InvalidSettingsError("Loop count must be between 0 and 20.")
        if self.start < 0 or not math.isfinite(self.start):
            raise InvalidSettingsError("Trim start must be zero or greater.")
        if self.end is not None:
            if not math.isfinite(self.end) or self.end <= self.start:
                raise InvalidSettingsError("Trim end must be greater than trim start.")
            if duration is not None and self.end > duration + 0.05:
                raise InvalidSettingsError("Trim end exceeds the available looped duration.")
        if duration is not None and self.start >= duration:
            raise InvalidSettingsError("Trim start must be before the source ends.")

        target_width = int(self.target_width)
        target_height = int(self.target_height)
        if not 2 <= target_width <= 4096 or not 2 <= target_height <= 4096:
            raise InvalidSettingsError("Target width and height must be between 2 and 4096.")
        if self.encoder != "libx264" or self.codec != "h264":
            raise InvalidSettingsError("Only H.264/libx264 output is currently supported.")
        if self.pixel_format != "yuv420p":
            raise InvalidSettingsError("Only yuv420p output is currently supported.")

        custom_width = int(self.custom_width)
        custom_height = int(self.custom_height)
        if not 2 <= custom_width <= 4096 or not 2 <= custom_height <= 4096:
            raise InvalidSettingsError("Custom width and height must be between 2 and 4096.")

        crop_values = (
            int(self.crop_left),
            int(self.crop_right),
            int(self.crop_top),
            int(self.crop_bottom),
        )
        if any(value < 0 or value > 4096 for value in crop_values):
            raise InvalidSettingsError("Crop values must be between 0 and 4096.")
        if source_width is not None and crop_values[0] + crop_values[1] >= source_width:
            raise InvalidSettingsError("Horizontal crop removes the entire source.")
        if source_height is not None and crop_values[2] + crop_values[3] >= source_height:
            raise InvalidSettingsError("Vertical crop removes the entire source.")

        background_mode = self.background_mode.lower().strip()
        if background_mode not in BACKGROUND_MODES:
            raise InvalidSettingsError(
                f"Unsupported background mode: {self.background_mode}"
            )
        background = self.background.removeprefix("#")
        if not re.fullmatch(r"[0-9A-Fa-f]{6}", background):
            raise InvalidSettingsError("Background must be a six-digit RGB color.")
        background_image = self.background_image
        if background_mode == "image":
            if not background_image:
                raise InvalidSettingsError(
                    "Choose a background image when using the image background mode."
                )
            image_path = Path(background_image).expanduser().resolve()
            if not image_path.is_file():
                raise InvalidSettingsError(
                    f"Background image was not found: {image_path}"
                )
            background_image = str(image_path)
        if not math.isfinite(self.blur_strength) or not 1 <= self.blur_strength <= 100:
            raise InvalidSettingsError("Blur strength must be between 1 and 100.")
        if not 0 <= self.crf <= 51:
            raise InvalidSettingsError("CRF must be between 0 and 51.")

        return ConversionSettings(
            mode=mode,
            zoom=float(self.zoom),
            offset_x=int(self.offset_x),
            offset_y=int(self.offset_y),
            target_width=target_width,
            target_height=target_height,
            profile_id=str(self.profile_id or "active-theme"),
            encoder=self.encoder,
            codec=self.codec,
            pixel_format=self.pixel_format,
            custom_width=custom_width,
            custom_height=custom_height,
            crop_left=crop_values[0],
            crop_right=crop_values[1],
            crop_top=crop_values[2],
            crop_bottom=crop_values[3],
            rotation=int(self.rotation),
            flip_horizontal=bool(self.flip_horizontal),
            flip_vertical=bool(self.flip_vertical),
            start=float(self.start),
            end=float(self.end) if self.end is not None else None,
            fps=int(self.fps),
            speed=float(self.speed),
            loop_count=int(self.loop_count),
            background_mode=background_mode,
            background=background.lower(),
            background_image=background_image,
            blur_strength=float(self.blur_strength),
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


def effective_duration(source_duration: float, loop_count: int) -> float:
    return source_duration * (int(loop_count) + 1)


def _rotation_filter(rotation: int) -> list[str]:
    if rotation == 90:
        return ["transpose=1"]
    if rotation == 180:
        return ["hflip", "vflip"]
    if rotation == 270:
        return ["transpose=2"]
    return []


def _mirror_filter(settings: ConversionSettings) -> list[str]:
    filters: list[str] = []
    if settings.flip_horizontal:
        filters.append("hflip")
    if settings.flip_vertical:
        filters.append("vflip")
    return filters


def _crop_filter(settings: ConversionSettings) -> list[str]:
    if not any(
        (
            settings.crop_left,
            settings.crop_right,
            settings.crop_top,
            settings.crop_bottom,
        )
    ):
        return []
    width = f"iw-{settings.crop_left + settings.crop_right}"
    height = f"ih-{settings.crop_top + settings.crop_bottom}"
    return [
        f"crop={width}:{height}:{settings.crop_left}:{settings.crop_top}"
    ]


def _base_scale_filter(settings: ConversionSettings) -> str:
    if settings.mode == "fit":
        return (
            f"scale={settings.target_width}:{settings.target_height}:"
            "force_original_aspect_ratio=decrease"
        )
    if settings.mode == "fill":
        return (
            f"scale={settings.target_width}:{settings.target_height}:"
            "force_original_aspect_ratio=increase"
        )
    if settings.mode == "stretch":
        return f"scale={settings.target_width}:{settings.target_height}"
    if settings.mode == "custom":
        return f"scale={settings.custom_width}:{settings.custom_height}"
    return "scale=iw:ih"


def foreground_size(
    source_width: int,
    source_height: int,
    settings: ConversionSettings,
) -> tuple[int, int]:
    settings = settings.validated(
        source_width=source_width,
        source_height=source_height,
    )
    width = source_width - settings.crop_left - settings.crop_right
    height = source_height - settings.crop_top - settings.crop_bottom
    if settings.rotation in {90, 270}:
        width, height = height, width
    if settings.mode == "fit":
        ratio = min(settings.target_width / width, settings.target_height / height)
        width, height = round(width * ratio), round(height * ratio)
    elif settings.mode == "fill":
        ratio = max(settings.target_width / width, settings.target_height / height)
        width, height = round(width * ratio), round(height * ratio)
    elif settings.mode == "stretch":
        width, height = settings.target_width, settings.target_height
    elif settings.mode == "custom":
        width, height = settings.custom_width, settings.custom_height
    width = max(2, round(width * settings.zoom))
    height = max(2, round(height * settings.zoom))
    return width, height


def alignment_offsets(
    source_width: int,
    source_height: int,
    settings: ConversionSettings,
    horizontal: str,
    vertical: str,
) -> tuple[int, int]:
    horizontal = horizontal.lower()
    vertical = vertical.lower()
    if horizontal not in ALIGN_X or vertical not in ALIGN_Y:
        raise InvalidSettingsError("Unknown alignment.")
    width, height = foreground_size(source_width, source_height, settings)
    if horizontal == "left":
        x = round((width - settings.target_width) / 2)
    elif horizontal == "right":
        x = round((settings.target_width - width) / 2)
    else:
        x = 0
    if vertical == "top":
        y = round((height - settings.target_height) / 2)
    elif vertical == "bottom":
        y = round((settings.target_height - height) / 2)
    else:
        y = 0
    return x, y


def build_filter(settings: ConversionSettings, *, preview: bool = False) -> str:
    settings = settings.validated()
    zoom = f"{settings.zoom:.6f}".rstrip("0").rstrip(".")
    source_chain = [
        f"setpts=(PTS-STARTPTS)/{settings.speed:.6f}",
        *_crop_filter(settings),
        *_rotation_filter(settings.rotation),
        *_mirror_filter(settings),
        _base_scale_filter(settings),
        (
            f"scale='max(2,trunc(iw*{zoom}/2)*2)':"
            f"'max(2,trunc(ih*{zoom}/2)*2)'"
        ),
        "setsar=1",
    ]
    x_term = f"{settings.offset_x:+d}"
    y_term = f"{settings.offset_y:+d}"
    final_format = "format=rgba" if preview else f"fps={settings.fps},format=yuv420p"

    if settings.background_mode == "blur":
        graph = (
            f"[0:v]setpts=(PTS-STARTPTS)/{settings.speed:.6f},split=2[fgsrc][bgsrc];"
            f"[fgsrc]{','.join(source_chain[1:])}[fg];"
            f"[bgsrc]scale={settings.target_width}:{settings.target_height}:"
            "force_original_aspect_ratio=increase,"
            f"crop={settings.target_width}:{settings.target_height},"
            f"gblur=sigma={settings.blur_strength:.3f},setsar=1[bg];"
        )
    else:
        graph = f"[0:v]{','.join(source_chain)}[fg];"
        if settings.background_mode == "image":
            graph += (
                f"[1:v]scale={settings.target_width}:{settings.target_height}:"
                "force_original_aspect_ratio=increase,"
                f"crop={settings.target_width}:{settings.target_height},setsar=1[bg];"
            )
        else:
            graph += (
                f"color=c=0x{settings.background}:"
                f"s={settings.target_width}x{settings.target_height}:r={settings.fps}[bg];"
            )

    graph += (
        f"[bg][fg]overlay=x='(W-w)/2{x_term}':y='(H-h)/2{y_term}':"
        f"shortest=1,{final_format}[out]"
    )
    return graph


def _source_input_arguments(
    source: Path,
    settings: ConversionSettings,
) -> list[str]:
    args: list[str] = []
    if settings.start > 0:
        args.extend(["-ss", f"{settings.start:.3f}"])
    if source.suffix.lower() == ".gif":
        args.extend(["-ignore_loop", "1"])
    if settings.loop_count:
        args.extend(["-stream_loop", str(settings.loop_count)])
    if settings.end is not None:
        args.extend(["-t", f"{settings.end - settings.start:.3f}"])
    args.extend(["-i", str(source)])
    return args


def _background_input_arguments(settings: ConversionSettings) -> list[str]:
    if settings.background_mode != "image" or not settings.background_image:
        return []
    return ["-loop", "1", "-i", str(settings.background_image)]


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
        *_source_input_arguments(source, settings),
        *_background_input_arguments(settings),
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
        *_source_input_arguments(source, settings),
        *_background_input_arguments(settings),
        "-filter_complex",
        build_filter(settings, preview=False),
        "-map",
        "[out]",
        "-an",
        "-c:v",
        settings.encoder,
        "-profile:v",
        "main",
        "-level:v",
        "3.1",
        "-bf",
        "1",
        "-maxrate",
        "2500k",
        "-bufsize",
        "5000k",
        "-preset",
        "medium",
        "-crf",
        str(settings.crf),
        "-pix_fmt",
        settings.pixel_format,
        "-fps_mode",
        "cfr",
        "-movflags",
        "+faststart",
        str(output),
    ]


def _validated_for_source(
    settings: ConversionSettings,
    source_media: SourceMedia,
) -> ConversionSettings:
    return settings.validated(
        duration=effective_duration(source_media.duration, settings.loop_count),
        source_width=source_media.width,
        source_height=source_media.height,
    )


def create_preview(
    source_path: str | os.PathLike[str],
    output_path: str | os.PathLike[str],
    settings: ConversionSettings,
) -> Path:
    source_media = probe_source(source_path)
    source = Path(source_media.path)
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    settings = _validated_for_source(settings, source_media)
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
    settings = _validated_for_source(settings, source_media)
    _run(build_conversion_command(source, output, settings))
    prepared = probe_source(output)
    issues: list[str] = []
    if prepared.codec != settings.codec:
        issues.append(
            f"codec is {prepared.codec}, expected {settings.codec}"
        )
    if (prepared.width, prepared.height) != (
        settings.target_width,
        settings.target_height,
    ):
        issues.append(
            f"resolution is {prepared.width}x{prepared.height}, "
            f"expected {settings.target_width}x{settings.target_height}"
        )
    if prepared.pixel_format not in {settings.pixel_format, "yuvj420p"}:
        issues.append(
            f"pixel format is {prepared.pixel_format}, expected {settings.pixel_format}"
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
