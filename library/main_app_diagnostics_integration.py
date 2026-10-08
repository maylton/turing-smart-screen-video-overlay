# SPDX-License-Identifier: GPL-3.0-or-later
"""Inline Diagnostics and Theme Editor pages for the main window.

Settings → Maintenance → Diagnostics and the gallery "Edit" action open inline
pages, falling back to the standalone tools.
"""

from __future__ import annotations

import sys
from typing import Any, Iterable

from gi.repository import Adw, Gtk

from library import main_app_base as app


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


def _widget_title(widget: Any) -> str:
    getter = getattr(widget, "get_title", None)
    if callable(getter):
        try:
            return str(getter() or "")
        except Exception:
            pass
    return ""


def _widget_label(widget: Any) -> str:
    getter = getattr(widget, "get_label", None)
    if callable(getter):
        try:
            return str(getter() or "")
        except Exception:
            pass
    return ""


def _translated_values(value: str) -> set[str]:
    values = {value}
    try:
        from library.i18n import t as _

        values.add(_(value))
    except Exception:
        pass
    return values


def _matches_translated_value(actual: str, expected: str) -> bool:
    return actual in _translated_values(expected)


def _find_titled_widget(root: Any, title: str) -> Any | None:
    for widget in _walk_widgets(root):
        if _matches_translated_value(_widget_title(widget), title):
            return widget
    return None


def _has_titled_widget(root: Any, title: str) -> bool:
    return _find_titled_widget(root, title) is not None


def _find_settings_content_box(root: Any) -> Any | None:
    """Find the vertical content box of the Settings page as a fallback."""
    for widget in _walk_widgets(root):
        if not isinstance(widget, Gtk.Box):
            continue
        for child in _iter_widget_children(widget):
            if _matches_translated_value(_widget_label(child), "Settings"):
                return widget
    return None


def _remove_stack_page(stack: Any, page_name: str) -> None:
    existing = None
    getter = getattr(stack, "get_child_by_name", None)
    if callable(getter):
        try:
            existing = getter(page_name)
        except Exception:
            existing = None
    if existing is None:
        return
    remover = getattr(stack, "remove", None)
    if callable(remover):
        try:
            remover(existing)
        except Exception:
            pass


def _html_theme_record(theme_name: str):
    """Return an HTML gallery record without routing it through YAML tools."""
    try:
        from library.theme_engine import ThemeManifest
        from library.theme_gallery import ThemeRecord

        directory = app.THEMES_DIR / theme_name
        manifest = ThemeManifest.load(directory)
        if manifest.engine != "html":
            return None
        native_video = manifest.native_video_overlay
        return ThemeRecord(
            name=theme_name,
            directory=directory,
            yaml_file=None,
            preview_file=directory / "preview.png",
            engine="html",
            resolution=(manifest.width, manifest.height),
            permissions=manifest.permissions,
            native_video_local=native_video.local_path if native_video is not None else "",
            native_video_device=native_video.device_path if native_video is not None else "",
        )
    except Exception:
        return None


def _make_diagnostics_row(window: Any) -> Any:
    diagnostics_row = Adw.ActionRow(
        title="Diagnostics",
        subtitle="Inspect theme, video, runtime, and USB state without opening the serial port",
        icon_name="utilities-system-monitor-symbolic",
        activatable=True,
    )
    diagnostics_row.connect("activated", window.open_diagnostics)
    diagnostics_row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
    return diagnostics_row


def _add_diagnostics_row(window: Any, root: Any) -> bool:
    if _has_titled_widget(root, "Diagnostics"):
        return True

    maintenance = _find_titled_widget(root, "Maintenance")
    if maintenance is not None:
        maintenance.add(_make_diagnostics_row(window))
        return True

    # Fallback: the Maintenance group may be hard to find after the window has
    # been constructed. Add a dedicated group instead of dropping the entry.
    settings_box = _find_settings_content_box(root)
    if settings_box is None:
        return False

    diagnostics_group = Adw.PreferencesGroup(
        title="Diagnostics",
        description="Inspect theme, video, runtime, and USB state without opening the display serial port.",
    )
    diagnostics_group.add(_make_diagnostics_row(window))
    settings_box.append(diagnostics_group)
    return True


class DiagnosticsMixin:
    """Inline Diagnostics and Theme Editor pages, and the Settings entry."""

    def __init__(self, application):
        super().__init__(application)
        # Safety net for builds where Settings was constructed before this
        # mixin's build_settings_page could add the entry.
        try:
            if not _add_diagnostics_row(self, self):
                print("[diagnostics] could not find Settings page after window init", file=sys.stderr, flush=True)
        except Exception as exc:  # pragma: no cover - defensive startup guard
            print(f"[diagnostics] could not add Settings row after init: {exc}", file=sys.stderr, flush=True)

    def build_settings_page(self):
        page = super().build_settings_page()
        if not _add_diagnostics_row(self, page):
            print("[diagnostics] Settings page was built but no Diagnostics target was found", file=sys.stderr, flush=True)
        return page

    def open_diagnostics(self, *_args) -> None:
        try:
            from library.main_app_inline_diagnostics import build_inline_diagnostics_page

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
            # Fall back to the standalone viewer.
            try:
                viewer = app.ROOT / "diagnostics-gtk.py"
                if viewer.is_file():
                    self.launch_script(viewer, use_system_python=True)
                    return
            except Exception:
                pass
            self.toast(f"Could not open diagnostics: {exc}")

    def open_theme_editor(self, *_args) -> None:
        self._open_theme_editor_theme(app.read_current_theme())

    def open_theme_editor_record(self, record, *_args) -> None:
        self._open_theme_editor_theme(getattr(record, "name", ""))

    def _open_theme_editor_theme(self, theme_name: str) -> None:
        theme_name = str(theme_name or "").strip()
        if not theme_name:
            self.toast("No active theme configured")
            return

        html_record = _html_theme_record(theme_name)
        if html_record is not None:
            authoring_dialog = getattr(self, "show_html_theme_authoring_dialog", None)
            if callable(authoring_dialog):
                authoring_dialog(html_record)
            else:
                self.toast("HTML theme editor is not available")
            return

        try:
            from library.main_app_inline_theme_editor import build_inline_theme_editor_page

            page_name = "theme-editor"
            current_page = getattr(self, "_inline_theme_editor_page", None)
            if current_page is not None and getattr(current_page, "_theme_name", None) == theme_name:
                self.stack.set_visible_child_name(page_name)
                return

            _remove_stack_page(self.stack, page_name)
            page = build_inline_theme_editor_page(app, self, theme_name)
            self._inline_theme_editor_page = page
            self.stack.add_named(page, page_name)
            self.stack.set_visible_child_name(page_name)
        except Exception as exc:
            # Fall back to the standalone editor.
            try:
                if app.THEME_EDITOR.is_file():
                    self.launch_script(app.THEME_EDITOR, theme_name, use_system_python=True)
                    return
            except Exception:
                pass
            self.toast(f"Could not open theme editor: {exc}")
