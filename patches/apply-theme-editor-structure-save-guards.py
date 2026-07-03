#!/usr/bin/env python3
"""Apply structure/edit save guard coverage to theme-editor-gtk.py.

This Safe Session Lifecycle slice routes structural/theme mutations that still
used direct save_yaml_atomic calls through save_theme_data(), so external
`theme.yaml` edits are not overwritten by layer moves, add/delete/enable actions,
or image layout inspector Apply.
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
        '''    def finish_structure_change(self, selected_path, message):
        save_yaml_atomic(self.theme_file, self.theme_data)
        self.populate_elements()
        self.selected_path = selected_path
        GLib.idle_add(self.restore_tree_selection, selected_path)
        if selected_path is not None:
            try:
                self.build_property_rows()
            except Exception:
                pass
        else:
            self.clear_property_group()
        self.update_elements_summary()
        self.update_catalog_status()
        self.update_actions_sensitivity()
        self.refresh_preview()
        self.toast(message)
''',
        '''    def restore_after_failed_structure_save(self):
        if self.undo_stack:
            state = self.undo_stack.pop()
            self.theme_data = copy.deepcopy(state["theme_data"])
            self.selected_path = copy.deepcopy(state.get("selected_path"))

        self.populate_elements()
        if self.selected_path is not None:
            try:
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

    def finish_structure_change(self, selected_path, message):
        if not self.save_theme_data():
            self.restore_after_failed_structure_save()
            return

        self.populate_elements()
        self.selected_path = selected_path
        GLib.idle_add(self.restore_tree_selection, selected_path)
        if selected_path is not None:
            try:
                self.build_property_rows()
            except Exception:
                pass
        else:
            self.clear_property_group()
        self.update_elements_summary()
        self.update_catalog_status()
        self.update_actions_sensitivity()
        self.refresh_preview()
        self.toast(message)
''',
        "def restore_after_failed_structure_save(self):",
    )

    text = replace_once(
        text,
        '''                for key, value in final_values.items():
                    current_node[key] = value
                save_yaml_atomic(self.theme_file, self.theme_data)
''',
        '''                for key, value in final_values.items():
                    current_node[key] = value
                if not self.save_theme_data():
                    for key, value in old_values.items():
                        current_node[key] = value
                    if pushed and self.undo_stack:
                        self.undo_stack.pop()
                        self.update_history_buttons()
                    return
''',
        "apply_layout save_theme_data guard",
    )

    text = replace_once(
        text,
        '''        self.push_undo()
        try:
            self.theme_data = move_layer(self.theme_data, selected_path, action)
''',
        '''        pushed = self.push_undo()
        try:
            self.theme_data = move_layer(self.theme_data, selected_path, action)
''',
        "move_selected_layer pushed guard",
    )

    text = replace_once(
        text,
        '''        save_yaml_atomic(self.theme_file, self.theme_data)
        self.populate_elements()
''',
        '''        if not self.save_theme_data():
            if pushed and self.undo_stack:
                state = self.undo_stack.pop()
                self.theme_data = copy.deepcopy(state["theme_data"])
                self.selected_path = copy.deepcopy(state.get("selected_path"))
            self.populate_elements()
            GLib.idle_add(self.restore_tree_selection, self.selected_path)
            self.update_elements_summary()
            self.update_catalog_status()
            self.update_actions_sensitivity()
            self.update_history_buttons()
            self.refresh_preview()
            return
        self.populate_elements()
''',
        "move_selected_layer save_theme_data guard",
    )

    text = replace_once(
        text,
        '''            self.selected_path = None
            save_yaml_atomic(self.theme_file, self.theme_data)
            self.populate_elements()
            self.clear_property_group()
''',
        '''            self.selected_path = None
            if not self.save_theme_data():
                self.restore_after_failed_structure_save()
                return
            self.populate_elements()
            self.clear_property_group()
''',
        "delete_selected save_theme_data guard",
    )

    TARGET.write_text(text, encoding="utf-8")
    print("Structure save guards applied to theme-editor-gtk.py")


if __name__ == "__main__":
    main()
