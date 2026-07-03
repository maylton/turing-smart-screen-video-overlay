# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure helpers for the GTK theme video inspector."""

from __future__ import annotations

import copy
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from library.media_preparation import (
    ConversionSettings,
    convert_media,
    create_preview,
    safe_output_name,
)


class ThemeVideoInspectorError(ValueError):
    """Raised when a video inspector operation is unsafe or invalid."""


@dataclass(frozen=True)
class VideoThemeUpdate:
    """Validated values written to the theme's ``video`` mapping."""

    local_filename: str
    remote_path: str
    preview_background: str
    background_frame_time: float = 0.0
    overlay: bool = True

    def __post_init__(self) -> None:
        local_filename = Path(str(self.local_filename or "")).name
        if not local_filename or local_filename in {".", ".."}:
            raise ThemeVideoInspectorError("A prepared local video filename is required.")
        if Path(local_filename).suffix.lower() != ".mp4":
            raise ThemeVideoInspectorError("Prepared local video must use the .mp4 extension.")

        remote_path = str(self.remote_path or "").strip()
        remote = Path(remote_path)
        if (
            any(part == ".." for part in remote.parts)
            or remote.parent.as_posix() not in {"/mnt/SDCARD/video", "/root/video"}
        ):
            raise ThemeVideoInspectorError("Remote video path must use supported display storage.")
        if remote.name != local_filename:
            raise ThemeVideoInspectorError("Local and remote video filenames must match.")

        preview_background = Path(str(self.preview_background or "")).name
        if not preview_background or preview_background in {".", ".."}:
            raise ThemeVideoInspectorError("A preview background filename is required.")
        if Path(preview_background).suffix.lower() != ".png":
            raise ThemeVideoInspectorError("Preview background must use the .png extension.")

        frame_time = float(self.background_frame_time)
        if frame_time < 0:
            raise ThemeVideoInspectorError("Background frame time cannot be negative.")

        object.__setattr__(self, "local_filename", local_filename)
        object.__setattr__(self, "remote_path", remote_path)
        object.__setattr__(self, "preview_background", preview_background)
        object.__setattr__(self, "background_frame_time", frame_time)
        object.__setattr__(self, "overlay", bool(self.overlay))


def resolve_local_video_source(
    theme_dir: str | Path,
    video_section: Mapping[str, Any] | None,
) -> Path | None:
    """Resolve an existing local video referenced by the theme.

    Remote display paths are intentionally ignored.  Callers may separately
    search the media-preparation cache by remote filename.
    """
    root = Path(theme_dir).expanduser().resolve()
    video = video_section if isinstance(video_section, Mapping) else {}
    for key in ("LOCAL_PATH", "PATH"):
        raw = str(video.get(key) or "").strip()
        if not raw or raw.startswith(("/mnt/SDCARD/", "/root/video/")):
            continue
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            if any(part == ".." for part in candidate.parts):
                continue
            candidate = root / candidate
        candidate = candidate.resolve()
        if candidate.is_file():
            return candidate
    return None


def prepared_output_path(directory: str | Path, requested_name: str) -> Path:
    """Return a safe MP4 destination inside an existing preparation directory."""
    root = Path(directory).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    name = safe_output_name(requested_name)
    destination = (root / name).resolve()
    try:
        destination.relative_to(root)
    except ValueError as exc:
        raise ThemeVideoInspectorError("Prepared output escapes its directory.") from exc
    return destination


def preview_background_path(theme_dir: str | Path, requested_name: str) -> Path:
    """Return a safe theme-local PNG destination."""
    root = Path(theme_dir).expanduser().resolve()
    raw = Path(str(requested_name or "")).name
    if not raw or raw in {".", ".."}:
        raw = "video-preview.png"
    if Path(raw).suffix.lower() != ".png":
        raw = f"{Path(raw).stem}.png"
    destination = (root / raw).resolve()
    try:
        destination.relative_to(root)
    except ValueError as exc:
        raise ThemeVideoInspectorError("Preview background escapes the theme.") from exc
    return destination


def build_video_section(
    existing: Mapping[str, Any] | None,
    update: VideoThemeUpdate,
) -> dict[str, Any]:
    """Return a video mapping that preserves unrelated existing keys."""
    update = VideoThemeUpdate(
        local_filename=update.local_filename,
        remote_path=update.remote_path,
        preview_background=update.preview_background,
        background_frame_time=update.background_frame_time,
        overlay=update.overlay,
    )
    section = copy.deepcopy(existing) if isinstance(existing, Mapping) else {}
    section.update(
        {
            "ENABLED": True,
            "MODE": "native",
            "PATH": update.remote_path,
            "LOCAL_PATH": update.local_filename,
            "PREVIEW_BACKGROUND": update.preview_background,
            "BACKGROUND_FRAME_TIME": update.background_frame_time,
            "OVERLAY": update.overlay,
        }
    )
    return section


def _temporary_mp4(destination: Path) -> Path:
    fd, name = tempfile.mkstemp(
        prefix=f".{destination.stem}.",
        suffix=".tmp.mp4",
        dir=str(destination.parent),
    )
    os.close(fd)
    path = Path(name)
    path.unlink(missing_ok=True)
    return path


def convert_media_atomic(
    source_path: str | Path,
    output_path: str | Path,
    settings: ConversionSettings,
) -> dict[str, Any]:
    """Convert and atomically install a prepared MP4."""
    destination = Path(output_path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_mp4(destination)
    try:
        result = convert_media(source_path, temporary, settings)
        if not temporary.is_file() or temporary.stat().st_size <= 0:
            raise ThemeVideoInspectorError("Media conversion did not create an output file.")
        os.replace(temporary, destination)
        return result
    finally:
        temporary.unlink(missing_ok=True)


def create_preview_atomic(
    source_path: str | Path,
    output_path: str | Path,
    settings: ConversionSettings,
) -> Path:
    """Create and atomically install a PNG preview frame."""
    destination = Path(output_path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(
        prefix=f".{destination.stem}.",
        suffix=".tmp.png",
        dir=str(destination.parent),
    )
    os.close(fd)
    temporary = Path(name)
    temporary.unlink(missing_ok=True)
    try:
        create_preview(source_path, temporary, settings)
        if not temporary.is_file() or temporary.stat().st_size <= 0:
            raise ThemeVideoInspectorError("Preview generation did not create an image.")
        os.replace(temporary, destination)
        return destination
    finally:
        temporary.unlink(missing_ok=True)
