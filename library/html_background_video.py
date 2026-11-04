# SPDX-License-Identifier: GPL-3.0-or-later
"""Background media sources for compiled HTML theme videos."""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from library.theme_engine import ThemeManifest, ThemeValidationError


SUPPORTED_FITS = ("cover", "contain", "stretch")
SUPPORTED_POSITIONS = (
    "center",
    "top-left",
    "top",
    "top-right",
    "left",
    "right",
    "bottom-left",
    "bottom",
    "bottom-right",
)
# Where each named position sits in the free space, in percent (0 = left/top).
POSITION_OFFSETS = {
    "center": (50.0, 50.0),
    "top-left": (0.0, 0.0),
    "top": (50.0, 0.0),
    "top-right": (100.0, 0.0),
    "left": (0.0, 50.0),
    "right": (100.0, 50.0),
    "bottom-left": (0.0, 100.0),
    "bottom": (50.0, 100.0),
    "bottom-right": (100.0, 100.0),
}
SUPPORTED_VIDEO_SUFFIXES = {
    ".mp4",
    ".m4v",
    ".mov",
    ".mkv",
    ".webm",
    ".avi",
    ".gif",
}
SUPPORTED_IMAGE_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
}
SUPPORTED_SOURCE_SUFFIXES = SUPPORTED_VIDEO_SUFFIXES | SUPPORTED_IMAGE_SUFFIXES


