# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure preflight checks for Theme Gallery export.

The current gallery export writes the selected theme folder to a ``.zip`` file.
This module inspects the theme before that export so the UI can warn when the
archive may be incomplete: missing referenced files, external local media,
unmanaged generated assets, or invalid generated-media metadata.

This module deliberately contains no GTK code and never mutates theme files.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from library.theme_generated_media import (
    GeneratedMediaReport,
    GeneratedMediaStatus,
    inspect_generated_media,
    normalize_theme_reference,
)
from library.theme_media_transform import GENERATED_MEDIA_DIR


ASSET_REFERENCE_KEYS = frozenset(
    {
        "PATH",
        "BACKGROUND_IMAGE",
        "PREVIEW_BACKGROUND",
        "FONT",
        "AXIS_FONT",
        "LOCAL_PATH",
        "IMAGE",
        "ICON",
    }
)

REMOTE_DEVICE_PREFIXES = (
    "/mnt/SDCARD/",
    "/mnt/sdcard/",
    "/root/video/",
    "/root/videos/",
)

GLOBAL_FONT_SUFFIXES = (".ttf", ".otf", ".ttc")


class ExportAssetStatus(str, Enum):
    INCLUDED = "included"
    MISSING = "missing"
    OUTSIDE_THEME = "outside-theme"
    INVALID = "invalid"
    REMOTE_DEVICE = "remote-device"
    GLOBAL_FONT = "global-font"
    GENERATED_MANAGED = "generated-managed"
    GENERATED_UNMANAGED = "generated-unmanaged"
    GENERATED_MISSING = "generated-missing"


@dataclass(frozen=True)
class ThemeAssetReference:
    key_path: str
    reference: str
    normalized_reference: str
    path: Path | None
    status: ExportAssetStatus
    included_in_archive: bool
    warning: str | None = None

    @property
    def needs_attention(self) -> bool:
        return self.warning is not None


@dataclass(frozen=True)
class ThemeExportPreflightReport:
    theme_dir: Path
    yaml_file: Path | None
    yaml_valid: bool
    asset_references: tuple[ThemeAssetReference, ...]
    generated_media: GeneratedMediaReport | None
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.yaml_valid and not self.errors and not self.warnings

    @property
    def blocking(self) -> bool:
        return bool(self.errors)

    def by_reference(self, reference: str) -> tuple[ThemeAssetReference, ...]:
        normalized = normalize_theme_reference(reference)
        return tuple(
            item
            for item in self.asset_references
            if item.normalized_reference == normalized
        )

    def to_text(self) -> str:
        lines = [
            "Theme Export Preflight",
            "======================",
            "",
            f"Theme folder: {self.theme_dir}",
            f"Theme YAML: {self.yaml_file if self.yaml_file is not None else 'missing'}",
            f"YAML valid: {'yes' if self.yaml_valid else 'no'}",
            f"Referenced assets: {len(self.asset_references)}",
            f"Errors: {len(self.errors)}",
            f"Warnings: {len(self.warnings)}",
        ]
        if self.errors:
            lines.extend(["", "Errors:"])
            lines.extend(f"- {error}" for error in self.errors)
        if self.warnings:
            lines.extend(["", "Warnings:"])
            lines.extend(f"- {warning}" for warning in self.warnings)
        if self.asset_references:
            lines.extend(["", "Assets:"])
            for asset in self.asset_references:
                detail = f"- [{asset.status.value}] {asset.key_path}: {asset.reference}"
                if asset.warning:
                    detail += f" — {asset.warning}"
                lines.append(detail)
        return "\n".join(lines)


def find_theme_file(theme_dir: str | Path) -> Path | None:
    root = Path(theme_dir).expanduser()
    for filename in ("theme.yaml", "theme.yml"):
        candidate = root / filename
        if candidate.is_file():
            return candidate
    return None


