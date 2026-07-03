#!/usr/bin/env python3
"""Apply Reload Theme From Disk action to theme-editor-gtk.py.

This complements the external theme.yaml change guard by giving the user a safe
in-app recovery path after external edits are detected.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()
TARGET = ROOT / "theme-editor-gtk.py"


def replace_once(text: str, old: str, new: str, marker: str) -> str:
    if marker in text:
        print(f"SKIP: {marker!r} already present")
        return text
    if old not in text:
        raise SystemExit(f"Could not find expected block for {marker!r}")
    print(f"OK: adding {marker}")
    return text.replace(old, new, 1)


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '''        overflow_box.append(
            popover_action_button(
                "Open Theme Folder",
                "folder-open-symbolic",
                lambda: self.reveal_generated_media(self.theme_dir),
                overflow_popover,
            )
        )
        overflow_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
''',
        '''        overflow_box.append(
            popover_action_button(
                "Open Theme Folder",
                "folder-open-symbolic",
                lambda: self.reveal_generated_media(self.theme_dir),
                overflow_popover,
            )
        )
        overflow_box.append(
            popover_action_button(
                "Reload Theme From Disk",
                "view-refresh-symbolic",
                self.confirm_reload_theme_from_disk,
                overflow_popover,
            )
        )
        overflow_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
''',
        '"Reload Theme From Disk"',
    )

    text = replace_once(
        text,
        '''        self.error_dialog(
            "Theme changed outside the editor",
            (
                f"{self.theme_file} was modified after this editor loaded it.\\n\\n"
                "To avoid overwriting external edits, close and reopen the theme "
                "before saving from the GTK editor."
            ),
        )
''',
        '''        self.error_dialog(
            "Theme changed outside the editor",
            (
                f"{self.theme_file} was modified after this editor loaded it.\\n\\n"
                "Use Reload Theme From Disk from the overflow menu before "
                "saving from the GTK editor."
            ),
        )
''',
        'Use Reload Theme From Disk from the overflow menu',
    )

    text = replace_once(
        text,
        '''    def redo(self):
        if not self.redo_stack:
            self.toast("Nothing to redo")
            self.update_history_buttons()
            return

        self.undo_stack.append(self.make_history_state())
        state = self.redo_stack.pop()
        self.restore_history_state(state)
        self.toast("Redo")


    def save_as(self):
''',
        '''    def redo(self):
        if not self.redo_stack:
            self.toast("Nothing to redo")
            self.update_history_buttons()
            return

        self.undo_stack.append(self.make_history_state())
        state = self.redo_stack.pop()
        self.restore_history_state(state)
        self.toast("Redo")

    def reload_theme_from_disk(self):
        target_path = copy.deepcopy(self.selected_path)

        try:
            reloaded = load_yaml(self.theme_file)
        except Exception as exc:
            self.error_dialog("Could not reload theme", str(exc))
            return

        self.theme_data = reloaded
        self.mark_theme_file_saved()
        self.session_original = copy.deepcopy(reloaded)
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.selected_path = target_path

        self.populate_elements()

        if self.selected_path is not None:
            try:
                self.node_at_path(self.selected_path)
                self.build_property_rows()
            except Exception:
                self.selected_path = None
                self.clear_property_group()
        else:
            self.clear_property_group()

        GLib.idle_add(self.restore_tree_selection, self.selected_path)
        self.update_elements_summary()
        self.update_catalog_status()
        self.update_actions_sensitivity()
        self.update_history_buttons()
        self.refresh_preview()
        self.toast("Theme reloaded from disk")

    def confirm_reload_theme_from_disk(self):
        changed_on_disk = self.theme_file_changed_on_disk()
        pending_edits = self.has_pending_property_edits()

        if not changed_on_disk and not pending_edits:
            self.toast("Theme file is already up to date")
            return

        details = []
        if changed_on_disk:
            details.append("The theme YAML changed outside the GTK editor.")
        if pending_edits:
            details.append("The selected element has unapplied typed changes.")
        details.append("Reloading discards GTK-only pending edits and clears Undo/Redo history.")

        dialog = Adw.AlertDialog(
            heading="Reload theme from disk?",
            body="\\n\\n".join(details),
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("reload", "Reload")
        dialog.set_close_response("cancel")
        dialog.set_default_response("reload")
        dialog.set_response_appearance(
            "reload",
            Adw.ResponseAppearance.SUGGESTED,
        )

        def response(_dialog, response_id):
            if response_id == "reload":
                self.reload_theme_from_disk()

        dialog.connect("response", response)
        dialog.present(self)

    def save_as(self):
''',
        'def reload_theme_from_disk(self):',
    )

    TARGET.write_text(text, encoding="utf-8")
    print("Reload Theme From Disk patch applied to theme-editor-gtk.py")


if __name__ == "__main__":
    main()
