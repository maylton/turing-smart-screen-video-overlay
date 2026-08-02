from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from library.html_theme_authoring import (
    discover_overlay_candidates,
    inspect_native_video_artifact,
    save_html_theme_authoring,
    update_overlay_markers_text,
    write_native_video_build_state,
)
from library.theme_engine import ThemeManifest, ThemeValidationError


class HtmlThemeAuthoringTests(unittest.TestCase):
    def make_theme(self, root: Path) -> ThemeManifest:
        root.mkdir()
        (root / "index.html").write_text(
            """<!doctype html>
<div id="static">Static</div>
<strong id="cpu" data-turing-overlay>--%</strong>
<i class="bar" id="cpu-bar"></i>
""",
            encoding="utf-8",
        )
        (root / "style.css").write_text(".bar { width: 20%; }\n", encoding="utf-8")
        (root / "manifest.json").write_text(
            json.dumps(
                {
                    "engine": "html",
                    "name": "Test HTML",
                    "version": 1,
                    "display": {"width": 480, "height": 480},
                    "entrypoint": "index.html",
                    "permissions": ["sensors"],
                    "network": False,
                    "nativeVideoOverlay": {
                        "enabled": True,
                        "localPath": "background.mp4",
                        "devicePath": "/mnt/SDCARD/video/background.mp4",
                        "fps": 24,
                        "duration": 8,
                        "backgroundFrame": 0,
                    },
                }
            ),
            encoding="utf-8",
        )
        return ThemeManifest.load(root)

    def test_build_fingerprint_detects_missing_ready_and_stale_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "theme"
            manifest = self.make_theme(root)
            video = root / "background.mp4"

            self.assertEqual(inspect_native_video_artifact(manifest).status, "missing")

            video.write_bytes(b"fake deterministic video")
            write_native_video_build_state(manifest, video)
            self.assertEqual(inspect_native_video_artifact(manifest).status, "ready")

            (root / "style.css").write_text(".bar { width: 90%; }\n", encoding="utf-8")
            self.assertEqual(inspect_native_video_artifact(manifest).status, "stale")

            write_native_video_build_state(manifest, video)
            video.write_bytes(b"changed after build")
            self.assertEqual(inspect_native_video_artifact(manifest).status, "stale")

    def test_discovers_and_rewrites_explicit_overlay_markers(self):
        html = (
            '<div id="one" data-turing-overlay>1</div>'
            "<span class='x' id='two'>2</span>"
            '<p id="three" data-turing-overlay="yes">3</p>'
        )
        updated = update_overlay_markers_text(html, {"two", "three"})

        self.assertNotIn('id="one" data-turing-overlay', updated)
        self.assertIn("id='two' data-turing-overlay", updated)
        self.assertIn('id="three" data-turing-overlay', updated)
        self.assertNotIn('data-turing-overlay="yes"', updated)

    def test_saves_video_settings_and_overlay_selection_with_backups(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "theme"
            manifest = self.make_theme(root)
            candidates = discover_overlay_candidates(manifest)
            self.assertEqual(
                [(item.element_id, item.marked) for item in candidates],
                [("static", False), ("cpu", True), ("cpu-bar", False)],
            )

            saved = save_html_theme_authoring(
                manifest,
                fps=30,
                duration=6,
                background_frame=1,
                device_directory="/root/video",
                filename="compiled.mp4",
                overlay_ids=["cpu", "cpu-bar"],
            )

            self.assertEqual(saved.native_video_overlay.local_path, "compiled.mp4")
            self.assertEqual(
                saved.native_video_overlay.device_path,
                "/root/video/compiled.mp4",
            )
            html = (root / "index.html").read_text(encoding="utf-8")
            self.assertIn('id="cpu" data-turing-overlay', html)
            self.assertIn('id="cpu-bar" data-turing-overlay', html)
            self.assertNotIn('id="static" data-turing-overlay', html)
            self.assertTrue((root / "index.html.editor-backup").is_file())
            self.assertTrue((root / "manifest.json.editor-backup").is_file())
            self.assertEqual(inspect_native_video_artifact(saved).status, "missing")

    def test_rejects_unknown_or_empty_overlay_selections(self):
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self.make_theme(Path(temporary) / "theme")
            for selected in ([], ["unknown"]):
                with self.subTest(selected=selected), self.assertRaises(ThemeValidationError):
                    save_html_theme_authoring(
                        manifest,
                        fps=24,
                        duration=8,
                        background_frame=0,
                        device_directory="/mnt/SDCARD/video",
                        filename="background.mp4",
                        overlay_ids=selected,
                    )


if __name__ == "__main__":
    unittest.main()
