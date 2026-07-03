from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from library.theme_media_layout import (
    MODE_CUSTOM,
    MODE_FIT,
    MODE_ORIGINAL,
    ImageLayoutSettings,
    compute_image_layout,
)
from library.theme_media_transform import (
    GENERATED_MEDIA_DIR,
    TRANSFORM_MANIFEST,
    TRANSFORM_MANIFEST_VERSION,
    ImageTransformSettings,
    ThemeMediaTransformError,
    derived_asset_name,
    is_identity_transform,
    load_transform_manifest,
    prepare_transform_asset,
    register_transform_asset,
    render_transform_preview_asset,
    resolve_transform_source,
    save_transform_manifest_atomic,
    theme_path_reference,
    transform_pillow_image,
    transformed_dimensions,
    uncropped_transformed_dimensions,
    validate_crop_box,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_pixels(path: Path) -> Path:
    image = Image.new("RGBA", (2, 3))
    pixels = image.load()
    colors = {
        (0, 0): (255, 0, 0, 255),
        (1, 0): (0, 255, 0, 255),
        (0, 1): (0, 0, 255, 255),
        (1, 1): (255, 255, 0, 255),
        (0, 2): (255, 0, 255, 128),
        (1, 2): (0, 255, 255, 255),
    }
    for point, color in colors.items():
        pixels[point] = color
    image.save(path)
    return path


class ThemeMediaTransformTests(unittest.TestCase):
    def assertPixelMap(self, image, expected):
        for point, color in expected.items():
            self.assertEqual(image.getpixel(point), color)

    def test_identity_settings(self):
        self.assertTrue(is_identity_transform(ImageTransformSettings()))

    def test_invalid_rotation(self):
        with self.assertRaises(ThemeMediaTransformError):
            ImageTransformSettings(rotation=45)

    def test_invalid_crop_box(self):
        with self.assertRaises(ThemeMediaTransformError):
            ImageTransformSettings(crop_box=(0, 0, 0, 10))
        with self.assertRaises(ThemeMediaTransformError):
            ImageTransformSettings(crop_box=(-1, 0, 10, 10))

    def test_crop_bounds_validation(self):
        self.assertEqual(validate_crop_box((10, 20), (2, 3, 4, 5)), (2, 3, 4, 5))
        with self.assertRaises(ThemeMediaTransformError):
            validate_crop_box((10, 20), (8, 0, 4, 5))

    def test_dimensions_0(self):
        self.assertEqual(transformed_dimensions((10, 20), ImageTransformSettings()), (10, 20))

    def test_dimensions_90(self):
        self.assertEqual(transformed_dimensions((10, 20), ImageTransformSettings(90)), (20, 10))

    def test_uncropped_dimensions_ignore_crop(self):
        settings = ImageTransformSettings(90, crop_box=(2, 1, 8, 6))
        self.assertEqual(uncropped_transformed_dimensions((10, 20), settings), (20, 10))
        self.assertEqual(transformed_dimensions((10, 20), settings), (8, 6))

    def test_dimensions_180(self):
        self.assertEqual(transformed_dimensions((10, 20), ImageTransformSettings(180)), (10, 20))

    def test_dimensions_270(self):
        self.assertEqual(transformed_dimensions((10, 20), ImageTransformSettings(270)), (20, 10))

    def test_flip_does_not_change_dimensions(self):
        settings = ImageTransformSettings(0, True, True)
        self.assertEqual(transformed_dimensions((10, 20), settings), (10, 20))

    def test_rotate_90_clockwise_pixels(self):
        with tempfile.TemporaryDirectory() as directory:
            source = save_pixels(Path(directory) / "source.png")
            with Image.open(source) as image:
                result = transform_pillow_image(image, ImageTransformSettings(90))
            self.assertEqual(result.size, (3, 2))
            self.assertPixelMap(
                result,
                {
                    (0, 0): (255, 0, 255, 128),
                    (2, 0): (255, 0, 0, 255),
                    (0, 1): (0, 255, 255, 255),
                    (2, 1): (0, 255, 0, 255),
                },
            )

    def test_rotate_180_pixels(self):
        with tempfile.TemporaryDirectory() as directory:
            source = save_pixels(Path(directory) / "source.png")
            with Image.open(source) as image:
                result = transform_pillow_image(image, ImageTransformSettings(180))
            self.assertEqual(result.getpixel((0, 0)), (0, 255, 255, 255))
            self.assertEqual(result.getpixel((1, 2)), (255, 0, 0, 255))

    def test_rotate_270_clockwise_pixels(self):
        with tempfile.TemporaryDirectory() as directory:
            source = save_pixels(Path(directory) / "source.png")
            with Image.open(source) as image:
                result = transform_pillow_image(image, ImageTransformSettings(270))
            self.assertEqual(result.size, (3, 2))
            self.assertEqual(result.getpixel((0, 0)), (0, 255, 0, 255))
            self.assertEqual(result.getpixel((2, 1)), (255, 0, 255, 128))

    def test_flip_horizontal_pixels(self):
        with tempfile.TemporaryDirectory() as directory:
            source = save_pixels(Path(directory) / "source.png")
            with Image.open(source) as image:
                result = transform_pillow_image(image, ImageTransformSettings(0, True, False))
            self.assertEqual(result.getpixel((0, 0)), (0, 255, 0, 255))
            self.assertEqual(result.getpixel((1, 0)), (255, 0, 0, 255))

    def test_flip_vertical_pixels(self):
        with tempfile.TemporaryDirectory() as directory:
            source = save_pixels(Path(directory) / "source.png")
            with Image.open(source) as image:
                result = transform_pillow_image(image, ImageTransformSettings(0, False, True))
            self.assertEqual(result.getpixel((0, 0)), (255, 0, 255, 128))
            self.assertEqual(result.getpixel((0, 2)), (255, 0, 0, 255))

    def test_rotation_plus_flip_horizontal(self):
        with tempfile.TemporaryDirectory() as directory:
            source = save_pixels(Path(directory) / "source.png")
            with Image.open(source) as image:
                result = transform_pillow_image(image, ImageTransformSettings(90, True, False))
            self.assertEqual(result.getpixel((0, 0)), (255, 0, 0, 255))

    def test_rotation_plus_flip_vertical(self):
        with tempfile.TemporaryDirectory() as directory:
            source = save_pixels(Path(directory) / "source.png")
            with Image.open(source) as image:
                result = transform_pillow_image(image, ImageTransformSettings(90, False, True))
            self.assertEqual(result.getpixel((0, 0)), (0, 255, 255, 255))

    def test_alpha_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            source = save_pixels(Path(directory) / "source.png")
            with Image.open(source) as image:
                result = transform_pillow_image(image, ImageTransformSettings(90))
            self.assertEqual(result.getpixel((0, 0))[3], 128)

    def test_crop_pixels_after_rotation(self):
        with tempfile.TemporaryDirectory() as directory:
            source = save_pixels(Path(directory) / "source.png")
            with Image.open(source) as image:
                result = transform_pillow_image(
                    image,
                    ImageTransformSettings(90, crop_box=(1, 0, 2, 2)),
                )
            self.assertEqual(result.size, (2, 2))
            self.assertEqual(result.getpixel((0, 0)), (0, 0, 255, 255))
            self.assertEqual(result.getpixel((1, 0)), (255, 0, 0, 255))
            self.assertEqual(result.getpixel((0, 1)), (255, 255, 0, 255))
            self.assertEqual(result.getpixel((1, 1)), (0, 255, 0, 255))

    def test_original_pillow_object_is_not_modified(self):
        image = Image.new("RGBA", (2, 1), (1, 2, 3, 4))
        before = image.copy()
        transform_pillow_image(image, ImageTransformSettings(180, True, True))
        self.assertEqual(image.tobytes(), before.tobytes())

    def test_derived_name_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            source = save_pixels(Path(directory) / "logo weird!.png")
            settings = ImageTransformSettings(90, True, False)
            self.assertEqual(derived_asset_name(source, settings), derived_asset_name(source, settings))

    def test_different_settings_change_name(self):
        with tempfile.TemporaryDirectory() as directory:
            source = save_pixels(Path(directory) / "logo.png")
            self.assertNotEqual(
                derived_asset_name(source, ImageTransformSettings(90)),
                derived_asset_name(source, ImageTransformSettings(180)),
            )

    def test_different_crop_changes_name(self):
        with tempfile.TemporaryDirectory() as directory:
            source = save_pixels(Path(directory) / "logo.png")
            self.assertNotEqual(
                derived_asset_name(source, ImageTransformSettings(crop_box=(0, 0, 1, 1))),
                derived_asset_name(source, ImageTransformSettings(crop_box=(1, 0, 1, 1))),
            )

    def test_different_content_changes_name(self):
        with tempfile.TemporaryDirectory() as directory:
            one = save_pixels(Path(directory) / "one.png")
            two = Path(directory) / "two.png"
            Image.new("RGBA", (2, 3), (1, 2, 3, 4)).save(two)
            self.assertNotEqual(
                derived_asset_name(one, ImageTransformSettings(90)),
                derived_asset_name(two, ImageTransformSettings(90)),
            )

    def test_name_has_only_safe_characters(self):
        with tempfile.TemporaryDirectory() as directory:
            source = save_pixels(Path(directory) / "../bad name 😀.png")
            name = derived_asset_name(source, ImageTransformSettings(90, True, True))
            self.assertRegex(name, r"^[A-Za-z0-9._-]+\.png$")

    def test_theme_reference_relative_posix(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / GENERATED_MEDIA_DIR / "image.png"
            image.parent.mkdir()
            image.write_bytes(b"x")
            self.assertEqual(theme_path_reference(root, image), "generated-media/image.png")

    def test_external_path_preserved_absolute(self):
        with tempfile.TemporaryDirectory() as theme, tempfile.TemporaryDirectory() as other:
            image = Path(other) / "image.png"
            image.write_bytes(b"x")
            self.assertEqual(theme_path_reference(theme, image), str(image.resolve()))

    def test_missing_manifest_returns_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(
                load_transform_manifest(directory),
                {"version": TRANSFORM_MANIFEST_VERSION, "assets": {}},
            )

    def test_save_and_load_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = {
                "version": TRANSFORM_MANIFEST_VERSION,
                "assets": {"generated-media/a.png": {"source_reference": "a.png"}},
            }
            save_transform_manifest_atomic(directory, manifest)
            self.assertEqual(load_transform_manifest(directory), manifest)

    def test_manifest_with_crop_round_trips(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = {
                "version": TRANSFORM_MANIFEST_VERSION,
                "assets": {
                    "generated-media/a.png": {
                        "source_reference": "a.png",
                        "crop": {"x": 1, "y": 2, "width": 3, "height": 4},
                    },
                },
            }
            save_transform_manifest_atomic(directory, manifest)
            self.assertEqual(load_transform_manifest(directory), manifest)

    def test_manifest_json_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = {
                "version": TRANSFORM_MANIFEST_VERSION,
                "assets": {
                    "generated-media/b.png": {"source_reference": "b.png"},
                    "generated-media/a.png": {"source_reference": "a.png"},
                },
            }
            path = save_transform_manifest_atomic(directory, manifest)
            first = path.read_text(encoding="utf-8")
            path = save_transform_manifest_atomic(directory, manifest)
            self.assertEqual(path.read_text(encoding="utf-8"), first)

    def test_manifest_atomic_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = save_transform_manifest_atomic(
                directory,
                {"version": TRANSFORM_MANIFEST_VERSION, "assets": {}},
            )
            self.assertTrue(path.is_file())
            self.assertFalse(list(path.parent.glob("*.tmp")))

    def test_corrupt_manifest_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / GENERATED_MEDIA_DIR / TRANSFORM_MANIFEST
            path.parent.mkdir()
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ThemeMediaTransformError):
                load_transform_manifest(directory)

    def test_unknown_manifest_version_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / GENERATED_MEDIA_DIR / TRANSFORM_MANIFEST
            path.parent.mkdir()
            path.write_text(json.dumps({"version": 999, "assets": {}}), encoding="utf-8")
            with self.assertRaises(ThemeMediaTransformError):
                load_transform_manifest(directory)

    def test_manifest_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / GENERATED_MEDIA_DIR / TRANSFORM_MANIFEST
            path.parent.mkdir()
            path.write_text(
                json.dumps({"version": TRANSFORM_MANIFEST_VERSION, "assets": {"../bad.png": {}}}),
                encoding="utf-8",
            )
            with self.assertRaises(ThemeMediaTransformError):
                load_transform_manifest(directory)

    def test_manifest_source_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / GENERATED_MEDIA_DIR / TRANSFORM_MANIFEST
            path.parent.mkdir()
            path.write_text(
                json.dumps(
                    {
                        "version": TRANSFORM_MANIFEST_VERSION,
                        "assets": {
                            "generated-media/a.png": {
                                "source_reference": "../source.png"
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ThemeMediaTransformError):
                load_transform_manifest(directory)

    def test_normal_image_resolves_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = save_pixels(root / "logo.png")
            resolved = resolve_transform_source(root, "logo.png")
            self.assertEqual(resolved.source_path, source.resolve())
            self.assertTrue(is_identity_transform(resolved.current_settings))
            self.assertFalse(resolved.is_managed_asset)

    def test_managed_asset_resolves_origin_and_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = save_pixels(root / "logo.png")
            prepared = prepare_transform_asset(root, "logo.png", ImageTransformSettings(90, True, False))
            resolved = resolve_transform_source(root, prepared.output_reference)
            self.assertEqual(resolved.source_path, source.resolve())
            self.assertEqual(resolved.current_settings, ImageTransformSettings(90, True, False))
            self.assertTrue(resolved.is_managed_asset)

    def test_managed_crop_resolves_origin_and_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = save_pixels(root / "logo.png")
            settings = ImageTransformSettings(90, True, False, (0, 0, 2, 2))
            prepared = prepare_transform_asset(root, "logo.png", settings)
            resolved = resolve_transform_source(root, prepared.output_reference)
            self.assertEqual(resolved.source_path, source.resolve())
            self.assertEqual(resolved.current_settings, settings)
            self.assertTrue(resolved.is_managed_asset)

    def test_unregistered_generated_asset_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = root / GENERATED_MEDIA_DIR / "orphan.png"
            generated.parent.mkdir()
            save_pixels(generated)
            with self.assertRaises(ThemeMediaTransformError):
                resolve_transform_source(root, "generated-media/orphan.png")

    def test_missing_origin_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = root / GENERATED_MEDIA_DIR / "a.png"
            generated.parent.mkdir()
            save_pixels(generated)
            register_transform_asset(
                root,
                "generated-media/a.png",
                "missing.png",
                "0" * 64,
                ImageTransformSettings(90),
            )
            with self.assertRaises(ThemeMediaTransformError):
                resolve_transform_source(root, "generated-media/a.png")

    def test_identity_returns_origin_without_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = save_pixels(root / "logo.png")
            prepared = prepare_transform_asset(root, "logo.png", ImageTransformSettings())
            self.assertEqual(prepared.output_path, source.resolve())
            self.assertEqual(prepared.output_reference, "logo.png")
            self.assertFalse(prepared.created)
            self.assertFalse((root / GENERATED_MEDIA_DIR).exists())

    def test_crop_only_creates_generated_png(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save_pixels(root / "logo.png")
            prepared = prepare_transform_asset(
                root,
                "logo.png",
                ImageTransformSettings(crop_box=(0, 1, 2, 2)),
            )
            self.assertTrue(prepared.output_path.is_file())
            self.assertEqual(prepared.output_size, (2, 2))
            self.assertTrue(prepared.output_reference.startswith("generated-media/"))

    def test_rotation_creates_generated_png(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save_pixels(root / "logo.png")
            prepared = prepare_transform_asset(root, "logo.png", ImageTransformSettings(90))
            self.assertTrue(prepared.output_path.is_file())
            self.assertTrue(prepared.output_reference.startswith("generated-media/"))
            self.assertTrue(prepared.created)

    def test_created_asset_dimensions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save_pixels(root / "logo.png")
            prepared = prepare_transform_asset(root, "logo.png", ImageTransformSettings(90))
            self.assertEqual(prepared.output_size, (3, 2))

    def test_created_asset_preserves_alpha(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save_pixels(root / "logo.png")
            prepared = prepare_transform_asset(root, "logo.png", ImageTransformSettings(90))
            with Image.open(prepared.output_path) as image:
                rgba = image.convert("RGBA")
                alpha_values = [
                    rgba.getpixel((x, y))[3]
                    for y in range(rgba.height)
                    for x in range(rgba.width)
                ]
                self.assertIn(128, alpha_values)

    def test_asset_is_registered(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save_pixels(root / "logo.png")
            prepared = prepare_transform_asset(root, "logo.png", ImageTransformSettings(90))
            manifest = load_transform_manifest(root)
            self.assertIn(prepared.output_reference, manifest["assets"])

    def test_same_transform_reuses_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save_pixels(root / "logo.png")
            first = prepare_transform_asset(root, "logo.png", ImageTransformSettings(90))
            second = prepare_transform_asset(root, "logo.png", ImageTransformSettings(90))
            self.assertEqual(second.output_path, first.output_path)
            self.assertFalse(second.created)

    def test_consecutive_transforms_start_from_origin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save_pixels(root / "logo.png")
            first = prepare_transform_asset(root, "logo.png", ImageTransformSettings(90))
            second = prepare_transform_asset(root, first.output_reference, ImageTransformSettings(180))
            direct = prepare_transform_asset(root, "logo.png", ImageTransformSettings(180))
            self.assertEqual(second.output_reference, direct.output_reference)

    def test_consecutive_crop_starts_from_origin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save_pixels(root / "logo.png")
            first = prepare_transform_asset(
                root,
                "logo.png",
                ImageTransformSettings(crop_box=(0, 0, 1, 2)),
            )
            second = prepare_transform_asset(
                root,
                first.output_reference,
                ImageTransformSettings(crop_box=(1, 0, 1, 2)),
            )
            direct = prepare_transform_asset(
                root,
                "logo.png",
                ImageTransformSettings(crop_box=(1, 0, 1, 2)),
            )
            self.assertEqual(second.output_reference, direct.output_reference)

    def test_original_file_is_not_modified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = save_pixels(root / "logo.png")
            before = sha256(source)
            prepare_transform_asset(root, "logo.png", ImageTransformSettings(90, True, True))
            self.assertEqual(sha256(source), before)

    def test_preview_does_not_create_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = save_pixels(root / "logo.png")
            render_transform_preview_asset(
                source,
                root / "cache" / "preview.png",
                ImageTransformSettings(90),
            )
            self.assertFalse((root / GENERATED_MEDIA_DIR / TRANSFORM_MANIFEST).exists())

    def test_preview_does_not_write_theme_generated_media(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = save_pixels(root / "logo.png")
            render_transform_preview_asset(
                source,
                root / "cache" / "preview.png",
                ImageTransformSettings(90),
            )
            self.assertFalse((root / GENERATED_MEDIA_DIR).exists())

    def test_returned_structures_are_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save_pixels(root / "logo.png")
            prepared = prepare_transform_asset(root, "logo.png", ImageTransformSettings(90))
            manifest = load_transform_manifest(root)
            manifest["assets"][prepared.output_reference]["rotation"] = 180
            self.assertEqual(
                load_transform_manifest(root)["assets"][prepared.output_reference]["rotation"],
                90,
            )

    def test_fit_uses_transformed_dimensions_after_rotation(self):
        transformed = transformed_dimensions((800, 400), ImageTransformSettings(90))
        layout = compute_image_layout(
            transformed[0],
            transformed[1],
            480,
            480,
            ImageLayoutSettings(MODE_FIT),
        )
        self.assertEqual(layout, {"X": 120, "Y": 0, "WIDTH": 240, "HEIGHT": 480})

    def test_original_uses_transformed_dimensions_after_rotation(self):
        transformed = transformed_dimensions((800, 400), ImageTransformSettings(90))
        layout = compute_image_layout(
            transformed[0],
            transformed[1],
            480,
            480,
            ImageLayoutSettings(MODE_ORIGINAL),
        )
        self.assertEqual(layout["WIDTH"], 400)
        self.assertEqual(layout["HEIGHT"], 800)

    def test_custom_size_is_not_swapped_by_rotation(self):
        transformed = transformed_dimensions((800, 400), ImageTransformSettings(90))
        layout = compute_image_layout(
            transformed[0],
            transformed[1],
            480,
            480,
            ImageLayoutSettings(MODE_CUSTOM, custom_width=300, custom_height=180),
        )
        self.assertEqual(layout["WIDTH"], 300)
        self.assertEqual(layout["HEIGHT"], 180)


if __name__ == "__main__":
    unittest.main()
