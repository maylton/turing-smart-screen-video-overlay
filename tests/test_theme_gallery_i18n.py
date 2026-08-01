from pathlib import Path
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

    def test_theme_gallery_i18n_patches_records_dialogs_window_and_pane(self):
        source = Path("library/theme_gallery_i18n.py").read_text(encoding="utf-8")
        self.assertIn("def install_theme_gallery_i18n", source)
        self.assertIn("_install_dialog_i18n(gallery)", source)
        self.assertIn("_install_window_i18n(gallery)", source)
        self.assertIn("record_class.status_label = property(status_label)", source)
        self.assertIn("record_class.display_label = property(display_label)", source)
        self.assertIn("gallery.build_theme_gallery_diagnostics_report = build_report_i18n", source)
        self.assertIn("pane_class.__init__ = init_with_i18n", source)
        self.assertIn("pane_class.update_result_label = update_result_label_i18n", source)

    def test_theme_gallery_window_callback_guard_handles_constructor_order(self):
        source = Path("library/theme_gallery_i18n.py").read_text(encoding="utf-8")
        self.assertIn("def update_records_state_i18n", source)
        self.assertIn('if not hasattr(self, "gallery")', source)
        self.assertIn("self.update_records_state(list(self.gallery.records))", source)
        self.assertIn("window_class.update_records_state = update_records_state_i18n", source)

    def test_main_app_delegates_gallery_i18n_to_dedicated_helper(self):
        source = Path("library/main_app_i18n.py").read_text(encoding="utf-8")
        self.assertIn("from library.theme_gallery_i18n import install_theme_gallery_i18n as install", source)
        self.assertIn("install(app)", source)

    def test_standalone_gallery_launcher_loads_i18n(self):
        source = Path("theme-gallery-gtk.py").read_text(encoding="utf-8")
        self.assertIn("from library.theme_gallery_i18n import install_theme_gallery_i18n", source)
        self.assertIn("install_theme_gallery_i18n()", source)
        self.assertLess(
            source.index("install_theme_gallery_i18n()"),
            source.index("main(sys.argv)"),
        )


if __name__ == "__main__":
    unittest.main()
