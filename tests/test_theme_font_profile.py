from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from library.theme_font_profile import (
    collect_theme_font_references,
    font_references_from_yaml_text,
    normalize_font_reference,
    preserve_referenced_fonts,
)


ROOT = Path(__file__).resolve().parents[1]
CORE_FONT_FILTER = ROOT / "packaging" / "core-fonts-rsync-filter.txt"


def core_font_paths() -> set[str]:
    prefix = "+ /res/fonts/"
    paths = set()
    for line in CORE_FONT_FILTER.read_text(encoding="utf-8").splitlines():
        if not line.startswith(prefix) or line.endswith("/"):
            continue
        relative = line[len(prefix):]
        if Path(relative).suffix.casefold() in {".otf", ".ttc", ".ttf"}:
            paths.add(relative)
    return paths


class ThemeFontProfileTests(unittest.TestCase):
    def test_normalizes_only_safe_font_references(self):
        self.assertEqual(
            normalize_font_reference(" roboto/Roboto-Regular.ttf # body "),
            "roboto/Roboto-Regular.ttf",
        )
        self.assertEqual(
            normalize_font_reference("'jetbrains-mono/JetBrainsMono-Bold.ttf'"),
            "jetbrains-mono/JetBrainsMono-Bold.ttf",
        )
        self.assertIsNone(normalize_font_reference("../outside.ttf"))
        self.assertIsNone(normalize_font_reference("image.png"))

    def test_extracts_font_and_axis_font_scalars(self):
        references = font_references_from_yaml_text(
            """
            FONT: roboto/Roboto-Regular.ttf
            AXIS_FONT: "roboto/Roboto-Black.ttf"
            FONT_SIZE: 20
            # FONT: ignored/Comment.ttf
            """
        )
        self.assertEqual(
            references,
            {"roboto/Roboto-Regular.ttf", "roboto/Roboto-Black.ttf"},
        )

    def test_core_profile_covers_bundled_themes_and_templates(self):
        references = collect_theme_font_references(
            (
                ROOT / "res" / "themes",
                ROOT / "res" / "editor-templates" / "default.yaml",
                ROOT / "res" / "editor-templates" / "theme_example.yaml",
            )
        )
        self.assertEqual(len(references), 18)
        self.assertEqual(references - core_font_paths(), set())

    def test_preserves_only_fonts_referenced_by_installed_themes(self):
        with tempfile.TemporaryDirectory(prefix="turing-font-profile-") as directory:
            root = Path(directory)
            themes = root / "themes"
            fonts = root / "fonts"
            destination = root / "preserved"
            theme_file = themes / "custom" / "theme.yaml"
            theme_file.parent.mkdir(parents=True)
            theme_file.write_text(
                "FONT: optional/Custom.ttf\nAXIS_FONT: missing/Missing.otf\n",
                encoding="utf-8",
            )
            custom_font = fonts / "optional" / "Custom.ttf"
            unused_font = fonts / "optional" / "Unused.ttf"
            custom_font.parent.mkdir(parents=True)
            custom_font.write_bytes(b"custom")
            unused_font.write_bytes(b"unused")

            copied, missing = preserve_referenced_fonts(
                theme_roots=(themes,),
                fonts_root=fonts,
                destination=destination,
            )

            self.assertEqual(copied, ["optional/Custom.ttf"])
            self.assertEqual(missing, ["missing/Missing.otf"])
            self.assertEqual(
                (destination / "optional" / "Custom.ttf").read_bytes(),
                b"custom",
            )
            self.assertFalse((destination / "optional" / "Unused.ttf").exists())


if __name__ == "__main__":
    unittest.main()
