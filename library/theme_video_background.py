"""Helpers shared by the GTK theme editor video/background workflow."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

SD_VIDEO_DIR = "/mnt/SDCARD/video/"
INTERNAL_VIDEO_DIR = "/root/video/"


def _install_theme_editor_i18n_startup_hook() -> None:
    """Install editor i18n before theme-editor-gtk.py defines its window."""

    try:
        from library.theme_editor_i18n import install_theme_editor_i18n_class_hook

        install_theme_editor_i18n_class_hook()
    except Exception:
        # Keep this helper import-safe for tests and non-UI tools.
        pass


_install_theme_editor_i18n_startup_hook()


def _theme_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def theme_uses_video_overlay(theme_data: dict) -> bool:
    """Return whether widgets should render as transparent video overlays."""
    video = theme_data.get("video", {}) if isinstance(theme_data, dict) else {}
    if not isinstance(video, dict):
        return False
    return _theme_bool(video.get("ENABLED")) and _theme_bool(video.get("OVERLAY"))


def display_video_path(filename: str, *, internal: bool = False) -> str:
    """Return a safe absolute video path for the selected display storage."""
    name = Path(str(filename)).name
    if not name or name in {".", ".."}:
        raise ValueError("A video filename is required.")
    try:
        name.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("Display video names must use ASCII characters.") from exc
    directory = INTERNAL_VIDEO_DIR if internal else SD_VIDEO_DIR
    return f"{directory}{name}"


def resolve_ffmpeg(executable: str | None = None) -> str:
    candidate = executable or shutil.which("ffmpeg")
    if not candidate:
        raise FileNotFoundError(
            "ffmpeg was not found. Install FFmpeg to generate a background."
        )
    return candidate


def build_background_command(
    source: Path,
    destination: Path,
    *,
    timestamp: float = 0.0,
    width: int = 480,
    height: int = 480,
    ffmpeg: str | None = None,
) -> list[str]:
    """Build the deterministic command used to extract a theme background."""
    if width <= 0 or height <= 0:
        raise ValueError("Background dimensions must be positive.")
    if timestamp < 0:
        raise ValueError("Timestamp cannot be negative.")

    source = Path(source).expanduser().resolve()
    destination = Path(destination).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Video not found: {source}")

    video_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height}"
    )
    return [
        resolve_ffmpeg(ffmpeg),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{timestamp:.3f}",
        "-i",
        str(source),
        "-frames:v",
        "1",
        "-vf",
        video_filter,
        "-an",
        str(destination),
    ]


def generate_background(
    source: Path,
    destination: Path,
    *,
    timestamp: float = 0.0,
    width: int = 480,
    height: int = 480,
    ffmpeg: str | None = None,
) -> Path:
    """Extract one centered frame and atomically install it as a PNG."""
    destination = Path(destination).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp.png")
    temporary.unlink(missing_ok=True)

    command = build_background_command(
        source,
        temporary,
        timestamp=timestamp,
        width=width,
        height=height,
        ffmpeg=ffmpeg,
    )
    try:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if not temporary.is_file() or temporary.stat().st_size <= 0:
            raise RuntimeError("FFmpeg did not create a background image.")
        temporary.replace(destination)
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(f"Could not generate background: {message}") from exc
    finally:
        temporary.unlink(missing_ok=True)

    return destination


def prepared_media_directories() -> tuple[Path, ...]:
    cache_home = Path(
        os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
    ).expanduser()
    data_home = Path(
        os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
    ).expanduser()
    return (
        cache_home / "turing-smart-screen" / "media-preparation",
        data_home / "turing-smart-screen" / "media",
    )


def find_prepared_local_video(remote_path: str) -> Path | None:
    filename = Path(str(remote_path)).name
    if not filename:
        return None

    candidates = []
    for directory in prepared_media_directories():
        candidate = directory / filename
        if candidate.is_file():
            candidates.append(candidate.resolve())

    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)
