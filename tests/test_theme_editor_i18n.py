from pathlib import Path
import unittest


class ThemeEditorI18nContractTests(unittest.TestCase):
    def test_theme_editor_i18n_has_expected_translation_keys(self):
        source = Path("library/theme_editor_i18n.py").read_text(encoding="utf-8")
        for key in (
            "Theme editor",
            "Save",
            "Tools",
            "Video Inspector",
            "Generated Media",
            "Theme elements",
            "Search elements",
            "Show / Enable",
            "Hide / Disable",
            "Layer order",
            "Live preview",
            "Properties",
            "Apply property changes",
            "Text effects…",
            "Gradient effect",
            "Apply gradient",
            "Mode",
            "Mirror horizontally",
            "Output FPS",
        ):
            self.assertIn(key, source)

    def test_theme_editor_i18n_uses_class_creation_hook(self):
        source = Path("library/theme_editor_i18n.py").read_text(encoding="utf-8")
        self.assertIn("def install_theme_editor_i18n_class_hook()", source)
        self.assertIn("builtins.__build_class__", source)
        self.assertIn('if name == "ThemeEditorWindow"', source)
        self.assertIn("install_theme_editor_i18n(cls)", source)

    def test_theme_editor_i18n_wraps_window_lifecycle(self):
        source = Path("library/theme_editor_i18n.py").read_text(encoding="utf-8")
        self.assertIn("def install_theme_editor_i18n(window_class: type)", source)
        self.assertIn("window_class.__init__ = init_with_i18n", source)
        self.assertIn('"build_elements_panel"', source)
        self.assertIn('"build_properties_panel"', source)
        self.assertIn('"open_gradient_effect_editor"', source)
        self.assertIn('"open_video_tools"', source)
        self.assertIn("translate_widget_tree(self)", source)
        self.assertIn("window_class.toast = toast_with_i18n", source)
        self.assertIn("window_class.error_dialog = error_dialog_with_i18n", source)

    def test_theme_editor_i18n_patches_dialog_present_and_responses(self):
        source = Path("library/theme_editor_i18n.py").read_text(encoding="utf-8")
        self.assertIn("def install_theme_editor_dialog_i18n", source)
        self.assertIn("present_with_i18n", source)
        self.assertIn("add_response_with_i18n", source)
        self.assertIn("_translate_dialog_title(self)", source)
        self.assertIn("translate_widget_tree(self)", source)

    def test_theme_editor_runtime_i18n_hook_is_disabled_until_safe_direct_integration(self):
        background_source = Path("library/theme_video_background.py").read_text(
            encoding="utf-8"
        )
        startup_source = Path("usercustomize.py").read_text(encoding="utf-8")
        self.assertNotIn("install_theme_editor_i18n_class_hook", background_source)
        self.assertNotIn("install_theme_editor_i18n_class_hook", startup_source)


if __name__ == "__main__":
    unittest.main()
