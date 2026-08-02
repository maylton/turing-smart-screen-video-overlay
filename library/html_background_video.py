# SPDX-License-Identifier: GPL-3.0-or-later
"""Background-video source settings for compiled HTML theme videos."""

from __future__ import annotations

import json
import math
import os
import shutil
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
SUPPORTED_SOURCE_SUFFIXES = {
    ".mp4",
    ".m4v",
    ".mov",
    ".mkv",
    ".webm",
    ".avi",
    ".gif",
}


@dataclass(frozen=True)
class HtmlBackgroundVideo:
    source_path: str
    fit: str = "cover"
    position: str = "center"
    loop: bool = True
    start_time: float = 0.0

    def source_file(self, root: Path) -> Path:
        return _safe_relative_file(root, self.source_path, "backgroundVideo.sourcePath")


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


def load_background_video(
    manifest: ThemeManifest,
    *,
    require_file: bool = True,
) -> HtmlBackgroundVideo | None:
    """Return the optional source video compiled behind the HTML base layer."""
    payload = _manifest_payload(manifest)
    native = payload.get("nativeVideoOverlay")
    if not isinstance(native, dict):
        return None
    value = native.get("backgroundVideo")
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ThemeValidationError("nativeVideoOverlay.backgroundVideo must be an object")

    source_path = str(value.get("sourcePath") or "").strip()
    source = _safe_relative_file(
        manifest.root,
        source_path,
        "nativeVideoOverlay.backgroundVideo.sourcePath",
    )
    if source.suffix.lower() not in SUPPORTED_SOURCE_SUFFIXES:
        raise ThemeValidationError(
            "background video source must be a common video or GIF file"
        )
    if require_file and not source.is_file():
        raise ThemeValidationError(
            f"background video source was not found: {source_path}"
        )

    fit = str(value.get("fit", "cover")).strip().lower()
    if fit not in SUPPORTED_FITS:
        raise ThemeValidationError(
            "backgroundVideo.fit must be cover, contain, or stretch"
        )
    position = str(value.get("position", "center")).strip().lower()
    if position not in SUPPORTED_POSITIONS:
        raise ThemeValidationError(
            "backgroundVideo.position uses an unsupported anchor"
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
    return HtmlBackgroundVideo(
        source_path=source_path,
        fit=fit,
        position=position,
        loop=loop,
        start_time=start_time,
    )


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def save_background_video(
    manifest: ThemeManifest,
    *,
    source: Path | None = None,
    fit: str = "cover",
    position: str = "center",
    loop: bool = True,
    start_time: float = 0.0,
) -> ThemeManifest:
    """Copy an optional source into assets and persist compilation settings."""
    if manifest.engine != "html" or manifest.native_video_overlay is None:
        raise ThemeValidationError(
            "background video requires an HTML native-video theme"
        )
    fit = str(fit).strip().lower()
    position = str(position).strip().lower()
    if fit not in SUPPORTED_FITS:
        raise ThemeValidationError("background video fit is unsupported")
    if position not in SUPPORTED_POSITIONS:
        raise ThemeValidationError("background video position is unsupported")
    if not isinstance(loop, bool):
        raise ThemeValidationError("background video loop must be a boolean")
    start_time = float(start_time)
    if not math.isfinite(start_time) or start_time < 0:
        raise ThemeValidationError("background video start time is invalid")

    payload = _manifest_payload(manifest)
    native = payload.get("nativeVideoOverlay")
    if not isinstance(native, dict):
        raise ThemeValidationError("nativeVideoOverlay must be an object")

    existing = load_background_video(manifest, require_file=False)
    source_path = existing.source_path if existing is not None else ""
    if source is not None:
        selected = Path(source).expanduser().resolve()
        if not selected.is_file():
            raise ThemeValidationError(f"background video was not found: {selected}")
        suffix = selected.suffix.lower()
        if suffix not in SUPPORTED_SOURCE_SUFFIXES:
            raise ThemeValidationError(
                "select an MP4, MOV, MKV, WebM, AVI, M4V, or GIF file"
            )
        assets = manifest.root / "assets"
        assets.mkdir(parents=True, exist_ok=True)
        destination = assets / f"background-source{suffix}"
        temporary = destination.with_name(
            f".{destination.name}.{os.getpid()}.tmp{suffix}"
        )
        shutil.copy2(selected, temporary)
        os.replace(temporary, destination)
        source_path = destination.relative_to(manifest.root).as_posix()

    if not source_path:
        raise ThemeValidationError("select a background video first")
    source_file = _safe_relative_file(
        manifest.root,
        source_path,
        "nativeVideoOverlay.backgroundVideo.sourcePath",
    )
    if not source_file.is_file():
        raise ThemeValidationError(
            f"background video source was not found: {source_path}"
        )

    native.pop("allowOriginalEncoding", None)
    native["backgroundVideo"] = {
        "sourcePath": source_path,
        "fit": fit,
        "position": position,
        "loop": loop,
        "startTime": start_time,
    }
    _atomic_write_json(manifest.root / "manifest.json", payload)
    return ThemeManifest.load(manifest.root)


def remove_background_video(manifest: ThemeManifest) -> ThemeManifest:
    payload = _manifest_payload(manifest)
    native = payload.get("nativeVideoOverlay")
    if isinstance(native, dict):
        native.pop("backgroundVideo", None)
        native.pop("allowOriginalEncoding", None)
    _atomic_write_json(manifest.root / "manifest.json", payload)
    return ThemeManifest.load(manifest.root)


def _anchor_expression(position: str, *, crop: bool) -> tuple[str, str]:
    horizontal, vertical = {
        "center": ("center", "center"),
        "top-left": ("start", "start"),
        "top": ("center", "start"),
        "top-right": ("end", "start"),
        "left": ("start", "center"),
        "right": ("end", "center"),
        "bottom-left": ("start", "end"),
        "bottom": ("center", "end"),
        "bottom-right": ("end", "end"),
    }[position]
    if crop:
        x = {"start": "0", "center": "(iw-ow)/2", "end": "iw-ow"}[horizontal]
        y = {"start": "0", "center": "(ih-oh)/2", "end": "ih-oh"}[vertical]
    else:
        x = {"start": "0", "center": "(ow-iw)/2", "end": "ow-iw"}[horizontal]
        y = {"start": "0", "center": "(oh-ih)/2", "end": "oh-ih"}[vertical]
    return x, y


def background_filter(
    background: HtmlBackgroundVideo,
    *,
    width: int,
    height: int,
    fps: int,
    duration: float,
) -> str:
    if background.fit == "stretch":
        framing = f"scale={width}:{height}"
    elif background.fit == "contain":
        x, y = _anchor_expression(background.position, crop=False)
        framing = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:{x}:{y}:color=black"
        )
    else:
        x, y = _anchor_expression(background.position, crop=True)
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
    background: HtmlBackgroundVideo | None,
    ffmpeg: str | None = None,
) -> list[str]:
    """Encode captured HTML frames, optionally composited over a source video."""
    executable = ffmpeg or shutil.which("ffmpeg")
    if not executable:
        raise FileNotFoundError("ffmpeg is required to build the native HTML video")
    spec = manifest.native_video_overlay
    if spec is None:
        raise ThemeValidationError("HTML theme does not enable nativeVideoOverlay")
    command = [executable, "-y", "-hide_banner", "-loglevel", "error"]
    if background is not None:
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
    subprocess_command = [
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
    import subprocess

    result = subprocess.run(subprocess_command, capture_output=True, check=False)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail or "ffmpeg could not extract the preview frame")
