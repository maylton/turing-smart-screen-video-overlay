from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from library.media_preparation import (
    ConversionSettings,
    InvalidSettingsError,
    alignment_offsets,
    build_conversion_command,
    build_filter,
    cache_directory,
    effective_duration,
    foreground_size,
    safe_output_name,
)


class MediaPreparationTests(unittest.TestCase):
    def test_fit_filter_uses_canvas_overlay_and_yuv420p(self):
        value = build_filter(ConversionSettings(mode="fit", fps=30))
        self.assertIn("force_original_aspect_ratio=decrease", value)
        self.assertIn("overlay=", value)
        self.assertIn("format=yuv420p", value)

    def test_custom_mode_uses_numeric_size(self):
        value = build_filter(
            ConversionSettings(mode="custom", custom_width=320, custom_height=240)
        )
        self.assertIn("scale=320:240", value)

    def test_original_mode_keeps_source_dimensions_before_zoom(self):
        value = build_filter(ConversionSettings(mode="original"))
        self.assertIn("scale=iw:ih", value)

    def test_crop_and_rotation_filters_are_applied(self):
        value = build_filter(
            ConversionSettings(
                crop_left=10,
                crop_right=20,
                crop_top=5,
                crop_bottom=15,
                rotation=90,
            )
        )
        self.assertIn("crop=iw-30:ih-20:10:5", value)
        self.assertIn("transpose=1", value)

    def test_mirror_filters_are_applied_after_rotation(self):
        value = build_filter(
            ConversionSettings(
                rotation=90,
                flip_horizontal=True,
                flip_vertical=True,
            )
        )
        source_graph = value.split("[fg];", 1)[0]
        self.assertIn("transpose=1,hflip,vflip", source_graph)

    def test_validated_preserves_boolean_mirror_flags(self):
        settings = ConversionSettings(
            flip_horizontal=1,
            flip_vertical="yes",
        ).validated()
        self.assertTrue(settings.flip_horizontal)
        self.assertTrue(settings.flip_vertical)

    def test_blurred_background_uses_split_and_gblur(self):
        value = build_filter(
            ConversionSettings(background_mode="blur", blur_strength=31)
        )
        self.assertIn("split=2", value)
        self.assertIn("gblur=sigma=31.000", value)

    def test_image_background_uses_second_input(self):
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp) / "background.png"
            image.write_bytes(b"placeholder")
            settings = ConversionSettings(
                background_mode="image",
                background_image=str(image),
            )
            value = build_filter(settings)
            self.assertIn("[1:v]scale=480:480", value)

    def test_speed_and_loop_are_added_to_command(self):
        with mock.patch(
            "library.media_preparation._require_command",
            return_value="ffmpeg",
        ):
            command = build_conversion_command(
                Path("source.mp4"),
                Path("output.mp4"),
                ConversionSettings(speed=1.5, loop_count=2),
            )
        self.assertIn("-stream_loop", command)
        self.assertIn("2", command)
        self.assertIn("setpts=(PTS-STARTPTS)/1.500000", " ".join(command))

    def test_alignment_offsets_cover_nine_point_grid(self):
        settings = ConversionSettings(mode="custom", custom_width=200, custom_height=100)
        self.assertEqual(
            alignment_offsets(640, 360, settings, "left", "top"),
            (-140, -190),
        )
        self.assertEqual(
            alignment_offsets(640, 360, settings, "center", "center"),
            (0, 0),
        )
        self.assertEqual(
            alignment_offsets(640, 360, settings, "right", "bottom"),
            (140, 190),
        )

    def test_foreground_size_accounts_for_rotation_and_crop(self):
        settings = ConversionSettings(
            mode="original",
            crop_left=10,
            crop_right=20,
            crop_top=5,
            crop_bottom=15,
            rotation=90,
            zoom=2,
        )
        self.assertEqual(foreground_size(640, 360, settings), (680, 1220))

    def test_invalid_crop_is_rejected_with_source_dimensions(self):
        with self.assertRaises(InvalidSettingsError):
            ConversionSettings(crop_left=400, crop_right=300).validated(
                source_width=640,
                source_height=360,
            )

    def test_image_background_requires_existing_file(self):
        with self.assertRaises(InvalidSettingsError):
            ConversionSettings(
                background_mode="image",
                background_image="/definitely/missing.png",
            ).validated()

    def test_trim_validation_uses_looped_duration(self):
        self.assertEqual(effective_duration(3, 2), 9)
        ConversionSettings(start=4, end=8, loop_count=2).validated(duration=9)
        with self.assertRaises(InvalidSettingsError):
            ConversionSettings(start=4, end=10, loop_count=2).validated(duration=9)

    def test_safe_output_name_is_ascii_mp4(self):
        self.assertEqual(safe_output_name("Vídeo legal!.webm"), "Video-legal.mp4")
        self.assertEqual(safe_output_name("---.gif"), "prepared-video.mp4")

    def test_cache_honors_xdg_cache_home(self):
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.dict(os.environ, {"XDG_CACHE_HOME": temp}):
                path = cache_directory()
            self.assertEqual(
                path,
                Path(temp) / "turing-smart-screen" / "media-preparation",
            )

    def test_conversion_command_removes_audio_and_uses_h264(self):
        with mock.patch(
            "library.media_preparation._require_command",
            return_value="ffmpeg",
        ):
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
