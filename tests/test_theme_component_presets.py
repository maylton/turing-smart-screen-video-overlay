from __future__ import annotations

import copy
import unittest

from library.theme_component_presets import (
    COMPONENT_TYPES,
    apply_component_preset,
    component_preset_ids,
    get_component_preset,
    list_component_presets,
    resolve_component_values,
    validate_component_registry,
)
from library.theme_engine_presets import resolve_semantic_tokens


EXPECTED_IDS = [
    "typography_display_clock",
    "typography_metric_value",
    "typography_small_label",
    "effects_soft_depth",
    "effects_video_readable",
    "bar_primary",
    "bar_success",
    "radial_primary",
    "radial_warning",
    "line_graph_primary",
    "line_graph_muted",
    "data_palette_status",
]


class ThemeComponentPresetTests(unittest.TestCase):
    def test_expected_ids_exist_in_order(self):
        self.assertEqual(component_preset_ids(), EXPECTED_IDS)

    def test_ids_are_unique(self):
        ids = component_preset_ids()
        self.assertEqual(len(ids), len(set(ids)))

    def test_component_types_are_valid(self):
        for preset in list_component_presets():
            self.assertIn(preset["component_type"], COMPONENT_TYPES)

    def test_filter_by_component_type(self):
        self.assertEqual(
            component_preset_ids("typography"),
            [
                "typography_display_clock",
                "typography_metric_value",
                "typography_small_label",
            ],
        )
        self.assertEqual(component_preset_ids("bar"), ["bar_primary", "bar_success"])

    def test_get_component_preset_returns_copy(self):
        first = get_component_preset("bar_primary")
        first["values"]["BAR_COLOR"]["$token"] = "DANGER"
        second = get_component_preset("bar_primary")
        self.assertEqual(second["values"]["BAR_COLOR"]["$token"], "PRIMARY")

    def test_list_component_presets_returns_copies(self):
        first = list_component_presets()
        first[0]["values"]["FONT_SIZE"] = 1
        second = list_component_presets()
        self.assertEqual(second[0]["values"]["FONT_SIZE"], 96)

    def test_unknown_component_preset_raises_clear_error(self):
        with self.assertRaisesRegex(KeyError, "Unknown component preset"):
            get_component_preset("missing")

    def test_registry_validates(self):
        self.assertEqual(validate_component_registry(), [])

    def test_resolve_component_values_without_tokens_keeps_token_refs(self):
        values = resolve_component_values("bar_primary")
        self.assertEqual(values["BAR_COLOR"], {"$token": "PRIMARY"})

    def test_resolve_component_values_with_tokens_returns_rgb_lists(self):
        tokens = resolve_semantic_tokens("technical_data_dark")
        values = resolve_component_values("bar_primary", tokens)
        self.assertEqual(values["BAR_COLOR"], [120, 169, 255])
        self.assertEqual(values["BAR_BACKGROUND_COLOR"], [57, 57, 57])

    def test_missing_semantic_token_raises_clear_error(self):
        with self.assertRaisesRegex(KeyError, "Missing semantic token"):
            resolve_component_values("bar_primary", {"SURFACE_ALT": [1, 2, 3]})

    def test_apply_component_preset_does_not_modify_original_node(self):
        node = {"BAR_COLOR": [1, 2, 3], "BAR_BACKGROUND_COLOR": [4, 5, 6]}
        original = copy.deepcopy(node)
        apply_component_preset(
            node,
            "bar_primary",
            resolve_semantic_tokens("technical_data_dark"),
        )
        self.assertEqual(node, original)

    def test_apply_updates_only_existing_top_level_keys(self):
        node = {"BAR_COLOR": [1, 2, 3]}
        applied = apply_component_preset(
            node,
            "bar_primary",
            resolve_semantic_tokens("technical_data_dark"),
        )
        self.assertEqual(applied, {"BAR_COLOR": [120, 169, 255]})
        self.assertNotIn("BAR_BACKGROUND_COLOR", applied)
        self.assertNotIn("BAR_OUTLINE", applied)

    def test_apply_preserves_geometry_and_text(self):
        node = {
            "X": 10,
            "Y": 20,
            "WIDTH": 100,
            "HEIGHT": 40,
            "TEXT": "CPU",
            "FONT_SIZE": 20,
            "ALIGN": "left",
            "FONT_COLOR": [1, 2, 3],
        }
        applied = apply_component_preset(
            node,
            "typography_metric_value",
            resolve_semantic_tokens("technical_data_dark"),
        )
        self.assertEqual(applied["X"], 10)
        self.assertEqual(applied["Y"], 20)
        self.assertEqual(applied["TEXT"], "CPU")
        self.assertEqual(applied["FONT_SIZE"], 32)
        self.assertEqual(applied["FONT_COLOR"], [244, 244, 244])

    def test_apply_does_not_add_absent_font_color(self):
        applied = apply_component_preset(
            {"FONT_SIZE": 20},
            "typography_small_label",
            resolve_semantic_tokens("technical_data_dark"),
        )
        self.assertEqual(applied, {"FONT_SIZE": 16})

    def test_effect_preset_updates_existing_nested_keys_only(self):
        node = {
            "EFFECTS": {
                "SHADOW": {"ENABLED": False, "COLOR": [1, 2, 3]},
                "OUTLINE": {"ENABLED": False, "WIDTH": 1},
            }
        }
        applied = apply_component_preset(
            node,
            "effects_video_readable",
            resolve_semantic_tokens("video_overlay_readable"),
        )
        self.assertEqual(applied["EFFECTS"]["SHADOW"]["ENABLED"], True)
        self.assertEqual(applied["EFFECTS"]["SHADOW"]["COLOR"], [0, 0, 0, 200])
        self.assertNotIn("OFFSET_X", applied["EFFECTS"]["SHADOW"])
        self.assertNotIn("GLOW", applied["EFFECTS"])
        self.assertEqual(applied["EFFECTS"]["OUTLINE"]["WIDTH"], 2)

    def test_apply_does_not_add_effects_section(self):
        applied = apply_component_preset(
            {"FONT_COLOR": [1, 2, 3]},
            "effects_soft_depth",
            resolve_semantic_tokens("technical_data_dark"),
        )
        self.assertEqual(applied, {"FONT_COLOR": [1, 2, 3]})

    def test_line_graph_preset_maps_line_and_axis_colors(self):
        node = {"LINE_COLOR": [1, 2, 3], "AXIS_COLOR": [4, 5, 6]}
        applied = apply_component_preset(
            node,
            "line_graph_muted",
            resolve_semantic_tokens("technical_data_dark"),
        )
        self.assertEqual(applied["LINE_COLOR"], [69, 137, 255])
        self.assertEqual(applied["AXIS_COLOR"], [57, 57, 57])

    def test_radial_preset_updates_existing_line_width(self):
        node = {"LINE_WIDTH": 2, "BAR_COLOR": [1, 2, 3]}
        applied = apply_component_preset(
            node,
            "radial_warning",
            resolve_semantic_tokens("technical_data_dark"),
        )
        self.assertEqual(applied["LINE_WIDTH"], 8)
        self.assertEqual(applied["BAR_COLOR"], [241, 194, 27])

    def test_data_palette_updates_existing_semantic_fields(self):
        node = {
            "FONT_COLOR": [1, 2, 3],
            "DISPLAY_RGB_LED": [4, 5, 6],
            "BACKGROUND_IMAGE": "background.png",
        }
        applied = apply_component_preset(
            node,
            "data_palette_status",
            resolve_semantic_tokens("technical_data_dark"),
        )
        self.assertEqual(applied["FONT_COLOR"], [244, 244, 244])
        self.assertEqual(applied["DISPLAY_RGB_LED"], [120, 169, 255])
        self.assertEqual(applied["BACKGROUND_IMAGE"], "background.png")

    def test_applied_color_lists_are_independent(self):
        node = {"BAR_COLOR": [1, 2, 3], "LINE_COLOR": [4, 5, 6]}
        applied = apply_component_preset(
            node,
            "data_palette_status",
            resolve_semantic_tokens("technical_data_dark"),
        )
        self.assertIsNot(applied["BAR_COLOR"], applied["LINE_COLOR"])
        applied["BAR_COLOR"][0] = 0
        self.assertEqual(applied["LINE_COLOR"], [120, 169, 255])


if __name__ == "__main__":
    unittest.main()