def inspect_theme_export(theme_dir: str | Path) -> ThemeExportPreflightReport:
    """Inspect a theme folder before export without mutating it."""
    root = Path(theme_dir).expanduser().resolve()
    yaml_file = find_theme_file(root)
    errors: list[str] = []
    warnings: list[str] = []

    if yaml_file is None:
        return ThemeExportPreflightReport(
            theme_dir=root,
            yaml_file=None,
            yaml_valid=False,
            asset_references=(),
            generated_media=None,
            errors=("Theme cannot be exported because theme.yaml/theme.yml is missing.",),
        )

    try:
        with yaml_file.open("r", encoding="utf-8") as stream:
            theme_data = yaml.safe_load(stream) or {}
    except yaml.YAMLError as exc:
        return ThemeExportPreflightReport(
            theme_dir=root,
            yaml_file=yaml_file,
            yaml_valid=False,
            asset_references=(),
            generated_media=None,
            errors=(f"Theme YAML is invalid: {exc}",),
        )
    except OSError as exc:
        return ThemeExportPreflightReport(
            theme_dir=root,
            yaml_file=yaml_file,
            yaml_valid=False,
            asset_references=(),
            generated_media=None,
            errors=(f"Theme YAML could not be read: {exc}",),
        )

    generated_report = inspect_generated_media(root, theme_data)
    if not generated_report.manifest_valid:
        warnings.append(
            generated_report.manifest_error
            or "Generated-media manifest is invalid."
        )

    references = tuple(
        _classify_reference(root, raw, generated_report)
        for raw in _walk_asset_references(theme_data)
    )
    references = tuple(_dedupe_references(references))
    warnings.extend(
        reference.warning for reference in references if reference.warning is not None
    )

    return ThemeExportPreflightReport(
        theme_dir=root,
        yaml_file=yaml_file,
        yaml_valid=True,
        asset_references=references,
        generated_media=generated_report,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def _walk_asset_references(node: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[str, str, str]]:
    if isinstance(node, Mapping):
        for key, value in node.items():
            key_text = str(key)
            key_upper = key_text.upper()
            child_path = (*path, key_text)
            if key_upper in ASSET_REFERENCE_KEYS and isinstance(value, str):
                yield (".".join(child_path), key_upper, value)
            elif isinstance(value, (Mapping, list, tuple)):
                yield from _walk_asset_references(value, child_path)
    elif isinstance(node, (list, tuple)):
        for index, value in enumerate(node):
            child_path = (*path, str(index))
            if isinstance(value, (Mapping, list, tuple)):
                yield from _walk_asset_references(value, child_path)


def _dedupe_references(
    references: Iterable[ThemeAssetReference],
) -> Iterable[ThemeAssetReference]:
    seen: set[tuple[str, str]] = set()
    for reference in references:
        key = (reference.key_path, reference.reference)
        if key in seen:
            continue
        seen.add(key)
        yield reference


def _classify_reference(
    theme_dir: Path,
    raw: tuple[str, str, str],
    generated_report: GeneratedMediaReport,
) -> ThemeAssetReference:
    key_path, key_name, value = raw
    reference = str(value or "").strip().strip('"\'')
    normalized = normalize_theme_reference(reference)

    if not normalized:
        return ThemeAssetReference(
            key_path=key_path,
            reference=reference,
            normalized_reference=normalized,
            path=None,
            status=ExportAssetStatus.INVALID,
            included_in_archive=False,
            warning=f"{key_path} is empty.",
        )

    if _is_remote_device_reference(reference):
        return ThemeAssetReference(
            key_path=key_path,
            reference=reference,
            normalized_reference=normalized,
            path=None,
            status=ExportAssetStatus.REMOTE_DEVICE,
            included_in_archive=False,
        )

    if _looks_like_url(reference):
        return ThemeAssetReference(
            key_path=key_path,
            reference=reference,
            normalized_reference=normalized,
            path=None,
            status=ExportAssetStatus.OUTSIDE_THEME,
            included_in_archive=False,
            warning=f"{key_path} points to an external URL that will not be included in the export.",
        )

    path = Path(reference).expanduser()
    if path.is_absolute():
        resolved = path.resolve()
        try:
            relative = resolved.relative_to(theme_dir)
        except ValueError:
            return ThemeAssetReference(
                key_path=key_path,
                reference=reference,
                normalized_reference=normalized,
                path=resolved,
                status=ExportAssetStatus.OUTSIDE_THEME,
                included_in_archive=False,
                warning=f"{key_path} points outside the theme folder and will not be included in the export.",
            )
        normalized = relative.as_posix()
        path = resolved
    else:
        if any(part == ".." for part in path.parts):
            return ThemeAssetReference(
                key_path=key_path,
                reference=reference,
                normalized_reference=normalized,
                path=None,
                status=ExportAssetStatus.INVALID,
                included_in_archive=False,
                warning=f"{key_path} contains path traversal and cannot be safely exported.",
            )
        path = (theme_dir / normalized).resolve()
        try:
            path.relative_to(theme_dir)
        except ValueError:
            return ThemeAssetReference(
                key_path=key_path,
                reference=reference,
                normalized_reference=normalized,
                path=path,
                status=ExportAssetStatus.INVALID,
                included_in_archive=False,
                warning=f"{key_path} escapes the theme folder and cannot be safely exported.",
            )

    if _is_global_font_reference(theme_dir, key_name, normalized, path):
        return ThemeAssetReference(
            key_path=key_path,
            reference=reference,
            normalized_reference=normalized,
            path=None,
            status=ExportAssetStatus.GLOBAL_FONT,
            included_in_archive=False,
        )

    generated_status = _classify_generated_reference(
        key_path,
        reference,
        normalized,
        path,
        generated_report,
    )
    if generated_status is not None:
        return generated_status

    if not path.is_file():
        return ThemeAssetReference(
            key_path=key_path,
            reference=reference,
            normalized_reference=normalized,
            path=path,
            status=ExportAssetStatus.MISSING,
            included_in_archive=False,
            warning=f"{key_path} references a missing file: {normalized}",
        )

    return ThemeAssetReference(
        key_path=key_path,
        reference=reference,
        normalized_reference=normalized,
        path=path,
        status=ExportAssetStatus.INCLUDED,
        included_in_archive=True,
    )


def _classify_generated_reference(
    key_path: str,
    reference: str,
    normalized: str,
    path: Path,
    generated_report: GeneratedMediaReport,
) -> ThemeAssetReference | None:
    if not normalized.startswith(f"{GENERATED_MEDIA_DIR}/"):
        return None

    record = generated_report.by_reference(normalized) if generated_report.manifest_valid else None
    if record is None:
        if path.is_file():
            return ThemeAssetReference(
                key_path=key_path,
                reference=reference,
                normalized_reference=normalized,
                path=path,
                status=ExportAssetStatus.GENERATED_UNMANAGED,
                included_in_archive=True,
                warning=f"{key_path} references generated media without manifest metadata: {normalized}",
            )
        return ThemeAssetReference(
            key_path=key_path,
            reference=reference,
            normalized_reference=normalized,
            path=path,
            status=ExportAssetStatus.GENERATED_MISSING,
            included_in_archive=False,
            warning=f"{key_path} references missing generated media: {normalized}",
        )

    if record.registered and record.exists:
        return ThemeAssetReference(
            key_path=key_path,
            reference=reference,
            normalized_reference=normalized,
            path=record.path,
            status=ExportAssetStatus.GENERATED_MANAGED,
            included_in_archive=True,
        )

    if record.exists:
        return ThemeAssetReference(
            key_path=key_path,
            reference=reference,
            normalized_reference=normalized,
            path=record.path,
            status=ExportAssetStatus.GENERATED_UNMANAGED,
            included_in_archive=True,
            warning=f"{key_path} references generated media without manifest metadata: {normalized}",
        )

    return ThemeAssetReference(
        key_path=key_path,
        reference=reference,
        normalized_reference=normalized,
        path=record.path,
        status=ExportAssetStatus.GENERATED_MISSING,
        included_in_archive=False,
        warning=f"{key_path} references missing generated media: {normalized}",
    )


def _is_remote_device_reference(value: str) -> bool:
    text = str(value or "").strip()
    return text.startswith(REMOTE_DEVICE_PREFIXES)


def _looks_like_url(value: str) -> bool:
    text = str(value or "").strip().lower()
    return text.startswith(("http://", "https://"))


def _is_global_font_reference(
    theme_dir: Path,
    key_name: str,
    normalized: str,
    resolved_theme_path: Path,
) -> bool:
    if key_name not in {"FONT", "AXIS_FONT"}:
        return False
    if resolved_theme_path.is_file():
        return False
    if Path(normalized).suffix.casefold() not in GLOBAL_FONT_SUFFIXES:
        return False

    # The common theme format stores fonts relative to res/fonts, not inside each
    # theme folder.  Those fonts are installation assets rather than theme export
    # payload.  Missing global fonts are intentionally not escalated here; the
    # theme diagnostics/font pipeline should handle installation-level assets.
    project_root = theme_dir.parents[1] if len(theme_dir.parents) >= 2 else theme_dir
    return (project_root / "fonts" / normalized).is_file()
