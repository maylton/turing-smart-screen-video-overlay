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


if __name__ == "__main__":
    unittest.main()
