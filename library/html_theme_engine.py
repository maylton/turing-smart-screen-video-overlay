# SPDX-License-Identifier: GPL-3.0-or-later
"""Sandboxed, transport-agnostic HTML engine for preview and worker runtimes.

This module renders only inside WebKitGTK and never imports a display transport.
The integrated worker owns the separately validated physical sink.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import unquote, urlparse

from library.sensor_snapshot import SensorSnapshot
from library.sensor_update_scheduler import SensorUpdateScheduler
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


def _gbytes_to_bytes(value: Any) -> bytes:
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)
    getter = getattr(value, "get_data", None)
    if not callable(getter):
        raise ThemeEngineError("GTK returned an unsupported byte container")
    data = getter()
    if isinstance(data, tuple):
        data = data[0]
    try:
        return bytes(data)
    except Exception as exc:
        raise ThemeEngineError("Could not read PNG bytes from GTK") from exc


def texture_png_bytes(texture: Any) -> bytes:
    """Serialize a GTK4 texture to PNG bytes without touching the filesystem."""
    saver = getattr(texture, "save_to_png_bytes", None)
    if callable(saver):
        return _gbytes_to_bytes(saver())

    filename_saver = getattr(texture, "save_to_png", None)
    if callable(filename_saver):
        import tempfile

        descriptor, filename = tempfile.mkstemp(suffix=".png")
        os.close(descriptor)
        path = Path(filename)
        try:
            saved = filename_saver(str(path))
            if saved is False:
                raise ThemeEngineError("GTK could not serialize the texture")
            return path.read_bytes()
        finally:
            try:
                path.unlink()
            except OSError:
                pass

    legacy_saver = getattr(texture, "write_to_png", None)
    if callable(legacy_saver):
        import tempfile

        descriptor, filename = tempfile.mkstemp(suffix=".png")
        os.close(descriptor)
        path = Path(filename)
        try:
            legacy_saver(str(path))
            return path.read_bytes()
        finally:
            try:
                path.unlink()
            except OSError:
                pass

    raise ThemeEngineError(
        "The snapshot texture exposes no supported PNG serialization API"
    )


class WebKitGtkBackend:
    """Thin lazy WebKitGTK adapter; importing this module does not require GI."""

    def __init__(self, manifest: ThemeManifest) -> None:
        self.manifest = manifest
        self._loaded = False
        self._pending_scripts: list[
            tuple[str, Optional[Callable[[Optional[Exception]], None]]]
        ] = []
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
            from gi.repository import Gdk, GLib, Gtk, WebKit
        except Exception as exc:
            raise WebKitUnavailableError(
                "WebKitGTK 6.0 GI bindings are required for HTML theme preview"
            ) from exc
        self.GLib = GLib
        self.Gdk = Gdk
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
        pending, self._pending_scripts = self._pending_scripts, []
        for script, callback in pending:
            self.evaluate(script, callback)

    def load(self) -> None:
        self.view.load_uri(self.manifest.entrypoint_path.as_uri())

    def evaluate(
        self,
        script: str,
        callback: Optional[Callable[[Optional[Exception]], None]] = None,
    ) -> None:
        if not self._loaded:
            self._pending_scripts.append((script, callback))
            return

        evaluator = getattr(self.view, "evaluate_javascript", None)
        if callable(evaluator):
            def evaluated(view: Any, result: Any, _user_data: Any = None) -> None:
                error = None
                try:
                    finisher = getattr(view, "evaluate_javascript_finish", None)
                    if callable(finisher):
                        finisher(result)
                except Exception as exc:
                    error = exc
                if callback:
                    callback(error)

            try:
                evaluator(
                    script,
                    -1,
                    None,
                    None,
                    None,
                    evaluated if callback else None,
                    None,
                )
            except TypeError:
                evaluator(
                    script,
                    -1,
                    None,
                    None,
                    None,
                    evaluated if callback else None,
                )
            return

        runner = getattr(self.view, "run_javascript", None)
        if callable(runner):
            def ran(view: Any, result: Any, _user_data: Any = None) -> None:
                error = None
                try:
                    finisher = getattr(view, "run_javascript_finish", None)
                    if callable(finisher):
                        finisher(result)
                except Exception as exc:
                    error = exc
                if callback:
                    callback(error)

            runner(script, None, ran if callback else None, None)
            return
        raise ThemeEngineError("WebKit view has no JavaScript evaluation API")

    def set_transparent_background(self) -> None:
        setter = getattr(self.view, "set_background_color", None)
        if callable(setter):
            color = self.Gdk.RGBA()
            color.red = color.green = color.blue = color.alpha = 0.0
            setter(color)

    def _request_snapshot(
        self,
        callback: Callable[[Optional[Any], Optional[Exception]], None],
    ) -> None:
        getter = getattr(self.view, "get_snapshot", None)
        finisher = getattr(self.view, "get_snapshot_finish", None)
        if not callable(getter) or not callable(finisher):
            callback(
                None,
                ThemeEngineError("This WebKitGTK build has no snapshot API"),
            )
            return

        def done(view: Any, result: Any, _user_data: Any = None) -> None:
            try:
                callback(view.get_snapshot_finish(result), None)
            except Exception as exc:
                callback(None, exc)

        region = getattr(self.WebKit.SnapshotRegion, "VISIBLE", None)
        if region is None:
            region = getattr(self.WebKit.SnapshotRegion, "FULL_DOCUMENT")
        options = getattr(
            self.WebKit.SnapshotOptions,
            "TRANSPARENT_BACKGROUND",
            0,
        )
        getter(region, options, None, done, None)

    def snapshot_png_bytes(
        self,
        callback: Callable[[Optional[bytes], Optional[Exception]], None],
    ) -> None:
        def finished(
            texture: Optional[Any],
            error: Optional[Exception],
        ) -> None:
            if error is not None or texture is None:
                callback(None, error or ThemeEngineError("Empty snapshot"))
                return
            try:
                callback(texture_png_bytes(texture), None)
            except Exception as exc:
                callback(None, exc)

        self._request_snapshot(finished)

    def snapshot_png(
        self,
        destination: Path,
        callback: Optional[Callable[[Optional[Exception]], None]] = None,
    ) -> None:
        destination = Path(destination).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)

        def finished(
            payload: Optional[bytes],
            error: Optional[Exception],
        ) -> None:
            if error is None and payload is not None:
                temporary = destination.with_name(
                    f".{destination.name}.{os.getpid()}.tmp"
                )
                try:
                    temporary.write_bytes(payload)
                    os.replace(temporary, destination)
                except Exception as exc:
                    error = exc
                    try:
                        temporary.unlink()
                    except OSError:
                        pass
            if callback:
                callback(error)

        self.snapshot_png_bytes(finished)

    def close(self) -> None:
        stop = getattr(self.view, "stop_loading", None)
        if callable(stop):
            stop()


BackendFactory = Callable[[ThemeManifest], Any]


class HtmlThemeEngine(ThemeEngine):
    """Experimental local-only HTML engine shared by preview and runtime."""

    def __init__(
        self,
        backend_factory: BackendFactory = WebKitGtkBackend,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._backend_factory = backend_factory
        self._clock = clock
        self._backend: Optional[Any] = None
        self._manifest: Optional[ThemeManifest] = None
        self._last_snapshot: Optional[SensorSnapshot] = None
        self._scheduler: Optional[SensorUpdateScheduler] = None

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
        self._scheduler = SensorUpdateScheduler(
            manifest.data_update_policy,
            clock=self._clock,
        )
        self._backend = self._backend_factory(manifest)
        self._backend.load()

    def update(self, snapshot: SensorSnapshot) -> None:
        if self._backend is None or self._scheduler is None:
            raise ThemeEngineError("HTML theme has not been loaded")
        scheduled = self._scheduler.apply(snapshot)
        self._last_snapshot = scheduled
        self._backend.evaluate(build_snapshot_script(scheduled))

    def update_async(
        self,
        snapshot: SensorSnapshot,
        callback: Callable[[Optional[Exception]], None],
    ) -> None:
        if self._backend is None or self._scheduler is None:
            raise ThemeEngineError("HTML theme has not been loaded")
        scheduled = self._scheduler.apply(snapshot)
        self._last_snapshot = scheduled
        try:
            self._backend.evaluate(build_snapshot_script(scheduled), callback)
        except TypeError:
            self._backend.evaluate(build_snapshot_script(scheduled))
            callback(None)

    def evaluate(
        self,
        script: str,
        callback: Optional[Callable[[Optional[Exception]], None]] = None,
    ) -> None:
        if self._backend is None:
            raise ThemeEngineError("HTML theme has not been loaded")
        try:
            self._backend.evaluate(script, callback)
        except TypeError:
            self._backend.evaluate(script)
            if callback:
                callback(None)

    def set_transparent_background(self) -> None:
        if self._backend is None:
            raise ThemeEngineError("HTML theme has not been loaded")
        setter = getattr(self._backend, "set_transparent_background", None)
        if callable(setter):
            setter()

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

    def snapshot_png_bytes(
        self,
        callback: Callable[[Optional[bytes], Optional[Exception]], None],
    ) -> None:
        if self._backend is None:
            raise ThemeEngineError("HTML theme has not been loaded")
        self._backend.snapshot_png_bytes(callback)

    def close(self) -> None:
        if self._backend is not None:
            self._backend.close()
        self._backend = None
        self._scheduler = None
        self._last_snapshot = None
