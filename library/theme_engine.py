# SPDX-License-Identifier: GPL-3.0-or-later
"""Theme-engine contracts shared by legacy YAML and experimental HTML themes."""

from __future__ import annotations

import json
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple

from library.atomic_regions import AtomicRegion, parse_atomic_regions
from library.sensor_snapshot import SensorSnapshot
from library.sensor_update_scheduler import (
    SensorUpdatePolicy,
    parse_sensor_update_policy,
)
from library.video_media import RemotePathError, normalize_remote_path


SUPPORTED_ENGINES = ("yaml", "html")


class ThemeEngineError(RuntimeError):
    """Base error for engine discovery and lifecycle failures."""


class ThemeValidationError(ThemeEngineError):
    """Raised when a theme package is malformed or unsafe."""


@dataclass(frozen=True)
class NativeVideoOverlay:
    """Opt-in native-video build/runtime contract for an HTML theme."""

    local_path: str
    device_path: str
    fps: int
    duration: float
    background_frame: float = 0.0

    def local_file(self, root: Path) -> Path:
        return _safe_relative_path(root, self.local_path, "nativeVideoOverlay.localPath")


def _parse_native_video_overlay(
    value: Any,
    *,
    root: Path,
    engine: str,
    width: int,
    height: int,
    permissions: Tuple[str, ...],
    network: bool,
) -> Optional[NativeVideoOverlay]:
    if value is None:
        return None
    if engine != "html":
        raise ThemeValidationError("nativeVideoOverlay is supported only by HTML themes")
    if not isinstance(value, Mapping):
        raise ThemeValidationError("nativeVideoOverlay must be an object")
    enabled = value.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ThemeValidationError("nativeVideoOverlay.enabled must be a boolean")
    if not enabled:
        return None
    if (width, height) != (480, 480):
        raise ThemeValidationError("nativeVideoOverlay currently requires a 480x480 theme")
    if network:
        raise ThemeValidationError("nativeVideoOverlay requires network=false")
    if "sensors" not in permissions:
        raise ThemeValidationError("nativeVideoOverlay requires the sensors permission")
    if "overlaySelector" in value:
        raise ThemeValidationError(
            "nativeVideoOverlay uses the fixed [data-turing-overlay] marker"
        )

    if not isinstance(value.get("localPath"), str):
        raise ThemeValidationError("nativeVideoOverlay.localPath must be a string")
    local_path = value["localPath"].strip()
    local_file = _safe_relative_path(root, local_path, "nativeVideoOverlay.localPath")
    if local_file.suffix.lower() != ".mp4":
        raise ThemeValidationError("nativeVideoOverlay.localPath must use .mp4")

    if not isinstance(value.get("devicePath"), str):
        raise ThemeValidationError("nativeVideoOverlay.devicePath must be a string")
    try:
        device_path = normalize_remote_path(value["devicePath"])
    except RemotePathError as exc:
        raise ThemeValidationError(
            f"invalid nativeVideoOverlay.devicePath: {exc}"
        ) from exc
    remote_name = Path(device_path).name
    if Path(remote_name).suffix.lower() != ".mp4":
        raise ThemeValidationError("nativeVideoOverlay.devicePath must use .mp4")
    if remote_name != local_file.name:
        raise ThemeValidationError(
            "nativeVideoOverlay localPath and devicePath must use the same filename"
        )

    fps_value = value.get("fps", 24)
    if isinstance(fps_value, bool) or not isinstance(fps_value, int):
        raise ThemeValidationError("nativeVideoOverlay.fps must be an integer")
    fps = _positive_int(fps_value, "nativeVideoOverlay.fps")
    if fps not in {24, 30}:
        raise ThemeValidationError("nativeVideoOverlay.fps must be 24 or 30")
    duration_value = value.get("duration")
    if isinstance(duration_value, bool) or not isinstance(
        duration_value, (int, float)
    ):
        raise ThemeValidationError("nativeVideoOverlay.duration must be a number")
    duration = _positive_float(
        duration_value,
        "nativeVideoOverlay.duration",
    )
    if not math.isfinite(duration) or duration > 60:
        raise ThemeValidationError(
            "nativeVideoOverlay.duration must be finite and at most 60 seconds"
        )
    if not math.isclose(duration * fps, round(duration * fps), abs_tol=1e-9):
        raise ThemeValidationError(
            "nativeVideoOverlay.duration must contain a whole number of frames"
        )
    background_value = value.get("backgroundFrame", 0.0)
    if isinstance(background_value, bool) or not isinstance(
        background_value, (int, float)
    ):
        raise ThemeValidationError(
            "nativeVideoOverlay.backgroundFrame must be a number"
        )
    background_frame = float(background_value)
    last_frame_time = duration - (1.0 / fps)
    if (
        not math.isfinite(background_frame)
        or background_frame < 0
        or background_frame > last_frame_time + 1e-9
    ):
        raise ThemeValidationError(
            "nativeVideoOverlay.backgroundFrame must select a rendered video frame"
        )
    if not math.isclose(
        background_frame * fps,
        round(background_frame * fps),
        abs_tol=1e-9,
    ):
        raise ThemeValidationError(
            "nativeVideoOverlay.backgroundFrame must align to the video frame rate"
        )
    return NativeVideoOverlay(
        local_path=local_path,
        device_path=device_path,
        fps=fps,
        duration=duration,
        background_frame=background_frame,
    )


