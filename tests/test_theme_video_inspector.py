# SPDX-License-Identifier: GPL-3.0-or-later

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from library.media_preparation import ConversionSettings
from library.theme_video_inspector import (
    ThemeVideoInspectorError,
    VideoThemeUpdate,
    build_video_section,
    convert_media_atomic,
    create_preview_atomic,
    live_preview_settings,
    prepared_output_path,
    preview_background_path,
    resolve_local_video_source,
)


class VideoInspectorPathTests(unittest.TestCase):
    def test_resolves_theme_relative_local_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "video.mp4"
            source.write_bytes(b"video")
            self.assertEqual(
                resolve_local_video_source(root, {"LOCAL_PATH": "video.mp4"}),
                source.resolve(),
            )

    def test_ignores_remote_display_path(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(
                resolve_local_video_source(
                    directory,
                    {"PATH": "/mnt/SDCARD/video/demo.mp4"},
                )
            )

    def test_safe_prepared_output_name(self):
        with tempfile.TemporaryDirectory() as directory:
            output = prepared_output_path(directory, "Vídeo demo.mov")
            self.assertEqual(output.name, "Video-demo.mp4")
            self.assertEqual(output.parent, Path(directory).resolve())

    def test_preview_background_is_theme_local_png(self):
        with tempfile.TemporaryDirectory() as directory:
            output = preview_background_path(directory, "preview.jpg")
            self.assertEqual(output, Path(directory).resolve() / "preview.png")


class VideoThemeUpdateTests(unittest.TestCase):
    def test_build_section_preserves_existing_unknown_keys(self):
        section = build_video_section(
            {"CUSTOM": "keep", "OVERLAY": False},
            VideoThemeUpdate(
                local_filename="demo.mp4",
                remote_path="/mnt/SDCARD/video/demo.mp4",
                preview_background="demo-preview.png",
                overlay=True,
            ),
        )
        self.assertEqual(section["CUSTOM"], "keep")
        self.assertTrue(section["ENABLED"])
        self.assertEqual(section["MODE"], "native")
        self.assertEqual(section["LOCAL_PATH"], "demo.mp4")
        self.assertEqual(section["PATH"], "/mnt/SDCARD/video/demo.mp4")
        self.assertEqual(section["PREVIEW_BACKGROUND"], "demo-preview.png")
        self.assertTrue(section["OVERLAY"])

    def test_rejects_mismatched_local_and_remote_names(self):
        with self.assertRaises(ThemeVideoInspectorError):
            VideoThemeUpdate(
                local_filename="one.mp4",
                remote_path="/root/video/two.mp4",
                preview_background="preview.png",
            )

    def test_rejects_unsupported_remote_directory(self):
        with self.assertRaises(ThemeVideoInspectorError):
            VideoThemeUpdate(
                local_filename="demo.mp4",
                remote_path="/tmp/demo.mp4",
                preview_background="preview.png",
            )

    def test_rejects_remote_path_traversal(self):
        with self.assertRaises(ThemeVideoInspectorError):
            VideoThemeUpdate(
                local_filename="demo.mp4",
                remote_path="/mnt/SDCARD/video/../demo.mp4",
                preview_background="preview.png",
            )


class LivePreviewSettingsTests(unittest.TestCase):
    def test_limits_preview_to_eight_seconds(self):
        original = ConversionSettings(fps=30, crf=20)
        preview = live_preview_settings(original, 30.0)
        self.assertEqual(preview.start, 0.0)
        self.assertEqual(preview.end, 8.0)
        self.assertEqual(preview.fps, 24)
        self.assertEqual(preview.crf, 28)
        self.assertIsNone(original.end)

    def test_uses_shorter_source_duration(self):
        preview = live_preview_settings(ConversionSettings(), 3.5)
        self.assertEqual(preview.end, 3.5)

    def test_rejects_invalid_duration(self):
        with self.assertRaises(ThemeVideoInspectorError):
            live_preview_settings(ConversionSettings(), 0)

    def test_live_preview_respects_trim_start_and_speed(self):
        preview = live_preview_settings(
            ConversionSettings(start=5.0, end=20.0, speed=1.5),
            30.0,
        )
        self.assertEqual(preview.start, 5.0)
        self.assertEqual(preview.end, 13.0)
        self.assertEqual(preview.speed, 1.5)


class AtomicMediaTests(unittest.TestCase):
    def test_conversion_replaces_destination_only_after_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp4"
            source.write_bytes(b"source")
            destination = root / "output.mp4"
            destination.write_bytes(b"old")

            def fake_convert(_source, temporary, _settings):
                Path(temporary).write_bytes(b"new")
                return {"ok": True}

            with mock.patch(
                "library.theme_video_inspector.convert_media",
                side_effect=fake_convert,
            ):
                result = convert_media_atomic(
                    source,
                    destination,
                    ConversionSettings(),
                )
            self.assertEqual(result, {"ok": True})
            self.assertEqual(destination.read_bytes(), b"new")

    def test_conversion_failure_keeps_existing_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp4"
            source.write_bytes(b"source")
            destination = root / "output.mp4"
            destination.write_bytes(b"old")
            with mock.patch(
                "library.theme_video_inspector.convert_media",
                side_effect=RuntimeError("failed"),
            ):
                with self.assertRaises(RuntimeError):
                    convert_media_atomic(
                        source,
                        destination,
                        ConversionSettings(),
                    )
            self.assertEqual(destination.read_bytes(), b"old")

    def test_preview_is_installed_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp4"
            source.write_bytes(b"source")
            destination = root / "preview.png"

            def fake_preview(_source, temporary, _settings):
                Path(temporary).write_bytes(b"png")
                return Path(temporary)

            with mock.patch(
                "library.theme_video_inspector.create_preview",
                side_effect=fake_preview,
            ):
                result = create_preview_atomic(
                    source,
                    destination,
                    ConversionSettings(),
                )
            self.assertEqual(result, destination.resolve())
            self.assertEqual(destination.read_bytes(), b"png")


if __name__ == "__main__":
    unittest.main()
