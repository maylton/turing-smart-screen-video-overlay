# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure HTML-theme authoring, fingerprint, and native-video state helpers."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

from library.theme_engine import ThemeManifest, ThemeValidationError
from library.video_media import RemotePathError, normalize_remote_path


BUILD_STATE_FILENAME = ".native-video-build.json"
BUILD_STATE_SCHEMA = 1


@dataclass(frozen=True)
class NativeVideoArtifactState:
    status: str
    message: str
    video_path: Path | None = None
    source_digest: str = ""

    @property
    def ready(self) -> bool:
        return self.status == "ready"

    @property
    def needs_build(self) -> bool:
        return self.status in {"missing", "stale", "error"}


@dataclass(frozen=True)
class OverlayCandidate:
    element_id: str
    tag: str
    marked: bool


def build_state_path(manifest: ThemeManifest) -> Path:
    return manifest.root / BUILD_STATE_FILENAME


def _generated_paths(manifest: ThemeManifest) -> set[Path]:
    spec = manifest.native_video_overlay
    if spec is None:
        return {build_state_path(manifest).resolve()}
    video = spec.local_file(manifest.root).resolve()
    return {
        video,
        video.with_name(f"{video.stem}-background.png"),
        build_state_path(manifest).resolve(),
    }


def html_theme_source_digest(manifest: ThemeManifest) -> str:
    """Hash every theme source/asset while excluding generated build outputs."""
    excluded = _generated_paths(manifest)
    digest = hashlib.sha256()
    for path in sorted(manifest.root.rglob("*")):
        if not path.is_file() or path.resolve() in excluded:
            continue
        relative = path.relative_to(manifest.root)
        if "__pycache__" in relative.parts or path.name.endswith(
            (".tmp", ".editor-backup")
        ):
            continue
        encoded = relative.as_posix().encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_native_video_build_state(
    manifest: ThemeManifest,
    video_path: Path,
) -> Path | None:
    spec = manifest.native_video_overlay
    if spec is None:
        return None
    video_path = Path(video_path).expanduser().resolve()
    if video_path != spec.local_file(manifest.root).resolve():
        return None
    payload = {
        "schemaVersion": BUILD_STATE_SCHEMA,
        "sourceDigest": html_theme_source_digest(manifest),
        "videoSha256": file_sha256(video_path),
        "fps": spec.fps,
        "duration": spec.duration,
        "builtAt": datetime.now(timezone.utc).isoformat(),
    }
    destination = build_state_path(manifest)
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, destination)
    return destination


