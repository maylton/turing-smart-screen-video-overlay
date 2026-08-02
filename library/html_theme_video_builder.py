# SPDX-License-Identifier: GPL-3.0-or-later
"""Deterministically compile an HTML theme base layer into native MP4."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

from library.html_hybrid import (
    OVERLAY_SELECTOR,
    base_layer_script,
    image_pipe_ffmpeg_command,
    seek_animations_script,
    validate_native_video_file,
)
from library.html_theme_engine import HtmlThemeEngine, WebKitGtkBackend
from library.theme_engine import ThemeManifest, ThemeValidationError


class HtmlVideoBuildError(RuntimeError):
    pass


def frame_count(manifest: ThemeManifest) -> int:
    spec = manifest.native_video_overlay
    if spec is None:
        raise ThemeValidationError("HTML theme does not enable nativeVideoOverlay")
    return int(round(spec.duration * spec.fps))


def _validate_built_video(path: Path, manifest: ThemeManifest) -> None:
    try:
        validate_native_video_file(manifest, path)
    except ThemeValidationError as exc:
        raise HtmlVideoBuildError(f"built video failed validation: {exc}") from exc


def build_native_video(
    manifest: ThemeManifest,
    *,
    destination: Optional[Path] = None,
    preview: Optional[Path] = None,
) -> tuple[Path, Path]:
    """Run the GTK builder. This function never opens a display serial port."""
    spec = manifest.native_video_overlay
    if manifest.engine != "html" or spec is None:
        raise ThemeValidationError("an opt-in HTML native-video theme is required")
    destination = (
        Path(destination).expanduser().resolve()
        if destination is not None
        else spec.local_file(manifest.root)
    )
    preview = (
        Path(preview).expanduser().resolve()
        if preview is not None
        else destination.with_name(f"{destination.stem}-background.png")
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    preview.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp.mp4")
    preview_temporary = preview.with_name(f".{preview.name}.{os.getpid()}.tmp")
    temporary.unlink(missing_ok=True)
    preview_temporary.unlink(missing_ok=True)

    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("WebKit", "6.0")
    from gi.repository import GLib, Gtk, WebKit

    def backend_factory(item):
        backend = WebKitGtkBackend(item)
        settings = backend.view.get_settings()
        policy = getattr(
            getattr(WebKit, "HardwareAccelerationPolicy", None),
            "NEVER",
            None,
        )
        setter = getattr(settings, "set_hardware_acceleration_policy", None)
        if callable(setter) and policy is not None:
            setter(policy)
        for name in ("set_enable_webgl", "set_enable_accelerated_2d_canvas"):
            disable = getattr(settings, name, None)
            if callable(disable):
                disable(False)
        return backend

    engine = HtmlThemeEngine(backend_factory)
    command = image_pipe_ffmpeg_command(temporary, fps=spec.fps)
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    class Builder(Gtk.Application):
        def __init__(self):
            super().__init__(application_id="io.github.turing.HtmlThemeVideoBuilder")
            self.window = None
            self.index = 0
            self.error: Optional[Exception] = None
            self.preview_written = False
            self.closed = False

        def fail(self, error: Exception) -> None:
            if self.error is None:
                self.error = error
            self.finish()

        def finish(self) -> None:
            if self.closed:
                return
            self.closed = True
            engine.close()
            self.quit()

        def capture_frame(self) -> bool:
            if self.closed:
                return False

            def captured(payload, error):
                if error is not None or payload is None:
                    self.fail(error or HtmlVideoBuildError("empty WebKit frame"))
                    return
                try:
                    if process.stdin is None:
                        raise HtmlVideoBuildError("FFmpeg input pipe is closed")
                    process.stdin.write(payload)
                    if (
                        not self.preview_written
                        and self.index / spec.fps >= spec.background_frame
                    ):
                        preview_temporary.write_bytes(payload)
                        self.preview_written = True
                    self.index += 1
                    if self.index >= frame_count(manifest):
                        self.finish()
                    else:
                        self.seek_next()
                except Exception as exc:
                    self.fail(exc)

            engine.snapshot_png_bytes(captured)
            return False

        def seek_next(self) -> None:
            # Warm up one complete loop before frame zero so positive CSS
            # animation delays are already in their periodic phase. This keeps
            # the last-to-first MP4 transition continuous.
            milliseconds = (
                spec.duration + self.index / spec.fps
            ) * 1000.0

            def sought(error):
                if error is not None:
                    self.fail(error)
                    return
                # Evaluation completion is a JS barrier; one short GTK paint
                # turn makes the selected animation time visible to snapshot.
                GLib.timeout_add(12, self.capture_frame)

            engine.evaluate(seek_animations_script(milliseconds), sought)

        def configured(self, error):
            if error is not None:
                self.fail(error)
                return
            self.seek_next()

        def do_activate(self):
            try:
                engine.load(manifest)
                self.window = Gtk.ApplicationWindow(application=self)
                self.window.set_default_size(manifest.width, manifest.height)
                self.window.set_resizable(False)
                self.window.set_decorated(False)
                self.window.set_child(engine.render())
                self.window.present()
                engine.evaluate(
                    base_layer_script(OVERLAY_SELECTOR),
                    self.configured,
                )
            except Exception as exc:
                self.fail(exc)

    app = Builder()
    try:
        app.run([])
        if process.stdin is not None:
            process.stdin.close()
            process.stdin = None
        _stdout, stderr = process.communicate(timeout=90)
        if app.error is not None:
            raise HtmlVideoBuildError(str(app.error)) from app.error
        if process.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace").strip()
            raise HtmlVideoBuildError(detail or f"FFmpeg exited {process.returncode}")
        if not temporary.is_file() or temporary.stat().st_size <= 0:
            raise HtmlVideoBuildError("FFmpeg did not produce a native video")
        if not preview_temporary.is_file():
            raise HtmlVideoBuildError("WebKit did not produce a preview frame")
        _validate_built_video(temporary, manifest)
        os.replace(temporary, destination)
        os.replace(preview_temporary, preview)
        return destination, preview
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        temporary.unlink(missing_ok=True)
        preview_temporary.unlink(missing_ok=True)
