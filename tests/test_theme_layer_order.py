from __future__ import annotations

import unittest

from ruamel.yaml.comments import CommentedMap

from library.theme_layer_order import (
    BRING_TO_FRONT,
    MOVE_BACKWARD,
    MOVE_FORWARD,
    SEND_TO_BACK,
    LayerOrderError,
    is_reorderable_layer,
    layer_action_state,
    layer_info,
    layer_position_label,
    move_layer,
    runtime_layer_sequence,
)


def mapping(*pairs):
    data = CommentedMap()
    for key, value in pairs:
        data[key] = value
    return data


class ThemeLayerOrderTests(unittest.TestCase):
    def sample_theme(self):
        return mapping(
            (
                "static_images",
                mapping(
                    ("backdrop", {"PATH": "backdrop.png"}),
                    ("logo", {"PATH": "logo.png", "SHOW": False}),
                    ("badge", {"PATH": "badge.png"}),
                ),
            ),
            (
                "static_text",
                mapping(
                    ("title", {"TEXT": "Title"}),
                    ("subtitle", {"TEXT": "Subtitle"}),
                ),
            ),
            ("STATS", {"CPU": {"TEXT": {"SHOW": True}}}),
        )

    def keys(self, theme, container):
        return list(theme[container].keys())

    def test_move_backward_moves_one_position(self):
        moved = move_layer(self.sample_theme(), ("static_images", "logo"), MOVE_BACKWARD)
        self.assertEqual(self.keys(moved, "static_images"), ["logo", "backdrop", "badge"])

    def test_move_forward_moves_one_position(self):
        moved = move_layer(self.sample_theme(), ("static_images", "logo"), MOVE_FORWARD)
        self.assertEqual(self.keys(moved, "static_images"), ["backdrop", "badge", "logo"])

    def test_send_to_back_moves_to_start(self):
        moved = move_layer(self.sample_theme(), ("static_images", "badge"), SEND_TO_BACK)
        self.assertEqual(self.keys(moved, "static_images"), ["badge", "backdrop", "logo"])

    def test_bring_to_front_moves_to_end(self):
        moved = move_layer(self.sample_theme(), ("static_images", "backdrop"), BRING_TO_FRONT)
        self.assertEqual(self.keys(moved, "static_images"), ["logo", "badge", "backdrop"])

    def test_first_layer_cannot_move_backward(self):
        state = layer_action_state(self.sample_theme(), ("static_images", "backdrop"))
        self.assertFalse(state[MOVE_BACKWARD])
        self.assertFalse(state[SEND_TO_BACK])

    def test_last_layer_cannot_move_forward(self):
        state = layer_action_state(self.sample_theme(), ("static_images", "badge"))
        self.assertFalse(state[MOVE_FORWARD])
        self.assertFalse(state[BRING_TO_FRONT])

    def test_single_layer_cannot_move(self):
        theme = {"static_images": {"only": {"PATH": "only.png"}}}
        self.assertEqual(
            layer_action_state(theme, ("static_images", "only")),
            {
                MOVE_BACKWARD: False,
                MOVE_FORWARD: False,
                SEND_TO_BACK: False,
                BRING_TO_FRONT: False,
            },
        )

    def test_text_and_image_keep_independent_stacks(self):
        moved = move_layer(self.sample_theme(), ("static_text", "title"), BRING_TO_FRONT)
        self.assertEqual(self.keys(moved, "static_images"), ["backdrop", "logo", "badge"])
        self.assertEqual(self.keys(moved, "static_text"), ["subtitle", "title"])

    def test_sensors_are_not_reorderable(self):
        self.assertFalse(is_reorderable_layer(self.sample_theme(), ("STATS", "CPU")))

    def test_containers_are_not_reorderable(self):
        self.assertFalse(is_reorderable_layer(self.sample_theme(), ("static_images",)))

    def test_hidden_item_is_reorderable(self):
        self.assertTrue(is_reorderable_layer(self.sample_theme(), ("static_images", "logo")))

    def test_theme_original_is_not_modified(self):
        theme = self.sample_theme()
        move_layer(theme, ("static_images", "logo"), MOVE_FORWARD)
        self.assertEqual(self.keys(theme, "static_images"), ["backdrop", "logo", "badge"])

    def test_nested_values_are_independent(self):
        theme = self.sample_theme()
        moved = move_layer(theme, ("static_images", "logo"), MOVE_FORWARD)
        moved["static_images"]["logo"]["PATH"] = "changed.png"
        self.assertEqual(theme["static_images"]["logo"]["PATH"], "logo.png")

    def test_commented_map_preserves_type(self):
        moved = move_layer(self.sample_theme(), ("static_images", "logo"), MOVE_FORWARD)
        self.assertIsInstance(moved, CommentedMap)
        self.assertIsInstance(moved["static_images"], CommentedMap)

    def test_position_labels_are_correct(self):
        self.assertEqual(
            layer_position_label(self.sample_theme(), ("static_images", "logo")),
            "Layer 2 of 3 · Images",
        )
        self.assertEqual(
            layer_position_label(self.sample_theme(), ("static_text", "subtitle")),
            "Layer 2 of 2 · Text",
        )

    def test_runtime_sequence_is_images_then_text(self):
        self.assertEqual(
            runtime_layer_sequence(self.sample_theme()),
            (
                ("static_images", "backdrop"),
                ("static_images", "logo"),
                ("static_images", "badge"),
                ("static_text", "title"),
                ("static_text", "subtitle"),
            ),
        )

    def test_errors_are_clear(self):
        with self.assertRaisesRegex(LayerOrderError, "not a reorderable"):
            move_layer(self.sample_theme(), ("STATS", "CPU"), MOVE_FORWARD)

    def test_unknown_actions_are_rejected(self):
        with self.assertRaisesRegex(LayerOrderError, "Unknown layer action"):
            move_layer(self.sample_theme(), ("static_images", "logo"), "sideways")

    def test_layer_info_contains_position_and_capabilities(self):
        info = layer_info(self.sample_theme(), ("static_images", "logo"))
        self.assertEqual(info["position"], 2)
        self.assertEqual(info["total"], 3)
        self.assertTrue(info["can_move_backward"])
        self.assertTrue(info["can_move_forward"])


if __name__ == "__main__":
    unittest.main()
