from __future__ import annotations

import unittest
from pathlib import Path

from library.video_media import (
    RemotePathError,
    evaluate_probe,
    normalize_remote_path,
    parse_rate,
)


class RemotePathTests(unittest.TestCase):
    def test_accepts_direct_video_files(self):
        self.assertEqual(
            normalize_remote_path("/mnt/SDCARD/video/demo.mp4"),
            "/mnt/SDCARD/video/demo.mp4",
        )
        self.assertEqual(
            normalize_remote_path("/root/video/demo.mp4"),
            "/root/video/demo.mp4",
        )

    def test_accepts_only_known_root_directories(self):
        self.assertEqual(
            normalize_remote_path(
                "/mnt/SDCARD/video/", allow_directory=True
            ),
            "/mnt/SDCARD/video/",
        )
        with self.assertRaises(RemotePathError):
            normalize_remote_path(
                "/mnt/SDCARD/video/subdir", allow_directory=True
            )

    def test_rejects_traversal_nested_and_outside_paths(self):
        invalid = (
            "/mnt/SDCARD/video/../etc/passwd",
            "/mnt/SDCARD/video/subdir/demo.mp4",
            "/root/video/../../etc/passwd",
            "/tmp/demo.mp4",
            "relative.mp4",
        )
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(RemotePathError):
                    normalize_remote_path(value)

    def test_rejects_non_ascii_remote_names(self):
        with self.assertRaises(RemotePathError):
            normalize_remote_path("/mnt/SDCARD/video/vídeo.mp4")


class ProbeTests(unittest.TestCase):
    def test_parse_rate(self):
        self.assertEqual(parse_rate("30/1"), 30.0)
        self.assertAlmostEqual(parse_rate("30000/1001"), 29.97002997)
        self.assertIsNone(parse_rate("0/0"))

    def test_compatible_probe(self):
        probe = evaluate_probe(
            Path("demo.mp4"),
            {
                "streams": [
                    {
                        "codec_type": "video",
                        "codec_name": "h264",
                        "width": 480,
                        "height": 480,
                        "pix_fmt": "yuv420p",
                        "avg_frame_rate": "30/1",
                    }
                ],
                "format": {"format_name": "mov,mp4", "duration": "5.0"},
            },
        )
        self.assertTrue(probe.compatible)
        self.assertEqual(probe.issues, ())

    def test_incompatible_probe_lists_all_required_changes(self):
        probe = evaluate_probe(
            Path("demo.webm"),
            {
                "streams": [
                    {
                        "codec_type": "video",
                        "codec_name": "vp9",
                        "width": 1920,
                        "height": 1080,
                        "pix_fmt": "yuv444p",
                        "r_frame_rate": "60/1",
                    },
                    {"codec_type": "audio", "codec_name": "opus"},
                ],
                "format": {"format_name": "matroska,webm"},
            },
        )
        self.assertFalse(probe.compatible)
        self.assertTrue(probe.has_audio)
        self.assertEqual(len(probe.issues), 3)


if __name__ == "__main__":
    unittest.main()
