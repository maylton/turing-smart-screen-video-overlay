from pathlib import Path
import unittest


class StatusNotifierMenuContractTests(unittest.TestCase):
    def setUp(self):
        self.source = Path("configure_gtk_app.py").read_text(encoding="utf-8")

    def test_exports_dbusmenu_path(self):
        self.assertIn(
            'DBUSMENU_OBJECT_PATH = "/StatusNotifierItem/Menu"',
            self.source,
        )
        self.assertIn('"Menu": GLib.Variant("o", DBUSMENU_OBJECT_PATH)', self.source)
        self.assertNotIn('"Menu": GLib.Variant("o", "/")', self.source)

    def test_implements_canonical_dbusmenu(self):
        self.assertIn("com.canonical.dbusmenu", self.source)
        self.assertIn("class StatusNotifierMenu", self.source)
        self.assertIn("GetLayout", self.source)
        self.assertIn("Event", self.source)

    def test_menu_labels_are_present(self):
        for label in (
            "Mostrar janela",
            "Ocultar janela",
            "Iniciar tela",
            "Desligar tela",
            "Abrir editor de tema",
            "Abrir gerenciador de vídeos",
            "Sair",
        ):
            self.assertIn(label, self.source)


if __name__ == "__main__":
    unittest.main()
