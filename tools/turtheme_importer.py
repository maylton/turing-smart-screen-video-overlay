#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Best-effort importer for original Turing/Windows theme packages.

This tool does not try to clone the proprietary editor format. It extracts
detectable media assets and generates an open, editable theme folder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}

GRAPH_MARKER_RE = re.compile(
    rb"(?:Data|Text|StatuBar|Image)--[A-Za-z0-9_ :%./()\\-]+"
)
REMOTE_VIDEO_RE = re.compile(
    rb"/(?:mnt/SDCARD|root)/video/[^\x00\r\n]+?\.mp4"
)
WINDOWS_VIDEO_RE = re.compile(
    rb"[A-Za-z]:[\\/][^\x00\r\n]+?\.mp4"
)
ANY_MP4_RE = re.compile(
    rb"[^\x00\r\n]{1,240}?\.mp4"
)

KNOWN_WIDGET_TOKENS = (
    "CPUTEMP",
    "CPULOAD",
    "TIME",
    "Time",
    "Temp",
    "Cpu Temp",
    "Cpu Usage",
    "StaticText",
)


@dataclass(frozen=True)
class OriginalThemeMetadata:
    remote_video_path: str | None
    referenced_video_paths: list[str]
    graph_markers: list[str]
    widget_tokens: list[str]
    is_usbmonitor_binary: bool


@dataclass(frozen=True)
class Asset:
    source: Path
    relative: str
    kind: str
    width: int | None = None
    height: int | None = None
    sha256: str = ""


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-._")
    return value or "converted-theme"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_member_path(base: Path, name: str) -> Path:
    target = (base / name).resolve()
    base_resolved = base.resolve()
    if not str(target).startswith(str(base_resolved) + os.sep):
        raise ValueError(f"Unsafe archive member path: {name}")
    return target


