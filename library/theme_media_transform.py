# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure static-image transform helpers for the theme editor."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from PIL import Image, ImageOps

ROTATION_0 = 0
ROTATION_90 = 90
ROTATION_180 = 180
ROTATION_270 = 270

ROTATIONS = (
    ROTATION_0,
    ROTATION_90,
    ROTATION_180,
    ROTATION_270,
)

GENERATED_MEDIA_DIR = "generated-media"
TRANSFORM_MANIFEST = "transform-manifest.json"
TRANSFORM_MANIFEST_VERSION = 1


class ThemeMediaTransformError(ValueError):
    """Raised when static image transform inputs are invalid."""


@dataclass(frozen=True)
class ImageTransformSettings:
    """Validated transform/crop controls."""

    rotation: int = ROTATION_0
    flip_horizontal: bool = False
    flip_vertical: bool = False
    crop_box: tuple[int, int, int, int] | None = None

    def __post_init__(self) -> None:
        rotation = int(self.rotation)
        if rotation not in ROTATIONS:
            raise ThemeMediaTransformError(f"Unsupported rotation: {self.rotation}")
        crop_box = self.crop_box
        if crop_box is not None:
            if len(crop_box) != 4:
                raise ThemeMediaTransformError("Crop box must have 4 values")
            x, y, width, height = (int(value) for value in crop_box)
            if x < 0 or y < 0:
                raise ThemeMediaTransformError("Crop origin cannot be negative")
            if width <= 0 or height <= 0:
                raise ThemeMediaTransformError("Crop dimensions must be positive")
            crop_box = (x, y, width, height)
        object.__setattr__(self, "rotation", rotation)
        object.__setattr__(self, "flip_horizontal", bool(self.flip_horizontal))
        object.__setattr__(self, "flip_vertical", bool(self.flip_vertical))
        object.__setattr__(self, "crop_box", crop_box)


@dataclass(frozen=True)
class TransformSource:
    source_path: Path
    source_reference: str
    current_asset_path: Path
    current_asset_reference: str
    current_settings: ImageTransformSettings
    is_managed_asset: bool


@dataclass(frozen=True)
class PreparedTransformAsset:
    source_path: Path
    output_path: Path
    output_reference: str
    settings: ImageTransformSettings
    source_size: tuple[int, int]
    output_size: tuple[int, int]
    created: bool


def is_identity_transform(settings: ImageTransformSettings) -> bool:
    """Return True when no transform is requested."""
    settings = ImageTransformSettings(
        settings.rotation,
        settings.flip_horizontal,
        settings.flip_vertical,
        settings.crop_box,
    )
    return (
        settings.rotation == ROTATION_0
        and not settings.flip_horizontal
        and not settings.flip_vertical
        and settings.crop_box is None
    )


def uncropped_transformed_dimensions(
    source_size: tuple[int, int],
    settings: ImageTransformSettings,
) -> tuple[int, int]:
    """Return dimensions after rotation/mirror, before crop."""
    width, height = int(source_size[0]), int(source_size[1])
    if width <= 0 or height <= 0:
        raise ThemeMediaTransformError("Image dimensions must be positive")
    if settings.rotation in (ROTATION_90, ROTATION_270):
        return height, width
    return width, height


def validate_crop_box(
    image_size: tuple[int, int],
    crop_box: tuple[int, int, int, int] | None,
) -> tuple[int, int, int, int] | None:
    """Validate a crop box in already-transformed image coordinates."""
    if crop_box is None:
        return None
    settings = ImageTransformSettings(crop_box=crop_box)
    x, y, width, height = settings.crop_box or (0, 0, 0, 0)
    image_width, image_height = int(image_size[0]), int(image_size[1])
    if image_width <= 0 or image_height <= 0:
        raise ThemeMediaTransformError("Image dimensions must be positive")
    if x + width > image_width or y + height > image_height:
        raise ThemeMediaTransformError("Crop box exceeds transformed image bounds")
    return (x, y, width, height)


def transformed_dimensions(
    source_size: tuple[int, int],
    settings: ImageTransformSettings,
) -> tuple[int, int]:
    """Return dimensions after rotation/mirror/crop."""
    size = uncropped_transformed_dimensions(source_size, settings)
    crop_box = validate_crop_box(size, settings.crop_box)
    if crop_box is None:
        return size
    return crop_box[2], crop_box[3]


