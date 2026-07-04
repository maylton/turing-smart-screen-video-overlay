# SPDX-License-Identifier: GPL-3.0-or-later
"""Main app UI polish and animated overview preview hooks."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any, Mapping

from PIL import Image

from library.theme_preview_renderer import (
    build_preview_context,
    load_theme_document,
    render_theme_preview_frame,
    theme_canvas_size,
)
from library.theme_video_background import find_prepared_local_video
from library.theme_video_inspector import resolve_local_video_source


def _truthy(value) -> bool:
    if isinstance(value, str):
        return value.strip().strip('"\'').lower() in {
            "1",
            "true",
            "yes",
            "on",
            "enabled",
        }
    return bool(value)


def _unquote(value: Any) -> str:
    value = str(value or "").strip()
    if "#" in value:
        value = value.split("#", 1)[0].strip()
    return value.strip().strip('"\'')


def _case_insensitive_get(mapping: Mapping[str, Any], key: str, default=None):
    key_upper = str(key).upper()
    for candidate, value in mapping.items():
        if str(candidate).upper() == key_upper:
            return value
    return default


def _read_theme_video_config(theme_yaml: Path) -> dict[str, Any]:
    """Read the theme's video section using the shared preview YAML loader."""
    document = load_theme_document(theme_yaml)
    if isinstance(document, Mapping):
        for key, value in document.items():
            if str(key).lower() == "video" and isinstance(value, Mapping):
                return {str(item_key).upper(): item_value for item_key, item_value in value.items()}

    # Fallback for broken/incomplete YAML files: enough to detect a simple
    # `video:` block without crashing the Overview.
    try:
        lines = theme_yaml.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}

    in_video = False
    video_indent = 0
    data: dict[str, Any] = {}
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if not in_video:
            if stripped == "video:" or stripped.startswith("video: "):
                in_video = True
                video_indent = indent
            continue

        if indent <= video_indent and not stripped.startswith("-"):
            break

        match = re.match(r"([A-Za-z0-9_\-]+)\s*:\s*(.*)$", stripped)
        if not match:
            continue
        data[match.group(1).upper()] = _unquote(match.group(2))

    return data


def _theme_yaml_path(app, theme_name: str) -> Path | None:
    theme_dir = app.THEMES_DIR / theme_name
    for filename in ("theme.yaml", "theme.yml"):
        path = theme_dir / filename
        if path.is_file():
            return path
    return None


def _theme_video_path(app, theme_name: str) -> Path | None:
    theme_name = str(theme_name or "").strip()
    if not theme_name:
        return None

    theme_dir = app.THEMES_DIR / theme_name
    theme_yaml = _theme_yaml_path(app, theme_name)
    if theme_yaml is None:
        return None

    config = _read_theme_video_config(theme_yaml)
    if not _truthy(_case_insensitive_get(config, "ENABLED")):
        return None

    local = resolve_local_video_source(theme_dir, config)
    if local is not None and local.is_file():
        return local

    remote_path = _unquote(_case_insensitive_get(config, "PATH", ""))
    if remote_path:
        prepared = find_prepared_local_video(remote_path)
        if prepared is not None and prepared.is_file():
            return prepared

    local_path = _unquote(_case_insensitive_get(config, "LOCAL_PATH", ""))
    path_values = [local_path, remote_path]
    candidates: list[Path] = []
    for raw_path in path_values:
        if not raw_path:
            continue
        path = Path(os.path.expanduser(raw_path))
        if path.is_absolute() and not raw_path.startswith(("/mnt/SDCARD/", "/root/video/")):
            candidates.append(path)
            continue
        filename = Path(raw_path).name
        if not filename:
            continue
        candidates.extend([
            theme_dir / filename,
            theme_dir / raw_path.lstrip("./"),
            app.ROOT / raw_path.lstrip("./"),
            app.ROOT / "res" / "video" / filename,
            app.ROOT / "res" / "videos" / filename,
        ])

    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate.resolve()
        except OSError:
            continue
    return None


