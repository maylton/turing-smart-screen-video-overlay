from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from library.theme_gallery import discover_themes


class ThemeDiscoveryTests(unittest.TestCase):
    def test_sample_asset_folders_are_not_listed_as_themes(self):
        with tempfile.TemporaryDirectory() as tmp:
            themes = Path(tmp) / "themes"
            (themes / "--Theme examples").mkdir(parents=True)
            (themes / "Real").mkdir()
            (themes / "Real" / "theme.yaml").write_text('display:\n  DISPLAY_SIZE: 3.5"\n', encoding="utf-8")
            names = [r.name for r in discover_themes(themes, Path(tmp) / "config.yaml", only_compatible=False)]
            self.assertEqual(names, ["Real"])

    def _html_theme(self, themes: Path, name: str, size=(480, 480)) -> None:
        import json

        root = themes / name
        root.mkdir(parents=True)
        (root / "index.html").write_text("<!doctype html><body></body>", encoding="utf-8")
        (root / "manifest.json").write_text(json.dumps({
            "engine": "html", "name": name, "version": 1, "entrypoint": "index.html",
            "display": {"width": size[0], "height": size[1]},
        }), encoding="utf-8")

    def test_html_theme_gets_display_size_from_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            themes = Path(tmp) / "themes"
            self._html_theme(themes, "round")
            config = Path(tmp) / "config.yaml"
            config.write_text('display:\n  DISPLAY_SIZE: 2.8"\n', encoding="utf-8")
            record = discover_themes(themes, config, only_compatible=False)[0]
            self.assertEqual(record.display_size, "2.8")
            config.write_text('display:\n  DISPLAY_SIZE: 3.5"\n', encoding="utf-8")
            record = discover_themes(themes, config, only_compatible=False)[0]
            self.assertEqual(record.display_size, "2.1")
            self.assertEqual(discover_themes(themes, config, only_compatible=True), [])


if __name__ == "__main__":
    unittest.main()
