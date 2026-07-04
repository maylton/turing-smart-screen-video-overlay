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


def _truthy(value: str) -> bool:
    return str(value or "").strip().strip('"\'').lower() in {
        "1",
        "true",
        "yes",
        "on",
        "enabled",
    }


def _unquote(value: str) -> str:
    value = str(value or "").strip()
    if "#" in value:
        value = value.split("#", 1)[0].strip()
    return value.strip().strip('"\'')


def _read_simple_theme_video_config(theme_yaml: Path) -> dict[str, str]:
    """Read a simple `video:` block without importing the full YAML stack."""
    try:
        lines = theme_yaml.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}

    in_video = False
    video_indent = 0
    data: dict[str, str] = {}
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
    theme_yaml = _theme_yaml_path(app, theme_name)
    if theme_yaml is None:
        return None

    config = _read_simple_theme_video_config(theme_yaml)
    if not _truthy(config.get("ENABLED", "")):
        return None

    raw_path = _unquote(config.get("PATH", ""))
    if not raw_path:
        return None

    candidates: list[Path] = []
    path = Path(os.path.expanduser(raw_path))
    if path.is_absolute():
        candidates.append(path)
    else:
        clean = raw_path.lstrip("./")
        candidates.extend([
            (app.THEMES_DIR / theme_name / clean),
            (app.ROOT / clean),
            (app.ROOT / raw_path),
        ])

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


class OverviewLivePreviewAnimator:
    """Extract a tiny frame loop from the active theme video and play it in overview."""

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

    def set_caption(self, text: str) -> None:
        label = getattr(self.window, "overview_preview_caption", None)
        if label is not None:
            label.set_label(text)

    def show_theme(self, theme_name: str) -> None:
        theme_name = str(theme_name or "").strip()
        if not theme_name:
            self.stop()
            self.set_caption("No active theme")
            return

        video_path = _theme_video_path(self.app, theme_name)
        if video_path is None:
            self.stop()
            self.theme_name = theme_name
            self.set_caption("Static theme preview")
            return

        key = self.cache_key(theme_name, video_path)
        if key == self.worker_key and self.frames:
            self.start_loop()
            return

        self.stop()
        self.theme_name = theme_name
        self.worker_key = key
        self.set_caption("Preparing live preview…")
        self.prepare_frames_async(theme_name, video_path, key)

    def cache_key(self, theme_name: str, video_path: Path) -> str:
        try:
            stat = video_path.stat()
            stamp = f"{video_path}:{stat.st_size}:{int(stat.st_mtime)}"
        except OSError:
            stamp = str(video_path)
        digest = hashlib.sha1(stamp.encode("utf-8")).hexdigest()[:12]
        safe_theme = re.sub(r"[^A-Za-z0-9_.-]+", "-", theme_name).strip("-._") or "theme"
        return f"{safe_theme}-{digest}"

    def prepare_frames_async(self, theme_name: str, video_path: Path, key: str) -> None:
        if self.loading:
            return
        self.loading = True

        def worker() -> None:
            frames: list[Path] = []
            error = ""
            try:
                frames = self.extract_frames(video_path, key)
            except Exception as exc:  # pragma: no cover - defensive UI guard
                error = str(exc)
            self.app.GLib.idle_add(
                self.finish_prepare_frames,
                theme_name,
                key,
                [str(frame) for frame in frames],
                error,
            )

        threading.Thread(target=worker, daemon=True).start()

    def extract_frames(self, video_path: Path, key: str) -> list[Path]:
        cache_dir = self.cache_root / key
        existing = sorted(cache_dir.glob("frame-*.png"))
        if existing:
            return existing

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return []

        cache_dir.mkdir(parents=True, exist_ok=True)
        output_pattern = cache_dir / "frame-%03d.png"
        command = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video_path),
            "-vf",
            "fps=2,scale=360:360:force_original_aspect_ratio=decrease",
            "-frames:v",
            "12",
            str(output_pattern),
        ]
        subprocess.run(
            command,
            cwd=str(self.app.ROOT),
            text=True,
            capture_output=True,
            check=False,
            timeout=12,
        )
        return sorted(cache_dir.glob("frame-*.png"))

    def finish_prepare_frames(
        self,
        theme_name: str,
        key: str,
        frame_paths: list[str],
        error: str,
    ) -> bool:
        self.loading = False
        if key != self.worker_key or theme_name != self.theme_name:
            return False

        self.frames = [Path(path) for path in frame_paths if Path(path).is_file()]
        self.frame_index = 0
        if not self.frames:
            self.set_caption("Static preview — no playable theme video found" if not error else f"Static preview — {error}")
            return False

        self.set_caption("Live theme preview")
        self.start_loop()
        return False

    def start_loop(self) -> None:
        if self.timeout_id:
            self.app.GLib.source_remove(self.timeout_id)
        self.timeout_id = self.app.GLib.timeout_add(500, self.tick)
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
    """Improve overview visual hierarchy and add a live video-backed preview."""

    original_build_overview_page = app.SmartScreenWindow.build_overview_page
    original_refresh_overview = app.SmartScreenWindow.refresh_overview

    def build_overview_page(self):
        page = original_build_overview_page(self)

        picture = getattr(self, "overview_picture", None)
        if picture is not None and not getattr(self, "_overview_preview_enhanced", False):
            picture.add_css_class("device-live-preview")
            parent = picture.get_parent()
            if parent is not None and hasattr(parent, "set_child"):
                parent.set_child(None)
                overlay = app.Gtk.Overlay()
                overlay.set_child(picture)

                caption = app.Gtk.Label(label="Static theme preview")
                caption.add_css_class("caption")
                caption.add_css_class("osd")
                caption.set_halign(app.Gtk.Align.CENTER)
                caption.set_valign(app.Gtk.Align.END)
                caption.set_margin_bottom(12)
                overlay.add_overlay(caption)

                parent.set_child(overlay)
                self.overview_preview_caption = caption
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
