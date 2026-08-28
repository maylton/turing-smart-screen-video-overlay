from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from library.theme_import_file_dialog import normalize_theme_import_path


class ThemeImportFileDialogTests(unittest.TestCase):
    def test_definition_files_resolve_to_their_theme_directory(self):
        with tempfile.TemporaryDirectory(prefix="turing-theme-import-dialog-") as directory:
            root = Path(directory)
            for filename in ("manifest.json", "theme.yaml", "theme.yml"):
                definition = root / filename
                definition.write_text("{}\n", encoding="utf-8")
                self.assertEqual(normalize_theme_import_path(definition), root)
                definition.unlink()

    def test_package_files_remain_files(self):
        with tempfile.TemporaryDirectory(prefix="turing-theme-import-dialog-") as directory:
            root = Path(directory)
            for filename in ("example.theme", "example.zip"):
                package = root / filename
                package.write_bytes(b"package")
                self.assertEqual(normalize_theme_import_path(package), package)

    def test_file_uri_and_quoted_paths_are_supported(self):
        with tempfile.TemporaryDirectory(prefix="turing theme import ") as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text("{}\n", encoding="utf-8")
            self.assertEqual(normalize_theme_import_path(manifest.as_uri()), root)
            self.assertEqual(normalize_theme_import_path(f'"{manifest}"'), root)


if __name__ == "__main__":
    unittest.main()
