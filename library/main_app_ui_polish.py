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

from PIL import Image, ImageDraw, ImageFont

from library.theme_video_background import find_prepared_local_video
from library.theme_video_inspector import resolve_local_video_source

_DISPLAY_SIZES = {
    '0.96"': (80, 160),
    '2.1"': (480, 480),
    '2.8"': (480, 480),
    '3.5"': (320, 480),
    '4.6"': (320, 960),
    '5"': (480, 800),
    '5.2"': (720, 1280),
    '8"': (800, 1280),
    '8.8"': (480, 1920),
    '9.2"': (480, 1920),
    '12.3"': (720, 1920),
}


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


def _read_theme_data(theme_yaml: Path) -> Mapping[str, Any]:
    try:
        import ruamel.yaml

        yaml = ruamel.yaml.YAML(typ="safe")
        with theme_yaml.open("r", encoding="utf-8") as stream:
            document = yaml.load(stream) or {}
        if isinstance(document, Mapping):
            return document
    except Exception:
        pass
    return {}


def _read_theme_video_config(theme_yaml: Path) -> dict[str, Any]:
    """Read the theme's video section using ruamel, with a tiny fallback parser."""
    document = _read_theme_data(theme_yaml)
    for key, value in document.items():
        if str(key).lower() == "video" and isinstance(value, Mapping):
            return {str(item_key).upper(): item_value for item_key, item_value in value.items()}

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


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _color(value: Any, default=(255, 255, 255, 255)) -> tuple[int, int, int, int]:
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
        if len(parts) in (3, 4):
            try:
                values = [int(part) for part in parts]
            except ValueError:
                values = list(default)
        else:
            values = list(default)
    elif isinstance(value, (list, tuple)):
        values = [int(component) for component in value[:4]]
    else:
        values = list(default)

    while len(values) < 4:
        values.append(255)
    return tuple(max(0, min(255, component)) for component in values[:4])


def _theme_canvas_size(theme_data: Mapping[str, Any]) -> tuple[int, int]:
    display = theme_data.get("display", {}) if isinstance(theme_data, Mapping) else {}
    size = str(display.get("DISPLAY_SIZE", '2.1"')) if isinstance(display, Mapping) else '2.1"'
    return _DISPLAY_SIZES.get(size, (480, 480))


def _resolve_theme_asset(theme_dir: Path, raw_path: Any) -> Path | None:
    raw = _unquote(raw_path)
    if not raw:
        return None
    path = Path(os.path.expanduser(raw))
    candidates = [path] if path.is_absolute() else [theme_dir / raw.lstrip("./")]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _paste_clipped(base: Image.Image, overlay: Image.Image, x: int, y: int) -> None:
    overlay = overlay.convert("RGBA")
    left = max(0, x)
    top = max(0, y)
    right = min(base.width, x + overlay.width)
    bottom = min(base.height, y + overlay.height)
    if right <= left or bottom <= top:
        return
    crop_left = left - x
    crop_top = top - y
    crop = overlay.crop((crop_left, crop_top, crop_left + right - left, crop_top + bottom - top))
    base.alpha_composite(crop, (left, top))


