from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from library.frame_pipeline import (
    FramePipeline,
    decode_png_frame,
    encode_png_frame,
    write_frame_artifacts,
)


class FramePipelineTests(unittest.TestCase):
    def test_first_frame_requires_full_refresh(self):
        pipeline = FramePipeline(tile_size=4)
        image = Image.new("RGBA", (8, 8), (0, 0, 0, 255))

        analysis = pipeline.process(image)

        self.assertTrue(analysis.full_refresh)
        self.assertEqual(analysis.changed_pixels, 64)
        self.assertEqual(len(analysis.regions), 1)
        self.assertEqual(analysis.regions[0].as_dict(), {
            "x": 0,
            "y": 0,
            "width": 8,
            "height": 8,
        })

    def test_identical_frame_has_no_dirty_regions(self):
        pipeline = FramePipeline(tile_size=4)
        image = Image.new("RGBA", (8, 8), (0, 0, 0, 255))
        pipeline.process(image)

        analysis = pipeline.process(image.copy())

        self.assertFalse(analysis.full_refresh)
        self.assertEqual(analysis.changed_pixels, 0)
        self.assertEqual(analysis.regions, ())

    def test_local_changes_are_grouped_into_tiles(self):
        pipeline = FramePipeline(
            tile_size=4,
            full_refresh_ratio=0.9,
        )
        first = Image.new("RGBA", (12, 8), (0, 0, 0, 255))
        second = first.copy()
        for y in range(1, 3):
            for x in range(5, 7):
                second.putpixel((x, y), (255, 255, 255, 255))

        pipeline.process(first)
        analysis = pipeline.process(second)

        self.assertFalse(analysis.full_refresh)
        self.assertEqual(analysis.changed_pixels, 4)
        self.assertEqual(len(analysis.regions), 1)
        self.assertEqual(analysis.regions[0].as_dict(), {
            "x": 4,
            "y": 0,
            "width": 4,
            "height": 4,
        })

    def test_small_channel_noise_is_ignored(self):
        pipeline = FramePipeline(
            tile_size=4,
            pixel_threshold=4,
        )
        first = Image.new("RGBA", (4, 4), (10, 10, 10, 255))
        second = Image.new("RGBA", (4, 4), (13, 13, 13, 255))

        pipeline.process(first)
        analysis = pipeline.process(second)

        self.assertEqual(analysis.changed_pixels, 0)

    def test_large_change_falls_back_to_full_refresh(self):
        pipeline = FramePipeline(
            tile_size=4,
            full_refresh_ratio=0.25,
        )
        first = Image.new("RGBA", (8, 8), (0, 0, 0, 255))
        second = Image.new("RGBA", (8, 8), (255, 255, 255, 255))

        pipeline.process(first)
        analysis = pipeline.process(second)

        self.assertTrue(analysis.full_refresh)
        self.assertEqual(len(analysis.regions), 1)

    def test_png_round_trip_and_artifacts(self):
        image = Image.new("RGBA", (8, 8), (10, 20, 30, 255))
        payload = encode_png_frame(image)
        decoded = decode_png_frame(payload, expected_size=(8, 8))
        pipeline = FramePipeline(tile_size=4)
        analysis = pipeline.process(decoded)

        with tempfile.TemporaryDirectory() as temporary:
            root = write_frame_artifacts(
                Path(temporary),
                decoded,
                analysis,
            )
            metrics = json.loads(
                (root / "metrics.json").read_text(encoding="utf-8")
            )
            self.assertTrue((root / "latest.png").is_file())
            self.assertTrue((root / "latest-diff.png").is_file())

        self.assertEqual(metrics["sequence"], 1)
        self.assertTrue(metrics["fullRefresh"])


if __name__ == "__main__":
    unittest.main()
