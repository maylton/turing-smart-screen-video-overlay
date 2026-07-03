#!/usr/bin/env python3
"""Apply final Classic Editor retirement gate to theme-editor-gtk.py.

This reduces the classic editor from a prominent escape hatch to an advanced
legacy fallback with an explicit confirmation dialog and clear guidance about
using the GTK editor first.
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
                "Open Classic Editor",
                "applications-system-symbolic",
                self.open_classic_editor,
                overflow_popover,
            )
        )
''',
        '''        overflow_box.append(
            popover_action_button(
                "Advanced / Legacy Editor…",
                "applications-system-symbolic",
                self.confirm_open_classic_editor,
                overflow_popover,
            )
        )
''',
        '"Advanced / Legacy Editor…"',
    )

    text = replace_once(
        text,
        '''        classic = Gtk.Button(
            label="Open classic editor…",
            tooltip_text="Open the original editor for tools not yet migrated to GTK",
        )
        classic.connect("clicked", lambda *_: self.open_classic_editor())
        box.append(classic)
        return box
''',
        '''        legacy_note = Gtk.Label(
            label=(
                "Legacy editor access moved to More theme actions → "
                "Advanced / Legacy Editor…"
            ),
            xalign=0,
            wrap=True,
        )
        legacy_note.add_css_class("dim-label")
        box.append(legacy_note)
        return box
''',
        "Legacy editor access moved to More theme actions",
    )

    text = replace_once(
        text,
        '''    def open_classic_editor(self):
        try:
            subprocess.Popen(
                [project_python(), str(CLASSIC_EDITOR), self.theme_name],
                cwd=str(ROOT),
                start_new_session=True,
            )
        except Exception as exc:
            self.toast(f"Could not open classic editor: {exc}")
''',
        '''    def launch_classic_editor(self):
        try:
            subprocess.Popen(
                [project_python(), str(CLASSIC_EDITOR), self.theme_name],
                cwd=str(ROOT),
                start_new_session=True,
            )
        except Exception as exc:
            self.toast(f"Could not open classic editor: {exc}")

    def confirm_open_classic_editor(self):
        dialog = Adw.AlertDialog(
            heading="Open legacy editor?",
            body=(
                "Most theme editing workflows now live in the GTK editor. "
                "The legacy editor is kept as an advanced fallback for tools "
                "that have not fully migrated yet.\\n\\n"
                "Before using it, save or reload the GTK editor state. Changes "
                "made outside this window may require Reload Theme From Disk "
                "before saving here again."
            ),
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("open", "Open Legacy Editor")
        dialog.set_close_response("cancel")
        dialog.set_default_response("cancel")
        dialog.set_response_appearance(
            "open",
            Adw.ResponseAppearance.DESTRUCTIVE,
        )

        def response(_dialog, response_id):
            if response_id == "open":
                self.launch_classic_editor()

        dialog.connect("response", response)
        dialog.present(self)
''',
        "def confirm_open_classic_editor(self):",
    )

    TARGET.write_text(text, encoding="utf-8")
    print("Legacy editor retirement gate applied to theme-editor-gtk.py")


if __name__ == "__main__":
    main()
