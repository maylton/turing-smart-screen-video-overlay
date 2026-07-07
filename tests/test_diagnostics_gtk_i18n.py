from pathlib import Path
import unittest


class DiagnosticsGtkI18nContractTests(unittest.TestCase):
    def test_diagnostics_i18n_has_expected_translation_keys(self):
        source = Path("library/diagnostics_gtk_i18n.py").read_text(encoding="utf-8")
        for key in (
            "Turing Smart Screen Diagnostics",
            "Safe display, theme, runtime, and serial report",
            "Back to Settings",
            "Refresh diagnostics",
            "Copy diagnostics report",
            "Full report",
            "Diagnostics refreshed",
            "No monitor process detected",
        ):
            self.assertIn(key, source)

    def test_standalone_diagnostics_uses_i18n_helper(self):
        source = Path("diagnostics-gtk.py").read_text(encoding="utf-8")
        self.assertIn("library.diagnostics_gtk_i18n", source)
        self.assertIn('title=_("Turing Smart Screen Diagnostics")', source)
        self.assertIn('self.toast(_("Diagnostics refreshed"))', source)
        self.assertIn('theme_name = config.get("theme") or _("No theme")', source)

    def test_inline_diagnostics_uses_i18n_helper(self):
        source = Path("library/main_app_inline_diagnostics.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("library.diagnostics_gtk_i18n", source)
        self.assertIn('label=_("Diagnostics")', source)
        self.assertIn('label=_("Back to Settings")', source)
        self.assertIn('window.toast(_("Diagnostics refreshed"))', source)


if __name__ == "__main__":
    unittest.main()
