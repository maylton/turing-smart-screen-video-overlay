# SPDX-License-Identifier: GPL-3.0-or-later

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from library.theme_generated_media import (
    GeneratedMediaRemovalError,
    GeneratedMediaStatus,
    inspect_generated_media,
    referenced_generated_media,
    remove_unused_managed_asset,
)
from library.theme_media_transform import (
    ImageTransformSettings,
    prepare_transform_asset,
)


def save_image(path: Path, color=(10, 20, 30, 255)) -> Path:
    Image.new("RGBA", (4, 3), color).save(path)
    return path


class GeneratedMediaReferencesTests(unittest.TestCase):
    def test_collects_nested_generated_media_references(self):
        data = {
            "static_images": {
                "one": {"PATH": "generated-media/a.png"},
                "two": [{"BACKGROUND_IMAGE": r"generated-media\b.png"}],
            },
            "unrelated": "image.png",
        }
        self.assertEqual(
            referenced_generated_media(data),
            frozenset(
                {
                    "generated-media/a.png",
                    "generated-media/b.png",
                }
            ),
        )

    def test_ignores_absolute_and_non_generated_references(self):
        data = {"a": "/tmp/generated-media/a.png", "b": "normal.png"}
        self.assertEqual(referenced_generated_media(data), frozenset())


class GeneratedMediaInventoryTests(unittest.TestCase):
    def test_classifies_in_use_and_unused_managed_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save_image(root / "one.png")
            save_image(root / "two.png", (40, 50, 60, 255))
            used = prepare_transform_asset(
                root, "one.png", ImageTransformSettings(rotation=90)
            )
            unused = prepare_transform_asset(
                root, "two.png", ImageTransformSettings(flip_horizontal=True)
            )

            report = inspect_generated_media(
                root,
                {"static_images": {"hero": {"PATH": used.output_reference}}},
            )
            by_reference = {record.reference: record for record in report.records}
            self.assertEqual(
                by_reference[used.output_reference].status,
                GeneratedMediaStatus.IN_USE,
            )
            self.assertEqual(
                by_reference[unused.output_reference].status,
                GeneratedMediaStatus.UNUSED,
            )
            self.assertFalse(by_reference[used.output_reference].removable)
            self.assertTrue(by_reference[unused.output_reference].removable)

    def test_classifies_registered_missing_output_as_orphaned(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save_image(root / "source.png")
            prepared = prepare_transform_asset(
                root, "source.png", ImageTransformSettings(rotation=90)
            )
            prepared.output_path.unlink()
            record = inspect_generated_media(root, {}).by_reference(
                prepared.output_reference
            )
            self.assertIsNotNone(record)
            self.assertEqual(record.status, GeneratedMediaStatus.ORPHANED)
            self.assertFalse(record.removable)

    def test_classifies_unregistered_file_as_unmanaged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = root / "generated-media"
            generated.mkdir()
            save_image(generated / "manual.png")

            record = inspect_generated_media(root, {}).by_reference(
                "generated-media/manual.png"
            )
            self.assertIsNotNone(record)
            self.assertEqual(record.status, GeneratedMediaStatus.UNMANAGED)
            self.assertFalse(record.registered)
            self.assertFalse(record.removable)

    def test_reports_source_hash_mismatch_without_making_used_asset_removable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = save_image(root / "source.png")
            prepared = prepare_transform_asset(
                root, "source.png", ImageTransformSettings(rotation=90)
            )
            save_image(source, (200, 10, 10, 255))

            record = inspect_generated_media(
                root, {"PATH": prepared.output_reference}
            ).by_reference(prepared.output_reference)
            self.assertEqual(record.status, GeneratedMediaStatus.IN_USE)
            self.assertFalse(record.source_hash_matches)
            self.assertIn("Source hash no longer matches", record.issues)

    def test_invalid_manifest_is_reported_without_listing_or_deleting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = root / "generated-media"
            generated.mkdir()
            (generated / "transform-manifest.json").write_text(
                "{broken", encoding="utf-8"
            )
            report = inspect_generated_media(root, {})
            self.assertFalse(report.manifest_valid)
            self.assertEqual(report.records, ())


class GeneratedMediaRemovalTests(unittest.TestCase):
    def test_removes_only_unused_registered_asset_and_manifest_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save_image(root / "source.png")
            prepared = prepare_transform_asset(
                root, "source.png", ImageTransformSettings(rotation=90)
            )
            report = remove_unused_managed_asset(
                root, {}, prepared.output_reference
            )
            self.assertFalse(prepared.output_path.exists())
            self.assertIsNone(report.by_reference(prepared.output_reference))
            manifest = json.loads(
                (root / "generated-media" / "transform-manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertNotIn(prepared.output_reference, manifest["assets"])

    def test_refuses_to_remove_referenced_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save_image(root / "source.png")
            prepared = prepare_transform_asset(
                root, "source.png", ImageTransformSettings(rotation=90)
            )
            with self.assertRaises(GeneratedMediaRemovalError):
                remove_unused_managed_asset(
                    root,
                    {"PATH": prepared.output_reference},
                    prepared.output_reference,
                )
            self.assertTrue(prepared.output_path.exists())

    def test_refuses_to_remove_unmanaged_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = root / "generated-media"
            generated.mkdir()
            manual = save_image(generated / "manual.png")
            with self.assertRaises(GeneratedMediaRemovalError):
                remove_unused_managed_asset(
                    root, {}, "generated-media/manual.png"
                )
            self.assertTrue(manual.exists())

    def test_restores_manifest_if_unlink_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save_image(root / "source.png")
            prepared = prepare_transform_asset(
                root, "source.png", ImageTransformSettings(rotation=90)
            )
            with mock.patch.object(
                Path, "unlink", side_effect=OSError("denied")
            ):
                with self.assertRaises(OSError):
                    remove_unused_managed_asset(
                        root, {}, prepared.output_reference
                    )
            report = inspect_generated_media(root, {})
            self.assertIsNotNone(report.by_reference(prepared.output_reference))
            self.assertTrue(prepared.output_path.exists())


if __name__ == "__main__":
    unittest.main()
