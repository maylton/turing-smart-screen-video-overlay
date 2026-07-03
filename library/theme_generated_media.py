# SPDX-License-Identifier: GPL-3.0-or-later
"""Inventory and safely manage generated theme media.

The module deliberately contains no GTK code.  UI callers receive immutable
records and may only delete an asset through ``remove_unused_managed_asset``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

from library.theme_media_transform import (
    GENERATED_MEDIA_DIR,
    TRANSFORM_MANIFEST,
    ImageTransformSettings,
    ThemeMediaTransformError,
    load_transform_manifest,
    save_transform_manifest_atomic,
)


class GeneratedMediaStatus(str, Enum):
    IN_USE = "in-use"
    UNUSED = "unused"
    ORPHANED = "orphaned"
    UNMANAGED = "unmanaged"


@dataclass(frozen=True)
class GeneratedMediaRecord:
    reference: str
    path: Path
    status: GeneratedMediaStatus
    registered: bool
    referenced: bool
    exists: bool
    source_reference: str | None = None
    source_path: Path | None = None
    source_exists: bool = False
    source_hash_matches: bool | None = None
    settings: ImageTransformSettings | None = None
    issues: tuple[str, ...] = ()

    @property
    def removable(self) -> bool:
        return (
            self.status is GeneratedMediaStatus.UNUSED
            and self.registered
            and not self.referenced
            and self.exists
        )


@dataclass(frozen=True)
class GeneratedMediaReport:
    theme_dir: Path
    manifest_path: Path
    records: tuple[GeneratedMediaRecord, ...]
    manifest_valid: bool
    manifest_error: str | None = None

    def by_reference(self, reference: str) -> GeneratedMediaRecord | None:
        normalized = normalize_theme_reference(reference)
        return next(
            (record for record in self.records if record.reference == normalized),
            None,
        )


class GeneratedMediaRemovalError(ValueError):
    """Raised when a requested generated-media deletion is unsafe."""


def normalize_theme_reference(value: str) -> str:
    """Normalize a theme-relative reference without accepting traversal."""
    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        return ""
    path = Path(raw)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        return raw
    return path.as_posix().lstrip("./")


def _walk_scalar_strings(node: Any) -> Iterable[str]:
    if isinstance(node, Mapping):
        for value in node.values():
            yield from _walk_scalar_strings(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield from _walk_scalar_strings(value)
    elif isinstance(node, str):
        yield node


def referenced_generated_media(theme_data: Any) -> frozenset[str]:
    """Return generated-media references found anywhere in the theme data."""
    prefix = f"{GENERATED_MEDIA_DIR}/"
    references = {
        normalized
        for value in _walk_scalar_strings(theme_data)
        if (normalized := normalize_theme_reference(value)).startswith(prefix)
    }
    return frozenset(references)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _settings_from_entry(entry: Mapping[str, Any]) -> ImageTransformSettings:
    crop = entry.get("crop")
    crop_box = None
    if isinstance(crop, Mapping):
        crop_box = (
            int(crop.get("x", 0)),
            int(crop.get("y", 0)),
            int(crop.get("width", 0)),
            int(crop.get("height", 0)),
        )
    return ImageTransformSettings(
        rotation=int(entry.get("rotation", 0)),
        flip_horizontal=bool(entry.get("flip_horizontal", False)),
        flip_vertical=bool(entry.get("flip_vertical", False)),
        crop_box=crop_box,
    )


def _resolve_source(theme_dir: Path, reference: str) -> Path:
    path = Path(str(reference or "")).expanduser()
    if not path.is_absolute():
        if any(part == ".." for part in path.parts):
            raise ThemeMediaTransformError(
                "Source reference cannot contain path traversal"
            )
        path = theme_dir / path
    return path.resolve()


def _registered_record(
    theme_dir: Path,
    reference: str,
    entry: Mapping[str, Any],
    references: frozenset[str],
) -> GeneratedMediaRecord:
    path = (theme_dir / reference).resolve()
    exists = path.is_file()
    referenced = reference in references
    issues: list[str] = []

    source_reference = str(entry.get("source_reference") or "").strip()
    source_path = None
    source_exists = False
    source_hash_matches = None
    if not source_reference:
        issues.append("Missing source_reference")
    else:
        try:
            source_path = _resolve_source(theme_dir, source_reference)
            source_exists = source_path.is_file()
        except ThemeMediaTransformError as exc:
            issues.append(str(exc))
        if not source_exists:
            issues.append("Source file is missing")

    expected_hash = str(entry.get("source_sha256") or "").strip()
    if source_exists and expected_hash:
        try:
            source_hash_matches = _sha256_file(source_path) == expected_hash
        except OSError as exc:
            issues.append(f"Could not hash source: {exc}")
        if source_hash_matches is False:
            issues.append("Source hash no longer matches")

    try:
        settings = _settings_from_entry(entry)
    except (TypeError, ValueError, ThemeMediaTransformError) as exc:
        settings = None
        issues.append(f"Invalid transform settings: {exc}")

    if not exists:
        issues.append("Registered output file is missing")

    if not exists or settings is None:
        status = GeneratedMediaStatus.ORPHANED
    elif referenced:
        status = GeneratedMediaStatus.IN_USE
    else:
        status = GeneratedMediaStatus.UNUSED

    return GeneratedMediaRecord(
        reference=reference,
        path=path,
        status=status,
        registered=True,
        referenced=referenced,
        exists=exists,
        source_reference=source_reference or None,
        source_path=source_path,
        source_exists=source_exists,
        source_hash_matches=source_hash_matches,
        settings=settings,
        issues=tuple(issues),
    )


def inspect_generated_media(
    theme_dir: str | Path,
    theme_data: Any,
) -> GeneratedMediaReport:
    """Build a complete, deterministic generated-media inventory."""
    root = Path(theme_dir).expanduser().resolve()
    generated_dir = root / GENERATED_MEDIA_DIR
    manifest_path = generated_dir / TRANSFORM_MANIFEST
    references = referenced_generated_media(theme_data)

    try:
        manifest = load_transform_manifest(root)
    except (OSError, ThemeMediaTransformError) as exc:
        return GeneratedMediaReport(
            theme_dir=root,
            manifest_path=manifest_path,
            records=(),
            manifest_valid=False,
            manifest_error=str(exc),
        )

    assets = manifest["assets"]
    records = [
        _registered_record(root, reference, entry, references)
        for reference, entry in sorted(assets.items())
    ]

    registered_paths = {record.path for record in records}
    if generated_dir.is_dir():
        for path in sorted(generated_dir.iterdir(), key=lambda item: item.name.casefold()):
            if (
                not path.is_file()
                or path.name == TRANSFORM_MANIFEST
                or path.resolve() in registered_paths
            ):
                continue
            records.append(
                GeneratedMediaRecord(
                    reference=f"{GENERATED_MEDIA_DIR}/{path.name}",
                    path=path.resolve(),
                    status=GeneratedMediaStatus.UNMANAGED,
                    registered=False,
                    referenced=(
                        f"{GENERATED_MEDIA_DIR}/{path.name}" in references
                    ),
                    exists=True,
                    issues=("File is not registered in the transform manifest",),
                )
            )

    order = {
        GeneratedMediaStatus.IN_USE: 0,
        GeneratedMediaStatus.UNUSED: 1,
        GeneratedMediaStatus.ORPHANED: 2,
        GeneratedMediaStatus.UNMANAGED: 3,
    }
    records.sort(key=lambda record: (order[record.status], record.reference.casefold()))
    return GeneratedMediaReport(
        theme_dir=root,
        manifest_path=manifest_path,
        records=tuple(records),
        manifest_valid=True,
    )


def remove_unused_managed_asset(
    theme_dir: str | Path,
    theme_data: Any,
    reference: str,
) -> GeneratedMediaReport:
    """Delete exactly one registered, existing and unreferenced asset.

    The manifest is changed first and restored if unlinking fails.  Unmanaged,
    referenced, missing or otherwise orphaned entries are never deleted.
    """
    root = Path(theme_dir).expanduser().resolve()
    normalized = normalize_theme_reference(reference)
    report = inspect_generated_media(root, theme_data)
    if not report.manifest_valid:
        raise GeneratedMediaRemovalError(
            report.manifest_error or "Transform manifest is invalid"
        )
    record = report.by_reference(normalized)
    if record is None:
        raise GeneratedMediaRemovalError("Asset is not registered")
    if not record.removable:
        raise GeneratedMediaRemovalError(
            f"Refusing to remove {normalized}: status is {record.status.value}"
        )

    manifest = load_transform_manifest(root)
    original_manifest = {
        "version": manifest["version"],
        "assets": dict(manifest["assets"]),
    }
    updated_manifest = {
        "version": manifest["version"],
        "assets": dict(manifest["assets"]),
    }
    if normalized not in updated_manifest["assets"]:
        raise GeneratedMediaRemovalError("Asset is not registered")
    del updated_manifest["assets"][normalized]

    save_transform_manifest_atomic(root, updated_manifest)
    try:
        record.path.unlink()
    except OSError:
        save_transform_manifest_atomic(root, original_manifest)
        raise

    return inspect_generated_media(root, theme_data)
