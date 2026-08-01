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
    DARK_THEME_TINT,
    LIGHT_THEME_TINT,
    TRAY_ICON_NAME,
    ensure_status_icon_theme,
    load_pystray_image,
    status_notifier_pixmaps,
    tray_icon_image,
)
from library.tray_icon_preferences import (
    MODE_COLOR,
    MODE_DARK_THEME,
    MODE_FOLLOW_THEME,
    MODE_LIGHT_THEME,
    load_tray_icon_mode,
    resolve_tray_icon_variant,
    save_tray_icon_mode,
)


class FakeVariant:
    def __init__(self, signature, value):
        self.signature = signature
        self.value = value


class FakeConnection:
    def __init__(self):
        self.signals = []

    def emit_signal(self, destination, path, interface, name, parameters):
        self.signals.append((destination, path, interface, name, parameters))


class FakeStyleManager:
    dark = True

    @classmethod
    def get_default(cls):
        return cls()

    def get_dark(self):
        return type(self).dark


class FakeNotifier:
    def __init__(self):
        self.connection = FakeConnection()

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
        FakeStyleManager.dark = True

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

    def fake_module(self, root: Path):
        return types.SimpleNamespace(
            ROOT=root,
            APP_ID="io.github.turing.SmartScreen",
            APP_NAME="Turing Smart Screen",
            TRAY_OBJECT_PATH="/StatusNotifierItem",
            GLib=types.SimpleNamespace(Variant=FakeVariant),
            Adw=types.SimpleNamespace(StyleManager=FakeStyleManager),
            StatusNotifierItem=FakeNotifier,
            STATUS_NOTIFIER_XML=(
                '<property name="IconName" type="s" access="read"/>\n'
            ),
            read_current_theme=lambda: "default",
        )

    def test_dark_theme_symbolic_tint_and_alpha(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = self.create_project_icon(Path(temporary))
            image = tray_icon_image(source, MODE_DARK_THEME, size=2)

        first = image.getpixel((0, 0))
        second = image.getpixel((1, 0))
        self.assertEqual(first[:3], DARK_THEME_TINT)
        self.assertEqual(second[:3], DARK_THEME_TINT)
        self.assertEqual(first[3], 235)
        self.assertEqual(second[3], 88)

    def test_light_theme_symbolic_tint(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = self.create_project_icon(Path(temporary))
            image = tray_icon_image(source, MODE_LIGHT_THEME, size=2)

        self.assertEqual(image.getpixel((0, 0))[:3], LIGHT_THEME_TINT)

    def test_color_variant_preserves_source_colors(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = self.create_project_icon(Path(temporary))
            image = tray_icon_image(source, MODE_COLOR, size=2)

        self.assertEqual(image.getpixel((0, 0)), (255, 0, 0, 255))
        self.assertEqual(image.getpixel((1, 0)), (0, 255, 0, 96))

    def test_preference_round_trip_is_atomic(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "tray-icon.conf"
            saved = save_tray_icon_mode(MODE_LIGHT_THEME, path)
            loaded = load_tray_icon_mode(path)

        self.assertEqual(saved, MODE_LIGHT_THEME)
        self.assertEqual(loaded, MODE_LIGHT_THEME)

    def test_follow_theme_resolves_both_symbolic_variants(self):
        self.assertEqual(
            resolve_tray_icon_variant(MODE_FOLLOW_THEME, dark_theme=True),
            MODE_DARK_THEME,
        )
        self.assertEqual(
            resolve_tray_icon_variant(MODE_FOLLOW_THEME, dark_theme=False),
            MODE_LIGHT_THEME,
        )

    def test_pystray_uses_persisted_variant(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            config = Path(temporary) / "config"
            self.create_project_icon(root)
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config)}):
                save_tray_icon_mode(MODE_LIGHT_THEME)
                image = load_pystray_image(root, size=2)

        self.assertEqual(image.getpixel((0, 0))[:3], LIGHT_THEME_TINT)

    def test_status_notifier_pixmap_uses_argb_network_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.create_project_icon(root)
            pixmaps = status_notifier_pixmaps(
                root,
                sizes=(2,),
                variant=MODE_DARK_THEME,
            )

        width, height, payload = pixmaps[0]
        self.assertEqual((width, height), (2, 2))
        self.assertEqual(len(payload), width * height * 4)
        alpha, red, green, blue = payload[:4]
        self.assertEqual(alpha, 235)
        self.assertEqual((red, green, blue), DARK_THEME_TINT)

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

    def test_caelestia_symbolic_mode_forces_icon_pixmap(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            config = Path(temporary) / "config"
            self.create_project_icon(root)
            module = self.fake_module(root)

            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config)}):
                save_tray_icon_mode(MODE_DARK_THEME)
                tray_icon_runtime.install_status_notifier_tray_icon(module)
                notifier = module.StatusNotifierItem()
                icon_name = notifier._on_get_property(
                    None, None, None, None, "IconName"
                )
                icon_pixmap = notifier._on_get_property(
                    None, None, None, None, "IconPixmap"
                )

        self.assertIn("IconPixmap", module.STATUS_NOTIFIER_XML)
        self.assertEqual(icon_name.value, "")
        self.assertEqual(icon_pixmap.signature, "a(iiay)")
        self.assertTrue(icon_pixmap.value)

    def test_color_mode_uses_application_icon_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            config = Path(temporary) / "config"
            self.create_project_icon(root)
            module = self.fake_module(root)

            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config)}):
                save_tray_icon_mode(MODE_COLOR)
                tray_icon_runtime.install_status_notifier_tray_icon(module)
                notifier = module.StatusNotifierItem()
                icon_name = notifier._on_get_property(
                    None, None, None, None, "IconName"
                )

        self.assertEqual(icon_name.value, module.APP_ID)

    def test_runtime_patch_repairs_later_property_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            config = Path(temporary) / "config"
            self.create_project_icon(root)
            module = self.fake_module(root)

            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config)}):
                save_tray_icon_mode(MODE_DARK_THEME)
                tray_icon_runtime.install_status_notifier_tray_icon(module)

                def translated_override(self, *_args):
                    return FakeVariant("s", module.APP_ID)

                module.StatusNotifierItem._on_get_property = translated_override
                tray_icon_runtime.install_status_notifier_tray_icon(module)
                notifier = module.StatusNotifierItem()
                icon_name = notifier._on_get_property(
                    None, None, None, None, "IconName"
                )

        self.assertEqual(icon_name.value, "")

    def test_refresh_emits_new_icon_and_tooltip(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            self.create_project_icon(root)
            module = self.fake_module(root)
            notifier = module.StatusNotifierItem()
            refreshed = tray_icon_runtime.refresh_status_notifier_icon(
                module,
                notifier,
            )

        self.assertTrue(refreshed)
        names = [signal[3] for signal in notifier.connection.signals]
        self.assertEqual(names, ["NewIcon", "NewToolTip"])


if __name__ == "__main__":
    unittest.main()
