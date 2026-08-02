# SPDX-License-Identifier: GPL-3.0-or-later
"""Versioned portable theme package contract and archive safety checks."""

from __future__ import annotations

import json
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


PACKAGE_FILENAME = "theme-package.json"
PACKAGE_FORMAT = "turing-smart-screen-theme"
PACKAGE_FORMAT_VERSION = 1
PACKAGE_EXTENSION = ".theme"
LEGACY_PACKAGE_EXTENSION = ".zip"
SUPPORTED_PACKAGE_EXTENSIONS = frozenset(
    {PACKAGE_EXTENSION, LEGACY_PACKAGE_EXTENSION}
)

MAX_ARCHIVE_MEMBERS = 4096
MAX_ARCHIVE_MEMBER_BYTES = 256 * 1024 * 1024
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
MAX_SUSPICIOUS_COMPRESSION_RATIO = 250
MIN_RATIO_CHECK_BYTES = 1024 * 1024


class ThemePackageError(RuntimeError):
    """Raised when a portable theme package is invalid or unsafe."""


def _safe_archive_path(raw_path: str, field_name: str) -> PurePosixPath:
    value = str(raw_path or "")
    if not value or "\x00" in value:
        raise ThemePackageError(f"{field_name} is empty or invalid")
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise ThemePackageError(f"Unsafe {field_name}: {raw_path}")
    if not path.parts or any(part in {"", "."} for part in path.parts):
        raise ThemePackageError(f"Invalid {field_name}: {raw_path}")
    return path


@dataclass(frozen=True)
class ThemePackageDescriptor:
    name: str
    engine: str
    definition: str
    format_version: int = PACKAGE_FORMAT_VERSION

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ThemePackageDescriptor":
        if payload.get("format") != PACKAGE_FORMAT:
            raise ThemePackageError(
                f"Unsupported theme package format: {payload.get('format')!r}"
            )
        version = payload.get("formatVersion")
        if isinstance(version, bool) or not isinstance(version, int):
            raise ThemePackageError("Theme package formatVersion must be an integer")
        if version != PACKAGE_FORMAT_VERSION:
            raise ThemePackageError(
                f"Unsupported theme package version {version}; "
                f"expected {PACKAGE_FORMAT_VERSION}"
            )

        name = str(payload.get("name") or "").strip()
        if not name or len(name) > 128 or any(char in name for char in "/\\\x00"):
            raise ThemePackageError("Theme package name is invalid")

        engine = str(payload.get("engine") or "").strip().casefold()
        if engine not in {"html", "yaml"}:
            raise ThemePackageError("Theme package engine must be html or yaml")

        definition = _safe_archive_path(
            str(payload.get("definition") or ""),
            "theme package definition",
        ).as_posix()
        if engine == "html" and definition != "manifest.json":
            raise ThemePackageError("HTML theme package definition must be manifest.json")
        if engine == "yaml" and definition.casefold() not in {"theme.yaml", "theme.yml"}:
            raise ThemePackageError("YAML theme package definition must be theme.yaml or theme.yml")

        return cls(
            name=name,
            engine=engine,
            definition=definition,
            format_version=version,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "format": PACKAGE_FORMAT,
            "formatVersion": self.format_version,
            "name": self.name,
            "engine": self.engine,
            "definition": self.definition,
        }

    def as_json(self) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False, indent=2) + "\n"


def load_theme_package_descriptor(root: Path) -> ThemePackageDescriptor:
    descriptor_path = Path(root) / PACKAGE_FILENAME
    try:
        payload = json.loads(descriptor_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ThemePackageError(
            f"Theme package is missing root {PACKAGE_FILENAME}"
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ThemePackageError(f"Invalid {PACKAGE_FILENAME}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ThemePackageError(f"{PACKAGE_FILENAME} must contain an object")

    descriptor = ThemePackageDescriptor.from_mapping(payload)
    definition_path = Path(root) / Path(descriptor.definition)
    if not definition_path.is_file():
        raise ThemePackageError(
            f"Theme package definition is missing: {descriptor.definition}"
        )
    return descriptor


def validate_archive_members(archive: zipfile.ZipFile) -> None:
    """Reject unsafe paths, special files, collisions, and oversized archives."""
    members = archive.infolist()
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise ThemePackageError(
            f"Theme archive has too many members ({len(members)} > {MAX_ARCHIVE_MEMBERS})"
        )

    total_size = 0
    normalized_names: set[str] = set()
    folded_names: dict[str, str] = {}
    for member in members:
        path = _safe_archive_path(member.filename, "archive path")
        normalized = path.as_posix().rstrip("/")
        folded = normalized.casefold()
        if normalized in normalized_names:
            raise ThemePackageError(f"Duplicate archive path: {member.filename}")
        previous = folded_names.get(folded)
        if previous is not None and previous != normalized:
            raise ThemePackageError(
                f"Case-colliding archive paths: {previous} and {normalized}"
            )
        normalized_names.add(normalized)
        folded_names[folded] = normalized

        if member.flag_bits & 0x1:
            raise ThemePackageError(f"Encrypted archive member is not supported: {member.filename}")

        unix_mode = member.external_attr >> 16
        file_type = stat.S_IFMT(unix_mode)
        if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
            raise ThemePackageError(
                f"Special archive member is not supported: {member.filename}"
            )

        if member.file_size > MAX_ARCHIVE_MEMBER_BYTES:
            raise ThemePackageError(
                f"Archive member is too large: {member.filename}"
            )
        total_size += member.file_size
        if total_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            raise ThemePackageError("Theme archive is too large when uncompressed")

        if member.file_size >= MIN_RATIO_CHECK_BYTES:
            if member.compress_size <= 0:
                raise ThemePackageError(
                    f"Archive member has an invalid compressed size: {member.filename}"
                )
            ratio = member.file_size / member.compress_size
            if ratio > MAX_SUSPICIOUS_COMPRESSION_RATIO:
                raise ThemePackageError(
                    f"Archive member has a suspicious compression ratio: {member.filename}"
                )
