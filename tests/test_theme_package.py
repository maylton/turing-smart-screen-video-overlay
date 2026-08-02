from __future__ import annotations

import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from library.theme_package import (
    PACKAGE_FILENAME,
    ThemePackageDescriptor,
    ThemePackageError,
    load_theme_package_descriptor,
    validate_archive_members,
)


class ThemePackageTests(unittest.TestCase):
    def test_descriptor_round_trip(self):
        with tempfile.TemporaryDirectory(prefix="turing-theme-package-") as directory:
            root = Path(directory)
            descriptor = ThemePackageDescriptor(
                name="Material Expressive",
                engine="html",
                definition="manifest.json",
            )
            (root / PACKAGE_FILENAME).write_text(descriptor.as_json(), encoding="utf-8")
            (root / "manifest.json").write_text("{}", encoding="utf-8")

            self.assertEqual(load_theme_package_descriptor(root), descriptor)

    def test_descriptor_rejects_unsupported_version_and_unsafe_definition(self):
        base = {
            "format": "turing-smart-screen-theme",
            "formatVersion": 1,
            "name": "Theme",
            "engine": "yaml",
            "definition": "theme.yaml",
        }
        with self.assertRaisesRegex(ThemePackageError, "Unsupported theme package version"):
            ThemePackageDescriptor.from_mapping({**base, "formatVersion": 99})
        with self.assertRaisesRegex(ThemePackageError, "definition"):
            ThemePackageDescriptor.from_mapping({**base, "definition": "../theme.yaml"})

    def test_archive_validator_accepts_normal_files(self):
        with tempfile.TemporaryDirectory(prefix="turing-theme-archive-") as directory:
            archive_path = Path(directory) / "safe.theme"
            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(PACKAGE_FILENAME, "{}")
                archive.writestr("assets/background.png", b"image")
            with zipfile.ZipFile(archive_path) as archive:
                validate_archive_members(archive)

    def test_archive_validator_rejects_traversal_and_case_collisions(self):
        with tempfile.TemporaryDirectory(prefix="turing-theme-archive-") as directory:
            root = Path(directory)
            traversal = root / "traversal.theme"
            with zipfile.ZipFile(traversal, "w") as archive:
                archive.writestr("../outside.txt", "unsafe")
            with zipfile.ZipFile(traversal) as archive:
                with self.assertRaisesRegex(ThemePackageError, "Unsafe archive path"):
                    validate_archive_members(archive)

            collision = root / "collision.theme"
            with zipfile.ZipFile(collision, "w") as archive:
                archive.writestr("Assets/font.ttf", "a")
                archive.writestr("assets/font.ttf", "b")
            with zipfile.ZipFile(collision) as archive:
                with self.assertRaisesRegex(ThemePackageError, "Case-colliding"):
                    validate_archive_members(archive)

    def test_archive_validator_rejects_links_and_suspicious_compression(self):
        with tempfile.TemporaryDirectory(prefix="turing-theme-archive-") as directory:
            root = Path(directory)
            link_archive = root / "link.theme"
            link = zipfile.ZipInfo("assets/link")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(link_archive, "w") as archive:
                archive.writestr(link, "../outside")
            with zipfile.ZipFile(link_archive) as archive:
                with self.assertRaisesRegex(ThemePackageError, "Special archive member"):
                    validate_archive_members(archive)

            compressed = root / "compressed.theme"
            with zipfile.ZipFile(compressed, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("assets/zeros.bin", b"\x00" * (2 * 1024 * 1024))
            with zipfile.ZipFile(compressed) as archive:
                with self.assertRaisesRegex(ThemePackageError, "compression ratio"):
                    validate_archive_members(archive)


if __name__ == "__main__":
    unittest.main()
