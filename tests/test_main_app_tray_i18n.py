from pathlib import Path
import unittest


class MainAppTrayI18nContractTests(unittest.TestCase):
    def test_tray_i18n_installer_patches_status_notifier_classes(self):
        source = Path("library/main_app_i18n.py").read_text(encoding="utf-8")
        self.assertIn("def install_main_app_tray_i18n(app)", source)
        self.assertIn("StatusNotifierMenu.menu_label = menu_label", source)
        self.assertIn(
            "StatusNotifierItem._on_get_property = status_notifier_get_property",
            source,
        )
        self.assertIn('tr("Theme: {theme}", theme=theme)', source)

    def test_tray_i18n_uses_stable_english_keys(self):
        source = Path("library/main_app_i18n.py").read_text(encoding="utf-8")
        for key in (
            "Show window",
            "Hide window",
            "Start screen",
            "Turn off screen",
            "Open theme editor",
            "Open video manager",
            "Quit",
            "not selected",
        ):
            self.assertIn(key, source)

    def test_usercustomize_loads_tray_i18n_for_gtk_shell_entrypoints(self):
        source = Path("usercustomize.py").read_text(encoding="utf-8")
        self.assertIn("_GTK_SHELL_ENTRY_POINTS", source)
        self.assertIn('"configure-gtk.py"', source)
        self.assertIn('"turing-smart-screen"', source)
        self.assertIn("return _entry_point_name() in _GTK_SHELL_ENTRY_POINTS", source)
        self.assertIn("install_main_app_tray_i18n", source)
        self.assertIn("_install_tray_i18n_import_hook()", source)


if __name__ == "__main__":
    unittest.main()
