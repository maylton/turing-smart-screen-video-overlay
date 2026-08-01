from pathlib import Path
import unittest


class MediaPreparationI18nContractTests(unittest.TestCase):
    def test_media_preparation_i18n_has_expected_translation_keys(self):
        source = Path("library/media_preparation_i18n.py").read_text(encoding="utf-8")
        for key in (
            "Media preparation",
            "Display profile",
            "Source information",
            "Framing and size",
            "Crop source",
            "Background",
            "Timing and output",
            "Framing preview",
            "Convert",
            "Preview output",
            "Upload",
            "Converting media…",
            "Uploading prepared video…",
        ):
            self.assertIn(key, source)

    def test_media_preparation_i18n_wraps_runtime_callbacks(self):
        source = Path("library/media_preparation_i18n.py").read_text(encoding="utf-8")
        self.assertIn("def install_media_preparation_i18n(app)", source)
        self.assertIn("window_class.__init__ = init_with_i18n", source)
        self.assertIn("window_class.run_json = run_json_with_i18n", source)
        self.assertIn("window_class.show_error = show_error_with_i18n", source)
        self.assertIn("window_class.on_conversion_complete = on_conversion_complete_with_i18n", source)
        self.assertIn("_translate_static_models(app, self)", source)

    def test_media_preparation_launcher_installs_i18n(self):
        source = Path("media-preparation-gtk.py").read_text(encoding="utf-8")
        self.assertIn("def install_i18n()", source)
        self.assertIn("install_media_preparation_i18n(app)", source)
        self.assertIn("install_i18n()", source)
        self.assertIn("app.MediaPreparationApplication().run(sys.argv)", source)


if __name__ == "__main__":
    unittest.main()
