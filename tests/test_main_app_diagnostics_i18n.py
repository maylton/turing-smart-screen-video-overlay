from pathlib import Path
import unittest


class MainAppDiagnosticsI18nContractTests(unittest.TestCase):
    def test_diagnostics_lookup_accepts_translated_widget_text(self):
        source = Path("library/main_app_diagnostics_integration.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def _translated_values(value: str)", source)
        self.assertIn("from library.i18n import t as _", source)
        self.assertIn("def _matches_translated_value", source)
        self.assertIn('_matches_translated_value(_widget_title(widget), title)', source)
        self.assertIn('_matches_translated_value(_widget_label(child), "Settings")', source)

    def test_diagnostics_still_targets_english_stable_keys(self):
        source = Path("library/main_app_diagnostics_integration.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('_has_titled_widget(root, "Diagnostics")', source)
        self.assertIn('_find_titled_widget(root, "Maintenance")', source)


if __name__ == "__main__":
    unittest.main()
