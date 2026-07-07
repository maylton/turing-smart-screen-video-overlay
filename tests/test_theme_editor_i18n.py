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

    def test_theme_editor_i18n_has_tree_and_property_translation_keys(self):
        source = Path("library/theme_editor_i18n.py").read_text(encoding="utf-8")
        for key in (
            "Available to add",
            "Content",
            "Custom text",
            "Configuration",
            "Video and background",
            "System metrics",
            "Percentage",
            "Graph",
            "Line graph",
            "Frequency",
            "Temperature",
            "Fan speed",
            "Weather",
            "Active theme",
            "Choose the target smart screen size.",
            "DISPLAY_SIZE",
            "DISPLAY_ORIENTATION",
            "Landscape",
            "Portrait",
        ):
            self.assertIn(key, source)

    def test_theme_editor_preset_catalog_has_expected_translations(self):
        source = Path("library/theme_editor_preset_i18n.py").read_text(encoding="utf-8")
        for key in (
            "Content",
            "System",
            "Information",
            "Network",
            "Custom text",
            "Static image",
            "CPU usage",
            "CPU usage % bar + text",
            "CPU temperature",
            "RAM usage",
            "GPU usage",
            "GPU usage % bar + text",
            "GPU temperature",
            "GPU memory usage",
            "Disk usage",
            "Internet download",
            "Internet upload",
            "System uptime",
        ):
            self.assertIn(key, source)
        self.assertIn('" — ".join(translated)', source)

    def test_theme_editor_property_rows_have_expected_translations(self):
        source = Path("library/theme_editor_preset_i18n.py").read_text(encoding="utf-8")
        for key in (
            "Radial gauge preset",
            "Text component preset",
            "Text style preset",
            "Graph bar preset",
            "Choose a preset…",
            "No gradient configured",
            "Apply a safe starter layout to this selected component.",
            "Apply values to the current text fields.",
            "BACKGROUND_IMAGE",
            "PREVIEW_BACKGROUND",
            "LOCAL_PATH",
            "Current — ",
            "Disabled",
            "Top left",
            "Choose an image from this theme folder.",
        ):
            self.assertIn(key, source)
        self.assertIn("def _dynamic_pt", source)
        self.assertIn('r"(\\d+) steps"', source)

    def test_theme_editor_graph_bar_property_labels_are_translated(self):
        source = Path("library/theme_editor_preset_i18n.py").read_text(encoding="utf-8")
        for key in (
            "BAR_BACKGROUND_COLOR",
            "ORIENTATION",
            "BAR_OUTLINE",
            "REVERSE_DIRECTION",
            "DRAW_BAR_BACKGROUND",
            "Choose how this GRAPH bar fills.",
            "Horizontal",
            "Vertical",
            "Auto",
        ):
            self.assertIn(key, source)

    def test_theme_editor_i18n_translates_dynamic_summaries_and_catalog_choices(self):
        source = Path("library/theme_editor_i18n.py").read_text(encoding="utf-8")
        self.assertIn("def _translate_visibility_summary", source)
        self.assertIn('r"(\\d+) visible · (\\d+) hidden"', source)
        self.assertIn("def _translate_catalog_choice", source)
        self.assertIn('" — "', source)
        self.assertIn("_translate_theme_editor_dynamic", source)
        self.assertIn("dynamic = _translate_theme_editor_dynamic(message)", source)

    def test_theme_editor_i18n_uses_class_creation_hook_but_startup_does_not_load_it(self):
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

    def test_theme_editor_uses_safe_widget_i18n_patch_at_startup(self):
        source = Path("library/theme_editor_widget_i18n.py").read_text(encoding="utf-8")
        startup_source = Path("usercustomize.py").read_text(encoding="utf-8")
        background_source = Path("library/theme_video_background.py").read_text(
            encoding="utf-8"
        )
        inline_source = Path("library/main_app_inline_theme_editor.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def install()", source)
        self.assertIn("_patch_init(cls)", source)
        self.assertIn("_patch_text_method(cls, method_name)", source)
        self.assertIn("_patch_dialog_response", source)
        self.assertIn("_patch_string_list(Gtk)", source)
        self.assertIn("def _patch_dropdown_new_from_strings", source)
        self.assertIn('getattr(Gtk, "DropDown", None)', source)
        self.assertIn("new_from_strings_with_i18n", source)
        self.assertIn("original_append", source)
        self.assertIn("original_splice", source)
        self.assertIn("library.theme_editor_preset_i18n", source)
        self.assertIn("install_theme_editor_widget_i18n()", startup_source)
        self.assertNotIn("install_theme_editor_i18n_class_hook", startup_source)
        self.assertNotIn("install_theme_editor_i18n_class_hook", background_source)
        self.assertNotIn("theme_editor_property_layout_i18n", inline_source)


if __name__ == "__main__":
    unittest.main()
