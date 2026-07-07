from pathlib import Path
import unittest


class NativeVideoCompatibilityTests(unittest.TestCase):
    def test_converter_uses_conservative_h264_settings(self):
        source = Path("library/media_preparation.py").read_text(encoding="utf-8")
        self.assertIn("    fps: int = 24", source)
        for token in (
            '"-profile:v"',
            '"main"',
            '"-level:v"',
            '"3.1"',
            '"-bf"',
            '"1"',
            '"-maxrate"',
            '"2500k"',
            '"-bufsize"',
            '"5000k"',
        ):
            self.assertIn(token, source)

    def test_theme_editor_defaults_to_24_fps(self):
        source = Path("theme-editor-gtk.py").read_text(encoding="utf-8")
        self.assertIn("fps_row.set_selected(0)", source)


if __name__ == "__main__":
    unittest.main()
