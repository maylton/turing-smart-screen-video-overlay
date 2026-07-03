#!/usr/bin/env python3
"""Apply external theme.yaml change guard to theme-editor-gtk.py.

This is the second Safe Session Lifecycle slice. It prevents the GTK editor from
silently overwriting a theme file that was changed on disk after the editor loaded
or after its last successful save.
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
        '''        self.theme_data = load_yaml(self.theme_file)
        self.session_original = copy.deepcopy(self.theme_data)
''',
        '''        self.theme_data = load_yaml(self.theme_file)
        self.theme_file_signature = self.current_theme_file_signature()
        self.session_original = copy.deepcopy(self.theme_data)
''',
        "self.theme_file_signature = self.current_theme_file_signature()",
    )

    text = replace_once(
        text,
        '''    def set_property_widget_value(self, key, value):
        widget = self.property_widgets.get(key)
        if widget is None:
            return

        if isinstance(widget, Adw.EntryRow):
            widget.set_text(self.value_to_text(value))
            self.sync_property_preset_dropdown(widget, value)
        elif isinstance(widget, Adw.SwitchRow):
            widget.set_active(bool(value))
        elif getattr(widget, "_theme_color_widget", False):
            self.set_color_selector_value(widget, value)
        elif hasattr(widget, "set_text"):
            widget.set_text(self.value_to_text(value))

    def property_preset_options(self, key, current_value):
''',
        '''    def set_property_widget_value(self, key, value):
        widget = self.property_widgets.get(key)
        if widget is None:
            return

        if isinstance(widget, Adw.EntryRow):
            widget.set_text(self.value_to_text(value))
            self.sync_property_preset_dropdown(widget, value)
        elif isinstance(widget, Adw.SwitchRow):
            widget.set_active(bool(value))
        elif getattr(widget, "_theme_color_widget", False):
            self.set_color_selector_value(widget, value)
        elif hasattr(widget, "set_text"):
            widget.set_text(self.value_to_text(value))

    def current_theme_file_signature(self):
        try:
            stat = self.theme_file.stat()
        except FileNotFoundError:
            return None
        return stat.st_mtime_ns, stat.st_size

    def mark_theme_file_saved(self):
        self.theme_file_signature = self.current_theme_file_signature()

    def theme_file_changed_on_disk(self):
        return self.current_theme_file_signature() != self.theme_file_signature

    def show_external_theme_change_error(self):
        self.error_dialog(
            "Theme changed outside the editor",
            (
                f"{self.theme_file} was modified after this editor loaded it.\n\n"
                "To avoid overwriting external edits, close and reopen the theme "
                "before saving from the GTK editor."
            ),
        )

    def save_theme_data(self):
        if self.theme_file_changed_on_disk():
            self.show_external_theme_change_error()
            return False

        try:
            save_yaml_atomic(self.theme_file, self.theme_data)
        except Exception as exc:
            self.error_dialog("Could not save theme", str(exc))
            return False

        self.mark_theme_file_saved()
        return True

    def property_preset_options(self, key, current_value):
''',
        "def save_theme_data(self):",
    )

    replacements = [
        (
            '''            save_yaml_atomic(self.theme_file, self.theme_data)
            self.populate_elements()
''',
            '''            if not self.save_theme_data():
                self.theme_data = load_yaml(self.theme_file)
                self.mark_theme_file_saved()
                self.populate_elements()
                return
            self.populate_elements()
''',
            "restore_history_state save guard",
        ),
        (
            '''        save_yaml_atomic(self.theme_file, self.theme_data)
        self.populate_elements()
''',
            '''        if not self.save_theme_data():
            return False
        self.populate_elements()
''',
            "apply_properties save guard",
        ),
        (
            '''        save_yaml_atomic(self.theme_file, self.theme_data)
        self.populate_elements()
        GLib.idle_add(self.restore_tree_selection, self.selected_path)
        self.build_property_rows()
        self.refresh_preview()
        self.toast("Element restored")
''',
            '''        if not self.save_theme_data():
            return
        self.populate_elements()
        GLib.idle_add(self.restore_tree_selection, self.selected_path)
        self.build_property_rows()
        self.refresh_preview()
        self.toast("Element restored")
''',
            "reset_selected save guard",
        ),
        (
            '''        save_yaml_atomic(self.theme_file, self.theme_data)
        self.refresh_preview()
        self.drag_dirty = False
''',
            '''        if not self.save_theme_data():
            return
        self.refresh_preview()
        self.drag_dirty = False
''',
            "preview drag save guard",
        ),
        (
            '''            try:
                save_yaml_atomic(self.theme_file, self.theme_data)
                shutil.copytree(self.theme_dir, destination)
''',
            '''            try:
                if not self.save_theme_data():
                    return
                shutil.copytree(self.theme_dir, destination)
''',
            "save_as source save guard",
        ),
        (
            '''            try:
                save_yaml_atomic(self.theme_file, self.theme_data)
                old_dir.rename(destination)
''',
            '''            try:
                if not self.save_theme_data():
                    return
                old_dir.rename(destination)
''',
            "rename source save guard",
        ),
        (
            '''    def save(self):
        save_yaml_atomic(self.theme_file, self.theme_data)
        self.toast("Theme saved")
''',
            '''    def save(self):
        if self.save_theme_data():
            self.toast("Theme saved")
''',
            "save button external change guard",
        ),
    ]

    for old, new, marker in replacements:
        text = replace_once(text, old, new, marker)

    TARGET.write_text(text, encoding="utf-8")
    print("External theme.yaml change guard applied to theme-editor-gtk.py")


if __name__ == "__main__":
    main()
