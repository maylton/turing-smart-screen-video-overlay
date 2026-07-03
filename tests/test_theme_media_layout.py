from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from library.theme_media_layout import (
    MODE_CUSTOM,
    MODE_FILL,
    MODE_FIT,
    MODE_ORIGINAL,
    MODE_STRETCH,
    ImageLayoutSettings,
    ThemeMediaLayoutError,
    apply_image_layout,
    compute_image_layout,
    image_dimensions,
    infer_layout_mode,
    render_image_layout_preview,
    resolve_theme_image_path,
    theme_canvas_dimensions,
)


class ThemeMediaLayoutTests(unittest.TestCase):
    def test_canvas_21_is_480_square(self):
        self.assertEqual(
            theme_canvas_dimensions(
                {"display": {"DISPLAY_SIZE": '2.1"', "DISPLAY_ORIENTATION": "portrait"}}
            ),
            (480, 480),
        )

    def test_canvas_88_portrait(self):
        self.assertEqual(
            theme_canvas_dimensions(
                {"display": {"DISPLAY_SIZE": '8.8"', "DISPLAY_ORIENTATION": "portrait"}}
            ),
            (480, 1920),
        )

    def test_canvas_88_landscape(self):
        self.assertEqual(
            theme_canvas_dimensions(
                {"display": {"DISPLAY_SIZE": '8.8"', "DISPLAY_ORIENTATION": "landscape"}}
            ),
            (1920, 480),
        )

    def test_canvas_fallback(self):
        self.assertEqual(theme_canvas_dimensions({}), (320, 480))

    def test_original_layout(self):
        layout = compute_image_layout(100, 50, 480, 480, ImageLayoutSettings(MODE_ORIGINAL))
        self.assertEqual(layout, {"X": 190, "Y": 215, "WIDTH": 100, "HEIGHT": 50})

    def test_fit_horizontal_source(self):
        layout = compute_image_layout(800, 400, 480, 480, ImageLayoutSettings(MODE_FIT))
        self.assertEqual(layout, {"X": 0, "Y": 120, "WIDTH": 480, "HEIGHT": 240})

    def test_fit_vertical_source(self):
        layout = compute_image_layout(400, 800, 480, 480, ImageLayoutSettings(MODE_FIT))
        self.assertEqual(layout, {"X": 120, "Y": 0, "WIDTH": 240, "HEIGHT": 480})

    def test_fill_horizontal_source(self):
        layout = compute_image_layout(800, 400, 480, 480, ImageLayoutSettings(MODE_FILL))
        self.assertEqual(layout, {"X": -240, "Y": 0, "WIDTH": 960, "HEIGHT": 480})

    def test_fill_vertical_source(self):
        layout = compute_image_layout(400, 800, 480, 480, ImageLayoutSettings(MODE_FILL))
        self.assertEqual(layout, {"X": 0, "Y": -240, "WIDTH": 480, "HEIGHT": 960})

    def test_stretch_layout(self):
        layout = compute_image_layout(100, 50, 480, 320, ImageLayoutSettings(MODE_STRETCH))
        self.assertEqual(layout, {"X": 0, "Y": 0, "WIDTH": 480, "HEIGHT": 320})

    def test_custom_layout(self):
        settings = ImageLayoutSettings(MODE_CUSTOM, custom_width=200, custom_height=100)
        layout = compute_image_layout(100, 50, 480, 480, settings)
        self.assertEqual(layout, {"X": 140, "Y": 190, "WIDTH": 200, "HEIGHT": 100})

    def test_zoom_increases(self):
        settings = ImageLayoutSettings(MODE_ORIGINAL, zoom=2.0)
        self.assertEqual(compute_image_layout(100, 50, 480, 480, settings)["WIDTH"], 200)

    def test_zoom_reduces(self):
        settings = ImageLayoutSettings(MODE_ORIGINAL, zoom=0.5)
        self.assertEqual(compute_image_layout(100, 50, 480, 480, settings)["WIDTH"], 50)

    def test_left_top_alignment(self):
        settings = ImageLayoutSettings(MODE_ORIGINAL, align_x="left", align_y="top")
        self.assertEqual(compute_image_layout(100, 50, 480, 480, settings)["X"], 0)
        self.assertEqual(compute_image_layout(100, 50, 480, 480, settings)["Y"], 0)

    def test_center_center_alignment(self):
        settings = ImageLayoutSettings(MODE_ORIGINAL, align_x="center", align_y="center")
        self.assertEqual(compute_image_layout(100, 50, 480, 480, settings)["X"], 190)
        self.assertEqual(compute_image_layout(100, 50, 480, 480, settings)["Y"], 215)

    def test_right_bottom_alignment(self):
        settings = ImageLayoutSettings(MODE_ORIGINAL, align_x="right", align_y="bottom")
        self.assertEqual(compute_image_layout(100, 50, 480, 480, settings)["X"], 380)
        self.assertEqual(compute_image_layout(100, 50, 480, 480, settings)["Y"], 430)

    def test_fill_can_have_negative_x(self):
        self.assertLess(
            compute_image_layout(800, 400, 480, 480, ImageLayoutSettings(MODE_FILL))["X"],
            0,
        )

    def test_fill_can_have_negative_y(self):
        self.assertLess(
            compute_image_layout(400, 800, 480, 480, ImageLayoutSettings(MODE_FILL))["Y"],
            0,
        )

    def test_invalid_mode(self):
        with self.assertRaises(ThemeMediaLayoutError):
            ImageLayoutSettings("bad")

    def test_invalid_zoom(self):
        with self.assertRaises(ThemeMediaLayoutError):
            ImageLayoutSettings(MODE_FIT, zoom=5.0)

    def test_invalid_alignment(self):
        with self.assertRaises(ThemeMediaLayoutError):
            ImageLayoutSettings(MODE_FIT, align_x="middle")

    def test_custom_incomplete(self):
        with self.assertRaises(ThemeMediaLayoutError):
            ImageLayoutSettings(MODE_CUSTOM, custom_width=100)

    def test_apply_preserves_path(self):
        node = {"PATH": "image.png"}
        updated = apply_image_layout(node, (100, 50), (480, 480), ImageLayoutSettings())
        self.assertEqual(updated["PATH"], "image.png")

    def test_apply_preserves_show(self):
        node = {"PATH": "image.png", "SHOW": False}
        updated = apply_image_layout(node, (100, 50), (480, 480), ImageLayoutSettings())
        self.assertFalse(updated["SHOW"])

    def test_apply_preserves_unknown_keys(self):
        node = {"PATH": "image.png", "COMMENT": "keep"}
        updated = apply_image_layout(node, (100, 50), (480, 480), ImageLayoutSettings())
        self.assertEqual(updated["COMMENT"], "keep")

    def test_apply_does_not_modify_original(self):
        node = {"PATH": "image.png", "X": 1, "Y": 2, "WIDTH": 3, "HEIGHT": 4}
        original = copy.deepcopy(node)
        apply_image_layout(node, (100, 50), (480, 480), ImageLayoutSettings())
        self.assertEqual(node, original)

    def test_relative_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "image.png"
            Image.new("RGBA", (2, 2), (255, 0, 0, 255)).save(image)
            self.assertEqual(resolve_theme_image_path(root, {"PATH": "image.png"}), image.resolve())

    def test_absolute_path(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "image.png"
            Image.new("RGBA", (2, 2), (255, 0, 0, 255)).save(image)
            self.assertEqual(resolve_theme_image_path(directory, {"PATH": str(image)}), image.resolve())

    def test_missing_path(self):
        with self.assertRaises(ThemeMediaLayoutError):
            resolve_theme_image_path(".", {})

    def test_image_dimensions(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "image.png"
            Image.new("RGBA", (7, 5), (255, 0, 0, 255)).save(image)
            self.assertEqual(image_dimensions(image), (7, 5))

    def test_preview_has_canvas_size(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.png"
            output = root / "preview.png"
            Image.new("RGBA", (2, 2), (255, 0, 0, 255)).save(source)
            render_image_layout_preview(
                source,
                output,
                canvas_size=(11, 13),
                layout={"X": 0, "Y": 0, "WIDTH": 2, "HEIGHT": 2},
            )
            self.assertEqual(image_dimensions(output), (11, 13))

    def test_preview_does_not_modify_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.png"
            output = root / "preview.png"
            Image.new("RGBA", (2, 2), (10, 20, 30, 40)).save(source)
            before = source.read_bytes()
            render_image_layout_preview(
                source,
                output,
                canvas_size=(5, 5),
                layout={"X": 0, "Y": 0, "WIDTH": 2, "HEIGHT": 2},
            )
            self.assertEqual(source.read_bytes(), before)

    def test_preview_preserves_alpha(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.png"
            output = root / "preview.png"
            Image.new("RGBA", (1, 1), (255, 0, 0, 128)).save(source)
            render_image_layout_preview(
                source,
                output,
                canvas_size=(3, 3),
                layout={"X": 1, "Y": 1, "WIDTH": 1, "HEIGHT": 1},
            )
            with Image.open(output) as rendered:
                pixel = rendered.convert("RGBA").getpixel((1, 1))
            self.assertGreater(pixel[0], pixel[1])
            self.assertLess(pixel[0], 255)

    def test_returns_are_independent(self):
        node = {"PATH": "image.png", "NESTED": {"value": 1}}
        updated = apply_image_layout(node, (100, 50), (480, 480), ImageLayoutSettings())
        updated["NESTED"]["value"] = 2
        self.assertEqual(node["NESTED"]["value"], 1)

    def test_infer_layout_modes(self):
        self.assertEqual(infer_layout_mode((100, 50), (480, 480), {"WIDTH": 100, "HEIGHT": 50}), MODE_ORIGINAL)
        self.assertEqual(infer_layout_mode((100, 50), (480, 480), {"WIDTH": 480, "HEIGHT": 480}), MODE_STRETCH)
        self.assertEqual(infer_layout_mode((800, 400), (480, 480), {"WIDTH": 480, "HEIGHT": 240}), MODE_FIT)
        self.assertEqual(infer_layout_mode((800, 400), (480, 480), {"WIDTH": 960, "HEIGHT": 480}), MODE_FILL)


if __name__ == "__main__":
    unittest.main()
