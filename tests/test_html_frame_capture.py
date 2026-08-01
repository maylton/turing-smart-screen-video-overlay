from __future__ import annotations

import unittest
from pathlib import Path

from library.html_theme_engine import texture_png_bytes
from library.theme_engine import ThemeEngineError


class FakeGBytes:
    def __init__(self, payload):
        self.payload = payload

    def get_data(self):
        return self.payload


class MemoryTexture:
    def __init__(self, payload=b"\x89PNG\r\n\x1a\npayload"):
        self.payload = payload

    def save_to_png_bytes(self):
        return FakeGBytes(self.payload)


class FilenameTexture:
    def save_to_png(self, filename):
        Path(filename).write_bytes(b"\x89PNG\r\n\x1a\nfile")
        return True


class MissingTexture:
    pass


class HtmlFrameCaptureTests(unittest.TestCase):
    def test_memory_texture_is_serialized_without_disk_round_trip(self):
        payload = texture_png_bytes(MemoryTexture())
        self.assertTrue(payload.startswith(b"\x89PNG"))

    def test_filename_fallback_is_supported(self):
        payload = texture_png_bytes(FilenameTexture())
        self.assertEqual(payload, b"\x89PNG\r\n\x1a\nfile")

    def test_unsupported_texture_has_clear_error(self):
        with self.assertRaises(ThemeEngineError):
            texture_png_bytes(MissingTexture())


if __name__ == "__main__":
    unittest.main()
