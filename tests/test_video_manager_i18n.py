from pathlib import Path
import unittest


class VideoManagerI18nContractTests(unittest.TestCase):
    def test_video_manager_i18n_has_expected_translation_keys(self):
        source = Path("library/video_manager_i18n.py").read_text(encoding="utf-8")
        for key in (
            "Video Manager",
            "Refresh video list",
            "Stop current video",
            "Storage",
            "Videos on display",
            "Import and prepare media…",
            "Upload compatible MP4…",
            "Play video",
            "Delete video",
            "Communicating with the display…",
        ):
            self.assertIn(key, source)

    def test_video_manager_i18n_wraps_window_lifecycle(self):
        source = Path("library/video_manager_i18n.py").read_text(encoding="utf-8")
        self.assertIn("def install_video_manager_i18n(app)", source)
        self.assertIn("window_class.__init__ = init_with_i18n", source)
        self.assertIn("window_class.run_backend = run_backend_with_i18n", source)
        self.assertIn("translate_widget_tree(self)", source)

    def test_video_manager_launcher_installs_i18n_after_backend_patch(self):
        source = Path("video-manager-gtk.py").read_text(encoding="utf-8")
        self.assertIn("def install_i18n(app)", source)
        self.assertIn("install_structured_backend(app)", source)
        self.assertIn("install_i18n(app)", source)
        self.assertLess(
            source.index("install_structured_backend(app)"),
            source.index("install_i18n(app)"),
        )


if __name__ == "__main__":
    unittest.main()
