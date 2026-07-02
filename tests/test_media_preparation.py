from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from library.media_preparation import (
    ConversionSettings,
    InvalidSettingsError,
    build_conversion_command,
    build_filter,
    cache_directory,
    safe_output_name,
)


class MediaPreparationTests(unittest.TestCase):
    def test_fit_filter_uses_canvas_overlay_and_yuv420p(self):
        value = build_filter(ConversionSettings(mode="fit", fps=30))
        self.assertIn("force_original_aspect_ratio=decrease", value)
        self.assertIn("overlay=", value)
        self.assertIn("format=yuv420p", value)

    def test_fill_filter_crops_by_canvas_clipping(self):
        value = build_filter(
            ConversionSettings(mode="fill", zoom=1.25, offset_x=12, offset_y=-8)
        )
        self.assertIn("force_original_aspect_ratio=increase", value)
        self.assertIn("(W-w)/2+12", value)
        self.assertIn("(H-h)/2-8", value)

    def test_stretch_filter_targets_480_square(self):
        value = build_filter(ConversionSettings(mode="stretch"))
        self.assertIn("scale=480:480", value)

    def test_preview_uses_rgba_not_output_pixel_format(self):
        value = build_filter(ConversionSettings(), preview=True)
        self.assertIn("format=rgba", value)
        self.assertNotIn("format=yuv420p", value)

    def test_trim_validation(self):
        with self.assertRaises(InvalidSettingsError):
            ConversionSettings(start=2, end=1).validated(duration=5)
        with self.assertRaises(InvalidSettingsError):
            ConversionSettings(start=0, end=6).validated(duration=5)

    def test_safe_output_name_is_ascii_mp4(self):
        self.assertEqual(safe_output_name("Vídeo legal!.webm"), "Video-legal.mp4")
        self.assertEqual(safe_output_name("---.gif"), "prepared-video.mp4")

    def test_cache_honors_xdg_cache_home(self):
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.dict(os.environ, {"XDG_CACHE_HOME": temp}):
                path = cache_directory()
            self.assertEqual(path, Path(temp) / "turing-smart-screen" / "media-preparation")

    def test_conversion_command_removes_audio_and_uses_h264(self):
        with mock.patch("library.media_preparation._require_command", return_value="ffmpeg"):
            command = build_conversion_command(
                Path("source.mp4"),
                Path("output.mp4"),
                ConversionSettings(start=1, end=3, fps=24),
            )
        self.assertIn("libx264", command)
        self.assertIn("yuv420p", command)
        self.assertIn("-an", command)
        self.assertIn("2.000", command)


if __name__ == "__main__":
    unittest.main()