def _positive_int(value: Any, field_name: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ThemeValidationError(f"{field_name} must be an integer") from exc
    if number <= 0:
        raise ThemeValidationError(f"{field_name} must be greater than zero")
    return number


def _positive_float(value: Any, field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ThemeValidationError(f"{field_name} must be a number") from exc
    if number <= 0:
        raise ThemeValidationError(f"{field_name} must be greater than zero")
    return number


def _safe_relative_path(root: Path, raw_path: Any, field_name: str) -> Path:
    text = str(raw_path or "").strip()
    if not text:
        raise ThemeValidationError(f"{field_name} cannot be empty")
    candidate = Path(text)
    if candidate.is_absolute():
        raise ThemeValidationError(f"{field_name} must be relative to the theme")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ThemeValidationError(f"{field_name} escapes the theme directory") from exc
    return resolved


@dataclass(frozen=True)
class ThemeManifest:
    engine: str
    name: str
    version: int
    width: int
    height: int
    refresh_rate: float
    entrypoint: str
    permissions: Tuple[str, ...]
    network: bool
    root: Path
    atomic_regions: Tuple[AtomicRegion, ...] = ()
    native_video_overlay: Optional[NativeVideoOverlay] = None
    data_update_policy: SensorUpdatePolicy = field(
        default_factory=lambda: SensorUpdatePolicy(default_interval=1.0)
    )

    @property
    def entrypoint_path(self) -> Path:
        return _safe_relative_path(self.root, self.entrypoint, "entrypoint")

    @classmethod
    def load(cls, theme_directory: Path) -> "ThemeManifest":
        root = Path(theme_directory).expanduser().resolve()
        if not root.is_dir():
            raise ThemeValidationError(f"Theme directory does not exist: {root}")

        manifest_path = root / "manifest.json"
        if not manifest_path.is_file():
            legacy_yaml = root / "theme.yaml"
            if legacy_yaml.is_file():
                return cls(
                    engine="yaml",
                    name=root.name,
                    version=1,
                    width=1,
                    height=1,
                    refresh_rate=1.0,
                    entrypoint="theme.yaml",
                    permissions=(),
                    network=False,
                    atomic_regions=(),
                    data_update_policy=SensorUpdatePolicy(default_interval=1.0),
                    root=root,
                )
            raise ThemeValidationError(
                "Theme must contain manifest.json or legacy theme.yaml"
            )

        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ThemeValidationError(f"Invalid manifest.json: {exc}") from exc
        if not isinstance(payload, Mapping):
            raise ThemeValidationError("manifest.json must contain an object")

        engine = str(payload.get("engine", "")).strip().lower()
        if engine not in SUPPORTED_ENGINES:
            raise ThemeValidationError(
                f"Unsupported theme engine {engine!r}; expected one of {SUPPORTED_ENGINES}"
            )

        display = payload.get("display", {})
        if not isinstance(display, Mapping):
            raise ThemeValidationError("display must be an object")
        width = _positive_int(display.get("width", 480), "display.width")
        height = _positive_int(display.get("height", 480), "display.height")

        default_entrypoint = "index.html" if engine == "html" else "theme.yaml"
        entrypoint = str(payload.get("entrypoint", default_entrypoint)).strip()
        entrypoint_path = _safe_relative_path(root, entrypoint, "entrypoint")
        if not entrypoint_path.is_file():
            raise ThemeValidationError(f"Theme entrypoint is missing: {entrypoint}")

        permissions_raw = payload.get("permissions", [])
        if not isinstance(permissions_raw, Sequence) or isinstance(
            permissions_raw, (str, bytes)
        ):
            raise ThemeValidationError("permissions must be an array")
        permissions = tuple(
            sorted(
                {
                    str(item).strip()
                    for item in permissions_raw
                    if str(item).strip()
                }
            )
        )

        network = bool(payload.get("network", False))
        if network and "network" not in permissions:
            raise ThemeValidationError(
                "network=true requires the explicit 'network' permission"
            )

        try:
            atomic_regions = parse_atomic_regions(
                payload.get("atomicRegions", []),
                display_width=width,
                display_height=height,
            )
        except ValueError as exc:
            raise ThemeValidationError(str(exc)) from exc

        refresh_rate = _positive_float(
            payload.get("refreshRate", 1.0),
            "refreshRate",
        )
        try:
            data_update_policy = parse_sensor_update_policy(
                payload.get("dataUpdateIntervals"),
                fallback_interval=1.0 / refresh_rate,
            )
        except ValueError as exc:
            raise ThemeValidationError(str(exc)) from exc

        native_video_overlay = _parse_native_video_overlay(
            payload.get("nativeVideoOverlay"),
            root=root,
            engine=engine,
            width=width,
            height=height,
            permissions=permissions,
            network=network,
        )

        return cls(
            engine=engine,
            name=str(payload.get("name", root.name)).strip() or root.name,
            version=_positive_int(payload.get("version", 1), "version"),
            width=width,
            height=height,
            refresh_rate=refresh_rate,
            entrypoint=entrypoint,
            permissions=permissions,
            network=network,
            atomic_regions=atomic_regions,
            native_video_overlay=native_video_overlay,
            data_update_policy=data_update_policy,
            root=root,
        )


class ThemeEngine(ABC):
    @abstractmethod
    def load(self, manifest: ThemeManifest) -> None:
        raise NotImplementedError

    @abstractmethod
    def update(self, snapshot: SensorSnapshot) -> None:
        raise NotImplementedError

    @abstractmethod
    def render(self) -> Any:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError


class LegacyYamlThemeEngine(ThemeEngine):
    def __init__(
        self,
        *,
        load_callback: Callable[[ThemeManifest], None],
        update_callback: Callable[[SensorSnapshot], None],
        render_callback: Callable[[], Any],
        close_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        self._load_callback = load_callback
        self._update_callback = update_callback
        self._render_callback = render_callback
        self._close_callback = close_callback or (lambda: None)

    def load(self, manifest: ThemeManifest) -> None:
        if manifest.engine != "yaml":
            raise ThemeEngineError("LegacyYamlThemeEngine only accepts YAML themes")
        self._load_callback(manifest)

    def update(self, snapshot: SensorSnapshot) -> None:
        self._update_callback(snapshot)

    def render(self) -> Any:
        return self._render_callback()

    def close(self) -> None:
        self._close_callback()


EngineFactory = Callable[[], ThemeEngine]


class ThemeEngineRegistry:
    def __init__(self) -> None:
        self._factories: Dict[str, EngineFactory] = {}

    def register(self, engine: str, factory: EngineFactory) -> None:
        name = str(engine).strip().lower()
        if name not in SUPPORTED_ENGINES:
            raise ThemeEngineError(f"Unsupported engine registration: {name!r}")
        if not callable(factory):
            raise TypeError("Theme engine factory must be callable")
        self._factories[name] = factory

    def create(self, manifest: ThemeManifest) -> ThemeEngine:
        try:
            factory = self._factories[manifest.engine]
        except KeyError as exc:
            raise ThemeEngineError(
                f"No factory registered for {manifest.engine!r} themes"
            ) from exc
        engine = factory()
        engine.load(manifest)
        return engine
