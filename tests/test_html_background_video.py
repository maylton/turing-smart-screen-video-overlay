import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from library.html_background_video import (
    HtmlBackgroundVideo,
    image_pipe_ffmpeg_command,
    load_background_video,
    save_background_video,
)
from library.theme_engine import ThemeManifest, ThemeValidationError


class HtmlBackgroundVideoTests(unittest.TestCase):
    def make_theme(self, root: Path, *, background=None) -> ThemeManifest:
        root.mkdir(parents=True)
        (root / "index.html").write_text("<!doctype html><body></body>", encoding="utf-8")
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
        if background is not None:
            payload["nativeVideoOverlay"]["backgroundVideo"] = background
        (root / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
        return ThemeManifest.load(root)

    def test_loads_background_source_without_changing_native_artifact(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "theme"
            manifest = self.make_theme(
                root,
                background={
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
            self.assertEqual(value.source_path, "assets/source.mp4")
            self.assertEqual(value.fit, "contain")
            self.assertEqual(value.position, "bottom-right")
            self.assertEqual(manifest.native_video_overlay.local_path, "compiled.mp4")

    def test_save_copies_source_and_removes_original_encoding_bypass(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "theme"
            manifest = self.make_theme(root)
            payload = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            payload["nativeVideoOverlay"]["allowOriginalEncoding"] = True
            (root / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
            manifest = ThemeManifest.load(root)
            selected = Path(temporary) / "portal.mp4"
            selected.write_bytes(b"original")
            updated = save_background_video(
                manifest,
                source=selected,
                fit="cover",
                position="center",
                loop=True,
                start_time=0,
            )
            source = updated.root / "assets" / "background-source.mp4"
            self.assertEqual(source.read_bytes(), b"original")
            saved = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            self.assertNotIn("allowOriginalEncoding", saved["nativeVideoOverlay"])
            self.assertEqual(
                saved["nativeVideoOverlay"]["backgroundVideo"]["sourcePath"],
                "assets/background-source.mp4",
            )

    def test_command_composites_background_and_html_then_encodes_safe_profile(self):
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
            self.assertIn("-r 24", joined)
            self.assertIn("-frames:v 192", joined)

    def test_rejects_source_that_escapes_theme(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "theme"
            manifest = self.make_theme(
                root,
                background={"sourcePath": "../outside.mp4"},
            )
            with self.assertRaises(ThemeValidationError):
                load_background_video(manifest, require_file=False)


if __name__ == "__main__":
    unittest.main()
