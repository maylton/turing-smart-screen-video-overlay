import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from library.html_background_video import (
    HtmlBackgroundMedia,
    HtmlBackgroundVideo,
    image_pipe_ffmpeg_command,
    load_background_image,
    load_background_media,
    load_background_video,
    remove_background_media,
    save_background_image,
    save_background_video,
)
from library.theme_engine import ThemeManifest, ThemeValidationError


class HtmlBackgroundVideoTests(unittest.TestCase):
    def make_theme(
        self,
        root: Path,
        *,
        background_video=None,
        background_image=None,
    ) -> ThemeManifest:
        root.mkdir(parents=True)
        (root / "index.html").write_text(
            "<!doctype html><body></body>",
            encoding="utf-8",
        )
        payload = {
            "engine": "html",
            "name": "Background",
            "version": 1,
            "display": {"width": 480, "height": 480},
            "refreshRate": 2,
            "entrypoint": "index.html",
            "permissions": ["sensors"],
            "network": False,
            "nativeVideoOverlay": {
                "enabled": True,
                "localPath": "compiled.mp4",
                "devicePath": "/mnt/SDCARD/video/compiled.mp4",
                "fps": 24,
                "duration": 8,
                "backgroundFrame": 0,
            },
        }
        if background_video is not None:
            payload["nativeVideoOverlay"]["backgroundVideo"] = background_video
        if background_image is not None:
            payload["nativeVideoOverlay"]["backgroundImage"] = background_image
        (root / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
        return ThemeManifest.load(root)

    def test_loads_background_video_without_changing_native_artifact(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "theme"
            manifest = self.make_theme(
                root,
                background_video={
                    "sourcePath": "assets/source.mp4",
                    "fit": "contain",
                    "position": "bottom-right",
                    "loop": True,
                    "startTime": 1.5,
                },
            )
            source = root / "assets" / "source.mp4"
            source.parent.mkdir()
            source.write_bytes(b"source")
            value = load_background_video(manifest)
            self.assertTrue(value.is_video)
            self.assertEqual(value.source_path, "assets/source.mp4")
            self.assertEqual(value.fit, "contain")
            self.assertEqual(value.position, "bottom-right")
            self.assertEqual(manifest.native_video_overlay.local_path, "compiled.mp4")

    def test_loads_static_background_image(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "theme"
            manifest = self.make_theme(
                root,
                background_image={
                    "sourcePath": "assets/source.png",
                    "fit": "cover",
                    "position": "top-left",
                },
            )
            source = root / "assets" / "source.png"
            source.parent.mkdir()
            source.write_bytes(b"png")
            value = load_background_image(manifest)
            self.assertTrue(value.is_image)
            self.assertEqual(value.position, "top-left")
            self.assertEqual(value.start_time, 0)
            self.assertIsNone(load_background_video(manifest))

    def test_save_image_replaces_video_and_removes_encoding_bypass(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "theme"
            manifest = self.make_theme(root)
            payload = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            payload["nativeVideoOverlay"]["allowOriginalEncoding"] = True
            payload["nativeVideoOverlay"]["backgroundVideo"] = {
                "sourcePath": "assets/old.mp4",
            }
            (root / "assets").mkdir()
            (root / "assets" / "old.mp4").write_bytes(b"old")
            (root / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
            manifest = ThemeManifest.load(root)
            selected = Path(temporary) / "wallpaper.png"
            selected.write_bytes(b"image")
            updated = save_background_image(
                manifest,
                source=selected,
                fit="contain",
                position="center",
            )
            source = updated.root / "assets" / "background-image.png"
            self.assertEqual(source.read_bytes(), b"image")
            saved = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            native = saved["nativeVideoOverlay"]
            self.assertNotIn("allowOriginalEncoding", native)
            self.assertNotIn("backgroundVideo", native)
            self.assertEqual(
                native["backgroundImage"]["sourcePath"],
                "assets/background-image.png",
            )
            self.assertTrue(load_background_media(updated).is_image)

    def test_save_video_replaces_image(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "theme"
            manifest = self.make_theme(
                root,
                background_image={"sourcePath": "assets/old.jpg"},
            )
            (root / "assets").mkdir()
            (root / "assets" / "old.jpg").write_bytes(b"old")
            selected = Path(temporary) / "portal.mp4"
            selected.write_bytes(b"video")
            updated = save_background_video(
                manifest,
                source=selected,
                fit="cover",
                position="center",
                loop=True,
                start_time=0,
            )
            saved = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            native = saved["nativeVideoOverlay"]
            self.assertNotIn("backgroundImage", native)
            self.assertEqual(
                native["backgroundVideo"]["sourcePath"],
                "assets/background-video.mp4",
            )
            self.assertTrue(load_background_media(updated).is_video)

    def test_video_command_composites_and_uses_safe_profile(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "theme"
            manifest = self.make_theme(root)
            source = root / "assets" / "source.mp4"
            source.parent.mkdir()
            source.write_bytes(b"source")
            background = HtmlBackgroundVideo("assets/source.mp4")
            command = image_pipe_ffmpeg_command(
                root / "compiled.mp4",
                manifest=manifest,
                frame_count=192,
                background=background,
                ffmpeg="ffmpeg",
            )
            joined = " ".join(command)
            self.assertIn("-stream_loop -1", joined)
            self.assertIn("[background][html]overlay=0:0", joined)
            self.assertIn("-profile:v baseline", joined)
            self.assertIn("-bf 0", joined)
            self.assertIn("-frames:v 192", joined)

    def test_image_command_holds_static_frame_for_entire_theme(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "theme"
            manifest = self.make_theme(root)
            source = root / "assets" / "source.png"
            source.parent.mkdir()
            source.write_bytes(b"source")
            background = HtmlBackgroundMedia("assets/source.png")
            command = image_pipe_ffmpeg_command(
                root / "compiled.mp4",
                manifest=manifest,
                frame_count=192,
                background=background,
                ffmpeg="ffmpeg",
            )
            joined = " ".join(command)
            self.assertIn("-loop 1 -framerate 24", joined)
            self.assertNotIn("-stream_loop", command)
            self.assertIn("trim=duration=8.000000", joined)
            self.assertIn("[background][html]overlay=0:0", joined)

    def test_remove_background_removes_configuration_and_managed_source(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "theme"
            manifest = self.make_theme(
                root,
                background_image={
                    "sourcePath": "assets/background-image.webp",
                },
            )
            source = root / "assets" / "background-image.webp"
            source.parent.mkdir()
            source.write_bytes(b"image")
            updated = remove_background_media(manifest)
            self.assertFalse(source.exists())
            self.assertIsNone(load_background_media(updated))

    def test_rejects_both_image_and_video_backgrounds(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "theme"
            manifest = self.make_theme(
                root,
                background_video={"sourcePath": "assets/source.mp4"},
                background_image={"sourcePath": "assets/source.png"},
            )
            with self.assertRaises(ThemeValidationError):
                load_background_media(manifest, require_file=False)

    def test_rejects_source_that_escapes_theme(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "theme"
            manifest = self.make_theme(
                root,
                background_image={"sourcePath": "../outside.png"},
            )
            with self.assertRaises(ThemeValidationError):
                load_background_media(manifest, require_file=False)


if __name__ == "__main__":
    unittest.main()
