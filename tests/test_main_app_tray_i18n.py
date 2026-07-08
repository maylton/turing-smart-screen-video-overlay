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

    def test_shell_i18n_wraps_main_window_lifecycle(self):
        source = Path("library/main_app_i18n.py").read_text(encoding="utf-8")
        self.assertIn("def install_main_app_shell_i18n(app)", source)
        self.assertIn("translate_widget_tree(self)", source)
        self.assertIn("window_class.__init__ = init_with_i18n", source)
        self.assertIn("window_class.build_settings_page = build_settings_page_with_i18n", source)
        self.assertIn("window_class.refresh_overview = refresh_overview_with_i18n", source)

    def test_shell_i18n_wraps_dynamic_updates_and_toasts(self):
        source = Path("library/main_app_i18n.py").read_text(encoding="utf-8")
        self.assertIn("def translate_main_app_text", source)
        self.assertIn("_EXACT_PT_BR", source)
        self.assertIn("_PREFIX_PT_BR", source)
        self.assertIn("window_class.toast = toast_with_i18n", source)
        for method_name in (
            "build_themes_page",
            "refresh_theme_list",
            "on_theme_selected",
            "finish_display_detection",
            "finish_turn_off_display",
            "show_checkup_result",
        ):
            self.assertIn(f'"{method_name}"', source)
        self.assertIn("_wrap_translate_after(window_class, method_name)", source)

    def test_shell_i18n_has_dynamic_theme_and_runtime_strings(self):
        source = Path("library/main_app_i18n.py").read_text(encoding="utf-8")
        for key in (
            "Installed themes",
            "Theme preview",
            "Set active theme",
            "No theme selected",
            "Showing themes compatible with the selected ",
            "Expected folder:\n",
            "No active theme configured",
            "Monitor started",
            "Display turned off",
            "Could not turn off display: ",
        ):
            self.assertIn(key, source)

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

    def test_usercustomize_installs_ctrl_c_traceback_guard_for_gtk_shell(self):
        source = Path("usercustomize.py").read_text(encoding="utf-8")
        self.assertIn("def _install_gtk_ctrl_c_handler", source)
        self.assertIn("except KeyboardInterrupt", source)
        self.assertIn("return 130", source)
        self.assertIn("application_class.run = run_without_keyboard_interrupt_traceback", source)
        self.assertIn("_install_gtk_ctrl_c_handler(module)", source)

    def test_main_app_integrations_install_shell_i18n_directly(self):
        source = Path("library/main_app_diagnostics_integration.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('label="main-shell-i18n"', source)
        self.assertIn("library.main_app_i18n", source)
        self.assertIn("install_main_app_shell_i18n", source)


if __name__ == "__main__":
    unittest.main()
