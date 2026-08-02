from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock
import json
import math
import unittest

from PIL import Image

from library.html_hybrid import (
    OVERLAY_SELECTOR,
    base_layer_script,
    image_pipe_ffmpeg_command,
    overlay_frames_equal,
    overlay_layer_script,
    seek_animations_script,
    validate_native_video,
)
from library.html_renderer_worker import configured_display_size, schedule_once
from library.html_theme_video_builder import frame_count
from library.monitor_renderers import HtmlWorkerRunner
from library.renderer_lifecycle import RendererSelection
from library.theme_engine import ThemeManifest, ThemeValidationError


class HtmlHybridTests(unittest.TestCase):
    def make_theme(self, root: Path, video=None):
        root.mkdir()
        (root / "index.html").write_text("<!doctype html>", encoding="utf-8")
        payload = {
            "engine": "html",
            "name": "Hybrid",
            "version": 1,
            "display": {"width": 480, "height": 480},
            "entrypoint": "index.html",
            "permissions": ["sensors"],
            "network": False,
        }
        if video is not None:
            payload["nativeVideoOverlay"] = video
        (root / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
        return ThemeManifest.load(root)

    @staticmethod
    def valid_spec(**overrides):
        value = {
            "enabled": True,
            "localPath": "base.mp4",
            "devicePath": "/mnt/SDCARD/video/base.mp4",
            "fps": 24,
            "duration": 8,
            "backgroundFrame": 0,
        }
        value.update(overrides)
        return value

    def test_hybrid_is_opt_in_and_validated(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            plain = self.make_theme(root / "plain")
            hybrid = self.make_theme(root / "hybrid", self.valid_spec())
        self.assertIsNone(plain.native_video_overlay)
        self.assertEqual(hybrid.native_video_overlay.fps, 24)
        self.assertEqual(frame_count(hybrid), 192)

    def test_manifest_rejects_unsafe_video_contracts(self):
        invalid = (
            self.valid_spec(localPath="../base.mp4"),
            self.valid_spec(devicePath="/tmp/base.mp4"),
            self.valid_spec(devicePath="/mnt/SDCARD/video/other.mp4"),
            self.valid_spec(devicePath="/mnt/SDCARD/video/base\\.mp4"),
            self.valid_spec(
                localPath="base\n.mp4",
                devicePath="/mnt/SDCARD/video/base\n.mp4",
            ),
            self.valid_spec(fps=25),
            self.valid_spec(fps=24.5),
            self.valid_spec(duration=float("inf")),
            self.valid_spec(duration="8"),
            self.valid_spec(duration=1.01),
            self.valid_spec(backgroundFrame=7.99),
            self.valid_spec(backgroundFrame=0.01),
            self.valid_spec(backgroundFrame=True),
            self.valid_spec(overlaySelector="#value"),
        )
        for index, spec in enumerate(invalid):
            with self.subTest(spec=spec), TemporaryDirectory() as temporary:
                with self.assertRaises(ThemeValidationError):
                    self.make_theme(Path(temporary) / str(index), spec)

    def test_layer_scripts_preserve_layout_and_disable_live_animation(self):
        base = base_layer_script(OVERLAY_SELECTOR)
        overlay = overlay_layer_script(OVERLAY_SELECTOR)
        self.assertIn("'visibility','hidden'", base)
        self.assertNotIn("display:none", base)
        self.assertIn("'background','transparent'", overlay)
        self.assertIn("'animation','none'", overlay)
        self.assertIn("'visibility','visible'", overlay)
        self.assertIn("currentTime=time", seek_animations_script(125.0))

    def test_ffmpeg_pipe_uses_known_safe_physical_profile(self):
        command = image_pipe_ffmpeg_command(Path("out.mp4"), fps=24, ffmpeg="ffmpeg")
        joined = " ".join(command)
        self.assertIn("image2pipe", command)
        self.assertIn("-profile:v baseline", joined)
        self.assertIn("-bf 0", joined)
        self.assertIn("-pix_fmt yuv420p", joined)
        self.assertIn("-an", command)

    def test_video_preflight_happens_without_transport(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "theme"
            manifest = self.make_theme(root, self.valid_spec())
            (root / "base.mp4").write_bytes(b"video")
            probe = SimpleNamespace(
                issues=(), has_audio=False, fps=24.0, duration=8.0,
                container="mov,mp4,m4a,3gp,3g2,mj2",
                profile="Constrained Baseline", level=31, has_b_frames=0,
            )
            self.assertIs(validate_native_video(manifest, probe=lambda _path: probe), probe)

            invalid_probes = (
                SimpleNamespace(
                    issues=("codec must be H.264",), has_audio=False,
                    fps=24.0, duration=8.0, container="mov,mp4",
                    profile="Main", level=31, has_b_frames=1,
                ),
                SimpleNamespace(
                    issues=(), has_audio=False, fps=math.nan, duration=math.nan,
                    container="mov,mp4", profile="Constrained Baseline",
                    level=31, has_b_frames=0,
                ),
                SimpleNamespace(
                    issues=(), has_audio=False, fps=24.0, duration=8.0,
                    container="matroska,webm", profile="Constrained Baseline",
                    level=40, has_b_frames=0,
                ),
            )
            for invalid in invalid_probes:
                with self.subTest(probe=invalid), self.assertRaises(ThemeValidationError):
                    validate_native_video(manifest, probe=lambda _path, value=invalid: value)

    def test_overlay_comparison_includes_rgb_when_alpha_is_unchanged(self):
        red = Image.new("RGBA", (2, 2), (255, 0, 0, 255))
        green = Image.new("RGBA", (2, 2), (0, 255, 0, 255))
        self.assertFalse(overlay_frames_equal(red, green))
        self.assertTrue(overlay_frames_equal(red, red.copy()))

    def test_schedule_once_ignores_truthy_callback_return(self):
        class FakeGLib:
            callback = None

            @classmethod
            def timeout_add(cls, _delay, callback):
                cls.callback = callback
                return 42

        calls = []
        sources = set()
        schedule_once(FakeGLib, 12, lambda: calls.append(True) or True, sources)
        self.assertEqual(sources, {42})
        self.assertFalse(FakeGLib.callback())
        self.assertEqual(calls, [True])
        self.assertEqual(sources, set())

    def test_parent_preflight_runs_before_worker_process(self):
        selection = RendererSelection(
            "html",
            "hybrid",
            SimpleNamespace(native_video_overlay=object(), root=Path("/theme")),
        )
        runner = HtmlWorkerRunner(selection, root=Path.cwd())
        with mock.patch(
            "library.html_hybrid.validate_native_video",
            side_effect=ThemeValidationError("invalid media"),
        ):
            with mock.patch("library.monitor_renderers.subprocess.Popen") as popen:
                with self.assertRaisesRegex(ThemeValidationError, "invalid media"):
                    runner.start()
        popen.assert_not_called()

    def test_physical_size_hint_accepts_only_480_square_rev_c(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, size in (("small", '2.1"'), ("large", '5"')):
                theme = root / "res" / "themes" / name
                theme.mkdir(parents=True)
                (theme / "theme.yaml").write_text(
                    f'display:\n  DISPLAY_SIZE: {size}\n',
                    encoding="utf-8",
                )
            self.assertEqual(
                configured_display_size({"config": {"THEME": "small"}}, root),
                '2.1"',
            )
            self.assertNotIn(
                configured_display_size({"config": {"THEME": "large"}}, root),
                {'2.1"', '2.8"'},
            )


if __name__ == "__main__":
    unittest.main()
