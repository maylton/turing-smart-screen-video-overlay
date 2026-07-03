from __future__ import annotations

import copy
import unittest

from library.theme_element_catalog import (
    CATALOG_CATEGORIES,
    STATE_ACTIVE,
    STATE_INACTIVE,
    STATE_MIXED,
    STATE_STRUCTURAL,
    catalog_entries,
    catalog_preferred_path,
    catalog_presence,
    element_state,
    humanize_element_label,
    theme_state_summary,
    tree_state,
)


EXPECTED_IDS = [
    "custom_text",
    "static_image",
    "cpu_usage",
    "cpu_temperature",
    "ram_usage",
    "gpu_usage",
    "gpu_temperature",
    "gpu_memory_usage",
    "disk_usage",
    "internet_download",
    "internet_upload",
    "ping",
    "weather",
    "system_uptime",
    "date",
    "time",
]


class ThemeElementCatalogTests(unittest.TestCase):
    def test_catalog_contains_all_expected_elements(self):
        self.assertEqual([entry["id"] for entry in catalog_entries()], EXPECTED_IDS)

    def test_ids_are_unique(self):
        ids = [entry["id"] for entry in catalog_entries()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_categories_are_valid(self):
        for entry in catalog_entries():
            self.assertIn(entry["category"], CATALOG_CATEGORIES)

    def test_labels_are_not_empty(self):
        for entry in catalog_entries():
            self.assertTrue(entry["label"].strip())

    def test_humanizes_static_text(self):
        self.assertEqual(humanize_element_label("static_text"), "Text")

    def test_humanizes_static_images(self):
        self.assertEqual(humanize_element_label("static_images"), "Images")

    def test_humanizes_percent_text(self):
        self.assertEqual(humanize_element_label("PERCENT_TEXT"), "Percentage text")

    def test_preserves_cpu_and_gpu_acronyms(self):
        self.assertEqual(humanize_element_label("CPU"), "CPU")
        self.assertEqual(humanize_element_label("GPU_MEMORY"), "GPU memory")

    def test_static_text_without_show_is_active(self):
        self.assertEqual(
            element_state(("static_text", "title"), {"TEXT": "Hello"}),
            STATE_ACTIVE,
        )

    def test_static_text_with_show_true_is_active(self):
        self.assertEqual(
            element_state(("static_text", "title"), {"SHOW": True}),
            STATE_ACTIVE,
        )

    def test_static_text_with_show_false_is_inactive(self):
        self.assertEqual(
            element_state(("static_text", "title"), {"SHOW": False}),
            STATE_INACTIVE,
        )

    def test_video_enabled_true_is_active(self):
        self.assertEqual(element_state(("video",), {"ENABLED": True}), STATE_ACTIVE)

    def test_video_enabled_false_is_inactive(self):
        self.assertEqual(element_state(("video",), {"ENABLED": False}), STATE_INACTIVE)

    def test_sensor_show_false_is_inactive(self):
        self.assertEqual(
            element_state(("STATS", "CPU", "TEXT"), {"SHOW": False}),
            STATE_INACTIVE,
        )

    def test_interval_zero_disables_descendants(self):
        node = {"INTERVAL": 0, "TEXT": {"SHOW": True}}
        self.assertEqual(tree_state(("STATS", "PING"), node), STATE_INACTIVE)

    def test_group_totally_active_returns_active(self):
        node = {"ONE": {"SHOW": True}, "TWO": {"SHOW": True}}
        self.assertEqual(tree_state(("STATS", "GROUP"), node), STATE_ACTIVE)

    def test_group_totally_inactive_returns_inactive(self):
        node = {"ONE": {"SHOW": False}, "TWO": {"SHOW": False}}
        self.assertEqual(tree_state(("STATS", "GROUP"), node), STATE_INACTIVE)

    def test_group_with_different_states_returns_mixed(self):
        node = {"ONE": {"SHOW": True}, "TWO": {"SHOW": False}}
        self.assertEqual(tree_state(("STATS", "GROUP"), node), STATE_MIXED)

    def test_group_without_state_properties_returns_structural(self):
        node = {"STYLE": {"FONT_SIZE": 12}}
        self.assertEqual(tree_state(("display",), node), STATE_STRUCTURAL)

    def test_summary_does_not_count_groups_twice(self):
        theme = {
            "STATS": {
                "CPU": {
                    "INTERVAL": 1,
                    "TEXT": {"SHOW": True},
                    "GRAPH": {"SHOW": False},
                }
            }
        }
        self.assertEqual(theme_state_summary(theme)[STATE_ACTIVE], 1)
        self.assertEqual(theme_state_summary(theme)[STATE_INACTIVE], 1)
        self.assertEqual(theme_state_summary(theme)[STATE_MIXED], 0)

    def test_custom_text_is_repeatable(self):
        entry = catalog_entries()[0]
        self.assertEqual(entry["id"], "custom_text")
        self.assertTrue(entry["repeatable"])

    def test_missing_sensor_is_reported_available(self):
        presence = catalog_presence({}, "cpu_usage")
        self.assertFalse(presence["present"])
        self.assertEqual(presence["state"], "missing")

    def test_existing_active_sensor_is_reported_active(self):
        theme = {"STATS": {"CPU": {"PERCENTAGE": {"TEXT": {"SHOW": True}}}}}
        presence = catalog_presence(theme, "cpu_usage")
        self.assertTrue(presence["present"])
        self.assertEqual(presence["state"], STATE_ACTIVE)

    def test_existing_inactive_sensor_is_reported_inactive(self):
        theme = {"STATS": {"CPU": {"PERCENTAGE": {"TEXT": {"SHOW": False}}}}}
        presence = catalog_presence(theme, "cpu_usage")
        self.assertTrue(presence["present"])
        self.assertEqual(presence["state"], STATE_INACTIVE)

    def test_preferred_path_points_to_editable_element(self):
        theme = {
            "STATS": {
                "CPU": {
                    "PERCENTAGE": {
                        "INTERVAL": 1,
                        "TEXT": {"SHOW": True},
                    }
                }
            }
        }
        self.assertEqual(
            catalog_preferred_path(theme, "cpu_usage"),
            ("STATS", "CPU", "PERCENTAGE", "TEXT"),
        )

    def test_functions_do_not_modify_theme_data(self):
        theme = {"static_text": {"title": {"TEXT": "Hello"}}}
        original = copy.deepcopy(theme)
        catalog_presence(theme, "custom_text")
        catalog_preferred_path(theme, "custom_text")
        theme_state_summary(theme)
        self.assertEqual(theme, original)

    def test_returned_structures_are_independent(self):
        first = catalog_entries()
        first[0]["label"] = "Changed"
        self.assertEqual(catalog_entries()[0]["label"], "Custom text")


if __name__ == "__main__":
    unittest.main()
