from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from library import theme_editor_backup_runtime, theme_editor_backups


class ThemeEditorBackupTests(unittest.TestCase):
    def test_create_backup_preserves_previous_yaml(self):
        with tempfile.TemporaryDirectory() as temporary:
            theme_file = Path(temporary) / "theme.yaml"
            theme_file.write_text("name: before\n", encoding="utf-8")

            backup = theme_editor_backups.create_backup(theme_file)

            self.assertIsNotNone(backup)
            assert backup is not None
            self.assertEqual(backup.read_text(encoding="utf-8"), "name: before\n")
            self.assertEqual(backup.parent.name, ".theme-editor-backups")

    def test_retention_keeps_newest_backups(self):
        with tempfile.TemporaryDirectory() as temporary:
            theme_file = Path(temporary) / "theme.yaml"
            theme_file.write_text("name: base\n", encoding="utf-8")
            directory = theme_editor_backups.backup_directory(theme_file)
            directory.mkdir()

            paths = []
            for index in range(5):
                path = directory / f"theme-{index}.yaml"
                path.write_text(str(index), encoding="utf-8")
                os.utime(path, ns=(index + 1, index + 1))
                paths.append(path)

            removed = theme_editor_backups.prune_backups(theme_file, keep=2)

            self.assertEqual({path.name for path in removed}, {
                "theme-0.yaml",
                "theme-1.yaml",
                "theme-2.yaml",
            })
            self.assertEqual(
                [path.name for path in theme_editor_backups.backup_files(theme_file)],
                ["theme-4.yaml", "theme-3.yaml"],
            )

    def test_restore_keeps_current_file_as_another_backup(self):
        with tempfile.TemporaryDirectory() as temporary:
            theme_file = Path(temporary) / "theme.yaml"
            theme_file.write_text("name: first\n", encoding="utf-8")
            old_backup = theme_editor_backups.create_backup(theme_file)
            assert old_backup is not None
            theme_file.write_text("name: current\n", encoding="utf-8")

            theme_editor_backups.restore_backup(old_backup, theme_file)

            self.assertEqual(theme_file.read_text(encoding="utf-8"), "name: first\n")
            contents = {
                path.read_text(encoding="utf-8")
                for path in theme_editor_backups.backup_files(theme_file)
            }
            self.assertIn("name: current\n", contents)

    def test_runtime_guard_matches_only_validated_theme_temp_file(self):
        theme_file = Path("/themes/demo/theme.yaml")
        self.assertTrue(
            theme_editor_backup_runtime._is_validated_theme_save(
                Path("/themes/demo/theme.yaml.tmp"),
                theme_file,
            )
        )
        self.assertFalse(
            theme_editor_backup_runtime._is_validated_theme_save(
                Path("/tmp/theme.yaml.tmp"),
                theme_file,
            )
        )
        self.assertFalse(
            theme_editor_backup_runtime._is_validated_theme_save(
                Path("/themes/demo/config.yaml.tmp"),
                Path("/themes/demo/config.yaml"),
            )
        )

    def test_retention_environment_is_bounded(self):
        with mock.patch.dict(os.environ, {"TURING_THEME_BACKUP_RETENTION": "9999"}):
            self.assertEqual(theme_editor_backups.retention_limit(), 200)
        with mock.patch.dict(os.environ, {"TURING_THEME_BACKUP_RETENTION": "0"}):
            self.assertEqual(theme_editor_backups.retention_limit(), 1)


if __name__ == "__main__":
    unittest.main()
