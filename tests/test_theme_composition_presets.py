from __future__ import annotations

import copy
import unittest

from library.theme_composition_presets import (
    COMPOSITION_CATEGORIES,
    apply_composition_preset,
    composition_preset_ids,
    get_composition_preset,
    list_composition_presets,
    validate_composition_registry,
)


EXPECTED_IDS = [
    "video_hud_readable",
    "compact_metrics_grid",
    "monochrome_accessible_readout",
]


class ThemeCompositionPresetTests(unittest.TestCase):
    def test_expected_ids_exist_in_order(self):
        self.assertEqual(composition_preset_ids(), EXPECTED_IDS)

    def test_ids_are_unique(self):
        ids = composition_preset_ids()
        self.assertEqual(len(ids), len(set(ids)))

    def test_categories_are_valid(self):
        for preset in list_composition_presets():
            self.assertIn(preset["category"], COMPOSITION_CATEGORIES)

    def test_category_filter_works(self):
        self.assertEqual(composition_preset_ids("overlay"), ["video_hud_readable"])
        self.assertEqual(
            composition_preset_ids("accessibility"),
            ["monochrome_accessible_readout"],
        )
        self.assertEqual(composition_preset_ids("layout"), ["compact_metrics_grid"])

    def test_registry_validates(self):
        self.assertEqual(validate_composition_registry(), [])

    def test_unknown_composition_preset_raises_clear_error(self):
        with self.assertRaisesRegex(KeyError, "Unknown composition preset"):
            get_composition_preset("missing")

    def test_get_composition_preset_returns_copy(self):
        first = get_composition_preset("video_hud_readable")
        first["rules"][0]["component_preset_id"] = "bar_primary"
        second = get_composition_preset("video_hud_readable")
        self.assertEqual(
            second["rules"][0]["component_preset_id"],
            "effects_video_readable",
        )

    def test_list_composition_presets_returns_copies(self):
        first = list_composition_presets()
        first[0]["semantic_preset_id"] = "technical_data_dark"
        second = list_composition_presets()
        self.assertEqual(second[0]["semantic_preset_id"], "video_overlay_readable")

    def test_apply_does_not_modify_original_theme_data(self):
        theme = {"CPU": {"PERCENTAGE": {"TEXT": {"FONT_COLOR": [1, 2, 3]}}}}
        original = copy.deepcopy(theme)
        apply_composition_preset(theme, "compact_metrics_grid")
        self.assertEqual(theme, original)

    def test_compact_metrics_applies_semantic_colors(self):
        theme = {"BACKGROUND_COLOR": [1, 2, 3], "FONT_COLOR": [4, 5, 6]}
        applied = apply_composition_preset(theme, "compact_metrics_grid")
        self.assertEqual(applied["BACKGROUND_COLOR"], [38, 38, 38])
        self.assertEqual(applied["FONT_COLOR"], [244, 244, 244])

    def test_compact_metrics_applies_typography_by_path(self):
        theme = {
            "CPU": {
                "PERCENTAGE": {
                    "TEXT": {
                        "FONT_SIZE": 20,
                        "FONT_COLOR": [1, 2, 3],
                        "WIDTH": 100,
                    }
                }
            }
        }
        applied = apply_composition_preset(theme, "compact_metrics_grid")
        node = applied["CPU"]["PERCENTAGE"]["TEXT"]
        self.assertEqual(node["FONT_SIZE"], 32)
        self.assertEqual(node["FONT_COLOR"], [244, 244, 244])
        self.assertEqual(node["WIDTH"], 140)
        self.assertNotIn("HEIGHT", node)

    def test_video_hud_applies_clock_typography(self):
        theme = {
            "DATE": {
                "HOUR": {
                    "TEXT": {
                        "FONT_SIZE": 20,
                        "FONT_COLOR": [1, 2, 3],
                        "ALIGN": "left",
                    }
                }
            }
        }
        applied = apply_composition_preset(theme, "video_hud_readable")
        node = applied["DATE"]["HOUR"]["TEXT"]
        self.assertEqual(node["FONT_SIZE"], 96)
        self.assertEqual(node["FONT_COLOR"], [255, 255, 255])
        self.assertEqual(node["ALIGN"], "center")

    def test_static_clock_title_uses_clock_preset_only(self):
        theme = {
            "static_text": {
                "CLOCK_TITLE": {
                    "FONT_SIZE": 20,
                    "FONT_COLOR": [1, 2, 3],
                    "ALIGN": "left",
                    "WIDTH": 100,
                }
            }
        }
        applied = apply_composition_preset(theme, "video_hud_readable")
        node = applied["static_text"]["CLOCK_TITLE"]
        self.assertEqual(node["FONT_SIZE"], 96)
        self.assertEqual(node["ALIGN"], "center")
        self.assertEqual(node["WIDTH"], 480)

    def test_clock_rule_does_not_block_effect_rule(self):
        theme = {
            "static_text": {
                "CLOCK": {
                    "FONT_SIZE": 20,
                    "FONT_COLOR": [1, 2, 3],
                    "ALIGN": "left",
                    "EFFECTS": {
                        "SHADOW": {
                            "ENABLED": False,
                            "COLOR": [1, 2, 3, 4],
                        },
                        "OUTLINE": {
                            "ENABLED": False,
                            "WIDTH": 1,
                        },
                    },
                }
            }
        }
        applied = apply_composition_preset(theme, "video_hud_readable")
        node = applied["static_text"]["CLOCK"]
        self.assertEqual(node["FONT_SIZE"], 96)
        self.assertTrue(node["EFFECTS"]["SHADOW"]["ENABLED"])
        self.assertTrue(node["EFFECTS"]["OUTLINE"]["ENABLED"])

    def test_video_hud_preserves_background_color(self):
        theme = {"BACKGROUND_COLOR": [9, 8, 7], "FONT_COLOR": [1, 2, 3]}
        applied = apply_composition_preset(theme, "video_hud_readable")
        self.assertEqual(applied["BACKGROUND_COLOR"], [9, 8, 7])
        self.assertEqual(applied["FONT_COLOR"], [255, 255, 255])

    def test_effects_rule_updates_existing_nested_effect_fields(self):
        theme = {
            "static_text": {
                "TITLE": {
                    "EFFECTS": {
                        "SHADOW": {"ENABLED": False, "COLOR": [1, 2, 3]},
                        "OUTLINE": {"ENABLED": False, "WIDTH": 1},
                    }
                }
            }
        }
        applied = apply_composition_preset(theme, "video_hud_readable")
        effects = applied["static_text"]["TITLE"]["EFFECTS"]
        self.assertEqual(effects["SHADOW"]["ENABLED"], True)
        self.assertEqual(effects["SHADOW"]["COLOR"], [0, 0, 0, 200])
        self.assertNotIn("OFFSET_X", effects["SHADOW"])
        self.assertEqual(effects["OUTLINE"]["WIDTH"], 2)

    def test_rules_do_not_add_effects_section(self):
        theme = {"static_text": {"TITLE": {"FONT_COLOR": [1, 2, 3]}}}
        applied = apply_composition_preset(theme, "video_hud_readable")
        self.assertNotIn("EFFECTS", applied["static_text"]["TITLE"])

    def test_bar_rule_updates_existing_bar_fields(self):
        theme = {"CPU": {"PERCENTAGE": {"BAR_COLOR": [1, 2, 3]}}}
        applied = apply_composition_preset(theme, "compact_metrics_grid")
        self.assertEqual(applied["CPU"]["PERCENTAGE"]["BAR_COLOR"], [120, 169, 255])
        self.assertNotIn("BAR_BACKGROUND_COLOR", applied["CPU"]["PERCENTAGE"])

    def test_radial_rule_updates_existing_radial_fields(self):
        theme = {
            "CPU": {
                "PERCENTAGE": {
                    "RADIAL": {
                        "RADIUS": 90,
                        "WIDTH": 10,
                        "BAR_COLOR": [1, 2, 3],
                    }
                }
            }
        }
        applied = apply_composition_preset(theme, "compact_metrics_grid")
        node = applied["CPU"]["PERCENTAGE"]["RADIAL"]
        self.assertEqual(node["RADIUS"], 90)
        self.assertEqual(node["WIDTH"], 8)
        self.assertEqual(node["BAR_COLOR"], [120, 169, 255])

    def test_line_graph_rule_updates_existing_line_fields(self):
        theme = {"CPU": {"GRAPH": {"LINE_COLOR": [1, 2, 3], "AXIS_COLOR": [4, 5, 6]}}}
        applied = apply_composition_preset(theme, "compact_metrics_grid")
        self.assertEqual(applied["CPU"]["GRAPH"]["LINE_COLOR"], [120, 169, 255])
        self.assertEqual(applied["CPU"]["GRAPH"]["AXIS_COLOR"], [111, 111, 111])

    def test_accessible_readout_applies_monochrome_palette(self):
        theme = {"FONT_COLOR": [1, 2, 3], "BAR_COLOR": [4, 5, 6]}
        applied = apply_composition_preset(theme, "monochrome_accessible_readout")
        self.assertEqual(applied["FONT_COLOR"], [255, 255, 255])
        self.assertEqual(applied["BAR_COLOR"], [255, 255, 255])

    def test_nested_lists_are_traversed(self):
        theme = {"items": [{"FONT_COLOR": [1, 2, 3], "BAR_COLOR": [4, 5, 6]}]}
        applied = apply_composition_preset(theme, "monochrome_accessible_readout")
        self.assertEqual(applied["items"][0]["FONT_COLOR"], [255, 255, 255])
        self.assertEqual(applied["items"][0]["BAR_COLOR"], [255, 255, 255])

    def test_geometry_text_and_media_are_preserved(self):
        theme = {
            "X": 1,
            "Y": 2,
            "WIDTH": 3,
            "HEIGHT": 4,
            "TEXT": "CPU",
            "FORMAT": "short",
            "FONT": "roboto/Roboto.ttf",
            "PATH": "clip.mp4",
            "FONT_COLOR": [1, 2, 3],
        }
        applied = apply_composition_preset(theme, "compact_metrics_grid")
        self.assertEqual(applied["X"], 1)
        self.assertEqual(applied["Y"], 2)
        self.assertEqual(applied["WIDTH"], 3)
        self.assertEqual(applied["HEIGHT"], 4)
        self.assertEqual(applied["TEXT"], "CPU")
        self.assertEqual(applied["FORMAT"], "short")
        self.assertEqual(applied["FONT"], "roboto/Roboto.ttf")
        self.assertEqual(applied["PATH"], "clip.mp4")

    def test_empty_theme_returns_equivalent_empty_structure(self):
        applied = apply_composition_preset({}, "compact_metrics_grid")
        self.assertEqual(applied, {})
        self.assertIsNot(applied, {})

    def test_applied_color_lists_are_independent(self):
        theme = {"left": {"FONT_COLOR": [1, 2, 3]}, "right": {"FONT_COLOR": [4, 5, 6]}}
        applied = apply_composition_preset(theme, "compact_metrics_grid")
        self.assertIsNot(applied["left"]["FONT_COLOR"], applied["right"]["FONT_COLOR"])
        applied["left"]["FONT_COLOR"][0] = 0
        self.assertEqual(applied["right"]["FONT_COLOR"], [244, 244, 244])


if __name__ == "__main__":
    unittest.main()
