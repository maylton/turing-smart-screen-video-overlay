# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure contracts shared by the HTML native-video builder and runtime."""

from __future__ import annotations

import json
import math
import shutil
from pathlib import Path
from typing import Callable

from PIL import Image, ImageChops

from library.theme_engine import NativeVideoOverlay, ThemeManifest, ThemeValidationError
from library.video_media import VideoProbe, probe_video

OVERLAY_SELECTOR = "[data-turing-overlay]"


def overlay_frames_equal(previous: Image.Image, current: Image.Image) -> bool:
    """Compare every RGBA channel; Pillow otherwise ignores RGB under alpha."""
    if previous.size != current.size:
        return False
    difference = ImageChops.difference(
        previous.convert("RGBA"),
        current.convert("RGBA"),
    )
    try:
        return difference.getbbox(alpha_only=False) is None
    except TypeError:  # Pillow < 12
        return all(channel.getbbox() is None for channel in difference.split())


def _selector_literal(selector: str) -> str:
    return json.dumps(str(selector), ensure_ascii=True)


def base_layer_script(selector: str) -> str:
    """Hide declared live elements and make CSS animations seekable."""
    encoded = _selector_literal(selector)
    return (
        "(() => {"
        f"const selector={encoded};"
        "const nodes=[...document.querySelectorAll(selector)];"
        "if(!nodes.length)throw new Error('No native overlay elements found');"
        "for(const node of nodes){"
        "node.style.setProperty('visibility','hidden','important');}"
        "for(const node of document.querySelectorAll('*')){"
        "node.style.setProperty('transition','none','important');"
        "node.style.setProperty('caret-color','transparent','important');}"
        "document.documentElement.dataset.turingRenderMode='base';"
        "for(const animation of document.getAnimations()){animation.pause();}"
        "return nodes.length;"
        "})()"
    )


def overlay_layer_script(selector: str) -> str:
    """Expose only declared live elements on a transparent page."""
    encoded = _selector_literal(selector)
    return (
        "(() => {"
        f"const selector={encoded};"
        "const nodes=[...document.querySelectorAll(selector)];"
        "if(!nodes.length)throw new Error('No native overlay elements found');"
        "document.documentElement.style.setProperty('background','transparent','important');"
        "document.body.style.setProperty('background','transparent','important');"
        "for(const node of document.body.querySelectorAll('*')){"
        "node.style.setProperty('visibility','hidden','important');"
        "node.style.setProperty('animation','none','important');"
        "node.style.setProperty('transition','none','important');}"
        "for(const root of nodes){"
        "root.style.setProperty('visibility','visible','important');"
        "for(const child of root.querySelectorAll('*')){"
        "child.style.setProperty('visibility','visible','important');}}"
        "document.documentElement.dataset.turingRenderMode='overlay';"
        "return nodes.length;"
        "})()"
    )


def seek_animations_script(milliseconds: float) -> str:
    value = float(milliseconds)
    if not math.isfinite(value) or value < 0:
        raise ValueError("animation time must be finite and non-negative")
    return (
        "(() => {"
        f"const time={value:.6f};"
        "for(const animation of document.getAnimations()){"
        "animation.pause();animation.currentTime=time;}"
        "if(window.TuringTheme&&typeof window.TuringTheme.seekAnimation==='function'){"
        "window.TuringTheme.seekAnimation(time/1000);};"
        "return time;"
        "})()"
    )


def _probe_issues(
    spec: NativeVideoOverlay,
    result: VideoProbe,
) -> list[str]:
    issues = list(result.issues)
    if result.has_audio:
        issues.append("audio stream is not allowed")
    if (
        result.fps is None
        or not math.isfinite(result.fps)
        or abs(result.fps - spec.fps) > 0.2
    ):
        issues.append(f"frame rate must be {spec.fps} fps")
    if (
        result.duration is None
        or not math.isfinite(result.duration)
        or abs(result.duration - spec.duration) > (1.0 / spec.fps + 0.05)
    ):
        issues.append(f"duration must be approximately {spec.duration:g} seconds")
    containers = {
        item.strip().lower()
        for item in str(result.container or "").split(",")
        if item.strip()
    }
    if "mp4" not in containers:
        issues.append("container must be MP4")
    if result.profile not in {"Baseline", "Constrained Baseline"}:
        issues.append("H.264 profile must be Baseline")
    if result.level != 31:
        issues.append("H.264 level must be 3.1")
    if result.has_b_frames != 0:
        issues.append("B-frames are not supported by the native HTML profile")
    return issues


def _allows_original_encoding(manifest: ThemeManifest) -> bool:
    """Read the explicit per-theme opt-out for source videos kept byte-for-byte."""
    try:
        payload = json.loads((manifest.root / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    video = payload.get("nativeVideoOverlay")
    return isinstance(video, dict) and video.get("allowOriginalEncoding") is True


def validate_native_video_file(
    manifest: ThemeManifest,
    path: Path,
    *,
    probe: Callable[[Path], VideoProbe] = probe_video,
) -> VideoProbe:
    spec = manifest.native_video_overlay
    if spec is None:
        raise ThemeValidationError("HTML theme does not enable nativeVideoOverlay")
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise ThemeValidationError(f"native video file was not found: {path}")
    result = probe(path)
    issues = _probe_issues(spec, result)
    if _allows_original_encoding(manifest):
        tolerated = {
            "H.264 profile must be Baseline",
            "B-frames are not supported by the native HTML profile",
        }
        issues = [issue for issue in issues if issue not in tolerated]
    if issues:
        raise ThemeValidationError("invalid native HTML video: " + "; ".join(issues))
    return result


def validate_native_video(
    manifest: ThemeManifest,
    *,
    probe: Callable[[Path], VideoProbe] = probe_video,
) -> VideoProbe:
    spec = manifest.native_video_overlay
    if spec is None:
        raise ThemeValidationError("HTML theme does not enable nativeVideoOverlay")
    path = spec.local_file(manifest.root)
    if not path.is_file():
        raise ThemeValidationError(
            f"native video has not been built: {path.name}; run html-theme-build-video.py"
        )
    return validate_native_video_file(manifest, path, probe=probe)


def image_pipe_ffmpeg_command(
    destination: Path,
    *,
    fps: int,
    ffmpeg: str | None = None,
) -> list[str]:
    executable = ffmpeg or shutil.which("ffmpeg")
    if not executable:
        raise FileNotFoundError("ffmpeg is required to build the native HTML video")
    return [
        executable,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "image2pipe",
        "-framerate",
        str(int(fps)),
        "-vcodec",
        "png",
        "-i",
        "pipe:0",
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
