from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from library import release_info


class ReleaseInfoTests(unittest.TestCase):
    def make_complete_tree(self, root: Path) -> None:
        for relative in release_info.REQUIRED_PROJECT_FILES:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("placeholder\n", encoding="utf-8")
        (root / "VERSION").write_text("0.9.0-test\n", encoding="utf-8")

    def test_validate_project_tree_reports_only_missing_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_complete_tree(root)
            (root / "library" / "i18n.py").unlink()

            self.assertEqual(
                release_info.validate_project_tree(root),
                ["library/i18n.py"],
            )

    def test_source_commit_marks_modified_checkout(self):
        with mock.patch.object(
            release_info,
            "_run_git",
            side_effect=("0123456789ab", " M configure-gtk.py"),
        ):
            self.assertEqual(
                release_info.source_commit(Path("/project")),
                "0123456789ab-dirty",
            )

    def test_write_and_load_metadata_round_trip(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
            install = base / "install"
            source.mkdir()
            install.mkdir()
            self.make_complete_tree(source)
            self.make_complete_tree(install)

            with mock.patch.object(
                release_info,
                "source_commit",
                return_value="abcdef123456",
            ):
                destination = release_info.write_metadata(
                    source_root=source,
                    install_root=install,
                    install_mode="user",
                )

            self.assertEqual(destination, install / ".installation.json")
            self.assertFalse((install / ".installation.json.tmp").exists())

            metadata = release_info.load_metadata(install)
            self.assertIsNotNone(metadata)
            assert metadata is not None
            self.assertEqual(metadata.version, "0.9.0-test")
            self.assertEqual(metadata.source_commit, "abcdef123456")
            self.assertEqual(metadata.install_mode, "user")

            payload = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(payload["install_root"], str(install.resolve()))

    def test_release_summary_falls_back_without_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "VERSION").write_text("1.2.3\n", encoding="utf-8")
            with mock.patch.object(
                release_info,
                "source_commit",
                return_value="unknown",
            ):
                summary = release_info.release_summary(root)

            self.assertEqual(summary["version"], "1.2.3")
            self.assertEqual(summary["source_commit"], "unknown")
            self.assertIn("main.py", summary["missing_files"])


if __name__ == "__main__":
    unittest.main()
