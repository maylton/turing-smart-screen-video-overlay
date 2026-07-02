from __future__ import annotations

import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_manifest():
    path = ROOT / "release-manifest.yaml"
    try:
        from ruamel.yaml import YAML

        with path.open(encoding="utf-8") as stream:
            return YAML(typ="safe").load(stream)
    except ImportError:
        import yaml

        with path.open(encoding="utf-8") as stream:
            return yaml.safe_load(stream)


class ReleaseReadinessTests(unittest.TestCase):
    def test_changelog_documents_unreleased_work(self):
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("## [Unreleased]", text)
        for phrase in (
            "Native Rev. C video overlay",
            "Media Preparation Editor",
            "Reusable display profiles",
            "automatic display detection",
        ):
            self.assertIn(phrase.lower(), text.lower())

    def test_release_notes_exist_and_are_not_published(self):
        text = (ROOT / "docs/releases/0.1.0-rc1.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("release candidate", text.lower())
        self.assertIn("not published", text.lower())
        self.assertIn("Rev. C 2.1-inch", text)

    def test_manifest_has_required_contract(self):
        data = load_manifest()
        for field in (
            "schema_version",
            "release",
            "runtime",
            "platforms",
            "external_tools",
            "hardware",
            "protocols",
            "entrypoints",
            "documentation",
            "known_limitations",
        ):
            self.assertIn(field, data)
        self.assertFalse(data["release"]["published"])
        validated = data["hardware"]["native_media_validated"]
        self.assertEqual(validated["revision"], "C")
        self.assertEqual(validated["resolution"], [480, 480])
        self.assertTrue(data["hardware"]["preview_only_profiles"])

    def test_manifest_entrypoints_and_docs_exist(self):
        data = load_manifest()
        for relative in data["entrypoints"] + data["documentation"]:
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_release_verifier_is_executable_and_has_core_checks(self):
        path = ROOT / "scripts/verify-release-readiness.sh"
        self.assertTrue(path.is_file())
        self.assertTrue(os.access(path, os.X_OK))
        text = path.read_text(encoding="utf-8")
        for token in (
            "unittest discover",
            "git diff --check",
            "bash -n",
            "compileall",
            "release-manifest.yaml",
            "ffmpeg",
            "ffprobe",
        ):
            self.assertIn(token, text)

    def test_readme_and_roadmap_reference_release_validation(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
        self.assertIn("verify-release-readiness.sh", readme)
        self.assertIn("Release readiness", roadmap)
        self.assertIn("implemented for isolated validation", roadmap.lower())


if __name__ == "__main__":
    unittest.main()
