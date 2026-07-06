# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional diagnostics integration for the main GTK configuration app.

This module is loaded by ``usercustomize.py`` only for ``configure-gtk.py``.
It keeps the Diagnostics viewer optional and low-risk while we validate the UI
before merging it permanently into the main launcher code.
"""

from __future__ import annotations

from typing import Any, Iterable


def _iter_widget_children(widget: Any) -> Iterable[Any]:
    """Yield direct GTK4 children without relying on removed GTK3 APIs."""
    child = None
    if hasattr(widget, "get_first_child"):
        try:
            child = widget.get_first_child()
        except Exception:
            child = None

    while child is not None:
        yield child
        try:
            child = child.get_next_sibling()
        except Exception:
            child = None


def _walk_widgets(widget: Any) -> Iterable[Any]:
    yield widget
    for child in _iter_widget_children(widget):
        yield from _walk_widgets(child)


def _find_preferences_group(root: Any, title: str) -> Any | None:
    for widget in _walk_widgets(root):
        if not hasattr(widget, "get_title"):
            continue
        try:
            if widget.get_title() == title:
                return widget
        except Exception:
            continue
    return None


def install_main_app_diagnostics_integration(app: Any) -> None:
    """Add Settings → Maintenance → Diagnostics to the GTK launcher."""
    window_class = getattr(app, "SmartScreenWindow", None)
    if window_class is None or getattr(window_class, "_diagnostics_integration_installed", False):
        return

    Gtk = app.Gtk
    Adw = app.Adw
    Gio = app.Gio
    diagnostics_viewer = app.ROOT / "diagnostics-gtk.py"

    original_install_actions = window_class.install_actions
    original_build_settings_page = window_class.build_settings_page

    def open_diagnostics(self, *_args) -> None:
        if not diagnostics_viewer.is_file():
            self.toast("diagnostics-gtk.py was not found")
            return
        self.launch_script(diagnostics_viewer, use_system_python=True)

    def install_actions(self) -> None:
        original_install_actions(self)
        if hasattr(self, "lookup_action") and self.lookup_action("open-diagnostics") is not None:
            return
        action = Gio.SimpleAction.new("open-diagnostics", None)
        action.connect("activate", self.open_diagnostics)
        self.add_action(action)

    def build_settings_page(self):
        page = original_build_settings_page(self)
        maintenance = _find_preferences_group(page, "Maintenance")
        if maintenance is None:
            return page

        diagnostics_row = Adw.ActionRow(
            title="Diagnostics",
            subtitle="Inspect theme, video, runtime, and USB state without opening the serial port",
            icon_name="utilities-system-monitor-symbolic",
            activatable=True,
        )
        diagnostics_row.set_action_name("win.open-diagnostics")
        diagnostics_row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
        maintenance.add(diagnostics_row)
        return page

    window_class.open_diagnostics = open_diagnostics
    window_class.install_actions = install_actions
    window_class.build_settings_page = build_settings_page
    window_class._diagnostics_integration_installed = True
