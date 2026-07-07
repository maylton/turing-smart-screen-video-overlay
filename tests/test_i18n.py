import os
import unittest
from unittest import mock

from library import i18n


class I18nTests(unittest.TestCase):
    def test_defaults_to_english_when_locale_is_not_portuguese(self):
        with mock.patch.dict(
            os.environ,
            {"TURING_SMART_SCREEN_LANG": "en_US"},
            clear=True,
        ):
            self.assertEqual(i18n.active_language(), "en")
            self.assertEqual(i18n.t("Settings"), "Settings")
            self.assertEqual(i18n.t("Show window"), "Show window")

    def test_uses_portuguese_from_override_locale(self):
        with mock.patch.dict(
            os.environ,
            {"TURING_SMART_SCREEN_LANG": "pt_BR"},
            clear=True,
        ):
            self.assertEqual(i18n.active_language(), "pt_BR")
            self.assertEqual(i18n.t("Settings"), "Configurações")
            self.assertEqual(i18n.t("Show window"), "Mostrar janela")
            self.assertEqual(i18n.t("Turn off screen"), "Desligar tela")
            self.assertEqual(i18n.t("Gallery"), "Galeria")
            self.assertEqual(i18n.t("Apply + Start"), "Aplicar + Iniciar")

    def test_uses_portuguese_from_system_locale_environment(self):
        with mock.patch.dict(
            os.environ,
            {"LANG": "pt_BR.UTF-8"},
            clear=True,
        ):
            self.assertEqual(i18n.active_language(), "pt_BR")

    def test_language_label_is_translated_locale_name(self):
        with mock.patch.dict(
            os.environ,
            {"TURING_SMART_SCREEN_LANG": "pt-BR"},
            clear=True,
        ):
            self.assertEqual(i18n.active_language_label(), "Português (Brasil)")

    def test_formats_translated_messages(self):
        with mock.patch.dict(
            os.environ,
            {"TURING_SMART_SCREEN_LANG": "pt_BR"},
            clear=True,
        ):
            self.assertEqual(
                i18n.tr("Theme: {theme}", theme="solar"),
                "Tema: solar",
            )

    def test_gtk_shell_catalog_has_no_missing_portuguese_translations(self):
        missing = i18n.missing_translations(i18n.GTK_SHELL_MESSAGES)
        self.assertEqual(missing, [])

    def test_main_app_polish_catalog_has_no_missing_portuguese_translations(self):
        missing = i18n.missing_translations(i18n.MAIN_APP_POLISH_MESSAGES)
        self.assertEqual(missing, [])

    def test_tray_catalog_has_no_missing_portuguese_translations(self):
        missing = i18n.missing_translations(i18n.TRAY_MESSAGES)
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
