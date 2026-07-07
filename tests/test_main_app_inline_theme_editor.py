from pathlib import Path
import unittest


class MainAppInlineThemeEditorContractTests(unittest.TestCase):
    def test_inline_theme_editor_builder_loads_editor_without_standalone_main(self):
        source = Path("library/main_app_inline_theme_editor.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def build_inline_theme_editor_page", source)
        self.assertIn("importlib.util.spec_from_file_location", source)
        self.assertIn("theme-editor-gtk.py", source)
        self.assertIn("ThemeEditorWindow", source)
        self.assertIn("editor.set_content(None)", source)
        self.assertIn("page._theme_editor_window = editor", source)
        self.assertIn("editor._embedded_dialog_parent = page", source)

    def test_inline_theme_editor_installs_widget_i18n_explicitly(self):
        source = Path("library/main_app_inline_theme_editor.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("from library.theme_editor_widget_i18n import install as install_widget_i18n", source)
        self.assertIn("install_widget_i18n()", source)
        self.assertIn("from library.theme_editor_i18n import translate_widget_tree", source)
        self.assertIn("translate_widget_tree(page)", source)

    def test_main_app_routes_theme_editor_actions_inline(self):
        source = Path("library/main_app_diagnostics_integration.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def _open_theme_editor_factory", source)
        self.assertIn("build_inline_theme_editor_page", source)
        self.assertIn('page_name = "theme-editor"', source)
        self.assertIn("window_class.open_theme_editor = open_theme_editor", source)
        self.assertIn("window_class.open_theme_editor_record = open_theme_editor_record", source)

    def test_theme_gallery_edit_actions_are_routed_to_inline_editor(self):
        source = Path("library/main_app_diagnostics_integration.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def _install_theme_gallery_editor_route", source)
        self.assertIn("gallery.launch_theme_editor = launch_theme_editor_inline", source)
        self.assertIn("opener = getattr(window, \"open_theme_editor_record\", None)", source)
        self.assertIn("_install_theme_gallery_editor_route(self)", source)


if __name__ == "__main__":
    unittest.main()
