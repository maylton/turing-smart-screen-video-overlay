# SPDX-License-Identifier: GPL-3.0-or-later
"""Theme-engine contracts shared by legacy YAML and experimental HTML themes."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple

from library.sensor_snapshot import SensorSnapshot


SUPPORTED_ENGINES = ("yaml", "html")


class ThemeEngineError(RuntimeError):
    """Base error for engine discovery and lifecycle failures."""


class ThemeValidationError(ThemeEngineError):
    """Raised when a theme package is malformed or unsafe."""


def _positive_int(value: Any, field: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ThemeValidationError(f"{field} must be an integer") from exc
    if number <= 0:
        raise ThemeValidationError(f"{field} must be greater than zero")
    return number


def _positive_float(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ThemeValidationError(f"{field} must be a number") from exc
    if number <= 0:
        raise ThemeValidationError(f"{field} must be greater than zero")
    return number


def _safe_relative_path(root: Path, raw_path: Any, field: str) -> Path:
    text = str(raw_path or "").strip()
    if not text:
        raise ThemeValidationError(f"{field} cannot be empty")
    candidate = Path(text)
    if candidate.is_absolute():
        raise ThemeValidationError(f"{field} must be relative to the theme")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ThemeValidationError(f"{field} escapes the theme directory") from exc
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

        return cls(
            engine=engine,
            name=str(payload.get("name", root.name)).strip() or root.name,
            version=_positive_int(payload.get("version", 1), "version"),
            width=_positive_int(display.get("width", 480), "display.width"),
            height=_positive_int(display.get("height", 480), "display.height"),
            refresh_rate=_positive_float(
                payload.get("refreshRate", 1.0),
                "refreshRate",
            ),
            entrypoint=entrypoint,
            permissions=permissions,
            network=network,
            root=root,
        )


class ThemeEngine(ABC):
    """Minimal lifecycle contract for all renderers."""

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
    """Callback adapter that lets the current YAML runtime remain unchanged."""

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