def _font_path(root: Path, theme_dir: Path, raw_font: Any) -> Path | None:
    raw = _unquote(raw_font)
    if not raw:
        raw = "roboto-mono/RobotoMono-Regular.ttf"
    candidates = [
        theme_dir / raw,
        root / raw,
        root / "res" / "fonts" / raw,
        root / "res" / "fonts" / "roboto-mono" / "RobotoMono-Regular.ttf",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _load_font(root: Path, theme_dir: Path, raw_font: Any, size: int) -> ImageFont.ImageFont:
    candidate = _font_path(root, theme_dir, raw_font)
    if candidate is not None:
        try:
            return ImageFont.truetype(str(candidate), max(1, size))
        except OSError:
            pass
    return ImageFont.load_default()


def _draw_static_images(frame: Image.Image, theme_dir: Path, theme_data: Mapping[str, Any]) -> None:
    images = theme_data.get("static_images", {}) if isinstance(theme_data, Mapping) else {}
    if not isinstance(images, Mapping):
        return
    for item in images.values():
        if not isinstance(item, Mapping) or not item.get("SHOW", True):
            continue
        source = _resolve_theme_asset(theme_dir, item.get("PATH"))
        if source is None:
            continue
        try:
            overlay = Image.open(source).convert("RGBA")
        except OSError:
            continue
        width = _safe_int(item.get("WIDTH"), overlay.width)
        height = _safe_int(item.get("HEIGHT"), overlay.height)
        if width > 0 and height > 0 and (width, height) != overlay.size:
            overlay = overlay.resize((width, height), Image.Resampling.LANCZOS)
        _paste_clipped(frame, overlay, _safe_int(item.get("X")), _safe_int(item.get("Y")))


def _draw_text_layer(
    frame: Image.Image,
    root: Path,
    theme_dir: Path,
    item: Mapping[str, Any],
) -> None:
    text = str(item.get("TEXT") or item.get("FORMAT") or "")
    if not text:
        return

    x = _safe_int(item.get("X"))
    y = _safe_int(item.get("Y"))
    width = max(1, _safe_int(item.get("WIDTH"), 160))
    height = max(1, _safe_int(item.get("HEIGHT"), _safe_int(item.get("FONT_SIZE"), 16) + 8))
    font_size = max(1, _safe_int(item.get("FONT_SIZE"), 16))
    font = _load_font(root, theme_dir, item.get("FONT"), font_size)

    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    background_image = _resolve_theme_asset(theme_dir, item.get("BACKGROUND_IMAGE"))
    if background_image is not None:
        try:
            bg = Image.open(background_image).convert("RGBA").resize((width, height), Image.Resampling.LANCZOS)
            layer.alpha_composite(bg, (0, 0))
        except OSError:
            pass
    elif "BACKGROUND_COLOR" in item:
        draw.rectangle((0, 0, width, height), fill=_color(item.get("BACKGROUND_COLOR"), (0, 0, 0, 0)))

    fill = _color(item.get("FONT_COLOR"), (255, 255, 255, 255))
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=2)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    align = str(item.get("ALIGN", "left")).lower()
    anchor = str(item.get("ANCHOR", "lt")).lower()

    tx = 0
    if align in {"center", "middle"}:
        tx = max(0, (width - text_width) // 2)
    elif align in {"right", "end"}:
        tx = max(0, width - text_width)

    ty = 0
    if "m" in anchor or "c" in anchor:
        ty = max(0, (height - text_height) // 2)
    elif "b" in anchor:
        ty = max(0, height - text_height)

    draw.multiline_text((tx, ty), text, font=font, fill=fill, spacing=2, align=align if align in {"left", "center", "right"} else "left")
    _paste_clipped(frame, layer, x, y)


def _draw_static_text(frame: Image.Image, root: Path, theme_dir: Path, theme_data: Mapping[str, Any]) -> None:
    texts = theme_data.get("static_text", {}) if isinstance(theme_data, Mapping) else {}
    if not isinstance(texts, Mapping):
        return
    for item in texts.values():
        if not isinstance(item, Mapping) or not item.get("SHOW", True):
            continue
        _draw_text_layer(frame, root, theme_dir, item)


def _render_theme_overlays(
    frame_path: Path,
    output_path: Path,
    *,
    root: Path,
    theme_dir: Path,
    theme_data: Mapping[str, Any],
) -> Path:
    frame = Image.open(frame_path).convert("RGBA")
    _draw_static_images(frame, theme_dir, theme_data)
    _draw_static_text(frame, root, theme_dir, theme_data)
    preview = frame.copy()
    preview.thumbnail((360, 360), Image.Resampling.LANCZOS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    preview.save(output_path)
    return output_path


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
        digest = hashlib.sha1(f"{video_stamp}:{theme_stamp}".encode("utf-8")).hexdigest()[:12]
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
        theme_data = _read_theme_data(theme_yaml) if theme_yaml is not None else {}
        canvas_width, canvas_height = _theme_canvas_size(theme_data)

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
            destination = frames_dir / f"frame-{index:03d}.png"
            rendered_frames.append(
                _render_theme_overlays(
                    raw_frame,
                    destination,
                    root=self.app.ROOT,
                    theme_dir=theme_dir,
                    theme_data=theme_data,
                )
            )

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
    """Improve overview visual hierarchy and add an overlay-aware video preview."""

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
