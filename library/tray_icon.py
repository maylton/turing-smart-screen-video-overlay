# SPDX-License-Identifier: GPL-3.0-or-later
"""Render color and symbolic tray icons for pystray and StatusNotifierItem."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from PIL import Image

from library.tray_icon_preferences import (
    MODE_COLOR,
    MODE_DARK_THEME,
    MODE_LIGHT_THEME,
    load_tray_icon_mode,
    resolve_tray_icon_variant,
)


TRAY_ICON_NAME = "turing-smart-screen-tray-symbolic"
DEFAULT_SIZES = (16, 22, 32, 64)
_SOURCE_RELATIVE = Path("res/icons/turing-screen-overlay.png")
_DEDICATED_TRAY_ARTWORK = "turing-screen-overlay.png"

# Tuned against Caelestia's Material tray palette. The dark-theme variant is
# intentionally not pure white, so it visually matches the other symbolic
# icons instead of drawing too much attention.
DARK_THEME_TINT = (216, 220, 226)  # #D8DCE2
LIGHT_THEME_TINT = (75, 81, 89)  # #4B5159
DARK_THEME_OPACITY = 0.92
LIGHT_THEME_OPACITY = 0.88


def source_icon_path(project_root: Path) -> Path:
    return Path(project_root).resolve() / _SOURCE_RELATIVE


def _resampling_filter():
    resampling = getattr(Image, "Resampling", Image)
    return resampling.LANCZOS


def _load_rgba(source: Path, size: int) -> Image.Image:
    if size <= 0:
        raise ValueError("Tray icon size must be greater than zero")

    source = Path(source)
    if not source.is_file():
        raise FileNotFoundError(source)

    with Image.open(source) as opened:
        image = opened.convert("RGBA")

    if image.size != (size, size):
        image = image.resize((size, size), _resampling_filter())
    return image


def _scaled_alpha(alpha: Image.Image, opacity: float) -> Image.Image:
    bounded = max(0.0, min(1.0, float(opacity)))
    return alpha.point(lambda value: int(round(value * bounded)))


def symbolic_image(
    source: Path,
    *,
    tint: Tuple[int, int, int],
    opacity: float,
    size: int = 64,
) -> Image.Image:
    """Return a flat symbolic RGBA icon while preserving source transparency."""
    rgba = _load_rgba(source, size)
    red, green, blue = (max(0, min(255, int(value))) for value in tint)
    result = Image.new("RGBA", rgba.size, (red, green, blue, 0))
    result.putalpha(_scaled_alpha(rgba.getchannel("A"), opacity))
    return result


def tray_icon_image(source: Path, variant: str, size: int = 64) -> Image.Image:
    """Render the dedicated tray artwork or a legacy symbolic variant."""
    # The dedicated tray asset is already a purpose-built two-tone glyph.
    # Recoloring it as a single alpha mask would erase the pulse line, so keep
    # its authored black/white contrast for every tray appearance mode.
    if Path(source).name == _DEDICATED_TRAY_ARTWORK:
        return _load_rgba(source, size)

    if variant == MODE_COLOR:
        return _load_rgba(source, size)
    if variant == MODE_LIGHT_THEME:
        return symbolic_image(
            source,
            tint=LIGHT_THEME_TINT,
            opacity=LIGHT_THEME_OPACITY,
            size=size,
        )
    return symbolic_image(
        source,
        tint=DARK_THEME_TINT,
        opacity=DARK_THEME_OPACITY,
        size=size,
    )


def grayscale_image(source: Path, size: int = 64) -> Image.Image:
    """Backward-compatible alias for the dark-panel symbolic variant."""
    return tray_icon_image(source, MODE_DARK_THEME, size=size)


def load_pystray_image(project_root: Path, size: int = 64) -> Image.Image:
    """Load the currently selected image consumed by ``pystray.Icon``."""
    variant = resolve_tray_icon_variant(load_tray_icon_mode())
    return tray_icon_image(source_icon_path(project_root), variant, size=size)


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


@lru_cache(maxsize=16)
def ensure_status_icon_theme(
    project_root: str,
    sizes: Sequence[int] = DEFAULT_SIZES,
    variant: str = MODE_DARK_THEME,
) -> Path:
    """Create a cached hicolor theme for hosts that request an icon name."""
    root = Path(project_root).resolve()
    source = source_icon_path(root)
    normalized_sizes = _normalized_sizes(sizes)
    theme_root = _cache_root() / variant
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
            _write_png_atomic(tray_icon_image(source, variant, size), destination)

    directory_list = ",".join(directories)
    sections = [
        "[Icon Theme]",
        "Name=Turing Smart Screen Tray",
        "Comment=Generated tray status icon",
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
    variant: str = MODE_DARK_THEME,
) -> List[Tuple[int, int, bytes]]:
    """Return SNI ``a(iiay)`` pixmaps in network-order ARGB format."""
    source = source_icon_path(project_root)
    return [
        (
            size,
            size,
            _rgba_to_argb_bytes(tray_icon_image(source, variant, size)),
        )
        for size in _normalized_sizes(sizes)
    ]
