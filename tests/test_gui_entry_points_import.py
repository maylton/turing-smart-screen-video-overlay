"""Load every GTK entry point so a removed or renamed import fails a test.

Source-text checks elsewhere cannot see that a name imported by a script no
longer exists in the library (the HTML editor stopped opening that way).
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _gtk_stack_available() -> bool:
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        gi.require_version("WebKit", "6.0")
        from gi.repository import Adw, Gtk, WebKit  # noqa: F401
    except (ImportError, ValueError):
        return False
    return True


ENTRY_POINTS = (
    "configure-gtk.py",
    "html-theme-editor-gtk.py",
    "theme-editor-gtk.py",
    "video_manager_gtk_app.py",
    "media_preparation_gtk_app.py",
)


@unittest.skipUnless(_gtk_stack_available(), "GTK 4, libadwaita or WebKitGTK 6 is unavailable")
class GuiEntryPointImportTests(unittest.TestCase):
    def test_entry_points_import(self):
        for name in ENTRY_POINTS:
            path = ROOT / name
            if not path.is_file():
                continue
            with self.subTest(entry_point=name):
                module_name = "_entry_" + path.stem.replace("-", "_")
                spec = importlib.util.spec_from_file_location(module_name, path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)


if __name__ == "__main__":
    unittest.main()
