from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from library.media_profiles import (
    estimate_output_size,
    get_profile,
    list_profiles,
    load_active_theme_profile,
    oriented_dimensions,
)


class MediaProfileTests(unittest.TestCase):
    def make_project(
        self,
        root: Path,
        *,
        size: str = '2.1"',
        orientation: str = "landscape",
        revision: str = "C",
    ) -> None:
        (root / "res" / "themes" / "demo").mkdir(parents=True)
        (root / "config.yaml").write_text(
            "config:\n"
            "  THEME: demo\n"
            "display:\n"
            f"  REVISION: {revision}\n",
            encoding="utf-8",
        )
        (root / "res" / "themes" / "demo" / "theme.yaml").write_text(
            "display:\n"
            f"  DISPLAY_SIZE: '{size}'\n"
            f"  DISPLAY_ORIENTATION: {orientation}\n",
            encoding="utf-8",
        )

    def test_orientation_swaps_non_square_dimensions(self):
        self.assertEqual(oriented_dimensions('5"', "portrait"), (480, 800))
        self.assertEqual(oriented_dimensions('5"', "landscape"), (800, 480))
        self.assertEqual(oriented_dimensions('2.1"', "landscape"), (480, 480))

    def test_active_rev_c_21_profile_is_upload_validated(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_project(root)
            profile = load_active_theme_profile(root)
        self.assertEqual((profile.width, profile.height), (480, 480))
        self.assertTrue(profile.upload_supported)
        self.assertTrue(profile.hardware_validated)

    def test_unvalidated_size_disables_native_upload(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_project(root, size='5"', orientation="landscape")
            profile = load_active_theme_profile(root)
        self.assertEqual((profile.width, profile.height), (800, 480))
        self.assertFalse(profile.upload_supported)
        self.assertFalse(profile.hardware_validated)

    def test_profile_registry_includes_active_and_reusable_presets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_project(root)
            profiles = list_profiles(root)
            ids = {profile.id for profile in profiles}
            selected = get_profile("portrait-320x480-preview", root)
        self.assertIn("active-theme", ids)
        self.assertIn("square-480-preview", ids)
        self.assertEqual((selected.width, selected.height), (320, 480))

    def test_estimate_grows_with_duration_and_resolution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_project(root)
            square = get_profile("square-480-preview", root)
            portrait = get_profile("portrait-320x480-preview", root)
            short = estimate_output_size(square, 2, 30, 20)
            long = estimate_output_size(square, 8, 30, 20)
            smaller = estimate_output_size(portrait, 2, 30, 20)
        self.assertGreater(long["estimated_bytes"], short["estimated_bytes"])
        self.assertGreater(short["estimated_bytes"], smaller["estimated_bytes"])
        self.assertLessEqual(short["low_bytes"], short["estimated_bytes"])
        self.assertGreaterEqual(short["high_bytes"], short["estimated_bytes"])


if __name__ == "__main__":
    unittest.main()
