from __future__ import annotations

import unittest

from library.html_editor_zoom import ZOOM_LEVELS, step_zoom, zoom_label, zoomed_size


class EditorZoomTests(unittest.TestCase):
    def test_steps_through_levels_and_stops_at_the_ends(self):
        self.assertEqual(step_zoom(1.0, +1), 1.25)
        self.assertEqual(step_zoom(1.0, -1), 0.75)
        self.assertEqual(step_zoom(ZOOM_LEVELS[-1], +1), ZOOM_LEVELS[-1])
        self.assertEqual(step_zoom(ZOOM_LEVELS[0], -1), ZOOM_LEVELS[0])

    def test_value_between_levels_snaps_in_the_requested_direction(self):
        self.assertEqual(step_zoom(1.1, +1), 1.25)
        self.assertEqual(step_zoom(1.1, -1), 1.0)

    def test_reset_returns_to_actual_size(self):
        self.assertEqual(step_zoom(2.0, 0), 1.0)

    def test_size_and_label(self):
        self.assertEqual(zoomed_size(480, 480, 0.75), (360, 360))
        self.assertEqual(zoomed_size(480, 320, 1.25), (600, 400))
        self.assertEqual(zoom_label(1.25), "125%")


if __name__ == "__main__":
    unittest.main()