def extract_zip(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(source) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            target = safe_member_path(destination, member.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)


def extract_png_chunks_from_binary(source: Path, destination: Path) -> int:
    data = source.read_bytes()
    signature = b"\x89PNG\r\n\x1a\n"
    count = 0
    index = 0

    while True:
        start = data.find(signature, index)
        if start < 0:
            break

        cursor = start + len(signature)
        end = None

        while cursor + 8 <= len(data):
            length = int.from_bytes(data[cursor : cursor + 4], "big")
            chunk_type = data[cursor + 4 : cursor + 8]
            cursor += 8 + length + 4

            if cursor > len(data):
                break

            if chunk_type == b"IEND":
                end = cursor
                break

        if end is None:
            index = start + len(signature)
            continue

        count += 1
        out = destination / f"carved_{count:03d}.png"
        out.write_bytes(data[start:end])
        index = end

    return count


def extract_jpeg_chunks_from_binary(source: Path, destination: Path, offset: int = 0) -> int:
    data = source.read_bytes()
    count = 0
    index = offset

    while True:
        start = data.find(b"\xff\xd8", index)
        if start < 0:
            break

        end = data.find(b"\xff\xd9", start + 2)
        if end < 0:
            break

        count += 1
        out = destination / f"carved_{count:03d}.jpg"
        out.write_bytes(data[start : end + 2])
        index = end + 2

    return count


def prepare_source_tree(source: Path, workdir: Path) -> Path:
    source = source.expanduser().resolve()

    if source.is_dir():
        return source

    if not source.is_file():
        raise FileNotFoundError(source)

    extracted = workdir / "source"
    extracted.mkdir(parents=True, exist_ok=True)

    if zipfile.is_zipfile(source):
        extract_zip(source, extracted)
        return extracted

    suffix = source.suffix.lower()
    if suffix in IMAGE_EXTENSIONS or suffix in VIDEO_EXTENSIONS:
        shutil.copy2(source, extracted / source.name)
        return extracted

    carved = workdir / "carved"
    carved.mkdir(parents=True, exist_ok=True)
    png_count = extract_png_chunks_from_binary(source, carved)
    jpg_count = extract_jpeg_chunks_from_binary(source, carved)

    if png_count or jpg_count:
        return carved

    raise RuntimeError(
        "Could not extract media assets. The file may be encrypted or use an "
        "unsupported proprietary container."
    )


def png_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        with path.open("rb") as handle:
            header = handle.read(24)
        if header[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        return struct.unpack(">II", header[16:24])
    except Exception:
        return None


def jpeg_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        data = path.read_bytes()
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            index += 2
            if marker in {0xD8, 0xD9}:
                continue
            length = int.from_bytes(data[index : index + 2], "big")
            if marker in {
                0xC0, 0xC1, 0xC2, 0xC3,
                0xC5, 0xC6, 0xC7,
                0xC9, 0xCA, 0xCB,
                0xCD, 0xCE, 0xCF,
            }:
                height = int.from_bytes(data[index + 3 : index + 5], "big")
                width = int.from_bytes(data[index + 5 : index + 7], "big")
                return width, height
            index += length
    except Exception:
        return None
    return None


def image_dimensions(path: Path) -> tuple[int, int] | None:
    suffix = path.suffix.lower()
    if suffix == ".png":
        return png_dimensions(path)
    if suffix in {".jpg", ".jpeg"}:
        return jpeg_dimensions(path)
    return None


def collect_assets(root: Path) -> list[Asset]:
    assets: list[Asset] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue

        suffix = path.suffix.lower()
        if suffix not in IMAGE_EXTENSIONS and suffix not in VIDEO_EXTENSIONS:
            continue

        relative = path.relative_to(root).as_posix()
        kind = "video" if suffix in VIDEO_EXTENSIONS else "image"
        width = None
        height = None

        if kind == "image":
            dims = image_dimensions(path)
            if dims is not None:
                width, height = dims

        assets.append(
            Asset(
                source=path,
                relative=relative,
                kind=kind,
                width=width,
                height=height,
                sha256=file_sha256(path),
            )
        )

    return assets


def score_asset(asset: Asset, keywords: tuple[str, ...]) -> int:
    name = asset.relative.lower()
    score = 0
    for keyword in keywords:
        if keyword in name:
            score += 10
    if asset.width and asset.height:
        score += min(asset.width * asset.height // 10000, 100)
    return score


def choose_asset(assets: list[Asset], keywords: tuple[str, ...]) -> Asset | None:
    candidates = [asset for asset in assets if asset.kind == "image"]
    if not candidates:
        return None
    ranked = sorted(
        candidates,
        key=lambda asset: score_asset(asset, keywords),
        reverse=True,
    )
    return ranked[0] if score_asset(ranked[0], keywords) > 0 else None


def asset_fs_path(asset: Asset) -> Path:
    """Return the filesystem path stored in an Asset, regardless of field name."""
    preferred_names = (
        "path",
        "source",
        "source_path",
        "file",
        "filepath",
        "full_path",
        "absolute_path",
        "src",
    )

    for name in preferred_names:
        value = getattr(asset, name, None)
        if isinstance(value, Path):
            return value
        if isinstance(value, str):
            candidate = Path(value)
            if candidate.exists():
                return candidate

    for name in getattr(asset, "__dataclass_fields__", {}):
        value = getattr(asset, name, None)
        if isinstance(value, Path):
            return value
        if isinstance(value, str):
            candidate = Path(value)
            if candidate.exists():
                return candidate

    fields = ", ".join(getattr(asset, "__dataclass_fields__", {}).keys())
    raise AttributeError(f"Cannot resolve filesystem path for Asset fields: {fields}")


def asset_byte_size(asset: Asset) -> int:
    """Return an Asset byte size, regardless of field name."""
    preferred_names = (
        "size",
        "size_bytes",
        "file_size",
        "filesize",
        "bytes",
        "length",
    )

    for name in preferred_names:
        value = getattr(asset, name, None)
        if isinstance(value, int):
            return value

    try:
        return asset_fs_path(asset).stat().st_size
    except OSError:
        return 0


def image_metadata(path: Path) -> tuple[str | None, tuple[int, int] | None]:
    try:
        from PIL import Image
    except Exception:
        return None, None

    try:
        with Image.open(path) as image:
            return image.mode, image.size
    except Exception:
        return None, None


def image_has_alpha(path: Path) -> bool:
    mode, _size = image_metadata(path)
    return mode in {"RGBA", "LA", "PA"}


def image_area(path: Path) -> int:
    _mode, size = image_metadata(path)
    if not size:
        return 0
    return size[0] * size[1]


def valid_image_assets(assets: list[Asset]) -> list[Asset]:
    return [
        asset for asset in assets
        if asset.kind == "image" and image_area(asset_fs_path(asset)) > 0
    ]


def choose_rendered_preview(assets: list[Asset]) -> Asset | None:
    images = valid_image_assets(assets)
    if not images:
        return None

    # Rendered previews from .turtheme usually are RGB and contain the final
    # baked layout. Keep this for preview.png only.
    rgb_images = [asset for asset in images if not image_has_alpha(asset_fs_path(asset))]
    if rgb_images:
        return max(rgb_images, key=lambda asset: (image_area(asset_fs_path(asset)), asset_byte_size(asset)))

    return max(images, key=lambda asset: (image_area(asset_fs_path(asset)), asset_byte_size(asset)))


def choose_clean_background(assets: list[Asset]) -> Asset | None:
    images = valid_image_assets(assets)
    if not images:
        return None

    # Clean layers/backgrounds are commonly RGBA in UsbMonitorL themes.
    alpha_images = [asset for asset in images if image_has_alpha(asset_fs_path(asset))]
    if alpha_images:
        return max(alpha_images, key=lambda asset: (image_area(asset_fs_path(asset)), asset_byte_size(asset)))

    return max(images, key=lambda asset: (image_area(asset_fs_path(asset)), asset_byte_size(asset)))


def choose_largest_image(assets: list[Asset]) -> Asset | None:
    images = valid_image_assets(assets)
    if not images:
        return None

    return max(images, key=lambda asset: (image_area(asset_fs_path(asset)), asset_byte_size(asset)))


def canonical_copy(asset: Asset, output: Path, filename: str) -> str:
    suffix = asset.source.suffix.lower()
    if not filename.lower().endswith(suffix):
        filename += suffix
    target = output / filename
    shutil.copy2(asset.source, target)
    return target.name


def unique_raw_name(relative: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", relative.replace("/", "__"))
    return clean.strip("._") or "asset"


def copy_raw_assets(assets: list[Asset], output: Path) -> list[dict[str, object]]:
    raw_dir = output / "original-assets"
    raw_dir.mkdir(parents=True, exist_ok=True)

    records = []
    used: set[str] = set()

    for asset in assets:
        raw_name = unique_raw_name(asset.relative)
        stem = Path(raw_name).stem
        suffix = Path(raw_name).suffix or asset.source.suffix
        candidate = stem + suffix
        counter = 2

        while candidate in used:
            candidate = f"{stem}-{counter}{suffix}"
            counter += 1

        used.add(candidate)
        target = raw_dir / candidate
        shutil.copy2(asset.source, target)

        records.append(
            {
                "source": asset.relative,
                "kind": asset.kind,
                "output": f"original-assets/{candidate}",
                "width": asset.width,
                "height": asset.height,
                "sha256": asset.sha256,
            }
        )

    return records


def decode_binary_string(value: bytes) -> str:
    return value.decode("utf-8", errors="ignore").strip("\\x00 \\r\\n")


def clean_detected_path(value: str) -> str:
    value = value.strip("\x00 \r\n")
    normalized = value.replace("\\", "/")

    # BinaryFormatter strings can leak a prefix before the real path:
    # "F/mnt/SDCARD/video/file.mp4" -> "/mnt/SDCARD/video/file.mp4"
    for marker in ("/mnt/SDCARD/video/", "/root/video/"):
        index = normalized.find(marker)
        if index >= 0:
            candidate = normalized[index:]
            end = candidate.lower().find(".mp4")
            if end >= 0:
                return candidate[: end + 4]

    # Windows paths can also be prefixed by BinaryFormatter length/type bytes:
    # "gC:\\Users\\..." or "MD:\\21inchENG\\..."
    drive_match = re.search(
        r"[A-Za-z]:[\\/][^\x00\r\n]+?\.mp4",
        normalized,
    )
    if drive_match:
        return drive_match.group(0)

    # Last fallback: keep only an MP4-looking basename.
    basename_match = re.search(
        r"[A-Za-z0-9_.@%+()\-]+?\.mp4",
        normalized,
    )
    if basename_match:
        return basename_match.group(0)

    value = re.sub(r"^[^A-Za-z/]*", "", value)
    return value


def printable_ascii_strings(data: bytes, min_length: int = 4) -> list[str]:
    result: list[str] = []
    buffer = bytearray()

    for byte in data:
        if 32 <= byte <= 126:
            buffer.append(byte)
            continue

        if len(buffer) >= min_length:
            result.append(buffer.decode("ascii", errors="ignore"))
        buffer.clear()

    if len(buffer) >= min_length:
        result.append(buffer.decode("ascii", errors="ignore"))

    return result


def detect_mp4_paths_from_strings(data: bytes) -> list[str]:
    paths: list[str] = []

    for item in printable_ascii_strings(data):
        if ".mp4" not in item.lower():
            continue

        clean = clean_detected_path(item)
        if clean.lower().endswith(".mp4"):
            paths.append(clean)

    return unique_preserve_order(paths)



def unique_preserve_order(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = value.strip()
        if not clean or clean in seen:
            continue
        output.append(clean)
        seen.add(clean)
    return output


def inspect_original_theme_metadata(source: Path) -> OriginalThemeMetadata:
    try:
        data = source.expanduser().resolve().read_bytes()
    except OSError:
        return OriginalThemeMetadata(
            remote_video_path=None,
            referenced_video_paths=[],
            graph_markers=[],
            widget_tokens=[],
            is_usbmonitor_binary=False,
        )

    remote_paths = [
        clean_detected_path(decode_binary_string(match.group(0)))
        for match in REMOTE_VIDEO_RE.finditer(data)
    ]
    windows_paths = [
        clean_detected_path(decode_binary_string(match.group(0)))
        for match in WINDOWS_VIDEO_RE.finditer(data)
    ]

    # Fallback: scan all MP4-looking binary strings and then clean them.
    any_mp4_paths = [
        clean_detected_path(decode_binary_string(match.group(0)))
        for match in ANY_MP4_RE.finditer(data)
    ]
    remote_paths.extend(
        path for path in any_mp4_paths
        if path.startswith(("/mnt/SDCARD/video/", "/root/video/"))
    )
    windows_paths.extend(
        path for path in any_mp4_paths
        if re.match(r"^[A-Za-z]:\\\\", path)
    )

    graph_markers = [
        decode_binary_string(match.group(0))
        for match in GRAPH_MARKER_RE.finditer(data)
    ]

    text = data.decode("latin-1", errors="ignore")
    widget_tokens = [
        token for token in KNOWN_WIDGET_TOKENS
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])", text)
    ]

    string_paths = detect_mp4_paths_from_strings(data)

    remote_paths.extend(
        path for path in string_paths
        if path.startswith(("/mnt/SDCARD/video/", "/root/video/"))
    )
    windows_paths.extend(
        path for path in string_paths
        if re.match(r"^[A-Za-z]:[\\\\/]", path)
    )

    referenced_video_paths = unique_preserve_order(
        remote_paths + windows_paths + string_paths
    )
    graph_markers = unique_preserve_order(graph_markers)

    return OriginalThemeMetadata(
        remote_video_path=next(
            (
                path for path in unique_preserve_order(remote_paths + referenced_video_paths)
                if path.startswith(("/mnt/SDCARD/video/", "/root/video/"))
            ),
            None,
        ),
        referenced_video_paths=referenced_video_paths,
        graph_markers=graph_markers,
        widget_tokens=unique_preserve_order(widget_tokens),
        is_usbmonitor_binary=b"UsbMonitorL.GraphItem" in data,
    )


def marker_to_open_theme_hint(marker: str) -> dict[str, str]:
    lower = marker.lower()

    if "cpu temp" in lower:
        return {
            "kind": "stat",
            "target": "STATS.CPU.TEMPERATURE.TEXT",
            "reason": marker,
        }

    if "cpu usage" in lower:
        return {
            "kind": "stat",
            "target": "STATS.CPU.PERCENTAGE.GRAPH",
            "reason": marker,
        }

    if "time" in lower or "hora" in lower:
        return {
            "kind": "stat",
            "target": "STATS.DATE.HOUR.TEXT",
            "reason": marker,
        }

    if lower.startswith("text--"):
        return {
            "kind": "static_text",
            "target": "static_text",
            "reason": marker,
        }

    if lower.startswith("image--"):
        return {
            "kind": "image",
            "target": "static_images",
            "reason": marker,
        }

    return {
        "kind": "unknown",
        "target": "manual_review",
        "reason": marker,
    }


def build_detected_layout_metadata(metadata: OriginalThemeMetadata) -> dict[str, object]:
    return {
        "format": "UsbMonitorL/.NET BinaryFormatter candidate"
        if metadata.is_usbmonitor_binary
        else "unknown",
        "remote_video_path": metadata.remote_video_path,
        "referenced_video_paths": metadata.referenced_video_paths,
        "graph_markers": metadata.graph_markers,
        "widget_tokens": metadata.widget_tokens,
        "open_theme_hints": [
            marker_to_open_theme_hint(marker)
            for marker in metadata.graph_markers
        ],
        "notes": [
            "This is a partial semantic extraction.",
            "Coordinates, font sizes, colors, and alignment still require a binary field parser.",
        ],
    }


def has_marker(metadata: OriginalThemeMetadata, *needles: str) -> bool:
    haystack = " ".join(metadata.graph_markers + metadata.widget_tokens).lower()
    return any(needle.lower() in haystack for needle in needles)


def render_best_effort_static_text(metadata: OriginalThemeMetadata) -> list[str]:
    lines: list[str] = ["static_text:"]

    wrote = False

    if has_marker(metadata, "Text--CPU", "CPULOAD", "Cpu Usage"):
        wrote = True
        lines.extend(
            [
                "  CPU_LABEL:",
                '    TEXT: "CPU"',
                "    X: 207",
                "    Y: 128",
                "    WIDTH: 130",
                "    HEIGHT: 38",
                "    FONT: roboto/Roboto-Black.ttf",
                "    FONT_SIZE: 34",
                "    FONT_COLOR: 255, 48, 0",
                "    BACKGROUND_IMAGE: background.png",
                "    ALIGN: center",
                "    ANCHOR: lt",
            ]
        )

    if has_marker(metadata, "Text--Temp", "CPUTEMP", "Cpu Temp", "Temp"):
        wrote = True
        lines.extend(
            [
                "  TEMP_LABEL:",
                '    TEXT: "Temp"',
                "    X: 226",
                "    Y: 106",
                "    WIDTH: 92",
                "    HEIGHT: 26",
                "    FONT: roboto/Roboto-Black.ttf",
                "    FONT_SIZE: 20",
                "    FONT_COLOR: 255, 48, 0",
                "    BACKGROUND_IMAGE: background.png",
                "    ALIGN: center",
                "    ANCHOR: lt",
            ]
        )

    if has_marker(metadata, "Horas", "Text--Horas"):
        wrote = True
        lines.extend(
            [
                "  HOURS_LABEL:",
                '    TEXT: "Horas"',
                "    X: 187",
                "    Y: 386",
                "    WIDTH: 130",
                "    HEIGHT: 34",
                "    FONT: roboto/Roboto-Black.ttf",
                "    FONT_SIZE: 30",
                "    FONT_COLOR: 255, 48, 0",
                "    BACKGROUND_IMAGE: background.png",
                "    ALIGN: center",
                "    ANCHOR: lt",
            ]
        )

    if not wrote:
        return ["static_text: {}"]

    return lines



def render_best_effort_stats(metadata: OriginalThemeMetadata) -> list[str]:
    if not (
        has_marker(metadata, "Cpu Temp", "CPUTEMP")
        or has_marker(metadata, "Cpu Usage", "CPULOAD")
        or has_marker(metadata, "Time", "TIME", "Horas")
    ):
        return ["STATS: {}"]

    lines: list[str] = ["STATS:"]

    if has_marker(metadata, "Cpu Temp", "CPUTEMP", "Temp"):
        lines.extend(
            [
                "  CPU:",
                "    TEMPERATURE:",
                "      INTERVAL: 5",
                "      TEXT:",
                "        SHOW: true",
                "        SHOW_UNIT: true",
                "        X: 180",
                "        Y: 158",
                "        WIDTH: 180",
                "        HEIGHT: 74",
                "        FONT: roboto/Roboto-Black.ttf",
                "        FONT_SIZE: 64",
                "        FONT_COLOR: 255, 48, 0",
                "        BACKGROUND_IMAGE: background.png",
                "        ALIGN: center",
                "        ANCHOR: lt",
            ]
        )

    if has_marker(metadata, "Cpu Usage", "CPULOAD", "StatuBar"):
        if "  CPU:" not in lines:
            lines.append("  CPU:")
        lines.extend(
            [
                "    PERCENTAGE:",
                "      INTERVAL: 5",
                "      TEXT:",
                "        SHOW: false",
                "        SHOW_UNIT: true",
                "        X: 174",
                "        Y: 360",
                "        FONT: roboto/Roboto-Black.ttf",
                "        FONT_SIZE: 24",
                "        FONT_COLOR: 255, 255, 255",
                "        BACKGROUND_IMAGE: background.png",
                "      GRAPH:",
                "        SHOW: true",
                "        X: 66",
                "        Y: 145",
                "        WIDTH: 32",
                "        HEIGHT: 170",
                "        ORIENTATION: vertical",
                "        MIN_VALUE: 0",
                "        MAX_VALUE: 100",
                "        BAR_COLOR: 255, 178, 0",
                "        BAR_OUTLINE: false",
                "        BACKGROUND_COLOR: 105, 20, 0",
            ]
        )

    if has_marker(metadata, "Time", "TIME", "Horas", "Time_h:m"):
        lines.extend(
            [
                "  DATE:",
                "    INTERVAL: 1",
                "    HOUR:",
                "      TEXT:",
                "        FORMAT: short",
                "        SHOW: true",
                "        X: 240",
                "        Y: 334",
                "        WIDTH: 220",
                "        HEIGHT: 58",
                "        ANCHOR: mm",
                "        FONT: roboto-mono/RobotoMono-Bold.ttf",
                "        FONT_SIZE: 50",
                "        FONT_COLOR: 255, 48, 0",
                "        BACKGROUND_IMAGE: background.png",
            ]
        )

    return lines



def render_detected_dynamic_yaml_comments(metadata: OriginalThemeMetadata) -> list[str]:
    if not metadata.graph_markers and not metadata.widget_tokens:
        return []

    lines = [
        "",
        "# Detected original Windows/.NET theme widgets:",
    ]

    for marker in metadata.graph_markers:
        lines.append(f"# - {marker}")

    for token in metadata.widget_tokens:
        if token not in metadata.graph_markers:
            lines.append(f"# - {token}")

    lines.extend(
        [
            "#",
            "# These markers are not fully converted yet because coordinates,",
            "# fonts, colors, and alignment need the BinaryFormatter field parser.",
        ]
    )
    return lines


def render_theme_yaml(
    *,
    theme_name: str,
    background_name: str | None,
    overlay_name: str | None,
    video_name: str | None,
    remote_video_path: str | None = None,
    original_metadata: OriginalThemeMetadata | None = None,
) -> str:
    lines: list[str] = []
    lines.append('author: "Converted from original Turing theme"')
    lines.append("")
    lines.append("display:")
    lines.append('  DISPLAY_SIZE: 2.1"')
    lines.append("  DISPLAY_ORIENTATION: landscape")
    lines.append("  DISPLAY_RGB_LED: 236, 214, 180")
    lines.append("")
    effective_video_path = (
        remote_video_path
        or (f"/mnt/SDCARD/video/{video_name}" if video_name else None)
    )
    lines.append("video:")
    lines.append(f"  ENABLED: {'true' if effective_video_path else 'false'}")
    lines.append("  MODE: native")
    lines.append(f"  PATH: {effective_video_path or f'/mnt/SDCARD/video/{theme_name}.mp4'}")
    lines.append("  OVERLAY: true")
    lines.append("")

    if background_name or overlay_name:
        lines.append("static_images:")

        if background_name:
            lines.append("  BACKGROUND:")
            lines.append(f"    PATH: {background_name}")
            lines.append("    X: 0")
            lines.append("    Y: 0")
            lines.append("    WIDTH: 480")
            lines.append("    HEIGHT: 480")

        if overlay_name and overlay_name != background_name:
            lines.append("  UI_OVERLAY:")
            lines.append(f"    PATH: {overlay_name}")
            lines.append("    X: 0")
            lines.append("    Y: 0")
            lines.append("    WIDTH: 480")
            lines.append("    HEIGHT: 480")
    else:
        lines.append("static_images: {}")

    lines.append("")
    lines.append("# This is a best-effort imported theme.")
    lines.append("# Dynamic widgets below are approximate until the BinaryFormatter")
    lines.append("# field parser recovers exact coordinates, fonts, colors, and alignment.")

    if original_metadata is not None:
        lines.extend(render_best_effort_static_text(original_metadata))
    else:
        lines.append("static_text: {}")

    lines.append("")

    if original_metadata is not None:
        lines.extend(render_best_effort_stats(original_metadata))
    else:
        lines.append("STATS: {}")

    if original_metadata is not None:
        lines.extend(render_detected_dynamic_yaml_comments(original_metadata))
    lines.append("")
    return "\n".join(lines)


def write_readme(output: Path, theme_name: str) -> None:
    (output / "README.md").write_text(
        f"""# {theme_name}

Best-effort conversion from an original Turing/Windows theme package.

This folder is intentionally open and editable:

- `theme.yaml` is the generated open theme.
- `preview.png` is the best detected preview/background.
- `original-assets/` keeps the extracted source media for audit/manual editing.
- `conversion-manifest.json` records detected assets and hashes.
- `detected-layout-candidates.json` records original widgets detected in the
  Windows/.NET theme metadata.

The converter does not promise pixel-perfect layout reconstruction yet. Use the
Theme Editor to place dynamic stats, labels, graphs, and final overlays.
""",
        encoding="utf-8",
    )


def convert_theme(source: Path, output_root: Path, theme_name: str, overwrite: bool) -> Path:
    slug = slugify(theme_name)
    output = output_root / slug
    original_metadata = inspect_original_theme_metadata(source)

    if output.exists():
        if not overwrite:
            raise FileExistsError(f"Output theme already exists: {output}")
        shutil.rmtree(output)

    output.mkdir(parents=True)

    with tempfile.TemporaryDirectory(prefix="turtheme-import-") as temporary:
        source_tree = prepare_source_tree(source, Path(temporary))
        assets = collect_assets(source_tree)

        if not assets:
            raise RuntimeError("No supported image/video assets were found.")

        raw_records = copy_raw_assets(assets, output)

        images = [asset for asset in assets if asset.kind == "image"]
        videos = [asset for asset in assets if asset.kind == "video"]

        preview = (
            choose_rendered_preview(images)
            or choose_asset(
                images,
                ("preview", "example", "windows_preview", "screenshot"),
            )
            or choose_largest_image(images)
        )
        background = (
            choose_clean_background(images)
            or choose_asset(
                images,
                ("background", "bg", "wallpaper", "full"),
            )
            or preview
            or choose_largest_image(images)
        )
        overlay = None

        preview_name = None
        background_name = None
        overlay_name = None
        video_name = None

        if background:
            background_name = canonical_copy(background, output, "background")
            preview_name = canonical_copy(preview or background, output, "preview")

        if overlay and overlay != background:
            overlay_name = canonical_copy(overlay, output, "ui_overlay")

        if videos:
            video_asset = videos[0]
            video_name = slug + video_asset.source.suffix.lower()
            shutil.copy2(video_asset.source, output / video_name)

        (output / "theme.yaml").write_text(
            render_theme_yaml(
                theme_name=slug,
                background_name=background_name,
                overlay_name=overlay_name,
                video_name=video_name,
                remote_video_path=original_metadata.remote_video_path,
                original_metadata=original_metadata,
            ),
            encoding="utf-8",
        )

        detected_layout = build_detected_layout_metadata(original_metadata)
        (output / "detected-layout-candidates.json").write_text(
            json.dumps(
                detected_layout,
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )

        manifest = {
            "version": 1,
            "source": str(source.expanduser().resolve()),
            "theme_name": slug,
            "conversion": "best-effort-open-theme",
            "selected": {
                "preview": preview_name,
                "background": background_name,
                "overlay": overlay_name,
                "video": video_name,
                "remote_video_path": original_metadata.remote_video_path,
            },
            "detected_layout": detected_layout,
            "assets": raw_records,
        }
        (output / "conversion-manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        write_readme(output, slug)

    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import original Turing theme packages into open YAML themes."
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Original .turtheme/.zip file, extracted folder, or media file.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("res/themes"),
        help="Directory where the converted theme folder will be created.",
    )
    parser.add_argument(
        "--name",
        help="Converted theme folder name. Defaults to the source filename.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing converted theme folder.",
    )
    args = parser.parse_args()

    theme_name = args.name or args.source.stem
    output = convert_theme(
        source=args.source,
        output_root=args.output_root,
        theme_name=theme_name,
        overwrite=args.overwrite,
    )
    print(f"Converted theme written to: {output}")
    print(f"Open theme YAML: {output / 'theme.yaml'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