class OverviewLivePreviewAnimator:
    """Generate a short GIF for video themes and play cached frames in overview."""

    def __init__(self, app, window):
        self.app = app
        self.window = window
        self.theme_name = ""
        self.frames: list[Path] = []
        self.frame_index = 0
        self.timeout_id = 0
        self.worker_key = ""
        self.loading = False
        self.cache_root = Path.home() / ".cache" / "turing-smart-screen" / "overview-preview"

    def stop(self) -> None:
        if self.timeout_id:
            self.app.GLib.source_remove(self.timeout_id)
            self.timeout_id = 0
        self.frames = []
        self.frame_index = 0

    def show_theme(self, theme_name: str) -> None:
        theme_name = str(theme_name or "").strip()
        if not theme_name:
            self.stop()
            return

        video_path = _theme_video_path(self.app, theme_name)
        if video_path is None:
            self.stop()
            self.theme_name = theme_name
            return
        key = self.cache_key(theme_name, video_path)
        if key == self.worker_key and self.frames:
            self.start_loop()
            return
        self.stop()
        self.theme_name = theme_name
        self.worker_key = key
        self.prepare_preview_async(theme_name, video_path, key)

    def cache_key(self, theme_name: str, video_path: Path) -> str:
        theme_yaml = _theme_yaml_path(self.app, theme_name)
        try:
            stat = video_path.stat()
            video_stamp = f"{video_path}:{stat.st_size}:{int(stat.st_mtime)}"
        except OSError:
            video_stamp = str(video_path)
        try:
            theme_stat = theme_yaml.stat() if theme_yaml is not None else None
            theme_stamp = f"{theme_yaml}:{theme_stat.st_size}:{theme_stat.st_mtime_ns}" if theme_stat else ""
        except OSError:
            theme_stamp = str(theme_yaml or "")
        renderer_version = "full-theme-preview-v1-datetime-presets"
        digest = hashlib.sha1(
            f"{video_stamp}:{theme_stamp}:{renderer_version}".encode("utf-8")
        ).hexdigest()[:12]
        safe_theme = re.sub(r"[^A-Za-z0-9_.-]+", "-", theme_name).strip("-._") or "theme"
        return f"{safe_theme}-{digest}"

    def prepare_preview_async(self, theme_name: str, video_path: Path, key: str) -> None:
        if self.loading:
            return
        self.loading = True

        def worker() -> None:
            frames: list[Path] = []
            gif_path = ""
            error = ""
            try:
                frames, gif = self.generate_preview_assets(theme_name, video_path, key)
                gif_path = str(gif) if gif is not None else ""
            except Exception as exc:  # pragma: no cover - defensive UI guard
                error = str(exc)
            self.app.GLib.idle_add(
                self.finish_prepare_preview,
                theme_name,
                key,
                [str(frame) for frame in frames],
                gif_path,
                error,
            )

        threading.Thread(target=worker, daemon=True).start()

    def generate_preview_assets(
        self,
        theme_name: str,
        video_path: Path,
        key: str,
    ) -> tuple[list[Path], Path | None]:
        cache_dir = self.cache_root / key
        gif_path = cache_dir / "preview.gif"
        frames_dir = cache_dir / "frames"
        raw_frames_dir = cache_dir / "raw-frames"
        existing = sorted(frames_dir.glob("frame-*.png"))
        if existing and gif_path.is_file():
            return existing, gif_path

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return [], None

        theme_dir = self.app.THEMES_DIR / theme_name
        theme_yaml = _theme_yaml_path(self.app, theme_name)
        theme_doc = load_theme_document(theme_yaml) if theme_yaml is not None else {}
        context = build_preview_context(theme_doc)
        canvas_width, canvas_height = theme_canvas_size(theme_doc)

        frames_dir.mkdir(parents=True, exist_ok=True)
        raw_frames_dir.mkdir(parents=True, exist_ok=True)
        cache_dir.mkdir(parents=True, exist_ok=True)
        for directory in (frames_dir, raw_frames_dir):
            for old_frame in directory.glob("frame-*.png"):
                old_frame.unlink(missing_ok=True)
        gif_path.unlink(missing_ok=True)

        raw_pattern = raw_frames_dir / "frame-%03d.png"
        frame_filter = (
            f"fps=8,scale={canvas_width}:{canvas_height}:force_original_aspect_ratio=increase,"
            f"crop={canvas_width}:{canvas_height}"
        )
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-t",
                "3.5",
                "-i",
                str(video_path),
                "-vf",
                frame_filter,
                "-frames:v",
                "28",
                str(raw_pattern),
            ],
            cwd=str(self.app.ROOT),
            text=True,
            capture_output=True,
            check=False,
            timeout=16,
        )

        rendered_frames: list[Path] = []
        for index, raw_frame in enumerate(sorted(raw_frames_dir.glob("frame-*.png")), start=1):
            try:
                background = Image.open(raw_frame)
            except OSError:
                continue
            destination = frames_dir / f"frame-{index:03d}.png"
            rendered = render_theme_preview_frame(
                root=self.app.ROOT,
                theme_dir=theme_dir,
                theme_doc=theme_doc,
                background=background,
                context=context,
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            rendered.save(destination)
            rendered_frames.append(destination)
            background.close()

        if rendered_frames:
            pil_frames = [Image.open(path).convert("P", palette=Image.Palette.ADAPTIVE) for path in rendered_frames]
            first, rest = pil_frames[0], pil_frames[1:]
            first.save(
                gif_path,
                save_all=True,
                append_images=rest,
                duration=125,
                loop=0,
                optimize=True,
            )
            for frame in pil_frames:
                frame.close()

        return rendered_frames, gif_path if gif_path.is_file() else None

    def finish_prepare_preview(
        self,
        theme_name: str,
        key: str,
        frame_paths: list[str],
        gif_path: str,
        error: str,
    ) -> bool:
        self.loading = False
        if key != self.worker_key or theme_name != self.theme_name:
            return False

        self.frames = [Path(path) for path in frame_paths if Path(path).is_file()]
        self.frame_index = 0
        if not self.frames:
            return False

        self.start_loop()
        return False

    def start_loop(self) -> None:
        if self.timeout_id:
            self.app.GLib.source_remove(self.timeout_id)
        self.timeout_id = self.app.GLib.timeout_add(125, self.tick)
        self.tick()

    def tick(self) -> bool:
        if not self.frames:
            self.timeout_id = 0
            return False
        picture = getattr(self.window, "overview_picture", None)
        if picture is None:
            self.timeout_id = 0
            return False

        frame = self.frames[self.frame_index % len(self.frames)]
        self.frame_index += 1
        try:
            texture = self.app.Gdk.Texture.new_from_filename(str(frame))
            picture.set_paintable(texture)
        except Exception:
            return True
        return True


def install_main_app_ui_polish_patches(app, *, root: Path) -> None:
    """Improve overview visual hierarchy and add a full-theme video preview."""

    original_build_overview_page = app.SmartScreenWindow.build_overview_page
    original_refresh_overview = app.SmartScreenWindow.refresh_overview

    def build_overview_page(self):
        page = original_build_overview_page(self)
        picture = getattr(self, "overview_picture", None)
        if picture is not None and not getattr(self, "_overview_preview_enhanced", False):
            picture.add_css_class("device-live-preview")
            self._overview_preview_enhanced = True
        return page

    def refresh_overview(self):
        result = original_refresh_overview(self)
        animator = getattr(self, "overview_preview_animator", None)
        if animator is None:
            animator = OverviewLivePreviewAnimator(app, self)
            self.overview_preview_animator = animator
        animator.show_theme(getattr(self, "current_theme", ""))
        return result

    app.SmartScreenWindow.build_overview_page = build_overview_page
    app.SmartScreenWindow.refresh_overview = refresh_overview
