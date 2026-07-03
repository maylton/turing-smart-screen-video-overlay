#!/usr/bin/env python3
"""Apply guarded Open Theme YAML action to theme-editor-gtk.py.

This starts the YAML/theme-folder access cleanup after the Safe Session Lifecycle
save guards. It gives users a direct way to open theme.yaml, but with an explicit
warning that external edits must be reloaded before saving in GTK.
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
        overflow_box.append(
            popover_action_button(
                "Reload Theme From Disk",
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
                "Open Theme YAML",
                "text-x-generic-symbolic",
                self.confirm_open_theme_yaml,
                overflow_popover,
            )
        )
        overflow_box.append(
            popover_action_button(
                "Reload Theme From Disk",
''',
        '"Open Theme YAML"',
    )

    text = replace_once(
        text,
        '''    def reload_theme_from_disk(self):
''',
        '''    def confirm_open_theme_yaml(self):
        dialog = Adw.AlertDialog(
            heading="Open theme.yaml externally?",
            body=(
                "External YAML edits are supported, but the GTK editor cannot "
                "merge conflicts automatically. After changing theme.yaml outside "
                "the editor, use Reload Theme From Disk before saving in GTK."
            ),
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("open", "Open YAML")
        dialog.set_close_response("cancel")
        dialog.set_default_response("open")
        dialog.set_response_appearance(
            "open",
            Adw.ResponseAppearance.SUGGESTED,
        )

        def response(_dialog, response_id):
            if response_id == "open":
                self.reveal_generated_media(self.theme_file)

        dialog.connect("response", response)
        dialog.present(self)

    def reload_theme_from_disk(self):
''',
        "def confirm_open_theme_yaml(self):",
    )

    TARGET.write_text(text, encoding="utf-8")
    print("Open Theme YAML action applied to theme-editor-gtk.py")


if __name__ == "__main__":
    main()
