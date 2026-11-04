# SPDX-License-Identifier: GPL-3.0-or-later
"""Unsaved-work drafts for the HTML theme editor.

Drafts live in the user's state directory, never inside the theme: every
file in a theme folder is part of the native video source digest, so a
draft there would mark the video as stale.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from library.html_theme_visual_editor import HtmlVisualElementStyle, visual_style_from_dict
from library.theme_engine import ThemeManifest, ThemeValidationError

DRAFT_FORMAT = "turing-html-editor-draft"
DRAFT_FORMAT_VERSION = 1
APP_STATE_DIR = "turing-smart-screen"


@dataclass(frozen=True)
class EditorDraft:
    styles: tuple[HtmlVisualElementStyle, ...]
    saved_at: datetime
    # False when the theme was saved again after the draft was written.
    matches_saved_theme: bool


def drafts_directory() -> Path:
    base = os.environ.get("XDG_STATE_HOME", "").strip()
    root = Path(base) if base else Path.home() / ".local" / "state"
    return root / APP_STATE_DIR / "editor-drafts"


def draft_path(manifest: ThemeManifest, directory: Path | None = None) -> Path:
    root = str(Path(manifest.root).resolve())
    key = hashlib.sha256(root.encode("utf-8")).hexdigest()[:16]
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in Path(root).name)[:48]
    return (directory or drafts_directory()) / f"{safe_name}-{key}.json"


def _saved_document_digest(manifest: ThemeManifest) -> str:
    document = Path(manifest.root) / "overlays.json"
    try:
        return hashlib.sha256(document.read_bytes()).hexdigest()
    except OSError:
        return ""


def write_draft(
    manifest: ThemeManifest,
    styles: Sequence[HtmlVisualElementStyle],
    *,
    directory: Path | None = None,
    now: datetime | None = None,
) -> Path:
    path = draft_path(manifest, directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": DRAFT_FORMAT,
        "formatVersion": DRAFT_FORMAT_VERSION,
        "theme": str(Path(manifest.root).resolve()),
        "savedAt": (now or datetime.now(timezone.utc)).isoformat(),
        "baseDocumentSha256": _saved_document_digest(manifest),
        "elements": [style.as_dict() for style in styles],
    }
    handle, temporary = tempfile.mkstemp(prefix=".draft-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=1)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return path


def load_draft(
    manifest: ThemeManifest,
    saved_styles: Iterable[HtmlVisualElementStyle],
    *,
    directory: Path | None = None,
) -> EditorDraft | None:
    """Return a draft that differs from the saved styles, else ``None``.

    Unreadable drafts, drafts of another folder and drafts identical to the
    saved theme are removed.
    """
    path = draft_path(manifest, directory)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("format") != DRAFT_FORMAT or payload.get("formatVersion") != DRAFT_FORMAT_VERSION:
            raise ValueError("unknown draft format")
        if payload.get("theme") != str(Path(manifest.root).resolve()):
            raise ValueError("draft belongs to another theme folder")
        styles = tuple(visual_style_from_dict(item) for item in payload["elements"])
        saved_at = datetime.fromisoformat(str(payload["savedAt"]))
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError, TypeError, ThemeValidationError):
        clear_draft(manifest, directory=directory)
        return None

    if _comparable(styles) == _comparable(saved_styles):
        clear_draft(manifest, directory=directory)
        return None
    return EditorDraft(
        styles=styles,
        saved_at=saved_at,
        matches_saved_theme=payload.get("baseDocumentSha256") == _saved_document_digest(manifest),
    )


def _comparable(styles: Iterable[HtmlVisualElementStyle]) -> list[dict[str, object]]:
    # Compare the serialized form: it normalizes defaults (for example
    # generatedWidget for catalog components) the same way overlays.json does.
    return sorted((style.as_dict() for style in styles), key=lambda item: str(item["id"]))


def clear_draft(manifest: ThemeManifest, *, directory: Path | None = None) -> None:
    try:
        draft_path(manifest, directory).unlink()
    except FileNotFoundError:
        pass
