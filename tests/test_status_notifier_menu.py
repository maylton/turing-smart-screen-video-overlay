import os
from pathlib import Path
from unittest import mock
import unittest

from library import main_app, main_app_base


def make_item():
    # Bypass __init__: it registers on the session bus.
    return main_app.StatusNotifierItem.__new__(main_app.StatusNotifierItem)


def make_menu(window_visible=True):
    menu = main_app.StatusNotifierMenu.__new__(main_app.StatusNotifierMenu)
    menu.window_visible = lambda: window_visible
    return menu


class StatusNotifierMenuContractTests(unittest.TestCase):
    def test_exports_dbusmenu_path(self):
        self.assertEqual(main_app_base.DBUSMENU_OBJECT_PATH, "/StatusNotifierItem/Menu")
        with mock.patch.object(main_app_base, "read_current_theme", return_value="demo"):
            value = make_item()._on_get_property(None, None, None, None, "Menu")
        self.assertEqual(value.unpack(), "/StatusNotifierItem/Menu")

    def test_implements_canonical_dbusmenu(self):
        source = Path("library/main_app_base.py").read_text(encoding="utf-8")
        self.assertIn("com.canonical.dbusmenu", source)
        self.assertIn("class StatusNotifierMenu", source)
        self.assertIn("GetLayout", source)
        self.assertIn("Event", source)

    def test_menu_labels_are_translated(self):
        with mock.patch.dict(os.environ, {"TURING_SMART_SCREEN_LANG": "pt_BR"}):
            labels = {
                action: make_menu().menu_label(action)
                for action in (
                    "show-hide-window",
                    "start-screen",
                    "turn-off-screen",
                    "open-theme-editor",
                    "open-video-manager",
                    "quit",
                )
            }
            hidden_label = make_menu(window_visible=False).menu_label("show-hide-window")
        self.assertEqual(labels["show-hide-window"], "Ocultar janela")
        self.assertEqual(hidden_label, "Mostrar janela")
        self.assertEqual(labels["start-screen"], "Iniciar tela")
        self.assertEqual(labels["turn-off-screen"], "Desligar tela")
        self.assertEqual(labels["open-theme-editor"], "Abrir editor de tema")
        self.assertEqual(labels["open-video-manager"], "Abrir gerenciador de vídeos")
        self.assertEqual(labels["quit"], "Sair")


if __name__ == "__main__":
    unittest.main()
