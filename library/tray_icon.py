# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate one grayscale tray icon for pystray and StatusNotifierItem."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from PIL import Image, ImageOps


TRAY_ICON_NAME = "turing-smart-screen-tray-grayscale"
DEFAULT_SIZES = (16, 22, 32, 64)
_SOURCE_RELATIVE = Path("res/icons/monitor-icon-17865/64.png")


def source_icon_path(project_root: Path) -> Path:
    return Path(project_root).resolve() / _SOURCE_RELATIVE


def _resampling_filter():
    resampling = getattr(Image, "Resampling", Image)
    return resampling.LANCZOS


def grayscale_image(source: Path, size: int = 64) -> Image.Image:
    """Return an RGBA grayscale copy while preserving source transparency."""
    if size <= 0:
        raise ValueError("Tray icon size must be greater than zero")

    source = Path(source)
    if not source.is_file():
        raise FileNotFoundError(source)

    with Image.open(source) as opened:
        rgba = opened.convert("RGBA")

    luminance = ImageOps.grayscale(rgba)
    alpha = rgba.getchannel("A")
    result = Image.merge("RGBA", (luminance, luminance, luminance, alpha))
    if result.size != (size, size):
        result = result.resize((size, size), _resampling_filter())
    return result


def load_pystray_image(project_root: Path, size: int = 64) -> Image.Image:
    """Load the monochrome Pillow image consumed by ``pystray.Icon``."""
    return grayscale_image(source_icon_path(project_root), size=size)


def _cache_root() -> Path:
    override = os.environ.get("XDG_CACHE_HOME", "").strip()
    base = Path(override).expanduser() if override else Path.home() / ".cache"
    return base / "turing-smart-screen" / "tray-icons"


def _write_png_atomic(image: Image.Image, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(
        f".{destination.name}.{os.getpid()}.tmp"
    )
    image.save(temporary, format="PNG")
    os.replace(temporary, destination)


def _write_text_atomic(destination: Path, content: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(
        f".{destination.name}.{os.getpid()}.tmp"
    )
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, destination)


def _normalized_sizes(sizes: Iterable[int]) -> Tuple[int, ...]:
    normalized = sorted({int(size) for size in sizes if int(size) > 0})
    if not normalized:
        raise ValueError("At least one positive tray icon size is required")
    return tuple(normalized)


@lru_cache(maxsize=8)
def ensure_status_icon_theme(
    project_root: str,
    sizes: Sequence[int] = DEFAULT_SIZES,
) -> Path:
    """Create a tiny cached hicolor theme for SNI hosts that prefer IconName."""
    root = Path(project_root).resolve()
    source = source_icon_path(root)
    normalized_sizes = _normalized_sizes(sizes)
    theme_root = _cache_root()
    hicolor_root = theme_root / "hicolor"
    source_mtime = source.stat().st_mtime_ns

    directories = []
    for size in normalized_sizes:
        relative_directory = Path(f"{size}x{size}") / "status"
        directories.append(relative_directory.as_posix())
        destination = hicolor_root / relative_directory / f"{TRAY_ICON_NAME}.png"
        regenerate = True
        try:
            regenerate = destination.stat().st_mtime_ns < source_mtime
        except OSError:
            pass
        if regenerate:
            _write_png_atomic(grayscale_image(source, size), destination)

    directory_list = ",".join(directories)
    sections = [
        "[Icon Theme]",
        "Name=Turing Smart Screen Tray",
        "Comment=Generated grayscale status icon",
        f"Directories={directory_list}",
        "",
    ]
    for size, directory in zip(normalized_sizes, directories):
        sections.extend(
            [
                f"[{directory}]",
                f"Size={size}",
                "Context=Status",
                "Type=Fixed",
                "",
            ]
        )
    _write_text_atomic(hicolor_root / "index.theme", "\n".join(sections))
    return theme_root


def _rgba_to_argb_bytes(image: Image.Image) -> bytes:
    rgba = image.convert("RGBA").tobytes()
    argb = bytearray(len(rgba))
    for offset in range(0, len(rgba), 4):
        red, green, blue, alpha = rgba[offset:offset + 4]
        argb[offset:offset + 4] = bytes((alpha, red, green, blue))
    return bytes(argb)


def status_notifier_pixmaps(
    project_root: Path,
    sizes: Sequence[int] = DEFAULT_SIZES,
) -> List[Tuple[int, int, bytes]]:
    """Return SNI ``a(iiay)`` pixmaps in network-order ARGB format."""
    source = source_icon_path(project_root)
    return [
        (size, size, _rgba_to_argb_bytes(grayscale_image(source, size)))
        for size in _normalized_sizes(sizes)
    ]
