#!/usr/bin/env python3
"""Apply YAML/theme-folder access polish to theme-editor-gtk.py.

This implements the next slice from docs/THEME_EDITOR_ROADMAP_STATUS.md:
small, safe file-access actions around the current theme folder and YAML file.
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
                "Open Theme YAML",
                "text-x-generic-symbolic",
                self.confirm_open_theme_yaml,
                overflow_popover,
            )
        )
''',
        '''        overflow_box.append(
            popover_action_button(
                "Copy Theme Folder Path",
                "edit-copy-symbolic",
                self.copy_theme_folder_path,
                overflow_popover,
            )
        )
        overflow_box.append(
            popover_action_button(
                "Copy Theme YAML Path",
                "edit-copy-symbolic",
                self.copy_theme_yaml_path,
                overflow_popover,
            )
        )
        overflow_box.append(
            popover_action_button(
                "Open Theme Folder",
                "folder-open-symbolic",
                lambda: self.reveal_generated_media(self.theme_dir),
                overflow_popover,
            )
        )
        overflow_box.append(
            popover_action_button(
                "Open Theme Folder in Terminal",
                "utilities-terminal-symbolic",
                self.open_theme_folder_terminal,
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
''',
        '"Copy Theme YAML Path"',
    )

    text = replace_once(
        text,
        '''    def open_theme_yaml_external(self):
''',
        '''    def copy_text_to_clipboard(self, text, label):
        copied = False
        errors = []

        display = Gdk.Display.get_default()
        if display is not None:
            try:
                clipboard = display.get_clipboard()
                clipboard.set(text)
                copied = True
            except Exception as exc:
                errors.append(f"GTK clipboard: {exc}")

        if not copied:
            import shutil

            for command in (
                ["wl-copy"],
                ["xclip", "-selection", "clipboard"],
                ["xsel", "--clipboard", "--input"],
            ):
                if not shutil.which(command[0]):
                    continue
                try:
                    subprocess.run(
                        command,
                        input=text,
                        text=True,
                        check=True,
                        timeout=2,
                    )
                    copied = True
                    break
                except Exception as exc:
                    errors.append(f"{command[0]}: {exc}")

        if copied:
            self.toast(f"{label} copied")
            return

        detail = f"Could not copy {label.lower()} to the clipboard.\\n\\n{text}"
        if errors:
            detail += "\\n\\nAttempts:\\n" + "\\n".join(errors)
        self.error_dialog("Could not copy path", detail)

    def copy_theme_folder_path(self):
        self.copy_text_to_clipboard(str(self.theme_dir), "Theme folder path")

    def copy_theme_yaml_path(self):
        self.copy_text_to_clipboard(str(self.theme_file), "Theme YAML path")

    def open_theme_folder_terminal(self):
        import shutil

        folder = str(self.theme_dir)
        candidates = []

        if shutil.which("kitty"):
            candidates.append(["kitty", "--working-directory", folder])
        if shutil.which("alacritty"):
            candidates.append(["alacritty", "--working-directory", folder])
        if shutil.which("foot"):
            candidates.append(["foot"])
        if shutil.which("ghostty"):
            candidates.append(["ghostty", "--working-directory", folder])
        if shutil.which("wezterm"):
            candidates.append(["wezterm", "start", "--cwd", folder])
        if shutil.which("konsole"):
            candidates.append(["konsole", "--workdir", folder])
        if shutil.which("gnome-terminal"):
            candidates.append(["gnome-terminal", "--working-directory", folder])
        if shutil.which("kgx"):
            candidates.append(["kgx"])
        if shutil.which("xterm"):
            candidates.append(["xterm"])

        errors = []
        for command in candidates:
            try:
                subprocess.Popen(
                    command,
                    cwd=folder,
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self.toast("Opening theme folder in terminal")
                return
            except Exception as exc:
                errors.append(f"{command[0]}: {exc}")

        detail = (
            "No supported terminal launcher was found.\\n\\n"
            f"Theme folder:\\n{folder}\\n\\n"
            "Install a terminal such as kitty, alacritty, foot, ghostty, "
            "wezterm, konsole, gnome-terminal, kgx, or xterm."
        )
        if errors:
            detail += "\\n\\nAttempts:\\n" + "\\n".join(errors)
        self.error_dialog("Could not open terminal", detail)

    def open_theme_yaml_external(self):
''',
        "def copy_theme_yaml_path(self):",
    )

    TARGET.write_text(text, encoding="utf-8")
    print("YAML/theme-folder access polish applied to theme-editor-gtk.py")


if __name__ == "__main__":
    main()
