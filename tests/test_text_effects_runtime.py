from __future__ import annotations

import unittest

import library.stats as stats


class CaptureLcd:
    def __init__(self):
        self.text_kwargs = None
        self.radial_kwargs = None

    def DisplayText(self, **kwargs):
        self.text_kwargs = kwargs

    def DisplayRadialProgressBar(self, **kwargs):
        self.radial_kwargs = kwargs


class TextEffectsRuntimeIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.original_lcd = stats.display.lcd
        self.capture = CaptureLcd()
        stats.display.lcd = self.capture

    def tearDown(self):
        stats.display.lcd = self.original_lcd

    def test_dynamic_text_forwards_effects(self):
        effects = {
            "GLOW": {
                "ENABLED": True,
                "COLOR": [80, 140, 255, 180],
                "BLUR_RADIUS": 8,
                "INTENSITY": 2,
            }
        }
        stats.display_themed_value(
            {
                "SHOW": True,
                "X": 10,
                "Y": 20,
                "FONT_SIZE": 24,
                "EFFECTS": effects,
            },
            42,
        )
        self.assertEqual(
            self.capture.text_kwargs["effects"],
            effects,
        )

    def test_radial_text_forwards_effects(self):
        effects = {
            "OUTLINE": {
                "ENABLED": True,
                "COLOR": [0, 0, 0, 255],
                "WIDTH": 2,
            }
        }
        stats.display_themed_radial_bar(
            {
                "SHOW": True,
                "SHOW_TEXT": True,
                "X": 50,
                "Y": 50,
                "RADIUS": 20,
                "WIDTH": 4,
                "EFFECTS": effects,
            },
            50,
        )
        self.assertEqual(
            self.capture.radial_kwargs["text_effects"],
            effects,
        )


if __name__ == "__main__":
    unittest.main()
