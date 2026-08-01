from __future__ import annotations

import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from library import tray_icon_runtime
from library.tray_icon import (
    TRAY_ICON_NAME,
    ensure_status_icon_theme,
    grayscale_image,
    load_pystray_image,
    status_notifier_pixmaps,
)


class FakeVariant:
    def __init__(self, signature, value):
        self.signature = signature
        self.value = value


class FakeNotifier:
    def _on_get_property(
        self,
        _connection,
        _sender,
        _object_path,
        _interface_name,
        property_name,
    ):
        return FakeVariant("s", f"original:{property_name}")


class TrayIconTests(unittest.TestCase):
    def setUp(self):
        ensure_status_icon_theme.cache_clear()
        tray_icon_runtime._INSTALLED = False

    def tearDown(self):
        ensure_status_icon_theme.cache_clear()
        tray_icon_runtime._INSTALLED = False

    def create_project_icon(self, root: Path) -> Path:
        source = root / "res" / "icons" / "monitor-icon-17865" / "64.png"
        source.parent.mkdir(parents=True)
        image = Image.new("RGBA", (2, 2))
        image.putdata(
            [
                (255, 0, 0, 255),
                (0, 255, 0, 96),
                (255, 0, 0, 255),
                (0, 255, 0, 96),
            ]
        )
        image.save(source)
        return source

    def test_grayscale_preserves_alpha(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = self.create_project_icon(Path(temporary))
            image = grayscale_image(source, size=2)

        pixels = list(image.getdata())
        self.assertEqual(image.mode, "RGBA")
        for red, green, blue, _alpha in pixels:
            self.assertEqual(red, green)
            self.assertEqual(green, blue)
        self.assertEqual(pixels[0][3], 255)
        self.assertEqual(pixels[1][3], 96)

    def test_pystray_uses_the_generated_grayscale_image(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.create_project_icon(root)
            image = load_pystray_image(root, size=16)

        self.assertEqual(image.size, (16, 16))
        red, green, blue, _alpha = image.getpixel((0, 0))
        self.assertEqual((red, green), (green, blue))

    def test_status_notifier_pixmap_uses_argb_network_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.create_project_icon(root)
            pixmaps = status_notifier_pixmaps(root, sizes=(2,))

        width, height, payload = pixmaps[0]
        self.assertEqual((width, height), (2, 2))
        self.assertEqual(len(payload), width * height * 4)
        alpha, red, green, blue = payload[:4]
        self.assertEqual(alpha, 255)
        self.assertEqual(red, green)
        self.assertEqual(green, blue)

    def test_cached_hicolor_theme_contains_all_status_sizes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            cache = Path(temporary) / "cache"
            self.create_project_icon(root)
            with mock.patch.dict(os.environ, {"XDG_CACHE_HOME": str(cache)}):
                theme_path = ensure_status_icon_theme(str(root), (16, 32, 64))

            index = theme_path / "hicolor" / "index.theme"
            self.assertTrue(index.is_file())
            text = index.read_text(encoding="utf-8")
            for size in (16, 32, 64):
                icon = (
                    theme_path
                    / "hicolor"
                    / f"{size}x{size}"
                    / "status"
                    / f"{TRAY_ICON_NAME}.png"
                )
                self.assertTrue(icon.is_file())
                self.assertIn(f"{size}x{size}/status", text)

    def test_runtime_patch_advertises_icon_name_theme_and_pixmap(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            cache = Path(temporary) / "cache"
            self.create_project_icon(root)
            module = types.SimpleNamespace(
                ROOT=root,
                APP_NAME="Turing Smart Screen",
                GLib=types.SimpleNamespace(Variant=FakeVariant),
                StatusNotifierItem=FakeNotifier,
                STATUS_NOTIFIER_XML=(
                    '<property name="IconName" type="s" access="read"/>\n'
                ),
                read_current_theme=lambda: "default",
            )

            with mock.patch.dict(os.environ, {"XDG_CACHE_HOME": str(cache)}):
                tray_icon_runtime.install_status_notifier_grayscale_icon(module)
                notifier = module.StatusNotifierItem()
                icon_name = notifier._on_get_property(
                    None, None, None, None, "IconName"
                )
                icon_path = notifier._on_get_property(
                    None, None, None, None, "IconThemePath"
                )
                icon_pixmap = notifier._on_get_property(
                    None, None, None, None, "IconPixmap"
                )

        self.assertIn("IconPixmap", module.STATUS_NOTIFIER_XML)
        self.assertEqual(icon_name.value, TRAY_ICON_NAME)
        self.assertEqual(icon_path.signature, "s")
        self.assertTrue(icon_path.value.endswith("tray-icons"))
        self.assertEqual(icon_pixmap.signature, "a(iiay)")
        self.assertTrue(icon_pixmap.value)


if __name__ == "__main__":
    unittest.main()
