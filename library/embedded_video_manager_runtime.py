# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime integration for embedding Video Manager in the main GTK app."""

from __future__ import annotations

from pathlib import Path

from library.embedded_video_manager import EmbeddedVideoManagerPage


def install_embedded_video_manager_patches(app, *, root: Path) -> None:
    """Patch SmartScreenWindow so every Video Manager entry opens in-app."""

    original_init = app.SmartScreenWindow.__init__

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

    def show_overview_page(self) -> None:
        self.stack.set_visible_child_name("overview")
        select_sidebar_page(self, "overview")
        self.refresh_overview()

    def open_external_video_manager(self) -> None:
        self.launch_script(
            app.VIDEO_MANAGER,
            use_system_python=True,
        )

    def open_embedded_video_manager(self) -> None:
        page = getattr(self, "embedded_video_manager_page", None)
        if page is None:
            self.toast("Embedded video manager page is not available")
            return

        try:
            page.open_manager()
            page.refresh()
        except Exception as exc:
            self.toast(f"Could not open embedded video manager: {exc}")
            return
        self.stack.set_visible_child_name("video-manager")
        self.toast("Video Manager opened inside the main app")

    def open_video_manager(self, *_args) -> None:
        """Handle win.open-videos from Overview, Tools, and future buttons."""
        open_embedded_video_manager(self)

    def patched_init(self, application):
        original_init(self, application)
        self.embedded_video_manager_page = EmbeddedVideoManagerPage(
            root=root,
            application=application,
            on_back=lambda: show_overview_page(self),
            on_open_external=lambda: open_external_video_manager(self),
        )
        self.stack.add_named(self.embedded_video_manager_page, "video-manager")

    app.SmartScreenWindow.__init__ = patched_init
    app.SmartScreenWindow.show_overview_page = show_overview_page
    app.SmartScreenWindow.open_embedded_video_manager = open_embedded_video_manager
    app.SmartScreenWindow.open_external_video_manager = open_external_video_manager
    app.SmartScreenWindow.open_video_manager = open_video_manager
