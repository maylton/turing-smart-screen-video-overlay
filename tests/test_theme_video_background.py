from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from library.theme_video_background import (
    INTERNAL_VIDEO_DIR,
    SD_VIDEO_DIR,
    build_background_command,
    display_video_path,
    find_prepared_local_video,
)


class ThemeVideoBackgroundTests(unittest.TestCase):
    def test_display_video_path_uses_selected_storage(self):
        self.assertEqual(
            display_video_path("gengar.mp4"),
            f"{SD_VIDEO_DIR}gengar.mp4",
        )
        self.assertEqual(
            display_video_path("gengar.mp4", internal=True),
            f"{INTERNAL_VIDEO_DIR}gengar.mp4",
        )

    def test_display_video_path_discards_directories(self):
        self.assertEqual(
            display_video_path("../../unsafe/demo.mp4"),
            f"{SD_VIDEO_DIR}demo.mp4",
        )

    def test_display_video_path_rejects_non_ascii_names(self):
        with self.assertRaises(ValueError):
            display_video_path("vídeo.mp4")

    def test_background_command_extracts_one_exact_size_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp4"
            source.write_bytes(b"test")
            destination = root / "background.tmp.png"

            command = build_background_command(
                source,
                destination,
                timestamp=2.5,
                width=480,
                height=480,
                ffmpeg="/usr/bin/ffmpeg",
            )

        self.assertEqual(command[0], "/usr/bin/ffmpeg")
        self.assertIn("2.500", command)
        self.assertIn("-frames:v", command)
        self.assertIn("1", command)
        self.assertIn(
            "scale=480:480:force_original_aspect_ratio=increase,"
            "crop=480:480",
            command,
        )

    def test_background_command_rejects_invalid_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.mp4"
            source.write_bytes(b"test")
            with self.assertRaises(ValueError):
                build_background_command(
                    source,
                    Path(directory) / "background.png",
                    timestamp=-1,
                    ffmpeg="/usr/bin/ffmpeg",
                )


    def test_find_prepared_local_video_uses_cache_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "cache"
            media = cache / "turing-smart-screen" / "media-preparation"
            media.mkdir(parents=True)
            expected = media / "gengar.mp4"
            expected.write_bytes(b"video")

            old_cache = os.environ.get("XDG_CACHE_HOME")
            old_data = os.environ.get("XDG_DATA_HOME")
            os.environ["XDG_CACHE_HOME"] = str(cache)
            os.environ["XDG_DATA_HOME"] = str(root / "data")
            try:
                found = find_prepared_local_video(
                    "/mnt/SDCARD/video/gengar.mp4"
                )
            finally:
                if old_cache is None:
                    os.environ.pop("XDG_CACHE_HOME", None)
                else:
                    os.environ["XDG_CACHE_HOME"] = old_cache
                if old_data is None:
                    os.environ.pop("XDG_DATA_HOME", None)
                else:
                    os.environ["XDG_DATA_HOME"] = old_data

            self.assertEqual(found, expected.resolve())

    def test_find_prepared_local_video_returns_none_when_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_cache = os.environ.get("XDG_CACHE_HOME")
            old_data = os.environ.get("XDG_DATA_HOME")
            os.environ["XDG_CACHE_HOME"] = str(root / "cache")
            os.environ["XDG_DATA_HOME"] = str(root / "data")
            try:
                found = find_prepared_local_video(
                    "/root/video/missing.mp4"
                )
            finally:
                if old_cache is None:
                    os.environ.pop("XDG_CACHE_HOME", None)
                else:
                    os.environ["XDG_CACHE_HOME"] = old_cache
                if old_data is None:
                    os.environ.pop("XDG_DATA_HOME", None)
                else:
                    os.environ["XDG_DATA_HOME"] = old_data

            self.assertIsNone(found)


if __name__ == "__main__":
    unittest.main()
