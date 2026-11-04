from __future__ import annotations

import unittest

from library.html_editor_rulers import MIN_LABEL_GAP_PX, cursor_position, ruler_ticks, selection_span, tick_steps


class RulerTests(unittest.TestCase):
    def test_labels_never_closer_than_the_minimum_gap(self):
        for zoom in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0):
            with self.subTest(zoom=zoom):
                _minor, major = tick_steps(zoom)
                self.assertGreaterEqual(major * zoom, MIN_LABEL_GAP_PX)

    def test_steps_at_actual_size(self):
        self.assertEqual(tick_steps(1.0), (25, 50))
        self.assertEqual(tick_steps(2.0), (10, 25))
        self.assertEqual(tick_steps(0.5), (50, 100))

    def test_ticks_cover_the_whole_length_and_label_majors(self):
        ticks = ruler_ticks(480, 1.0)
        self.assertEqual(ticks[0].position, 0)
        self.assertEqual(ticks[-1].position, 475)
        self.assertEqual([t.label for t in ticks if t.major][:3], ["0", "50", "100"])
        self.assertTrue(all(t.label == "" for t in ticks if not t.major))

    def test_selection_span(self):
        boxes = [(10, 20, 100, 30), (200, 5, 50, 10)]
        self.assertEqual(selection_span(boxes, "x"), (10, 250))
        self.assertEqual(selection_span(boxes, "y"), (5, 50))
        self.assertIsNone(selection_span([], "x"))

    def test_cursor_position_accounts_for_zoom(self):
        self.assertEqual(cursor_position(300, 100, 2.0, 480, 480), (150, 50))
        self.assertEqual(cursor_position(119.9, 0, 0.5, 480, 480), (239, 0))
        self.assertIsNone(cursor_position(961, 10, 2.0, 480, 480))
        self.assertIsNone(cursor_position(-1, 10, 1.0, 480, 480))


if __name__ == "__main__":
    unittest.main()
