import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from library.html_background_video import (
    image_pipe_ffmpeg_command,
    load_background_video,
    save_background_video,
)
from library.html_theme_background_compat import ensure_native_video_overlay
from library.theme_engine import ThemeManifest, ThemeValidationError


class HtmlThemeBackgroundCompatTests(unittest.TestCase):
    def make_plain_theme(self, root: Path, *, width: int = 480) -> ThemeManifest:
        root.mkdir(parents=True)
        (root / "index.html").write_text(
            "<!doctype html><html><body></body></html>",
            encoding="utf-8",
        )
        (root / "manifest.json").write_text(
            json.dumps(
                {
                    "engine": "html",
                    "name": "Imported Theme",
                    "version": 1,
                    "display": {"width": width, "height": 480},
                    "refreshRate": 2,
                    "entrypoint": "index.html",
                    "permissions": ["sensors"],
                    "network": False,
                }
            ),
            encoding="utf-8",
        )
        return ThemeManifest.load(root)

    def test_plain_html_theme_gets_native_video_defaults(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "dbz-nimbus"
            manifest = self.make_plain_theme(root)

            upgraded = ensure_native_video_overlay(manifest)

            spec = upgraded.native_video_overlay
            self.assertIsNotNone(spec)
            self.assertEqual(spec.local_path, "dbz-nimbus-background.mp4")
            self.assertEqual(
                spec.device_path,
                "/mnt/SDCARD/video/dbz-nimbus-background.mp4",
            )
            self.assertEqual(spec.fps, 24)
            self.assertEqual(spec.duration, 8)
            self.assertEqual(spec.background_frame, 0)

    def test_gif_can_be_saved_and_composited_after_upgrade(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "dbz-nimbus"
            manifest = ensure_native_video_overlay(self.make_plain_theme(root))
            selected = Path(temporary) / "goku.gif"
            selected.write_bytes(b"GIF89a")

            updated = save_background_video(
                manifest,
                source=selected,
                fit="cover",
                position="center",
                loop=True,
                start_time=0,
            )
            background = load_background_video(updated)

            self.assertIsNotNone(background)
            self.assertEqual(
                background.source_path,
                "assets/background-video.gif",
            )
            command = image_pipe_ffmpeg_command(
                root / "dbz-nimbus-background.mp4",
                manifest=updated,
                frame_count=192,
                background=background,
                ffmpeg="ffmpeg",
            )
            joined = " ".join(command)
            self.assertIn("-stream_loop -1", joined)
            self.assertIn("assets/background-video.gif", joined)
            self.assertIn("-c:v libx264", joined)
            self.assertIn("-frames:v 192", joined)

    def test_non_square_theme_is_not_auto_upgraded(self):
        with TemporaryDirectory() as temporary:
            manifest = self.make_plain_theme(
                Path(temporary) / "wide-theme",
                width=800,
            )
            with self.assertRaises(ThemeValidationError):
                ensure_native_video_overlay(manifest)


if __name__ == "__main__":
    unittest.main()
