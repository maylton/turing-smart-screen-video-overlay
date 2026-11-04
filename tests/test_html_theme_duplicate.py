from __future__ import annotations

import unittest

from library.html_theme_visual_editor import HtmlVisualElementStyle, duplicate_visual_style
from library.theme_engine import ThemeValidationError


def widget(element_id: str, **overrides) -> HtmlVisualElementStyle:
    values = dict(
        element_id=element_id,
        x=40,
        y=50,
        width=120,
        height=40,
        font_size=22,
        color="#ff8800",
        z_index=1000,
        component_type="cpu-temperature",
        glow_radius=6,
    )
    values.update(overrides)
    return HtmlVisualElementStyle(**values)


class DuplicateVisualStyleTests(unittest.TestCase):
    def duplicate(self, style, styles=None):
        return duplicate_visual_style(
            style,
            styles if styles is not None else [style],
            display_width=480,
            display_height=480,
        )

    def test_copy_keeps_style_with_new_id_offset_and_top_layer(self):
        original = widget("turing-cpu-temperature-1")
        other = widget("turing-cpu-temperature-2", z_index=1200)
        copy = self.duplicate(original, [original, other])
        self.assertEqual(copy.element_id, "turing-cpu-temperature-3")
        self.assertEqual((copy.x, copy.y), (52, 62))
        self.assertEqual(copy.z_index, 1201)
        self.assertEqual((copy.color, copy.glow_radius, copy.width), ("#ff8800", 6, 120))

    def test_copy_near_the_edge_steps_back_inside_the_canvas(self):
        original = widget("turing-cpu-temperature-1", x=360, y=440)
        copy = self.duplicate(original)
        self.assertEqual((copy.x, copy.y), (348, 428))

    def test_custom_binding_widget_gets_copy_suffix(self):
        original = widget("hostname", component_type="", generated_widget=True, binding="system.hostname")
        first = self.duplicate(original)
        self.assertEqual(first.element_id, "hostname-copy")
        second = self.duplicate(original, [original, first])
        self.assertEqual(second.element_id, "hostname-copy-2")

    def test_hidden_generated_widget_copy_is_visible(self):
        self.assertTrue(self.duplicate(widget("turing-cpu-temperature-1", visible=False)).visible)

    def test_author_html_overlay_cannot_be_duplicated(self):
        author = widget("clock", component_type="")
        with self.assertRaises(ThemeValidationError):
            self.duplicate(author)

    def test_layer_is_capped(self):
        original = widget("turing-cpu-temperature-1", z_index=9999)
        self.assertEqual(self.duplicate(original).z_index, 9999)


if __name__ == "__main__":
    unittest.main()
