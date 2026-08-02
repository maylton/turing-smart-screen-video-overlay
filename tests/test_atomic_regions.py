import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from library.dirty_region_optimizer import optimize_frame_analysis
from library.atomic_regions import AtomicRegion, parse_atomic_regions
from library.frame_pipeline import FramePipeline, write_frame_artifacts
from library.theme_engine import ThemeManifest, ThemeValidationError


class AtomicRegionTests(unittest.TestCase):
    def test_changed_pixel_expands_to_complete_atomic_widget(self):
        first = Image.new("RGBA", (40, 24), (0, 0, 0, 255))
        second = first.copy()
        second.putpixel((12, 9), (255, 255, 255, 255))
        pipeline = FramePipeline(
            tile_size=4,
            pixel_threshold=0,
            full_refresh_ratio=1.0,
            max_regions=64,
        )
        pipeline.process(first)
        previous = pipeline.previous
        analysis = pipeline.process(second)
        atomic = AtomicRegion("cpu-value", 8, 4, 20, 16)

        optimized = optimize_frame_analysis(
            previous,
            second,
            analysis,
            tile_size=4,
            pixel_threshold=0,
            max_regions=8,
            full_refresh_ratio=1.0,
            atomic_regions=(atomic,),
        )

        self.assertFalse(optimized.full_refresh)
        self.assertEqual(
            [region.as_dict() for region in optimized.regions],
            [{"x": 8, "y": 4, "width": 20, "height": 16}],
        )

    def test_unmodified_atomic_widget_is_not_transmitted(self):
        first = Image.new("RGBA", (40, 24), (0, 0, 0, 255))
        second = first.copy()
        second.putpixel((35, 20), (255, 255, 255, 255))
        pipeline = FramePipeline(
            tile_size=4,
            pixel_threshold=0,
            full_refresh_ratio=1.0,
            max_regions=64,
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
            max_regions=8,
            full_refresh_ratio=1.0,
            atomic_regions=(AtomicRegion("cpu-value", 8, 4, 20, 16),),
        )

        self.assertEqual(
            [region.as_dict() for region in optimized.regions],
            [{"x": 32, "y": 20, "width": 4, "height": 4}],
        )

    def test_artifacts_publish_atomic_region_metadata(self):
        image = Image.new("RGBA", (20, 20), (0, 0, 0, 255))
        pipeline = FramePipeline(tile_size=4)
        analysis = pipeline.process(image)
        atomic = AtomicRegion("clock", 2, 3, 10, 6)
        with tempfile.TemporaryDirectory() as temporary:
            root = write_frame_artifacts(
                Path(temporary),
                image,
                analysis,
                atomic_regions=(atomic,),
            )
            metrics = json.loads(
                (root / "metrics.json").read_text(encoding="utf-8")
            )
        self.assertEqual(metrics["atomicRegions"], [atomic.as_dict()])

    def test_manifest_loads_and_validates_atomic_regions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "index.html").write_text("<html></html>", encoding="utf-8")
            payload = {
                "engine": "html",
                "display": {"width": 40, "height": 24},
                "entrypoint": "index.html",
                "permissions": ["sensors"],
                "atomicRegions": [
                    {"name": "cpu", "x": 8, "y": 4, "width": 20, "height": 16}
                ],
            }
            (root / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
            manifest = ThemeManifest.load(root)
        self.assertEqual(manifest.atomic_regions[0].name, "cpu")

    def test_manifest_rejects_out_of_bounds_atomic_region(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "index.html").write_text("<html></html>", encoding="utf-8")
            payload = {
                "engine": "html",
                "display": {"width": 40, "height": 24},
                "entrypoint": "index.html",
                "permissions": ["sensors"],
                "atomicRegions": [
                    {"name": "bad", "x": 30, "y": 4, "width": 20, "height": 16}
                ],
            }
            (root / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ThemeValidationError):
                ThemeManifest.load(root)

    def test_duplicate_names_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            parse_atomic_regions(
                [
                    {"name": "same", "x": 0, "y": 0, "width": 2, "height": 2},
                    {"name": "same", "x": 2, "y": 2, "width": 2, "height": 2},
                ],
                display_width=8,
                display_height=8,
            )


if __name__ == "__main__":
    unittest.main()