def media_kind_for_path(path: Path | str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in SUPPORTED_IMAGE_SUFFIXES:
        return "image"
    if suffix in SUPPORTED_VIDEO_SUFFIXES:
        return "video"
    raise ThemeValidationError(
        "background source must be an MP4, MOV, M4V, MKV, WebM, AVI, GIF, "
        "PNG, JPG, JPEG, WebP, or BMP file"
    )


@dataclass(frozen=True)
class HtmlBackgroundMedia:
    source_path: str
    kind: str = ""
    fit: str = "cover"
    position: str = "center"
    loop: bool = True
    start_time: float = 0.0
    # Free framing: share of the spare width/height left of/above the frame
    # (0-100). None keeps the named ``position``.
    offset_x: float | None = None
    offset_y: float | None = None

    def __post_init__(self) -> None:
        inferred = media_kind_for_path(self.source_path)
        kind = str(self.kind or inferred).strip().lower()
        if kind not in {"video", "image"}:
            raise ThemeValidationError("background media kind must be video or image")
        if kind != inferred:
            raise ThemeValidationError(
                f"background media kind {kind!r} does not match {Path(self.source_path).suffix}"
            )
        object.__setattr__(self, "kind", kind)
        for name in ("offset_x", "offset_y"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _offset_value(value, name))
        if kind == "image":
            object.__setattr__(self, "loop", True)
            object.__setattr__(self, "start_time", 0.0)

    @property
    def offsets(self) -> tuple[float, float]:
        """Framing in percent of the spare space, (horizontal, vertical)."""
        default_x, default_y = POSITION_OFFSETS.get(self.position, (50.0, 50.0))
        return (
            default_x if self.offset_x is None else self.offset_x,
            default_y if self.offset_y is None else self.offset_y,
        )

    @property
    def is_video(self) -> bool:
        return self.kind == "video"

    @property
    def is_image(self) -> bool:
        return self.kind == "image"

    def source_file(self, root: Path) -> Path:
        field = f"background{self.kind.title()}.sourcePath"
        return _safe_relative_file(root, self.source_path, field)


HtmlBackgroundVideo = HtmlBackgroundMedia
HtmlBackgroundImage = HtmlBackgroundMedia


def _safe_relative_file(root: Path, raw_path: Any, field_name: str) -> Path:
    text = str(raw_path or "").strip()
    if not text:
        raise ThemeValidationError(f"{field_name} cannot be empty")
    candidate = Path(text)
    if candidate.is_absolute():
        raise ThemeValidationError(f"{field_name} must be relative to the theme")
    resolved = (Path(root) / candidate).resolve()
    try:
        resolved.relative_to(Path(root).resolve())
    except ValueError as exc:
        raise ThemeValidationError(f"{field_name} escapes the theme directory") from exc
    return resolved


def _manifest_payload(manifest: ThemeManifest) -> dict[str, Any]:
    try:
        payload = json.loads(
            (manifest.root / "manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ThemeValidationError(f"Invalid manifest.json: {exc}") from exc
    if not isinstance(payload, dict):
        raise ThemeValidationError("manifest.json must contain an object")
    return payload


def _offset_value(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ThemeValidationError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 100.0:
        raise ThemeValidationError(f"{field} must be between 0 and 100")
    return round(number, 2)


def _read_offsets(value: dict[str, Any], field: str) -> tuple[float | None, float | None]:
    offsets = []
    for key in ("offsetX", "offsetY"):
        raw = value.get(key)
        offsets.append(None if raw is None else _offset_value(raw, f"{field}.{key}"))
    return offsets[0], offsets[1]


def _validate_common_settings(value: dict[str, Any], field: str) -> tuple[str, str]:
    fit = str(value.get("fit", "cover")).strip().lower()
    if fit not in SUPPORTED_FITS:
        raise ThemeValidationError(f"{field}.fit must be cover, contain, or stretch")
    position = str(value.get("position", "center")).strip().lower()
    if position not in SUPPORTED_POSITIONS:
        raise ThemeValidationError(f"{field}.position uses an unsupported anchor")
    return fit, position


def load_background_media(
    manifest: ThemeManifest,
    *,
    require_file: bool = True,
) -> HtmlBackgroundMedia | None:
    """Return the optional image/video source compiled behind the HTML base."""
    payload = _manifest_payload(manifest)
    native = payload.get("nativeVideoOverlay")
    if not isinstance(native, dict):
        return None

    video_value = native.get("backgroundVideo")
    image_value = native.get("backgroundImage")
    if video_value is not None and image_value is not None:
        raise ThemeValidationError(
            "nativeVideoOverlay cannot define backgroundVideo and backgroundImage together"
        )
    if video_value is None and image_value is None:
        return None

    kind = "image" if image_value is not None else "video"
    value = image_value if image_value is not None else video_value
    field = f"nativeVideoOverlay.background{kind.title()}"
    if not isinstance(value, dict):
        raise ThemeValidationError(f"{field} must be an object")

    source_path = str(value.get("sourcePath") or "").strip()
    source = _safe_relative_file(manifest.root, source_path, f"{field}.sourcePath")
    detected_kind = media_kind_for_path(source)
    if detected_kind != kind:
        raise ThemeValidationError(f"{field}.sourcePath must reference a {kind} file")
    if require_file and not source.is_file():
        raise ThemeValidationError(f"background {kind} source was not found: {source_path}")

    fit, position = _validate_common_settings(value, field)
    offset_x, offset_y = _read_offsets(value, field)
    if kind == "image":
        return HtmlBackgroundMedia(
            source_path=source_path,
            kind="image",
            fit=fit,
            position=position,
            offset_x=offset_x,
            offset_y=offset_y,
        )

    loop = value.get("loop", True)
    if not isinstance(loop, bool):
        raise ThemeValidationError("backgroundVideo.loop must be a boolean")
    start_value = value.get("startTime", 0)
    if isinstance(start_value, bool) or not isinstance(start_value, (int, float)):
        raise ThemeValidationError("backgroundVideo.startTime must be a number")
    start_time = float(start_value)
    if not math.isfinite(start_time) or start_time < 0:
        raise ThemeValidationError(
            "backgroundVideo.startTime must be finite and non-negative"
        )
    return HtmlBackgroundMedia(
        source_path=source_path,
        kind="video",
        fit=fit,
        position=position,
        loop=loop,
        start_time=start_time,
        offset_x=offset_x,
        offset_y=offset_y,
    )


def load_background_video(
    manifest: ThemeManifest,
    *,
    require_file: bool = True,
) -> HtmlBackgroundMedia | None:
    value = load_background_media(manifest, require_file=require_file)
    return value if value is not None and value.is_video else None


def load_background_image(
    manifest: ThemeManifest,
    *,
    require_file: bool = True,
) -> HtmlBackgroundMedia | None:
    value = load_background_media(manifest, require_file=require_file)
    return value if value is not None and value.is_image else None


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _managed_destination(manifest: ThemeManifest, kind: str, suffix: str) -> Path:
    assets = manifest.root / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    return assets / f"background-{kind}{suffix}"


def _cleanup_managed_sources(assets: Path, *, keep: Path | None = None) -> None:
    keep = keep.resolve() if keep is not None else None
    for pattern in ("background-image.*", "background-video.*"):
        for candidate in assets.glob(pattern):
            if keep is not None and candidate.resolve() == keep:
                continue
            candidate.unlink(missing_ok=True)


def save_background_media(
    manifest: ThemeManifest,
    *,
    source: Path | None = None,
    media_kind: str | None = None,
    fit: str = "cover",
    position: str = "center",
    loop: bool = True,
    start_time: float = 0.0,
    offset_x: float | None = None,
    offset_y: float | None = None,
) -> ThemeManifest:
    """Copy/replace a background source and persist compilation settings.

    ``offset_x``/``offset_y`` (0-100) frame the source freely; without them
    the named ``position`` is used.
    """
    if manifest.engine != "html" or manifest.native_video_overlay is None:
        raise ThemeValidationError(
            "background media requires an HTML native-video theme"
        )
    fit = str(fit).strip().lower()
    position = str(position).strip().lower()
    if fit not in SUPPORTED_FITS:
        raise ThemeValidationError("background media fit is unsupported")
    if position not in SUPPORTED_POSITIONS:
        raise ThemeValidationError("background media position is unsupported")
    if not isinstance(loop, bool):
        raise ThemeValidationError("background video loop must be a boolean")
    start_time = float(start_time)
    if not math.isfinite(start_time) or start_time < 0:
        raise ThemeValidationError("background video start time is invalid")
    offsets = {}
    if offset_x is not None:
        offsets["offsetX"] = _offset_value(offset_x, "background offset x")
    if offset_y is not None:
        offsets["offsetY"] = _offset_value(offset_y, "background offset y")

    payload = _manifest_payload(manifest)
    native = payload.get("nativeVideoOverlay")
    if not isinstance(native, dict):
        raise ThemeValidationError("nativeVideoOverlay must be an object")

    existing = load_background_media(manifest, require_file=False)
    kind = str(media_kind or (existing.kind if existing is not None else "")).lower()
    source_path = existing.source_path if existing is not None else ""

    if source is not None:
        selected = Path(source).expanduser().resolve()
        if not selected.is_file():
            raise ThemeValidationError(f"background media was not found: {selected}")
        detected_kind = media_kind_for_path(selected)
        if kind and kind != detected_kind:
            raise ThemeValidationError(
                f"selected file is a {detected_kind}, not a {kind}"
            )
        kind = detected_kind
        destination = _managed_destination(manifest, kind, selected.suffix.lower())
        temporary = destination.with_name(
            f".{destination.name}.{os.getpid()}.tmp{selected.suffix.lower()}"
        )
        shutil.copy2(selected, temporary)
        os.replace(temporary, destination)
        _cleanup_managed_sources(destination.parent, keep=destination)
        source_path = destination.relative_to(manifest.root).as_posix()

    if kind not in {"video", "image"}:
        raise ThemeValidationError("select a background image or video first")
    if not source_path:
        raise ThemeValidationError(f"select a background {kind} first")
    source_file = _safe_relative_file(
        manifest.root,
        source_path,
        f"nativeVideoOverlay.background{kind.title()}.sourcePath",
    )
    if not source_file.is_file():
        raise ThemeValidationError(
            f"background {kind} source was not found: {source_path}"
        )
    if media_kind_for_path(source_file) != kind:
        raise ThemeValidationError("background source extension does not match its media kind")

    native.pop("allowOriginalEncoding", None)
    native.pop("backgroundVideo", None)
    native.pop("backgroundImage", None)
    if kind == "image":
        native["backgroundImage"] = {
            "sourcePath": source_path,
            "fit": fit,
            "position": position,
            **offsets,
        }
    else:
        native["backgroundVideo"] = {
            "sourcePath": source_path,
            "fit": fit,
            "position": position,
            "loop": loop,
            "startTime": start_time,
            **offsets,
        }
    _atomic_write_json(manifest.root / "manifest.json", payload)
    return ThemeManifest.load(manifest.root)


def save_background_video(
    manifest: ThemeManifest,
    *,
    source: Path | None = None,
    fit: str = "cover",
    position: str = "center",
    loop: bool = True,
    start_time: float = 0.0,
    offset_x: float | None = None,
    offset_y: float | None = None,
) -> ThemeManifest:
    return save_background_media(
        manifest,
        source=source,
        media_kind="video",
        fit=fit,
        position=position,
        loop=loop,
        start_time=start_time,
        offset_x=offset_x,
        offset_y=offset_y,
    )


def save_background_image(
    manifest: ThemeManifest,
    *,
    source: Path | None = None,
    fit: str = "cover",
    position: str = "center",
    offset_x: float | None = None,
    offset_y: float | None = None,
) -> ThemeManifest:
    return save_background_media(
        manifest,
        source=source,
        media_kind="image",
        fit=fit,
        position=position,
        offset_x=offset_x,
        offset_y=offset_y,
    )


def _remove_background_kind(manifest: ThemeManifest, kind: str) -> ThemeManifest:
    payload = _manifest_payload(manifest)
    native = payload.get("nativeVideoOverlay")
    key = f"background{kind.title()}"
    source_path = ""
    if isinstance(native, dict):
        value = native.get(key)
        if isinstance(value, dict):
            source_path = str(value.get("sourcePath") or "")
        native.pop(key, None)
        native.pop("allowOriginalEncoding", None)
    _atomic_write_json(manifest.root / "manifest.json", payload)
    if source_path:
        source = _safe_relative_file(manifest.root, source_path, f"{key}.sourcePath")
        if source.parent == (manifest.root / "assets").resolve() and source.name.startswith(
            f"background-{kind}."
        ):
            source.unlink(missing_ok=True)
    return ThemeManifest.load(manifest.root)


def remove_background_video(manifest: ThemeManifest) -> ThemeManifest:
    return _remove_background_kind(manifest, "video")


def remove_background_image(manifest: ThemeManifest) -> ThemeManifest:
    return _remove_background_kind(manifest, "image")


def remove_background_media(manifest: ThemeManifest) -> ThemeManifest:
    value = load_background_media(manifest, require_file=False)
    if value is None:
        return manifest
    return _remove_background_kind(manifest, value.kind)


def _anchor_expression(background: HtmlBackgroundMedia, *, crop: bool) -> tuple[str, str]:
    """FFmpeg x/y for crop (cover) or pad (contain) from the framing offsets."""
    horizontal, vertical = (value / 100.0 for value in background.offsets)
    if crop:
        return f"(iw-ow)*{horizontal:.4f}", f"(ih-oh)*{vertical:.4f}"
    return f"(ow-iw)*{horizontal:.4f}", f"(oh-ih)*{vertical:.4f}"


def background_filter(
    background: HtmlBackgroundMedia,
    *,
    width: int,
    height: int,
    fps: int,
    duration: float,
) -> str:
    if background.fit == "stretch":
        framing = f"scale={width}:{height}"
    elif background.fit == "contain":
        x, y = _anchor_expression(background, crop=False)
        framing = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:{x}:{y}:color=black"
        )
    else:
        x, y = _anchor_expression(background, crop=True)
        framing = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}:{x}:{y}"
        )
    return (
        f"[0:v]fps={fps},{framing},setsar=1,"
        f"tpad=stop_mode=clone:stop_duration={duration:.6f},"
        f"trim=duration={duration:.6f},setpts=PTS-STARTPTS[background];"
        "[1:v]format=rgba,setpts=PTS-STARTPTS[html];"
        "[background][html]overlay=0:0:shortest=1:format=auto[composite]"
    )


def image_pipe_ffmpeg_command(
    destination: Path,
    *,
    manifest: ThemeManifest,
    frame_count: int,
    background: HtmlBackgroundMedia | None,
    ffmpeg: str | None = None,
) -> list[str]:
    """Encode HTML frames, optionally composited over an image or video source."""
    executable = ffmpeg or shutil.which("ffmpeg")
    if not executable:
        raise FileNotFoundError("ffmpeg is required to build the native HTML video")
    spec = manifest.native_video_overlay
    if spec is None:
        raise ThemeValidationError("HTML theme does not enable nativeVideoOverlay")
    command = [executable, "-y", "-hide_banner", "-loglevel", "error"]
    if background is not None:
        if background.is_image:
            command.extend(["-loop", "1", "-framerate", str(spec.fps)])
        else:
            if background.loop:
                command.extend(["-stream_loop", "-1"])
            if background.start_time > 0:
                command.extend(["-ss", f"{background.start_time:.6f}"])
        command.extend(["-i", str(background.source_file(manifest.root))])
    command.extend(
        [
            "-f",
            "image2pipe",
            "-framerate",
            str(spec.fps),
            "-vcodec",
            "png",
            "-i",
            "pipe:0",
        ]
    )
    if background is not None:
        command.extend(
            [
                "-filter_complex",
                background_filter(
                    background,
                    width=manifest.width,
                    height=manifest.height,
                    fps=spec.fps,
                    duration=spec.duration,
                ),
                "-map",
                "[composite]",
            ]
        )
    command.extend(
        [
            "-r",
            str(spec.fps),
            "-frames:v",
            str(int(frame_count)),
            "-an",
            "-c:v",
            "libx264",
            "-profile:v",
            "baseline",
            "-level:v",
            "3.1",
            "-bf",
            "0",
            "-maxrate",
            "2500k",
            "-bufsize",
            "5000k",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-fps_mode",
            "cfr",
            "-movflags",
            "+faststart",
            str(Path(destination)),
        ]
    )
    return command


def extract_preview_frame(
    video: Path,
    destination: Path,
    *,
    timestamp: float,
    ffmpeg: str | None = None,
) -> None:
    executable = ffmpeg or shutil.which("ffmpeg")
    if not executable:
        raise FileNotFoundError("ffmpeg is required to extract the theme preview")
    command = [
        executable,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{max(0.0, float(timestamp)):.6f}",
        "-i",
        str(Path(video)),
        "-frames:v",
        "1",
        "-f",
        "image2",
        str(Path(destination)),
    ]
    result = subprocess.run(command, capture_output=True, check=False)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail or "ffmpeg could not extract the preview frame")
