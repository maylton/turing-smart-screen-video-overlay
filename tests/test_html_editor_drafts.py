from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from library.html_editor_drafts import clear_draft, draft_path, load_draft, write_draft
from library.html_theme_visual_editor import HtmlVisualElementStyle


def style(element_id: str, **overrides) -> HtmlVisualElementStyle:
    values = dict(element_id=element_id, x=10, y=20, width=100, height=30, font_size=20, color="#ffffff")
    values.update(overrides)
    return HtmlVisualElementStyle(**values)


class EditorDraftTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.theme_root = base / "themes" / "My Theme"
        self.theme_root.mkdir(parents=True)
        (self.theme_root / "overlays.json").write_text('{"elements": []}', encoding="utf-8")
        self.manifest = SimpleNamespace(root=self.theme_root)
        self.drafts = base / "state"
        self.saved = [style("cpu"), style("ram", y=60)]

    def tearDown(self):
        self.tmp.cleanup()

    def test_draft_is_stored_outside_the_theme_folder(self):
        path = write_draft(self.manifest, self.saved, directory=self.drafts)
        self.assertEqual(path.parent, self.drafts)
        self.assertEqual(sorted(p.name for p in self.theme_root.iterdir()), ["overlays.json"])

    def test_changed_draft_round_trips(self):
        edited = [replace(self.saved[0], x=200, glow_radius=8), self.saved[1], style("turing-cpu-usage-1", component_type="cpu-usage", generated_widget=True)]
        write_draft(self.manifest, edited, directory=self.drafts)
        draft = load_draft(self.manifest, self.saved, directory=self.drafts)
        self.assertIsNotNone(draft)
        self.assertEqual(draft.styles, tuple(edited))
        self.assertTrue(draft.matches_saved_theme)

    def test_normalized_generated_widget_counts_as_unchanged(self):
        added = style("turing-cpu-usage-1", component_type="cpu-usage")
        write_draft(self.manifest, [*self.saved, added], directory=self.drafts)
        saved = [*self.saved, replace(added, generated_widget=True)]
        self.assertIsNone(load_draft(self.manifest, saved, directory=self.drafts))

    def test_draft_equal_to_saved_theme_is_dropped(self):
        write_draft(self.manifest, list(reversed(self.saved)), directory=self.drafts)
        self.assertIsNone(load_draft(self.manifest, self.saved, directory=self.drafts))
        self.assertFalse(draft_path(self.manifest, self.drafts).exists())

    def test_theme_saved_after_the_draft_is_reported(self):
        write_draft(self.manifest, [replace(self.saved[0], x=1)], directory=self.drafts)
        (self.theme_root / "overlays.json").write_text('{"elements": [1]}', encoding="utf-8")
        draft = load_draft(self.manifest, self.saved, directory=self.drafts)
        self.assertFalse(draft.matches_saved_theme)

    def test_corrupt_draft_is_removed(self):
        path = draft_path(self.manifest, self.drafts)
        path.parent.mkdir(parents=True)
        path.write_text("{not json", encoding="utf-8")
        self.assertIsNone(load_draft(self.manifest, self.saved, directory=self.drafts))
        self.assertFalse(path.exists())

    def test_clear_draft_is_idempotent(self):
        write_draft(self.manifest, [replace(self.saved[0], x=1)], directory=self.drafts)
        clear_draft(self.manifest, directory=self.drafts)
        clear_draft(self.manifest, directory=self.drafts)
        self.assertIsNone(load_draft(self.manifest, self.saved, directory=self.drafts))

    def test_drafts_of_two_folders_with_the_same_name_do_not_collide(self):
        other_root = Path(self.tmp.name) / "elsewhere" / "My Theme"
        other_root.mkdir(parents=True)
        self.assertNotEqual(
            draft_path(self.manifest, self.drafts),
            draft_path(SimpleNamespace(root=other_root), self.drafts),
        )


if __name__ == "__main__":
    unittest.main()
