from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path

from library.html_theme_background_editor import (
    _preview_data_uri,
    _preview_image_script,
)


class HtmlThemeBackgroundEditorTests(unittest.TestCase):
    def test_image_preview_is_embedded_as_data_uri(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "background.png"
            source.write_bytes(b"png-preview")
            uri = _preview_data_uri(source, "image")
            self.assertTrue(uri.startswith("data:image/png;base64,"))
            payload = uri.split(",", 1)[1]
            self.assertEqual(base64.b64decode(payload), b"png-preview")

    def test_video_preview_uses_extracted_png_frame(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "background.mp4"
            source.write_bytes(b"video")
            calls = []

            def extractor(video, destination, *, timestamp):
                calls.append((Path(video), float(timestamp)))
                Path(destination).write_bytes(b"static-frame")

            uri = _preview_data_uri(
                source,
                "video",
                timestamp=1.25,
                extractor=extractor,
            )
            self.assertEqual(calls, [(source.resolve(), 1.25)])
            self.assertTrue(uri.startswith("data:image/png;base64,"))
            payload = uri.split(",", 1)[1]
            self.assertEqual(base64.b64decode(payload), b"static-frame")

    def test_preview_script_never_starts_webkit_media(self):
        script = _preview_image_script(
            "data:image/png;base64,cHJldmlldw==",
            "cover",
            "center",
        )
        self.assertIn("document.createElement('img')", script)
        self.assertNotIn("createElement('video')", script)
        self.assertNotIn(".play(", script)
        self.assertNotIn("autoplay", script)
        self.assertNotIn("muted", script)
        self.assertNotIn("currentTime", script)

    def test_background_editor_source_contains_no_media_playback(self):
        source = Path("library/html_theme_background_editor.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("createElement('video')", source)
        self.assertNotIn(".play(", source)
        self.assertNotIn("autoplay", source)
        self.assertNotIn("loadedmetadata", source)


if __name__ == "__main__":
    unittest.main()
