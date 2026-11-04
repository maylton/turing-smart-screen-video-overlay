from __future__ import annotations

import unittest

from library.html_theme_visual_editor import HtmlVisualElementStyle, align_visual_group, move_visual_group


def box(element_id, x, y, width=100, height=40):
    return HtmlVisualElementStyle(element_id=element_id, x=x, y=y, width=width, height=height, font_size=20, color="#ffffff")


SIZE = dict(display_width=480, display_height=480)


class GroupEditTests(unittest.TestCase):
    def test_move_keeps_relative_positions(self):
        moved = move_visual_group([box("a", 10, 10), box("b", 200, 100)], dx=30, dy=-5, **SIZE)
        self.assertEqual([(s.x, s.y) for s in moved], [(40, 5), (230, 95)])

    def test_move_is_clamped_by_the_group_not_per_element(self):
        moved = move_visual_group([box("a", 10, 10), box("b", 360, 100)], dx=50, dy=-50, **SIZE)
        # b's right edge stops at 480, a keeps the same 350 px distance.
        self.assertEqual([(s.x, s.y) for s in moved], [(30, 0), (380, 90)])

    def test_align_left_and_right_to_the_group_box(self):
        group = [box("a", 50, 10, width=100), box("b", 120, 80, width=200)]
        self.assertEqual([s.x for s in align_visual_group(group, "left", **SIZE)], [50, 50])
        self.assertEqual([s.x for s in align_visual_group(group, "right", **SIZE)], [220, 120])

    def test_align_centers(self):
        group = [box("a", 0, 0, width=100, height=40), box("b", 200, 200, width=200, height=80)]
        self.assertEqual([s.x for s in align_visual_group(group, "horizontal-center", **SIZE)], [150, 100])
        self.assertEqual([s.y for s in align_visual_group(group, "vertical-center", **SIZE)], [120, 100])

    def test_single_element_aligns_to_the_canvas(self):
        self.assertEqual(align_visual_group([box("a", 50, 10)], "right", **SIZE)[0].x, 380)

    def test_unknown_alignment(self):
        with self.assertRaises(ValueError):
            align_visual_group([box("a", 0, 0), box("b", 10, 10)], "diagonal", **SIZE)


if __name__ == "__main__":
    unittest.main()