def inspect_native_video_artifact(
    manifest: ThemeManifest,
) -> NativeVideoArtifactState:
    spec = manifest.native_video_overlay
    if spec is None:
        return NativeVideoArtifactState("none", "Native video is not enabled")
    video = spec.local_file(manifest.root)
    source_digest = html_theme_source_digest(manifest)
    if not video.is_file():
        return NativeVideoArtifactState(
            "missing",
            "Native video has not been built",
            video,
            source_digest,
        )
    state_file = build_state_path(manifest)
    try:
        payload = json.loads(state_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return NativeVideoArtifactState(
            "stale",
            "Video exists but has no source fingerprint; rebuild it",
            video,
            source_digest,
        )
    except (OSError, json.JSONDecodeError) as exc:
        return NativeVideoArtifactState(
            "error",
            f"Could not read video build state: {exc}",
            video,
            source_digest,
        )
    if not isinstance(payload, dict) or payload.get("schemaVersion") != BUILD_STATE_SCHEMA:
        return NativeVideoArtifactState(
            "stale",
            "Video build metadata uses an unsupported schema",
            video,
            source_digest,
        )
    if payload.get("sourceDigest") != source_digest:
        return NativeVideoArtifactState(
            "stale",
            "HTML/CSS/JS or theme assets changed; rebuild the video",
            video,
            source_digest,
        )
    if payload.get("fps") != spec.fps or payload.get("duration") != spec.duration:
        return NativeVideoArtifactState(
            "stale",
            "Native-video settings changed; rebuild the video",
            video,
            source_digest,
        )
    try:
        video_digest = file_sha256(video)
    except OSError as exc:
        return NativeVideoArtifactState(
            "error",
            f"Could not hash native video: {exc}",
            video,
            source_digest,
        )
    if payload.get("videoSha256") != video_digest:
        return NativeVideoArtifactState(
            "stale",
            "Native video changed after it was built",
            video,
            source_digest,
        )
    return NativeVideoArtifactState(
        "ready",
        "Native video matches the current HTML sources",
        video,
        source_digest,
    )


class _OverlayParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.candidates: list[OverlayCandidate] = []
        self._seen: set[str] = set()

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = {str(name).lower(): value for name, value in attrs}
        element_id = str(attributes.get("id") or "").strip()
        if not element_id or element_id in self._seen:
            return
        self._seen.add(element_id)
        self.candidates.append(
            OverlayCandidate(
                element_id,
                tag,
                "data-turing-overlay" in attributes,
            )
        )


def discover_overlay_candidates(manifest: ThemeManifest) -> tuple[OverlayCandidate, ...]:
    if manifest.engine != "html":
        raise ThemeValidationError("overlay markers are supported only by HTML themes")
    parser = _OverlayParser()
    parser.feed(manifest.entrypoint_path.read_text(encoding="utf-8"))
    return tuple(parser.candidates)


_START_TAG = re.compile(
    r"<(?P<tag>[A-Za-z][A-Za-z0-9:_-]*)(?P<attrs>[^<>]*?)(?P<closing>\s*/?)>",
    re.DOTALL,
)
_ID_ATTRIBUTE = re.compile(
    r"\bid\s*=\s*(?P<quote>['\"])(?P<id>[^'\"]+)(?P=quote)",
    re.IGNORECASE,
)
_OVERLAY_ATTRIBUTE = re.compile(
    r"\s+data-turing-overlay(?:\s*=\s*(?:['\"][^'\"]*['\"]|[^\s>]+))?",
    re.IGNORECASE,
)


def update_overlay_markers_text(html: str, selected_ids: Iterable[str]) -> str:
    selected = {str(item).strip() for item in selected_ids if str(item).strip()}

    def replace(match: re.Match[str]) -> str:
        attrs = match.group("attrs")
        id_match = _ID_ATTRIBUTE.search(attrs)
        if id_match is None:
            return match.group(0)
        element_id = id_match.group("id")
        attrs = _OVERLAY_ATTRIBUTE.sub("", attrs)
        if element_id in selected:
            attrs = attrs.rstrip() + " data-turing-overlay"
        return f'<{match.group("tag")}{attrs}{match.group("closing")}>'

    return _START_TAG.sub(replace, html)


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def save_html_theme_authoring(
    manifest: ThemeManifest,
    *,
    fps: int,
    duration: float,
    background_frame: float,
    device_directory: str,
    filename: str,
    overlay_ids: Iterable[str],
) -> ThemeManifest:
    """Atomically update native-video settings and explicit live markers."""
    if manifest.engine != "html":
        raise ThemeValidationError("HTML theme authoring requires an HTML theme")
    if fps not in {24, 30}:
        raise ThemeValidationError("FPS must be 24 or 30")
    duration = float(duration)
    background_frame = float(background_frame)
    if not math.isfinite(duration) or duration <= 0 or duration > 60:
        raise ThemeValidationError("duration must be between 0 and 60 seconds")
    if not math.isclose(duration * fps, round(duration * fps), abs_tol=1e-9):
        raise ThemeValidationError("duration must contain a whole number of frames")
    if not math.isfinite(background_frame) or background_frame < 0:
        raise ThemeValidationError("background frame must be non-negative")
    if not math.isclose(
        background_frame * fps,
        round(background_frame * fps),
        abs_tol=1e-9,
    ):
        raise ThemeValidationError("background frame must align to the frame rate")
    if background_frame > duration - (1.0 / fps) + 1e-9:
        raise ThemeValidationError("background frame must select a rendered frame")

    requested_filename = str(filename).strip()
    filename = Path(requested_filename).name
    if filename != requested_filename:
        raise ThemeValidationError("video filename must not contain a directory")
    if not filename or Path(filename).suffix.lower() != ".mp4":
        raise ThemeValidationError("video filename must end in .mp4")
    directory = str(device_directory).rstrip("/")
    try:
        device_path = normalize_remote_path(f"{directory}/{filename}")
    except RemotePathError as exc:
        raise ThemeValidationError(str(exc)) from exc

    candidates = discover_overlay_candidates(manifest)
    known_ids = {candidate.element_id for candidate in candidates}
    selected = {str(item).strip() for item in overlay_ids if str(item).strip()}
    unknown = sorted(selected - known_ids)
    if unknown:
        raise ThemeValidationError(
            "unknown overlay element ids: " + ", ".join(unknown)
        )
    if not selected:
        raise ThemeValidationError("select at least one live overlay element")

    manifest_path = manifest.root / "manifest.json"
    entrypoint = manifest.entrypoint_path
    manifest_original = manifest_path.read_text(encoding="utf-8")
    html_original = entrypoint.read_text(encoding="utf-8")
    payload = json.loads(manifest_original)
    payload["nativeVideoOverlay"] = {
        "enabled": True,
        "localPath": filename,
        "devicePath": device_path,
        "fps": fps,
        "duration": duration,
        "backgroundFrame": background_frame,
    }
    manifest_updated = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    html_updated = update_overlay_markers_text(html_original, selected)

    for path, original in (
        (manifest_path, manifest_original),
        (entrypoint, html_original),
    ):
        backup = path.with_name(f"{path.name}.editor-backup")
        if not backup.exists():
            backup.write_text(original, encoding="utf-8")

    try:
        _atomic_write(manifest_path, manifest_updated)
        _atomic_write(entrypoint, html_updated)
        return ThemeManifest.load(manifest.root)
    except Exception:
        _atomic_write(manifest_path, manifest_original)
        _atomic_write(entrypoint, html_original)
        raise
