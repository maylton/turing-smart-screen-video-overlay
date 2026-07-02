from __future__ import annotations

import copy
import unittest

from library.theme_text_style_presets import (
    is_text_style_node,
    text_effect_preset,
    text_effect_preset_names,
    text_style_preset_names,
    text_style_updates,
)


EXPECTED_STYLE_NAMES = [
    "Large clock",
    "Centered title",
    "Metric value",
    "Compact value",
    "Small label",
    "Caption",
]

EXPECTED_EFFECT_NAMES = [
    "None",
    "Soft shadow",
    "Strong shadow",
    "Subtle glow",
    "Neon glow",
    "Thin outline",
    "High-contrast outline",
    "Glow + outline",
    "Video overlay readable",
]

SECTION_FIELDS = {
    "SHADOW": {
        "ENABLED",
        "COLOR",
        "OFFSET_X",
        "OFFSET_Y",
        "BLUR_RADIUS",
    },
    "GLOW": {
        "ENABLED",
        "COLOR",
        "BLUR_RADIUS",
        "INTENSITY",
    },
    "OUTLINE": {
        "ENABLED",
        "COLOR",
        "WIDTH",
    },
}


class ThemeTextStylePresetTests(unittest.TestCase):
    def test_all_expected_text_style_names_exist(self):
        self.assertEqual(text_style_preset_names(), EXPECTED_STYLE_NAMES)

    def test_clock_context_only_offers_clock_presets(self):
        node = {"FORMAT": "short", "FONT": "Roboto.ttf", "FONT_SIZE": 96}
        self.assertEqual(
            text_style_preset_names(node, ("DATE", "HOUR", "TEXT")),
            ["Large clock"],
        )

    def test_percentage_context_does_not_offer_clock_presets(self):
        node = {"FONT_SIZE": 26, "ALIGN": "right", "TEXT": ""}
        names = text_style_preset_names(node, ("CPU", "PERCENTAGE", "TEXT"))
        self.assertEqual(names, ["Metric value", "Compact value"])
        self.assertNotIn("Large clock", names)

    def test_label_context_does_not_offer_metric_presets(self):
        node = {"TEXT": "TEMP. CPU", "FONT_SIZE": 25, "ALIGN": "left"}
        names = text_style_preset_names(node, ("static_text", "CPUTEMP_LABEL"))
        self.assertEqual(names, ["Centered title", "Small label", "Caption"])
        self.assertNotIn("Metric value", names)

    def test_all_expected_effect_names_exist(self):
        self.assertEqual(text_effect_preset_names(), EXPECTED_EFFECT_NAMES)

    def test_is_text_style_node_recognizes_static_text(self):
        node = {"TEXT": "Hello", "FONT_SIZE": 24, "FONT_COLOR": [255, 255, 255]}
        self.assertTrue(is_text_style_node(node))

    def test_is_text_style_node_recognizes_date_hour_format_and_font(self):
        node = {"FORMAT": "short", "FONT": "Roboto.ttf"}
        self.assertTrue(is_text_style_node(node))

    def test_is_text_style_node_rejects_non_text_graph(self):
        node = {"WIDTH": 120, "HEIGHT": 40, "MIN_VALUE": 0, "MAX_VALUE": 100}
        self.assertFalse(is_text_style_node(node))

    def test_text_style_updates_does_not_modify_original_node(self):
        node = {
            "FONT_SIZE": 20,
            "ALIGN": "left",
            "ANCHOR": "lt",
            "WIDTH": 100,
            "HEIGHT": 20,
        }
        original = copy.deepcopy(node)
        text_style_updates("Large clock", node)
        self.assertEqual(node, original)

    def test_text_style_updates_returns_only_existing_properties(self):
        node = {"FONT_SIZE": 20, "ALIGN": "left", "TEXT": "CPU"}
        self.assertEqual(
            text_style_updates("Large clock", node),
            {"FONT_SIZE": 96, "ALIGN": "center"},
        )

    def test_text_style_updates_does_not_return_x_or_y(self):
        node = {
            "X": 10,
            "Y": 20,
            "FONT_SIZE": 20,
            "ALIGN": "left",
            "ANCHOR": "lt",
            "WIDTH": 100,
            "HEIGHT": 20,
        }
        updates = text_style_updates("Large clock", node)
        self.assertNotIn("X", updates)
        self.assertNotIn("Y", updates)

    def test_text_style_presets_keep_expected_value_types(self):
        node = {
            "FONT_SIZE": 20,
            "ALIGN": "left",
            "ANCHOR": "lt",
            "WIDTH": 100,
            "HEIGHT": 20,
            "MIN_SIZE": 2,
        }
        updates = text_style_updates("Metric value", node)
        self.assertIsInstance(updates["FONT_SIZE"], int)
        self.assertIsInstance(updates["WIDTH"], int)
        self.assertIsInstance(updates["ALIGN"], str)
        self.assertIsInstance(updates["ANCHOR"], str)

    def test_text_style_updates_return_independent_objects(self):
        node = {"FONT_SIZE": 20, "ALIGN": "left"}
        first = text_style_updates("Large clock", node)
        second = text_style_updates("Large clock", node)
        self.assertIsNot(first, second)
        first["FONT_SIZE"] = 1
        self.assertEqual(second["FONT_SIZE"], 96)

    def test_effect_presets_have_required_sections_and_fields(self):
        for name in EXPECTED_EFFECT_NAMES:
            with self.subTest(name=name):
                preset = text_effect_preset(name)
                self.assertEqual(set(preset.keys()), set(SECTION_FIELDS.keys()))
                for section, fields in SECTION_FIELDS.items():
                    self.assertEqual(set(preset[section].keys()), fields)

    def test_effect_colors_have_valid_rgba_components(self):
        for name in EXPECTED_EFFECT_NAMES:
            preset = text_effect_preset(name)
            for section in SECTION_FIELDS:
                color = preset[section]["COLOR"]
                self.assertEqual(len(color), 4)
                self.assertTrue(all(0 <= component <= 255 for component in color))

    def test_effect_numeric_ranges_are_valid(self):
        for name in EXPECTED_EFFECT_NAMES:
            preset = text_effect_preset(name)
            self.assertGreaterEqual(preset["SHADOW"]["BLUR_RADIUS"], 0)
            self.assertGreaterEqual(preset["GLOW"]["BLUR_RADIUS"], 0)
            self.assertGreaterEqual(preset["GLOW"]["INTENSITY"], 1)
            self.assertLessEqual(preset["GLOW"]["INTENSITY"], 4)
            self.assertGreaterEqual(preset["OUTLINE"]["WIDTH"], 0)
            self.assertLessEqual(preset["OUTLINE"]["WIDTH"], 20)

    def test_none_preset_disables_all_effects(self):
        preset = text_effect_preset("None")
        self.assertFalse(preset["SHADOW"]["ENABLED"])
        self.assertFalse(preset["GLOW"]["ENABLED"])
        self.assertFalse(preset["OUTLINE"]["ENABLED"])

    def test_video_overlay_readable_enables_shadow_or_outline(self):
        preset = text_effect_preset("Video overlay readable")
        self.assertTrue(
            preset["SHADOW"]["ENABLED"] or preset["OUTLINE"]["ENABLED"]
        )

    def test_mutating_effect_preset_result_does_not_affect_future_calls(self):
        first = text_effect_preset("Soft shadow")
        first["SHADOW"]["COLOR"][0] = 255
        second = text_effect_preset("Soft shadow")
        self.assertEqual(second["SHADOW"]["COLOR"], [0, 0, 0, 150])

    def test_unknown_text_style_preset_raises_key_error(self):
        with self.assertRaisesRegex(KeyError, "Unknown text style preset"):
            text_style_updates("Missing", {"FONT_SIZE": 12})

    def test_unknown_effect_preset_raises_key_error(self):
        with self.assertRaisesRegex(KeyError, "Unknown text effect preset"):
            text_effect_preset("Missing")


if __name__ == "__main__":
    unittest.main()
