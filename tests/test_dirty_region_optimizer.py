# SPDX-License-Identifier: GPL-3.0-or-later
import unittest

from PIL import Image, ImageDraw

from library.dirty_region_optimizer import optimize_frame_analysis
from library.frame_pipeline import FramePipeline


class DirtyRegionOptimizerTests(unittest.TestCase):
    def optimize(
        self,
        first,
        second,
        *,
        tile_size=4,
        max_regions=16,
        full_refresh_ratio=0.95,
    ):
        pipeline = FramePipeline(
            tile_size=tile_size,
            pixel_threshold=0,
            full_refresh_ratio=full_refresh_ratio,
            max_regions=64,
        )
        pipeline.process(first)
        previous = pipeline.previous
        analysis = pipeline.process(second)
        optimized = optimize_frame_analysis(
            previous,
            second,
            analysis,
            tile_size=tile_size,
            pixel_threshold=0,
            max_regions=max_regions,
            full_refresh_ratio=full_refresh_ratio,
        )
        return analysis, optimized

    def test_l_shape_uses_two_tight_rectangles(self):
        first = Image.new("RGBA", (20, 20), (0, 0, 0, 255))
        second = first.copy()
        draw = ImageDraw.Draw(second)
        draw.rectangle((0, 0, 15, 3), fill=(255, 255, 255, 255))
        draw.rectangle((0, 4, 3, 15), fill=(255, 255, 255, 255))

        original, optimized = self.optimize(first, second)

        self.assertEqual(len(original.regions), 1)
        self.assertEqual(original.regions[0].area, 16 * 16)
        self.assertEqual(
            [region.as_dict() for region in optimized.regions],
            [
                {"x": 0, "y": 0, "width": 16, "height": 4},
                {"x": 0, "y": 4, "width": 4, "height": 12},
            ],
        )
        self.assertEqual(
            sum(region.area for region in optimized.regions),
            112,
        )

    def test_ring_uses_four_tight_bands(self):
        first = Image.new("RGBA", (112, 112), (0, 0, 0, 255))
        second = first.copy()
        draw = ImageDraw.Draw(second)
        draw.rectangle((0, 0, 111, 15), fill=(255, 255, 255, 255))
        draw.rectangle((0, 96, 111, 111), fill=(255, 255, 255, 255))
        draw.rectangle((0, 16, 15, 95), fill=(255, 255, 255, 255))
        draw.rectangle((96, 16, 111, 95), fill=(255, 255, 255, 255))

        original, optimized = self.optimize(
            first,
            second,
            tile_size=16,
        )

        self.assertEqual(len(original.regions), 1)
        self.assertEqual(original.regions[0].area, 112 * 112)
        self.assertEqual(len(optimized.regions), 4)
        self.assertEqual(
            sum(region.area for region in optimized.regions),
            6144,
        )

    def test_merge_limit_preserves_changed_pixels(self):
        first = Image.new("RGBA", (40, 16), (0, 0, 0, 255))
        second = first.copy()
        changed = [(1, 1), (9, 1), (17, 1), (25, 9), (33, 9)]
        for x, y in changed:
            second.putpixel((x, y), (255, 255, 255, 255))

        _original, optimized = self.optimize(
            first,
            second,
            tile_size=4,
            max_regions=2,
            full_refresh_ratio=1.0,
        )

        self.assertLessEqual(len(optimized.regions), 2)
        self.assertFalse(optimized.full_refresh)
        for x, y in changed:
            self.assertTrue(
                any(
                    region.x <= x < region.right
                    and region.y <= y < region.bottom
                    for region in optimized.regions
                )
            )

    def test_full_refresh_is_not_downgraded(self):
        first = Image.new("RGBA", (8, 8), (0, 0, 0, 255))
        second = Image.new("RGBA", (8, 8), (255, 255, 255, 255))
        pipeline = FramePipeline(
            tile_size=4,
            pixel_threshold=0,
            full_refresh_ratio=0.25,
        )
        pipeline.process(first)
        previous = pipeline.previous
        analysis = pipeline.process(second)

        optimized = optimize_frame_analysis(
            previous,
            second,
            analysis,
            tile_size=4,
            pixel_threshold=0,
            max_regions=16,
            full_refresh_ratio=0.25,
        )

        self.assertTrue(optimized.full_refresh)
        self.assertEqual(optimized, analysis)


if __name__ == "__main__":
    unittest.main()
