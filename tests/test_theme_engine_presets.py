from __future__ import annotations

import copy
import unittest

from library.theme_engine_presets import (
    APPLICATION_POLICY_FIELDS,
    PROPERTY_COLOR_ROLES,
    REQUIRED_COLOR_ROLES,
    VALID_CATEGORIES,
    apply_theme_preset,
    get_preset,
    list_presets,
    preset_ids,
    resolve_semantic_tokens,
    validate_registry,
)


EXPECTED_IDS = [
    "tonal_expressive_dark",
    "tonal_expressive_light",
    "soft_neutral_dark",
    "soft_neutral_light",
    "technical_data_dark",
    "technical_data_light",
    "video_overlay_readable",
    "monochrome_high_contrast",
]


class ThemeEnginePresetTests(unittest.TestCase):
    def test_exactly_eight_expected_ids_exist(self):
        self.assertEqual(preset_ids(), EXPECTED_IDS)

    def test_ids_are_unique(self):
        ids = preset_ids()
        self.assertEqual(len(ids), len(set(ids)))

    def test_labels_are_not_empty(self):
        for preset in list_presets():
            self.assertTrue(preset["label"].strip())

    def test_categories_are_valid(self):
        for preset in list_presets():
            self.assertIn(preset["category"], VALID_CATEGORIES)

    def test_each_preset_contains_all_required_color_roles(self):
        for preset in list_presets():
            self.assertEqual(set(preset["tokens"].keys()), set(REQUIRED_COLOR_ROLES))

    def test_colors_have_exactly_three_components(self):
        for preset in list_presets():
            for color in preset["tokens"].values():
                self.assertEqual(len(color), 3)

    def test_color_components_are_ints(self):
        for preset in list_presets():
            for color in preset["tokens"].values():
                self.assertTrue(all(isinstance(component, int) for component in color))

    def test_color_components_are_rgb_range(self):
        for preset in list_presets():
            for color in preset["tokens"].values():
                self.assertTrue(all(0 <= component <= 255 for component in color))

    def test_versions_are_positive_integers(self):
        for preset in list_presets():
            self.assertIsInstance(preset["version"], int)
            self.assertGreaterEqual(preset["version"], 1)

    def test_application_policy_contains_all_fields(self):
        for preset in list_presets():
            self.assertEqual(
                set(preset["application_policy"].keys()),
                set(APPLICATION_POLICY_FIELDS),
            )

    def test_validate_registry_passes_current_registry(self):
        self.assertEqual(validate_registry(), [])

    def test_unknown_preset_raises_clear_error(self):
        with self.assertRaisesRegex(KeyError, "Unknown theme engine preset"):
            get_preset("missing")

    def test_get_preset_returns_independent_copy(self):
        first = get_preset("technical_data_dark")
        first["tokens"]["PRIMARY"][0] = 0
        second = get_preset("technical_data_dark")
        self.assertEqual(second["tokens"]["PRIMARY"], [120, 169, 255])

    def test_resolve_semantic_tokens_returns_independent_copy(self):
        first = resolve_semantic_tokens("technical_data_dark")
        first["PRIMARY"][0] = 0
        second = resolve_semantic_tokens("technical_data_dark")
        self.assertEqual(second["PRIMARY"], [120, 169, 255])

    def test_list_presets_returns_independent_copies(self):
        first = list_presets()
        first[0]["tokens"]["PRIMARY"][0] = 0
        second = list_presets()
        self.assertEqual(second[0]["tokens"]["PRIMARY"], [214, 174, 255])

    def test_category_filter_works(self):
        self.assertEqual(preset_ids("overlay"), ["video_overlay_readable"])
        self.assertEqual(
            preset_ids("accessibility"),
            ["monochrome_high_contrast"],
        )
        self.assertEqual(len(preset_ids("foundation")), 6)
        self.assertEqual(len(list_presets("foundation")), 6)

    def test_apply_does_not_modify_original_theme_data(self):
        theme = {"component": {"FONT_COLOR": "1, 2, 3"}}
        original = copy.deepcopy(theme)
        apply_theme_preset(theme, "technical_data_dark")
        self.assertEqual(theme, original)

    def test_font_color_maps_to_on_surface(self):
        applied = apply_theme_preset(
            {"FONT_COLOR": [1, 2, 3]},
            "technical_data_dark",
        )
        self.assertEqual(applied["FONT_COLOR"], [244, 244, 244])

    def test_background_color_maps_to_surface(self):
        applied = apply_theme_preset(
            {"BACKGROUND_COLOR": [1, 2, 3]},
            "technical_data_dark",
        )
        self.assertEqual(applied["BACKGROUND_COLOR"], [38, 38, 38])

    def test_bar_color_maps_to_primary(self):
        applied = apply_theme_preset(
            {"BAR_COLOR": [1, 2, 3]},
            "technical_data_dark",
        )
        self.assertEqual(applied["BAR_COLOR"], [120, 169, 255])

    def test_bar_background_color_maps_to_surface_alt(self):
        applied = apply_theme_preset(
            {"BAR_BACKGROUND_COLOR": [1, 2, 3]},
            "technical_data_dark",
        )
        self.assertEqual(applied["BAR_BACKGROUND_COLOR"], [57, 57, 57])

    def test_line_color_maps_to_primary(self):
        applied = apply_theme_preset(
            {"LINE_COLOR": [1, 2, 3]},
            "technical_data_dark",
        )
        self.assertEqual(applied["LINE_COLOR"], [120, 169, 255])

    def test_axis_color_maps_to_outline(self):
        applied = apply_theme_preset(
            {"AXIS_COLOR": [1, 2, 3]},
            "technical_data_dark",
        )
        self.assertEqual(applied["AXIS_COLOR"], [111, 111, 111])

    def test_display_rgb_led_maps_to_primary(self):
        applied = apply_theme_preset(
            {"DISPLAY_RGB_LED": [1, 2, 3]},
            "technical_data_dark",
        )
        self.assertEqual(applied["DISPLAY_RGB_LED"], [120, 169, 255])

    def test_all_mapped_properties_are_documented(self):
        self.assertEqual(
            set(PROPERTY_COLOR_ROLES.keys()),
            {
                "FONT_COLOR",
                "BACKGROUND_COLOR",
                "BAR_COLOR",
                "BAR_BACKGROUND_COLOR",
                "LINE_COLOR",
                "AXIS_COLOR",
                "DISPLAY_RGB_LED",
            },
        )

    def test_missing_properties_are_not_added(self):
        applied = apply_theme_preset({"TEXT": "CPU"}, "technical_data_dark")
        self.assertEqual(applied, {"TEXT": "CPU"})

    def test_nested_dicts_are_traversed(self):
        theme = {"CPU": {"PERCENTAGE": {"TEXT": {"FONT_COLOR": [1, 2, 3]}}}}
        applied = apply_theme_preset(theme, "technical_data_dark")
        self.assertEqual(
            applied["CPU"]["PERCENTAGE"]["TEXT"]["FONT_COLOR"],
            [244, 244, 244],
        )

    def test_nested_lists_are_traversed(self):
        theme = {"items": [{"LINE_COLOR": [1, 2, 3]}]}
        applied = apply_theme_preset(theme, "technical_data_dark")
        self.assertEqual(applied["items"][0]["LINE_COLOR"], [120, 169, 255])

    def test_x_and_y_are_preserved(self):
        theme = {"X": 10, "Y": 20, "FONT_COLOR": [1, 2, 3]}
        applied = apply_theme_preset(theme, "technical_data_dark")
        self.assertEqual(applied["X"], 10)
        self.assertEqual(applied["Y"], 20)

    def test_width_and_height_are_preserved(self):
        theme = {"WIDTH": 100, "HEIGHT": 40, "FONT_COLOR": [1, 2, 3]}
        applied = apply_theme_preset(theme, "technical_data_dark")
        self.assertEqual(applied["WIDTH"], 100)
        self.assertEqual(applied["HEIGHT"], 40)

    def test_text_and_format_are_preserved(self):
        theme = {"TEXT": "CPU", "FORMAT": "short", "FONT_COLOR": [1, 2, 3]}
        applied = apply_theme_preset(theme, "technical_data_dark")
        self.assertEqual(applied["TEXT"], "CPU")
        self.assertEqual(applied["FORMAT"], "short")

    def test_path_and_font_are_preserved(self):
        theme = {"PATH": "video.mp4", "FONT": "roboto/Roboto.ttf"}
        applied = apply_theme_preset(theme, "technical_data_dark")
        self.assertEqual(applied["PATH"], "video.mp4")
        self.assertEqual(applied["FONT"], "roboto/Roboto.ttf")

    def test_background_image_is_preserved(self):
        theme = {"BACKGROUND_IMAGE": "background.png", "BACKGROUND_COLOR": [1, 2, 3]}
        applied = apply_theme_preset(theme, "technical_data_dark")
        self.assertEqual(applied["BACKGROUND_IMAGE"], "background.png")

    def test_video_section_is_preserved(self):
        theme = {"video": {"BACKGROUND_COLOR": [1, 2, 3], "PATH": "clip.mp4"}}
        applied = apply_theme_preset(theme, "technical_data_dark")
        self.assertEqual(applied["video"], theme["video"])
        self.assertIsNot(applied["video"], theme["video"])

    def test_static_images_section_is_preserved(self):
        theme = {"static_images": {"logo": {"BACKGROUND_COLOR": [1, 2, 3]}}}
        applied = apply_theme_preset(theme, "technical_data_dark")
        self.assertEqual(applied["static_images"], theme["static_images"])
        self.assertIsNot(applied["static_images"], theme["static_images"])

    def test_video_overlay_readable_preserves_background_by_default(self):
        theme = {"BACKGROUND_COLOR": [9, 8, 7], "FONT_COLOR": [1, 2, 3]}
        applied = apply_theme_preset(theme, "video_overlay_readable")
        self.assertEqual(applied["BACKGROUND_COLOR"], [9, 8, 7])
        self.assertEqual(applied["FONT_COLOR"], [255, 255, 255])

    def test_preserve_background_false_overrides_policy(self):
        theme = {"BACKGROUND_COLOR": [9, 8, 7]}
        applied = apply_theme_preset(
            theme,
            "video_overlay_readable",
            preserve_background=False,
        )
        self.assertEqual(applied["BACKGROUND_COLOR"], [20, 20, 20])

    def test_preserve_background_true_preserves_background_for_other_preset(self):
        theme = {"BACKGROUND_COLOR": [9, 8, 7]}
        applied = apply_theme_preset(
            theme,
            "technical_data_dark",
            preserve_background=True,
        )
        self.assertEqual(applied["BACKGROUND_COLOR"], [9, 8, 7])

    def test_empty_theme_returns_equivalent_empty_structure(self):
        applied = apply_theme_preset({}, "technical_data_dark")
        self.assertEqual(applied, {})
        self.assertIsNot(applied, {})

    def test_old_string_color_is_replaced_by_rgb_list(self):
        applied = apply_theme_preset(
            {"FONT_COLOR": "255, 255, 255"},
            "technical_data_dark",
        )
        self.assertEqual(applied["FONT_COLOR"], [244, 244, 244])

    def test_applied_color_lists_do_not_share_references(self):
        theme = {
            "left": {"FONT_COLOR": [1, 2, 3]},
            "right": {"FONT_COLOR": [4, 5, 6]},
        }
        applied = apply_theme_preset(theme, "technical_data_dark")
        self.assertIsNot(applied["left"]["FONT_COLOR"], applied["right"]["FONT_COLOR"])
        applied["left"]["FONT_COLOR"][0] = 0
        self.assertEqual(applied["right"]["FONT_COLOR"], [244, 244, 244])


if __name__ == "__main__":
    unittest.main()