def transform_pillow_image(
    image: Image.Image,
    settings: ImageTransformSettings,
) -> Image.Image:
    """Apply EXIF normalization, clockwise rotation, mirrors, then crop."""
    settings = ImageTransformSettings(
        settings.rotation,
        settings.flip_horizontal,
        settings.flip_vertical,
        settings.crop_box,
    )
    if image.width <= 0 or image.height <= 0:
        raise ThemeMediaTransformError("Image dimensions must be positive")

    result = ImageOps.exif_transpose(image).convert("RGBA")
    if settings.rotation == ROTATION_90:
        result = result.transpose(Image.Transpose.ROTATE_270)
    elif settings.rotation == ROTATION_180:
        result = result.transpose(Image.Transpose.ROTATE_180)
    elif settings.rotation == ROTATION_270:
        result = result.transpose(Image.Transpose.ROTATE_90)

    if settings.flip_horizontal:
        result = result.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if settings.flip_vertical:
        result = result.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    crop_box = validate_crop_box(result.size, settings.crop_box)
    if crop_box is not None:
        x, y, width, height = crop_box
        result = result.crop((x, y, x + width, y + height))
    return result


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_stem(value: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    return stem or "image"


def _settings_token(settings: ImageTransformSettings) -> str:
    token = f"r{settings.rotation}-h{int(settings.flip_horizontal)}-v{int(settings.flip_vertical)}"
    if settings.crop_box is not None:
        x, y, width, height = settings.crop_box
        token += f"-c{x}-{y}-{width}-{height}"
    return token


def derived_asset_name(source_path: str | Path, settings: ImageTransformSettings) -> str:
    """Return a deterministic safe PNG name for a source/settings pair."""
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise ThemeMediaTransformError(f"Source image is not available: {source}")
    settings = ImageTransformSettings(
        settings.rotation,
        settings.flip_horizontal,
        settings.flip_vertical,
        settings.crop_box,
    )
    source_hash = _sha256_file(source)
    config_hash = hashlib.sha256(
        json.dumps(
            {
                "source_sha256": source_hash,
                "rotation": settings.rotation,
                "flip_horizontal": settings.flip_horizontal,
                "flip_vertical": settings.flip_vertical,
                "crop_box": settings.crop_box,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:12]
    return f"{_safe_stem(source.stem)}--{_settings_token(settings)}--{config_hash}.png"


def _theme_dir(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _manifest_path(theme_dir: str | Path) -> Path:
    return _theme_dir(theme_dir) / GENERATED_MEDIA_DIR / TRANSFORM_MANIFEST


def theme_path_reference(theme_dir: str | Path, path: str | Path) -> str:
    """Return a safe theme-relative POSIX reference or an absolute path."""
    root = _theme_dir(theme_dir)
    target = Path(path).expanduser().resolve()
    try:
        relative = target.relative_to(root)
    except ValueError:
        return str(target)
    if any(part == ".." for part in relative.parts):
        raise ThemeMediaTransformError("Path traversal is not allowed")
    return relative.as_posix()


def _resolve_reference(theme_dir: str | Path, reference: str) -> Path:
    raw = str(reference or "").strip()
    if not raw:
        raise ThemeMediaTransformError("Image reference is required")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        if any(part == ".." for part in path.parts):
            raise ThemeMediaTransformError("Path traversal is not allowed")
        path = _theme_dir(theme_dir) / path
    return path.resolve()


def _validate_output_reference(theme_dir: str | Path, reference: str) -> Path:
    path = Path(str(reference))
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise ThemeMediaTransformError("Managed asset reference must stay inside the theme")
    if len(path.parts) < 2 or path.parts[0] != GENERATED_MEDIA_DIR:
        raise ThemeMediaTransformError("Managed asset must be in generated-media")
    resolved = (_theme_dir(theme_dir) / path).resolve()
    generated_root = (_theme_dir(theme_dir) / GENERATED_MEDIA_DIR).resolve()
    try:
        resolved.relative_to(generated_root)
    except ValueError as exc:
        raise ThemeMediaTransformError("Managed asset escapes generated-media") from exc
    return resolved


def load_transform_manifest(theme_dir: str | Path) -> dict[str, Any]:
    """Load and validate the transform manifest, returning a new dict."""
    path = _manifest_path(theme_dir)
    if not path.exists():
        return {"version": TRANSFORM_MANIFEST_VERSION, "assets": {}}
    try:
        with path.open("r", encoding="utf-8") as stream:
            manifest = json.load(stream)
    except json.JSONDecodeError as exc:
        raise ThemeMediaTransformError(f"Transform manifest is invalid: {path}") from exc
    if not isinstance(manifest, dict):
        raise ThemeMediaTransformError("Transform manifest must be a mapping")
    if manifest.get("version") != TRANSFORM_MANIFEST_VERSION:
        raise ThemeMediaTransformError("Unsupported transform manifest version")
    assets = manifest.get("assets")
    if not isinstance(assets, dict):
        raise ThemeMediaTransformError("Transform manifest assets must be a mapping")
    for reference, entry in assets.items():
        _validate_output_reference(theme_dir, reference)
        if not isinstance(entry, dict):
            raise ThemeMediaTransformError("Transform manifest entry must be a mapping")
        _settings_from_entry(entry)
        source_reference = Path(str(entry.get("source_reference") or ""))
        if not source_reference.is_absolute() and any(
            part == ".." for part in source_reference.parts
        ):
            raise ThemeMediaTransformError("Source reference cannot contain path traversal")
    return {"version": TRANSFORM_MANIFEST_VERSION, "assets": dict(assets)}


def save_transform_manifest_atomic(theme_dir: str | Path, manifest: Mapping[str, Any]) -> Path:
    """Atomically save a validated transform manifest."""
    if manifest.get("version") != TRANSFORM_MANIFEST_VERSION:
        raise ThemeMediaTransformError("Unsupported transform manifest version")
    assets = manifest.get("assets")
    if not isinstance(assets, Mapping):
        raise ThemeMediaTransformError("Transform manifest assets must be a mapping")
    for reference in assets:
        _validate_output_reference(theme_dir, reference)

    path = _manifest_path(theme_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{TRANSFORM_MANIFEST}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(
                {"version": TRANSFORM_MANIFEST_VERSION, "assets": dict(assets)},
                stream,
                indent=2,
                sort_keys=True,
            )
            stream.write("\n")
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return path


def register_transform_asset(
    theme_dir: str | Path,
    output_reference: str,
    source_reference: str,
    source_sha256: str,
    settings: ImageTransformSettings,
) -> None:
    """Register a generated transform asset in the manifest."""
    _validate_output_reference(theme_dir, output_reference)
    source_path = Path(str(source_reference))
    if not source_path.is_absolute() and any(part == ".." for part in source_path.parts):
        raise ThemeMediaTransformError("Source reference cannot contain path traversal")
    settings = ImageTransformSettings(
        settings.rotation,
        settings.flip_horizontal,
        settings.flip_vertical,
        settings.crop_box,
    )
    entry = {
        "source_reference": source_reference,
        "source_sha256": source_sha256,
        "rotation": settings.rotation,
        "flip_horizontal": settings.flip_horizontal,
        "flip_vertical": settings.flip_vertical,
    }
    if settings.crop_box is not None:
        x, y, width, height = settings.crop_box
        entry["crop"] = {
            "x": x,
            "y": y,
            "width": width,
            "height": height,
        }
    manifest = load_transform_manifest(theme_dir)
    manifest["assets"][output_reference] = entry
    save_transform_manifest_atomic(theme_dir, manifest)


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


def _is_generated_reference(reference: str) -> bool:
    path = Path(str(reference))
    return not path.is_absolute() and len(path.parts) >= 2 and path.parts[0] == GENERATED_MEDIA_DIR


def resolve_transform_source(
    theme_dir: str | Path,
    current_reference: str,
) -> TransformSource:
    """Resolve a YAML PATH to the original source and current transform state."""
    current_asset_path = _resolve_reference(theme_dir, current_reference)
    current_asset_reference = theme_path_reference(theme_dir, current_asset_path)
    if not current_asset_path.is_file():
        raise ThemeMediaTransformError(f"Current image asset is missing: {current_asset_path}")

    if not _is_generated_reference(current_asset_reference):
        return TransformSource(
            source_path=current_asset_path,
            source_reference=current_asset_reference,
            current_asset_path=current_asset_path,
            current_asset_reference=current_asset_reference,
            current_settings=ImageTransformSettings(),
            is_managed_asset=False,
        )

    manifest = load_transform_manifest(theme_dir)
    entry = manifest["assets"].get(current_asset_reference)
    if entry is None:
        raise ThemeMediaTransformError("Generated media asset is not registered in the transform manifest")
    source_reference = str(entry.get("source_reference") or "")
    source_path = _resolve_reference(theme_dir, source_reference)
    if not source_path.is_file():
        raise ThemeMediaTransformError(f"Original source image is missing: {source_path}")
    source_hash = _sha256_file(source_path)
    if source_hash != entry.get("source_sha256"):
        raise ThemeMediaTransformError("Original source image no longer matches the transform manifest")
    return TransformSource(
        source_path=source_path,
        source_reference=source_reference,
        current_asset_path=current_asset_path,
        current_asset_reference=current_asset_reference,
        current_settings=_settings_from_entry(entry),
        is_managed_asset=True,
    )


def _image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return int(image.width), int(image.height)


def _write_transformed_png_atomic(source_path: Path, output_path: Path, settings: ImageTransformSettings) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{output_path.stem}.",
        suffix=".tmp.png",
        dir=str(output_path.parent),
    )
    os.close(fd)
    try:
        with Image.open(source_path) as source:
            transformed = transform_pillow_image(source, settings)
            transformed.save(temp_name, "PNG")
        with Image.open(temp_name) as check:
            check.verify()
        os.replace(temp_name, output_path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _manifest_entry_matches(
    entry: Mapping[str, Any],
    source_reference: str,
    source_sha256: str,
    settings: ImageTransformSettings,
) -> bool:
    try:
        entry_settings = _settings_from_entry(entry)
    except Exception:
        return False
    return (
        entry.get("source_reference") == source_reference
        and entry.get("source_sha256") == source_sha256
        and entry_settings == settings
    )


def prepare_transform_asset(
    theme_dir: str | Path,
    current_reference: str,
    settings: ImageTransformSettings,
) -> PreparedTransformAsset:
    """Prepare or reuse a managed transform asset without mutating theme YAML."""
    settings = ImageTransformSettings(
        settings.rotation,
        settings.flip_horizontal,
        settings.flip_vertical,
        settings.crop_box,
    )
    source = resolve_transform_source(theme_dir, current_reference)
    source_size = _image_size(source.source_path)
    if is_identity_transform(settings):
        return PreparedTransformAsset(
            source_path=source.source_path,
            output_path=source.source_path,
            output_reference=source.source_reference,
            settings=settings,
            source_size=source_size,
            output_size=source_size,
            created=False,
        )

    source_hash = _sha256_file(source.source_path)
    output_reference = (
        Path(GENERATED_MEDIA_DIR) / derived_asset_name(source.source_path, settings)
    ).as_posix()
    output_path = _validate_output_reference(theme_dir, output_reference)
    manifest = load_transform_manifest(theme_dir)
    entry = manifest["assets"].get(output_reference)
    if output_path.exists():
        if entry is None:
            raise ThemeMediaTransformError("Refusing to overwrite unregistered generated media")
        if _manifest_entry_matches(entry, source.source_reference, source_hash, settings):
            try:
                output_size = _image_size(output_path)
            except Exception as exc:
                raise ThemeMediaTransformError("Registered generated media is not a valid image") from exc
            return PreparedTransformAsset(
                source_path=source.source_path,
                output_path=output_path,
                output_reference=output_reference,
                settings=settings,
                source_size=source_size,
                output_size=output_size,
                created=False,
            )
        raise ThemeMediaTransformError("Generated media name is already registered for a different transform")

    _write_transformed_png_atomic(source.source_path, output_path, settings)
    register_transform_asset(
        theme_dir,
        output_reference,
        source.source_reference,
        source_hash,
        settings,
    )
    return PreparedTransformAsset(
        source_path=source.source_path,
        output_path=output_path,
        output_reference=output_reference,
        settings=settings,
        source_size=source_size,
        output_size=_image_size(output_path),
        created=True,
    )


def render_transform_preview_asset(
    source_path: str | Path,
    output_path: str | Path,
    settings: ImageTransformSettings,
) -> Path:
    """Render a temporary transformed PNG without writing manifest/theme files."""
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise ThemeMediaTransformError(f"Source image is not available: {source}")
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        transformed = transform_pillow_image(image, settings)
        transformed.save(output, "PNG")
    return output
