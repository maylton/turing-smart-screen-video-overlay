# SPDX-License-Identifier: GPL-3.0-or-later
"""Renderer selection and exclusive lifecycle for the monitor process.

The legacy YAML renderer remains the implicit default.  HTML is deliberately
opt-in and is validated before a runner (and therefore a serial transport) is
created.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional, Protocol

from library.theme_engine import ThemeManifest, ThemeValidationError


class RendererConfigurationError(ValueError):
    pass


class RendererRunner(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def wait(self) -> int: ...


@dataclass(frozen=True)
class RendererSelection:
    engine: str
    theme: str
    manifest: Optional[ThemeManifest] = None


@dataclass(frozen=True)
class RendererState:
    engine: str = "stopped"
    theme: str = ""
    running: bool = False
    error: str = ""


def select_renderer(
    config: Mapping[str, object],
    themes_directory: Path,
) -> RendererSelection:
    legacy = config.get("config", {})
    legacy = legacy if isinstance(legacy, Mapping) else {}
    renderer = config.get("renderer")
    if renderer is None:
        return RendererSelection("yaml", str(legacy.get("THEME") or ""))
    if not isinstance(renderer, Mapping):
        raise RendererConfigurationError("renderer must be a mapping")

    engine = str(renderer.get("engine", "yaml") or "yaml").strip().lower()
    if engine not in {"yaml", "html"}:
        raise RendererConfigurationError(
            f"renderer.engine must be 'yaml' or 'html', received {engine!r}"
        )
    if engine == "yaml":
        return RendererSelection("yaml", str(legacy.get("THEME") or ""))

    theme = str(renderer.get("theme") or "").strip()
    if not theme:
        raise RendererConfigurationError(
            "renderer.theme is required when renderer.engine is html"
        )
    root = Path(themes_directory).resolve()
    directory = (root / theme).resolve()
    try:
        directory.relative_to(root)
    except ValueError as exc:
        raise RendererConfigurationError(
            "renderer.theme must name a theme inside res/themes"
        ) from exc
    try:
        manifest = ThemeManifest.load(directory)
    except ThemeValidationError as exc:
        raise RendererConfigurationError(f"invalid HTML theme {theme!r}: {exc}") from exc
    if manifest.engine != "html":
        raise RendererConfigurationError(f"theme {theme!r} is not an HTML theme")
    if manifest.network:
        raise RendererConfigurationError("network-enabled HTML themes are not supported")
    if "sensors" not in manifest.permissions:
        raise RendererConfigurationError("HTML themes must request the sensors permission")
    return RendererSelection("html", theme, manifest)


RunnerFactory = Callable[[RendererSelection], RendererRunner]


class RendererController:
    """Own exactly one renderer and stop it before every replacement."""

    def __init__(self, factories: Mapping[str, RunnerFactory]) -> None:
        self._factories = dict(factories)
        self._runner: Optional[RendererRunner] = None
        self._condition = threading.Condition()
        self._generation = 0
        self._replacement_in_progress = False
        self.state = RendererState()

    def start(self, selection: RendererSelection) -> RendererState:
        with self._condition:
            if self._runner is not None:
                raise RuntimeError("a renderer is already active")
        factory = self._factories.get(selection.engine)
        if factory is None:
            raise RuntimeError(f"no runner is registered for {selection.engine}")
        runner = factory(selection)
        try:
            runner.start()
        except Exception as exc:
            try:
                runner.stop()
            finally:
                with self._condition:
                    self.state = RendererState(
                        engine=selection.engine,
                        theme=selection.theme,
                        error=str(exc),
                    )
                    self._condition.notify_all()
            raise
        with self._condition:
            self._runner = runner
            self._generation += 1
            self.state = RendererState(selection.engine, selection.theme, True, "")
            self._condition.notify_all()
            return self.state

    def stop(self) -> RendererState:
        with self._condition:
            runner, self._runner = self._runner, None
            self._generation += 1
            self.state = RendererState()
            self._condition.notify_all()
        if runner is not None:
            runner.stop()
        return self.state

    def reload(self, selection: RendererSelection) -> RendererState:
        with self._condition:
            self._replacement_in_progress = True
            self._condition.notify_all()
        try:
            self.stop()
            return self.start(selection)
        finally:
            with self._condition:
                self._replacement_in_progress = False
                self._condition.notify_all()

    def wait(self) -> int:
        while True:
            with self._condition:
                while self._runner is None and self._replacement_in_progress:
                    self._condition.wait()
                runner = self._runner
                generation = self._generation
                if runner is None:
                    return 0
            result = int(runner.wait())
            with self._condition:
                if self._runner is runner and self._generation == generation:
                    return result
