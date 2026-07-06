# SPDX-License-Identifier: GPL-3.0-or-later
"""Consolidated Main App integration for Diagnostics and runtime UI polish.

This module is the single entry point for the Main App / Diagnostics draft work:

- Settings → Maintenance → Diagnostics opens inline inside the main GTK app;
- Apply + Sync + Start status messages are installed;
- the polished Overview Monitor card refreshes automatically.

The helpers are guarded and idempotent so the draft branch can still be tested
from the installer while the source launcher is being consolidated.
"""

from __future__ import annotations

import sys
from typing import Any, Callable, Iterable


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


def _has_titled_widget(root: Any, title: str) -> bool:
    return _find_preferences_group(root, title) is not None


def _install_optional_integration(
    app: Any,
    *,
    label: str,
    importer: Callable[[], Callable[[Any], None]],
) -> None:
    try:
        installer = importer()
    except Exception as exc:  # pragma: no cover - defensive startup guard
        print(
            f"[{label}] could not import main app integration: {exc}",
            file=sys.stderr,
            flush=True,
        )
        return

    try:
        installer(app)
    except Exception as exc:  # pragma: no cover - defensive startup guard
        print(
            f"[{label}] could not install main app integration: {exc}",
            file=sys.stderr,
            flush=True,
        )


def _install_runtime_ui_integrations(app: Any) -> None:
    _install_optional_integration(
        app,
        label="apply-status",
        importer=lambda: __import__(
            "library.main_app_apply_status",
            fromlist=["install_main_app_apply_status"],
        ).install_main_app_apply_status,
    )
    _install_optional_integration(
        app,
        label="overview-refresh",
        importer=lambda: __import__(
            "library.main_app_overview_refresh",
            fromlist=["install_main_app_overview_auto_refresh"],
        ).install_main_app_overview_auto_refresh,
    )


def install_main_app_diagnostics_integration(app: Any) -> None:
    """Install the validated Main App / Diagnostics draft integrations."""

    _install_runtime_ui_integrations(app)

    window_class = getattr(app, "SmartScreenWindow", None)
    if window_class is None or getattr(
        window_class,
        "_main_app_diagnostics_integration_installed",
        False,
    ):
        return

    Gtk = app.Gtk
    Adw = app.Adw
    diagnostics_viewer = app.ROOT / "diagnostics-gtk.py"

    current_build_settings_page = window_class.build_settings_page
    original_build_settings_page = current_build_settings_page

    def open_diagnostics(self, *_args) -> None:
        try:
            from library.main_app_inline_diagnostics import (
                build_inline_diagnostics_page,
            )

            page_name = "diagnostics"
            page = getattr(self, "_inline_diagnostics_page", None)
            if page is None:
                page = build_inline_diagnostics_page(app, self)
                self._inline_diagnostics_page = page
                self.stack.add_named(page, page_name)
            elif hasattr(page, "refresh_diagnostics"):
                page.refresh_diagnostics()
            self.stack.set_visible_child_name(page_name)
        except Exception as exc:
            # Keep the standalone viewer as a fallback during the draft branch.
            try:
                if diagnostics_viewer.is_file():
                    self.launch_script(diagnostics_viewer, use_system_python=True)
                    return
            except Exception:
                pass
            self.toast(f"Could not open diagnostics: {exc}")

    def build_settings_page(self):
        page = original_build_settings_page(self)
        maintenance = _find_preferences_group(page, "Maintenance")
        if maintenance is None:
            return page

        # Some installed test builds were patched by the installer before this
        # integration became centralized. Do not add a duplicate row.
        if _has_titled_widget(page, "Diagnostics"):
            return page

        diagnostics_row = Adw.ActionRow(
            title="Diagnostics",
            subtitle=(
                "Inspect theme, video, runtime, and USB state without "
                "opening the serial port"
            ),
            icon_name="utilities-system-monitor-symbolic",
            activatable=True,
        )
        diagnostics_row.connect("activated", self.open_diagnostics)
        diagnostics_row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
        maintenance.add(diagnostics_row)
        return page

    build_settings_page._diagnostics_integration_wrapper = True

    window_class.open_diagnostics = open_diagnostics
    window_class.build_settings_page = build_settings_page
    window_class._main_app_diagnostics_integration_installed = True
    window_class._diagnostics_integration_installed = True
