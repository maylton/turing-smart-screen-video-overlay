# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime integration for embedding Theme Editor in the main GTK app."""

from __future__ import annotations

from pathlib import Path

from library.embedded_theme_editor import EmbeddedThemeEditorPage
from library.theme_gallery import ThemeRecord


def install_embedded_theme_editor_patches(app, *, root: Path) -> None:
    """Patch SmartScreenWindow so gallery Edit opens an embedded editor page."""

    original_init = app.SmartScreenWindow.__init__
    original_open_theme_record_editor = getattr(
        app.SmartScreenWindow,
        "open_theme_record_editor",
        None,
    )

    def select_sidebar_page(self, page_name: str) -> None:
        sidebar = getattr(self, "sidebar", None)
        if sidebar is None:
            return
        row = sidebar.get_first_child()
        while row is not None:
            if getattr(row, "page_name", None) == page_name:
                sidebar.select_row(row)
                return
            row = row.get_next_sibling()

    def show_themes_page(self) -> None:
        self.stack.set_visible_child_name("themes")
        select_sidebar_page(self, "themes")
        self.refresh_theme_list()

    def open_external_theme_editor(self, theme_name: str) -> None:
        self.launch_script(
            app.THEME_EDITOR,
            theme_name,
            use_system_python=True,
        )

    def open_embedded_theme_editor(self, theme_name: str) -> None:
        page = getattr(self, "embedded_theme_editor_page", None)
        if page is None:
            if original_open_theme_record_editor is None:
                self.toast("Embedded editor page is not available")
                return
            original_open_theme_record_editor(self, ThemeRecord(
                name=theme_name,
                directory=app.THEMES_DIR / theme_name,
                yaml_file=None,
                preview_file=app.THEMES_DIR / theme_name / "preview.png",
            ))
            return

        try:
            page.open_theme(theme_name)
        except Exception as exc:
            self.toast(f"Could not open embedded editor: {exc}")
            return
        self.stack.set_visible_child_name("theme-editor")
        self.toast(f"Editing {theme_name} inside the main app")

    def open_theme_record_editor(self, record: ThemeRecord) -> None:
        open_embedded_theme_editor(self, record.name)

    def patched_init(self, application):
        original_init(self, application)
        self.embedded_theme_editor_page = EmbeddedThemeEditorPage(
            root=root,
            application=application,
            on_back=lambda: show_themes_page(self),
            on_open_external=lambda theme_name: open_external_theme_editor(
                self,
                theme_name,
            ),
        )
        self.stack.add_named(self.embedded_theme_editor_page, "theme-editor")

    app.SmartScreenWindow.__init__ = patched_init
    app.SmartScreenWindow.show_themes_page = show_themes_page
    app.SmartScreenWindow.open_embedded_theme_editor = open_embedded_theme_editor
    app.SmartScreenWindow.open_external_theme_editor = open_external_theme_editor
    app.SmartScreenWindow.open_theme_record_editor = open_theme_record_editor
