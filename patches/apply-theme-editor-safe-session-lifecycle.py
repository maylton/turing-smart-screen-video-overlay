#!/usr/bin/env python3
"""Apply the first safe-session lifecycle patch to theme-editor-gtk.py.

This patch adds a close-request guard for unapplied property editor changes.
It intentionally does not change the project's auto-save behavior yet; it only
prevents typed form edits from being lost when the window closes before the
user clicks Apply.
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
        '''        self.populate_elements()
        self.update_history_buttons()
        self.refresh_preview()
''',
        '''        self.populate_elements()
        self.update_history_buttons()
        self.refresh_preview()
        self.connect("close-request", self.on_close_request)
''',
        'self.connect("close-request", self.on_close_request)',
    )

    text = replace_once(
        text,
        '''    def apply_properties(self):
        if self.selected_path is None:
            return

        node = self.node_at_path(self.selected_path)
        updates = {}
        changed = False

        try:
            for key, widget in self.property_widgets.items():
                old = node[key]

                if key in BOOLEAN_KEYS:
                    new = self.parse_value(key, widget.get_active(), old)
                elif getattr(widget, "_theme_color_widget", False):
                    new = self.color_selector_value(widget)
                else:
                    new = self.parse_value(key, widget.get_text(), old)

                updates[key] = new
                changed = changed or new != old
        except Exception as exc:
            self.error_dialog("Invalid property", str(exc))
            return

        if not changed:
            self.toast("No property changes")
            return

        self.push_undo()
        for key, value in updates.items():
            node[key] = value

        save_yaml_atomic(self.theme_file, self.theme_data)
        self.populate_elements()
        GLib.idle_add(self.restore_tree_selection, self.selected_path)
        self.build_property_rows()
        self.refresh_preview()
        self.toast("Properties updated")
''',
        '''    def property_widget_current_value(self, key, widget, old_value):
        if key in BOOLEAN_KEYS:
            return self.parse_value(key, widget.get_active(), old_value)
        if getattr(widget, "_theme_color_widget", False):
            return self.color_selector_value(widget)
        return self.parse_value(key, widget.get_text(), old_value)

    def has_pending_property_edits(self):
        if self.selected_path is None or not self.property_widgets:
            return False

        try:
            node = self.node_at_path(self.selected_path)
        except Exception:
            return False
        if not isinstance(node, dict):
            return False

        for key, widget in self.property_widgets.items():
            if key not in node:
                continue
            old = node[key]
            try:
                new = self.property_widget_current_value(key, widget, old)
            except Exception:
                # Invalid typed values are still unsaved edits and should not be
                # silently discarded by a window close.
                return True
            if new != old:
                return True
        return False

    def discard_pending_property_edits(self):
        if self.selected_path is not None:
            try:
                self.build_property_rows()
            except Exception:
                self.clear_property_group()
        self.toast("Pending property edits discarded")

    def on_close_request(self, *_args):
        if not self.has_pending_property_edits():
            return False

        dialog = Adw.AlertDialog(
            heading="Save pending property changes?",
            body=(
                "The selected element has typed changes that have not been "
                "applied yet. Save them before closing?"
            ),
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("discard", "Discard")
        dialog.add_response("save", "Save and close")
        dialog.set_close_response("cancel")
        dialog.set_default_response("save")
        dialog.set_response_appearance(
            "discard",
            Adw.ResponseAppearance.DESTRUCTIVE,
        )
        dialog.set_response_appearance(
            "save",
            Adw.ResponseAppearance.SUGGESTED,
        )

        def response(_dialog, response_id):
            if response_id == "save":
                if self.apply_properties():
                    self.destroy()
            elif response_id == "discard":
                self.discard_pending_property_edits()
                self.destroy()

        dialog.connect("response", response)
        dialog.present(self)
        return True

    def apply_properties(self):
        if self.selected_path is None:
            return False

        node = self.node_at_path(self.selected_path)
        updates = {}
        changed = False

        try:
            for key, widget in self.property_widgets.items():
                old = node[key]
                new = self.property_widget_current_value(key, widget, old)

                updates[key] = new
                changed = changed or new != old
        except Exception as exc:
            self.error_dialog("Invalid property", str(exc))
            return False

        if not changed:
            self.toast("No property changes")
            return False

        self.push_undo()
        for key, value in updates.items():
            node[key] = value

        save_yaml_atomic(self.theme_file, self.theme_data)
        self.populate_elements()
        GLib.idle_add(self.restore_tree_selection, self.selected_path)
        self.build_property_rows()
        self.refresh_preview()
        self.toast("Properties updated")
        return True
''',
        'def on_close_request(self, *_args):',
    )

    TARGET.write_text(text, encoding="utf-8")
    print("Safe session lifecycle patch applied to theme-editor-gtk.py")


if __name__ == "__main__":
    main()
