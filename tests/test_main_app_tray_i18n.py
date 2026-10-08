from pathlib import Path
import unittest


def assert_source_contains(testcase, source: str, needle: str) -> None:
    testcase.assertIn(needle, source, msg=f"Missing expected source fragment: {needle!r}")


class MainAppTrayI18nContractTests(unittest.TestCase):
    def test_tray_i18n_installer_patches_status_notifier_classes(self):
        source = Path("library/main_app_i18n.py").read_text(encoding="utf-8")
        assert_source_contains(self, source, "def install_main_app_tray_i18n(app)")
        assert_source_contains(self, source, "StatusNotifierMenu.menu_label = menu_label")
        assert_source_contains(
            self,
            source,
            "StatusNotifierItem._on_get_property = status_notifier_get_property",
        )
        assert_source_contains(self, source, 'tr("Theme: {theme}", theme=theme)')

    def test_shell_i18n_wraps_main_window_lifecycle(self):
        source = Path("library/main_app_i18n.py").read_text(encoding="utf-8")
        assert_source_contains(self, source, "def install_main_app_shell_i18n(app)")
        assert_source_contains(self, source, "translate_widget_tree(self)")
        assert_source_contains(self, source, "window_class.__init__ = init_with_i18n")
        assert_source_contains(self, source, "window_class.build_settings_page = build_settings_page_with_i18n")
        assert_source_contains(self, source, "window_class.refresh_overview = refresh_overview_with_i18n")

    def test_shell_i18n_wraps_dynamic_updates_and_toasts(self):
        source = Path("library/main_app_i18n.py").read_text(encoding="utf-8")
        assert_source_contains(self, source, "def translate_main_app_text")
        assert_source_contains(self, source, "_EXACT_PT_BR")
        assert_source_contains(self, source, "_PREFIX_PT_BR")
        assert_source_contains(self, source, "window_class.toast = toast_with_i18n")
        for method_name in (
            "build_themes_page",
            "refresh_theme_list",
            "on_theme_selected",
            "finish_display_detection",
            "finish_turn_off_display",
            "show_checkup_result",
        ):
            assert_source_contains(self, source, f'"{method_name}"')
        assert_source_contains(self, source, "_wrap_translate_after(window_class, method_name)")

    def test_shell_i18n_has_dynamic_theme_and_runtime_strings(self):
        source = Path("library/main_app_i18n.py").read_text(encoding="utf-8")
        for key in (
            "Installed themes",
            "Theme preview",
            "Set active theme",
            "No theme selected",
            "Showing themes compatible with the selected ",
            r"Expected folder:\n",
            "No active theme configured",
            "Monitor started",
            "Display turned off",
            "Could not turn off display: ",
        ):
            assert_source_contains(self, source, key)

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
            assert_source_contains(self, source, key)

    def test_ctrl_c_in_the_launching_terminal_exits_quietly(self):
        import importlib.util
        from unittest import mock

        spec = importlib.util.spec_from_file_location("configure_gtk_app_ctrl_c", "configure_gtk_app.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        application = mock.Mock()
        application.run.side_effect = KeyboardInterrupt
        with mock.patch.object(module, "SmartScreenApplication", return_value=application):
            self.assertEqual(module.main(), 130)

    def test_main_app_integrations_install_shell_i18n_directly(self):
        source = Path("library/main_app_diagnostics_integration.py").read_text(
            encoding="utf-8"
        )
        assert_source_contains(self, source, 'label="main-shell-i18n"')
        assert_source_contains(self, source, "library.main_app_i18n")
        assert_source_contains(self, source, "install_main_app_shell_i18n")


if __name__ == "__main__":
    unittest.main()
