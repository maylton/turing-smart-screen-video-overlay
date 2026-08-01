# SPDX-License-Identifier: GPL-3.0-or-later
"""Sandboxed HTML theme engine used by the developer simulator.

The first milestone intentionally renders only inside WebKitGTK. It never imports
or calls display transports. Hardware frame capture and upload belong to a later,
separately reviewed stage.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import unquote, urlparse

from library.sensor_snapshot import SensorSnapshot
from library.theme_engine import (
    ThemeEngine,
    ThemeEngineError,
    ThemeManifest,
    ThemeValidationError,
)


class WebKitUnavailableError(ThemeEngineError):
    """Raised when the WebKitGTK GI namespace cannot be loaded."""


def is_allowed_theme_uri(uri: str, theme_root: Path) -> bool:
    """Allow only local theme assets and inert in-document URI schemes."""
    parsed = urlparse(str(uri or ""))
    scheme = parsed.scheme.lower()
    if scheme in {"about", "data", "blob"}:
        return True
    if scheme != "file":
        return False

    candidate = Path(unquote(parsed.path)).resolve()
    root = Path(theme_root).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def build_snapshot_script(snapshot: SensorSnapshot) -> str:
    """Build one self-contained update call without exposing Python objects."""
    payload = json.dumps(
        snapshot.as_dict(),
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return (
        "(() => {"
        f"const snapshot={payload};"
        "if(window.TuringTheme&&typeof window.TuringTheme.update==='function'){"
        "window.TuringTheme.update(snapshot);"
        "}"
        "window.dispatchEvent(new CustomEvent('turing-snapshot',{detail:snapshot}));"
        "})();"
    )


class WebKitGtkBackend:
    """Thin lazy WebKitGTK adapter; importing this module does not require GI."""

    def __init__(self, manifest: ThemeManifest) -> None:
        self.manifest = manifest
        self._loaded = False
        self._pending_script: Optional[str] = None
        self._load_gi()
        self.view = self.WebKit.WebView()
        settings = self.view.get_settings()
        if settings is not None:
            setter = getattr(settings, "set_enable_developer_extras", None)
            if callable(setter):
                setter(False)
            setter = getattr(settings, "set_enable_javascript", None)
            if callable(setter):
                setter(True)
            setter = getattr(settings, "set_allow_file_access_from_file_urls", None)
            if callable(setter):
                setter(True)
            setter = getattr(
                settings,
                "set_allow_universal_access_from_file_urls",
                None,
            )
            if callable(setter):
                setter(False)

        self.view.connect("decide-policy", self._on_decide_policy)
        self.view.connect("load-changed", self._on_load_changed)

    def _load_gi(self) -> None:
        try:
            import gi

            gi.require_version("Gtk", "4.0")
            gi.require_version("WebKit", "6.0")
            from gi.repository import GLib, Gtk, WebKit
        except Exception as exc:
            raise WebKitUnavailableError(
                "WebKitGTK 6.0 GI bindings are required for HTML theme preview"
            ) from exc
        self.GLib = GLib
        self.Gtk = Gtk
        self.WebKit = WebKit

    def _decision_uri(self, decision: Any) -> str:
        request = None
        getter = getattr(decision, "get_request", None)
        if callable(getter):
            request = getter()
        if request is None:
            action_getter = getattr(decision, "get_navigation_action", None)
            if callable(action_getter):
                action = action_getter()
                request_getter = getattr(action, "get_request", None)
                if callable(request_getter):
                    request = request_getter()
        if request is None:
            return ""
        uri_getter = getattr(request, "get_uri", None)
        return str(uri_getter() if callable(uri_getter) else "")

    def _on_decide_policy(self, _view: Any, decision: Any, _kind: Any) -> bool:
        uri = self._decision_uri(decision)
        if not uri or is_allowed_theme_uri(uri, self.manifest.root):
            use = getattr(decision, "use", None)
            if callable(use):
                use()
            return True
        ignore = getattr(decision, "ignore", None)
        if callable(ignore):
            ignore()
        return True

    def _on_load_changed(self, _view: Any, event: Any) -> None:
        finished = getattr(self.WebKit.LoadEvent, "FINISHED", None)
        if finished is not None and event != finished:
            return
        self._loaded = True
        if self._pending_script:
            script = self._pending_script
            self._pending_script = None
            self.evaluate(script)

    def load(self) -> None:
        self.view.load_uri(self.manifest.entrypoint_path.as_uri())

    def evaluate(self, script: str) -> None:
        if not self._loaded:
            self._pending_script = script
            return

        evaluator = getattr(self.view, "evaluate_javascript", None)
        if callable(evaluator):
            try:
                evaluator(script, -1, None, None, None, None, None)
            except TypeError:
                evaluator(script, -1, None, None, None, None)
            return

        runner = getattr(self.view, "run_javascript", None)
        if callable(runner):
            runner(script, None, None, None)
            return
        raise ThemeEngineError("WebKit view has no JavaScript evaluation API")

    @staticmethod
    def _save_snapshot_texture(texture: Any, destination: Path) -> None:
        """Persist GTK4 textures, with a legacy Cairo fallback."""
        destination = Path(destination)

        saver = getattr(texture, "save_to_png", None)
        if callable(saver):
            saved = saver(str(destination))
            if saved is False:
                raise ThemeEngineError(
                    f"GTK could not save the snapshot to {destination}"
                )
            return

        legacy_saver = getattr(texture, "write_to_png", None)
        if callable(legacy_saver):
            legacy_saver(str(destination))
            return

        raise ThemeEngineError(
            "The snapshot result exposes neither Gdk.Texture.save_to_png() "
            "nor the legacy Cairo write_to_png() API"
        )

    def snapshot_png(
        self,
        destination: Path,
        callback: Optional[Callable[[Optional[Exception]], None]] = None,
    ) -> None:
        getter = getattr(self.view, "get_snapshot", None)
        finisher = getattr(self.view, "get_snapshot_finish", None)
        if not callable(getter) or not callable(finisher):
            error = ThemeEngineError("This WebKitGTK build has no snapshot API")
            if callback:
                callback(error)
                return
            raise error

        destination = Path(destination).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)

        def done(view: Any, result: Any, _user_data: Any = None) -> None:
            error: Optional[Exception] = None
            try:
                texture = view.get_snapshot_finish(result)
                self._save_snapshot_texture(texture, destination)
            except Exception as exc:
                error = exc
            if callback:
                callback(error)

        region = getattr(self.WebKit.SnapshotRegion, "VISIBLE", None)
        if region is None:
            region = getattr(self.WebKit.SnapshotRegion, "FULL_DOCUMENT")
        options = getattr(
            self.WebKit.SnapshotOptions,
            "TRANSPARENT_BACKGROUND",
            0,
        )
        getter(region, options, None, done, None)

    def close(self) -> None:
        stop = getattr(self.view, "stop_loading", None)
        if callable(stop):
            stop()


BackendFactory = Callable[[ThemeManifest], Any]


class HtmlThemeEngine(ThemeEngine):
    """Experimental HTML engine restricted to the simulator in this milestone."""

    def __init__(self, backend_factory: BackendFactory = WebKitGtkBackend) -> None:
        self._backend_factory = backend_factory
        self._backend: Optional[Any] = None
        self._manifest: Optional[ThemeManifest] = None
        self._last_snapshot: Optional[SensorSnapshot] = None

    @property
    def manifest(self) -> ThemeManifest:
        if self._manifest is None:
            raise ThemeEngineError("HTML theme has not been loaded")
        return self._manifest

    def load(self, manifest: ThemeManifest) -> None:
        if manifest.engine != "html":
            raise ThemeEngineError("HtmlThemeEngine only accepts HTML themes")
        if manifest.network:
            raise ThemeValidationError(
                "Network-enabled themes are not supported by the safe prototype"
            )
        if "sensors" not in manifest.permissions:
            raise ThemeValidationError(
                "HTML themes must request the 'sensors' permission"
            )
        self.close()
        self._manifest = manifest
        self._backend = self._backend_factory(manifest)
        self._backend.load()

    def update(self, snapshot: SensorSnapshot) -> None:
        if self._backend is None:
            raise ThemeEngineError("HTML theme has not been loaded")
        self._last_snapshot = snapshot
        self._backend.evaluate(build_snapshot_script(snapshot))

    def render(self) -> Any:
        if self._backend is None:
            raise ThemeEngineError("HTML theme has not been loaded")
        return self._backend.view

    def snapshot_png(
        self,
        destination: Path,
        callback: Optional[Callable[[Optional[Exception]], None]] = None,
    ) -> None:
        if self._backend is None:
            raise ThemeEngineError("HTML theme has not been loaded")
        self._backend.snapshot_png(destination, callback)

    def close(self) -> None:
        if self._backend is not None:
            self._backend.close()
        self._backend = None
        self._last_snapshot = None
