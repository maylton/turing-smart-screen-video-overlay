from pathlib import Path
import unittest


class ThemeEditorI18nValueSafetyContractTests(unittest.TestCase):
    def test_widget_i18n_does_not_patch_entry_text_values(self):
        source = Path("library/theme_editor_widget_i18n.py").read_text(encoding="utf-8")
        self.assertNotIn('"set_text"', source)
        self.assertNotIn("set_text,", source)
        self.assertIn("set_label", source)
        self.assertIn("set_title", source)
        self.assertIn("set_subtitle", source)

    def test_component_presets_save_updates_not_translated_labels(self):
        source = Path("theme-editor-gtk.py").read_text(encoding="utf-8")
        self.assertIn("dropdown._theme_component_preset_updates", source)
        self.assertIn("updates = dropdown._theme_component_preset_updates", source)
        self.assertIn("for key, value in updates[index - 1].items():", source)
        self.assertIn("current[key] = copy.deepcopy(value)", source)

    def test_property_presets_keep_display_labels_separate_from_saved_values(self):
        source = Path("theme-editor-gtk.py").read_text(encoding="utf-8")
        self.assertIn("labels = tuple(label for label, _value in options)", source)
        self.assertIn("values = tuple(value for _label, value in options)", source)
        self.assertIn("dropdown._theme_preset_values = values", source)
        self.assertIn("preset_values = widget._theme_preset_values", source)
        self.assertIn("self.value_to_text(preset_values[index])", source)

    def test_text_style_presets_use_original_preset_names_for_updates(self):
        source = Path("theme-editor-gtk.py").read_text(encoding="utf-8")
        self.assertIn("preset_names = text_style_preset_names", source)
        self.assertIn("updates = text_style_updates(preset_names[index - 1], node)", source)
        self.assertIn("self.set_property_widget_value(key, value)", source)

    def test_choice_rows_use_canonical_values_not_translated_labels(self):
        source = Path("theme-editor-gtk.py").read_text(encoding="utf-8")
        self.assertIn("_theme_choice_values", source)
        self.assertIn("self.set_choice_widget_value", source)
        self.assertIn("self.parse_value(key, value, value)", source)

    def test_gradient_direction_saves_canonical_values(self):
        source = Path("theme-editor-gtk.py").read_text(encoding="utf-8")
        self.assertIn('(\"Auto\", \"auto\")', source)
        self.assertIn('(\"Horizontal\", \"horizontal\")', source)
        self.assertIn('(\"Vertical\", \"vertical\")', source)
        self.assertIn("direction_values = [value for _label, value in direction_options]", source)
        self.assertIn('"DIRECTION": direction_values[direction_row.get_selected()]', source)

    def test_safety_audit_document_exists(self):
        source = Path("docs/THEME_EDITOR_I18N_SAFETY.md").read_text(encoding="utf-8")
        self.assertIn("Theme Editor i18n value safety audit", source)
        self.assertIn("must remain canonical", source)
        self.assertIn("does **not** patch `set_text()`", source)


if __name__ == "__main__":
    unittest.main()
