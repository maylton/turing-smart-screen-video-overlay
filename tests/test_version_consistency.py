import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class VersionConsistencyTests(unittest.TestCase):
    """VERSION is the single source of truth for the released version."""

    def setUp(self):
        self.version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

    def test_version_is_semantic(self):
        self.assertRegex(self.version, r"^\d+\.\d+\.\d+$")

    def test_readme_matches_version(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"badge/version-{self.version}-", readme)
        self.assertIn(f"The application version is **{self.version}**", readme)

    def test_latest_changelog_release_matches_version(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        releases = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.MULTILINE)
        self.assertTrue(releases)
        self.assertEqual(releases[0], self.version)
        self.assertIn(f"[{self.version}]: ", changelog)


if __name__ == "__main__":
    unittest.main()
