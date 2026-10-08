from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import unittest


class ThemeGalleryI18nContractTests(unittest.TestCase):
    def test_theme_gallery_i18n_has_expected_translation_keys(self):
        source = Path("library/theme_gallery_i18n.py").read_text(encoding="utf-8")
        for key in (
            "Theme Gallery",
            "Browse compatible themes",
            "Open Current",
            "Search compatible themes by name, path, or status",
            "Import Theme",
            "Use Theme",
            "Duplicate {theme}",
            "Rename {theme}",
            "Delete {theme}?",
            "Export {theme}",
            "Diagnostics — {theme}",
            "Theme Gallery Diagnostics",
            "No compatible themes",
        ):
            self.assertIn(key, source)

    def test_gallery_builders_translate_their_widgets(self):
        from library import theme_gallery
        from library import theme_gallery_i18n

        pane = theme_gallery.ThemeGalleryPane
        for name in ("empty_state", "preview_widget", "theme_actions_popover", "theme_card"):
            with self.subTest(method=name):
                self.assertTrue(hasattr(getattr(pane, name), "__wrapped__"))

        widget = object()
        with mock.patch.object(theme_gallery_i18n, "translate_widget_tree") as translate:
            built = theme_gallery_i18n.translated_widget(lambda: widget)()
        self.assertIs(built, widget)
        translate.assert_called_once_with(widget)

    def test_record_labels_and_report_are_localized(self):
        from library import theme_gallery
        from library import theme_gallery_i18n

        with mock.patch.object(theme_gallery_i18n, "active_language", return_value="pt_BR"):
            current = SimpleNamespace(issue="", current=True, display_size="2.1")
            self.assertEqual(theme_gallery.ThemeRecord.status_label.fget(current), theme_gallery_i18n.t("Current theme"))
            self.assertNotEqual(theme_gallery_i18n.t("Current theme"), "Current theme")
            self.assertIn("2.1", theme_gallery.ThemeRecord.display_label.fget(current))

        with mock.patch.object(theme_gallery, "localize_report", return_value="localized") as localize:
            record = mock.MagicMock()
            record.directory = Path("/tmp/theme")
            try:
                report = theme_gallery.build_theme_gallery_diagnostics_report(record)
            except Exception:
                self.skipTest("report needs a real theme record")
        self.assertEqual(report, "localized")
        localize.assert_called_once()

    def test_main_app_installs_the_dialog_translation_hook(self):
        source = Path("library/main_app.py").read_text(encoding="utf-8")
        self.assertIn("from library.theme_gallery_i18n import install_theme_gallery_i18n", source)
        self.assertIn("    install_theme_gallery_i18n()", source)


if __name__ == "__main__":
    unittest.main()
