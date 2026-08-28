# SPDX-License-Identifier: GPL-3.0-or-later
"""Upgrade plain 480x480 HTML themes when a compiled background is added.

The visual background page is useful for imported HTML themes that already
provide live ``data-turing-overlay`` elements but do not yet declare the
optional ``nativeVideoOverlay`` build contract.  This module creates that
contract only when the user explicitly saves a background.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from library.theme_engine import ThemeManifest, ThemeValidationError


_PATCHED = False


def _output_stem(manifest: ThemeManifest) -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", manifest.root.name)
    value = re.sub(r"-{2,}", "-", value).strip("-._")
    return value or "html-theme"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def ensure_native_video_overlay(manifest: ThemeManifest) -> ThemeManifest:
    """Enable a conservative native-video contract for a plain HTML theme."""
    if manifest.native_video_overlay is not None:
        return manifest
    if manifest.engine != "html":
        raise ThemeValidationError("background media requires an HTML theme")
    if (manifest.width, manifest.height) != (480, 480):
        raise ThemeValidationError(
            "compiled background media currently requires a 480x480 HTML theme"
        )
    if manifest.network:
        raise ThemeValidationError(
            "compiled background media requires network=false"
        )
    if "sensors" not in manifest.permissions:
        raise ThemeValidationError(
            "compiled background media requires the sensors permission"
        )

    manifest_path = manifest.root / "manifest.json"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ThemeValidationError(f"Invalid manifest.json: {exc}") from exc
    if not isinstance(payload, dict):
        raise ThemeValidationError("manifest.json must contain an object")

    filename = f"{_output_stem(manifest)}-background.mp4"
    payload["nativeVideoOverlay"] = {
        "enabled": True,
        "localPath": filename,
        "devicePath": f"/mnt/SDCARD/video/{filename}",
        "fps": 24,
        "duration": 8,
        "backgroundFrame": 0,
    }
    _atomic_write_json(manifest_path, payload)
    return ThemeManifest.load(manifest.root)


def install_background_editor_hook() -> None:
    """Install the normal background page with plain-theme auto-upgrade."""
    global _PATCHED

    from library import html_theme_background_editor as editor

    if not _PATCHED:
        original_save_background_media = editor.save_background_media

        def save_background_media_with_upgrade(manifest, *args, **kwargs):
            upgraded = ensure_native_video_overlay(manifest)
            return original_save_background_media(upgraded, *args, **kwargs)

        save_background_media_with_upgrade.__name__ = (
            original_save_background_media.__name__
        )
        save_background_media_with_upgrade.__doc__ = (
            original_save_background_media.__doc__
        )
        editor.save_background_media = save_background_media_with_upgrade
        _PATCHED = True

    editor.install_background_editor_hook()
