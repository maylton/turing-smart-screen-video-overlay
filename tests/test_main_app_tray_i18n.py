from pathlib import Path
import unittest


def assert_source_contains(testcase, source: str, needle: str) -> None:
    testcase.assertIn(needle, source, msg=f"Missing expected source fragment: {needle!r}")


class MainAppTrayI18nContractTests(unittest.TestCase):
    def test_tray_classes_include_the_translation_mixins(self):
        from library import main_app
        from library.main_app_i18n import TrayItemI18nMixin, TrayMenuI18nMixin

        self.assertTrue(issubclass(main_app.StatusNotifierMenu, TrayMenuI18nMixin))
        self.assertTrue(issubclass(main_app.StatusNotifierItem, TrayItemI18nMixin))
        source = Path("library/main_app_i18n.py").read_text(encoding="utf-8")
        assert_source_contains(self, source, 'tr("Theme: {theme}", theme=theme)')

    def test_window_translates_after_each_ui_build(self):
        from unittest import mock

        from library import main_app, main_app_i18n
        from library.main_app_i18n import I18nMixin

        mro = main_app.SmartScreenWindow.__mro__
        from library.main_app_diagnostics_integration import DiagnosticsMixin
        self.assertLess(mro.index(DiagnosticsMixin), mro.index(I18nMixin))

        calls = []

        class Base:
            def build_themes_page(self):
                calls.append("build")
                return "page"

            def toast(self, message):
                calls.append(("toast", message))

        class Window(I18nMixin, Base):
            pass

        with (
            mock.patch.object(main_app_i18n, "translate_widget_tree", side_effect=lambda widget: calls.append("translate")),
            mock.patch.object(main_app_i18n, "translate_main_app_text", side_effect=lambda text: f"pt:{text}"),
        ):
            window = Window.__new__(Window)
            self.assertEqual(window.build_themes_page(), "page")
            window.toast("Monitor started")
        self.assertEqual(calls, ["build", "translate", ("toast", "pt:Monitor started")])
        for name in (
            "build_themes_page",
            "refresh_theme_list",
            "on_theme_selected",
            "finish_display_detection",
            "finish_turn_off_display",
            "show_checkup_result",
        ):
            with self.subTest(method=name):
                self.assertIn(name, vars(I18nMixin))

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
        from unittest import mock

        from library import main_app

        application = mock.Mock()
        application.run.side_effect = KeyboardInterrupt
        with (
            mock.patch.object(main_app, "SmartScreenApplication", return_value=application),
            mock.patch.object(main_app, "install_theme_gallery_i18n"),
        ):
            self.assertEqual(main_app.main(), 130)

if __name__ == "__main__":
    unittest.main()
