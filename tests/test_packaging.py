from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PackagingContractTests(unittest.TestCase):
    def test_installer_exposes_system_gtk_to_the_venv(self):
        text = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertGreaterEqual(text.count("-m venv --system-site-packages"), 2)
        self.assertIn('"$PREFIX/venv/bin/python3" -m pip', text)
        self.assertIn("System GTK4 and Libadwaita imports OK", text)
        self.assertIn("Project venv GTK, Pillow and ruamel.yaml imports OK", text)

    def test_installer_runs_the_installed_checkup(self):
        text = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn('/usr/bin/python3 "$PREFIX/gtk-checkup.py" "$PREFIX"', text)

    def test_fork_documentation_exists(self):
        for relative in (
            "docs/INSTALLATION.md",
            "docs/ROADMAP.md",
            "scripts/test-install.py",
        ):
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file())

    def test_readme_describes_current_media_support(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("MAYLTON_FORK_OVERVIEW", text)
        self.assertNotIn("no video or storage support for now", text)
        self.assertIn("Rev. C 2.1-inch", text)

    def test_installation_guide_documents_safe_updates(self):
        text = (ROOT / "docs" / "INSTALLATION.md").read_text(encoding="utf-8")
        self.assertIn("./install.sh --no-deps", text)
        self.assertIn("--system-site-packages", text)
        self.assertIn("Isolated packaging test", text)


if __name__ == "__main__":
    unittest.main()
