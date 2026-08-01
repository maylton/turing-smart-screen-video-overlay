# SPDX-License-Identifier: GPL-3.0-or-later
"""Consolidated Main App integration for Diagnostics and runtime UI polish.

This module is the single entry point for the Main App / Diagnostics draft work:

- Settings → Maintenance → Diagnostics opens inline inside the main GTK app;
- theme editing routes through an inline Theme Editor page when possible;
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


def _find_settings_content_box(app: Any, root: Any) -> Any | None:
    """Find the vertical content box of the Settings page as a fallback."""

    Gtk = app.Gtk
    for widget in _walk_widgets(root):
        if not isinstance(widget, Gtk.Box):
            continue
        for child in _iter_widget_children(widget):
            if _matches_translated_value(_widget_label(child), "Settings"):
                return widget
    return None


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
        label="main-shell-i18n",
        importer=lambda: __import__(
            "library.main_app_i18n",
            fromlist=["install_main_app_shell_i18n"],
        ).install_main_app_shell_i18n,
    )
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


def _open_diagnostics_factory(app: Any):
    diagnostics_viewer = app.ROOT / "diagnostics-gtk.py"

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

    return open_diagnostics


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


def _open_theme_editor_factory(app: Any):
    standalone_editor = app.THEME_EDITOR

    def open_theme_editor_theme(self, theme_name: str) -> None:
        theme_name = str(theme_name or "").strip()
        if not theme_name:
            self.toast("No active theme configured")
            return
        try:
            from library.main_app_inline_theme_editor import (
                build_inline_theme_editor_page,
            )

            page_name = "theme-editor"
            current_page = getattr(self, "_inline_theme_editor_page", None)
            if (
                current_page is not None
                and getattr(current_page, "_theme_name", None) == theme_name
            ):
                self.stack.set_visible_child_name(page_name)
                return

            _remove_stack_page(self.stack, page_name)
            page = build_inline_theme_editor_page(app, self, theme_name)
            self._inline_theme_editor_page = page
            self.stack.add_named(page, page_name)
            self.stack.set_visible_child_name(page_name)
        except Exception as exc:
            # Keep the separate editor as a fallback until inline editing is fully
            # proven on the installed app path.
            try:
                if standalone_editor.is_file():
                    self.launch_script(
                        standalone_editor,
                        theme_name,
                        use_system_python=True,
                    )
                    return
            except Exception:
                pass
            self.toast(f"Could not open theme editor: {exc}")

    def open_theme_editor(self, *_args) -> None:
        theme = app.read_current_theme()
        open_theme_editor_theme(self, theme)

    def open_theme_editor_record(self, record, *_args) -> None:
        open_theme_editor_theme(self, getattr(record, "name", ""))

    return open_theme_editor, open_theme_editor_record


def _bind_existing_gallery_pane(window: Any) -> None:
    opener = getattr(window, "open_theme_editor_record", None)
    if not callable(opener):
        return
    for attr_name in ("theme_gallery", "gallery"):
        pane = getattr(window, attr_name, None)
        if pane is not None and hasattr(pane, "on_open_theme"):
            pane.on_open_theme = opener


def _install_theme_gallery_editor_route(window: Any) -> None:
    """Route Theme Gallery Edit actions to the inline editor in the main app."""

    try:
        from library import theme_gallery as gallery
    except Exception:
        return

    original = getattr(gallery, "_main_app_original_launch_theme_editor", None)
    if original is None:
        original = getattr(gallery, "launch_theme_editor", None)
        gallery._main_app_original_launch_theme_editor = original

    if callable(original):
        def launch_theme_editor_inline(record, theme_editor=None):
            opener = getattr(window, "open_theme_editor_record", None)
            if callable(opener):
                opener(record)
                return None
            if theme_editor is None:
                return original(record)
            return original(record, theme_editor)

        gallery.launch_theme_editor = launch_theme_editor_inline

    pane_class = getattr(gallery, "ThemeGalleryPane", None)
    if pane_class is not None and not getattr(
        pane_class,
        "_main_app_inline_editor_route_installed",
        False,
    ):
        original_init = pane_class.__init__

        def init_with_inline_editor_route(self, *args, **kwargs):
            opener = getattr(window, "open_theme_editor_record", None)
            if callable(opener):
                if args:
                    args = (opener, *args[1:])
                else:
                    kwargs["on_open_theme"] = opener
            original_init(self, *args, **kwargs)

        pane_class.__init__ = init_with_inline_editor_route
        pane_class._main_app_inline_editor_route_installed = True

    _bind_existing_gallery_pane(window)


def _make_diagnostics_row(app: Any, window: Any) -> Any:
    diagnostics_row = app.Adw.ActionRow(
        title="Diagnostics",
        subtitle=(
            "Inspect theme, video, runtime, and USB state without "
            "opening the serial port"
        ),
        icon_name="utilities-system-monitor-symbolic",
        activatable=True,
    )
    diagnostics_row.connect("activated", window.open_diagnostics)
    diagnostics_row.add_suffix(app.Gtk.Image.new_from_icon_name("go-next-symbolic"))
    return diagnostics_row


def _add_diagnostics_row(app: Any, window: Any, root: Any) -> bool:
    if _has_titled_widget(root, "Diagnostics"):
        return True

    maintenance = _find_titled_widget(root, "Maintenance")
    if maintenance is not None:
        maintenance.add(_make_diagnostics_row(app, window))
        return True

    # Fallback: the exact Maintenance group may be hard to find after the
    # window has been constructed. Add a dedicated Diagnostics group to the
    # Settings content box instead of silently dropping the entry.
    settings_box = _find_settings_content_box(app, root)
    if settings_box is None:
        return False

    diagnostics_group = app.Adw.PreferencesGroup(
        title="Diagnostics",
        description=(
            "Inspect theme, video, runtime, and USB state without opening "
            "the display serial port."
        ),
    )
    diagnostics_group.add(_make_diagnostics_row(app, window))
    settings_box.append(diagnostics_group)
    return True


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

    original_build_settings_page = window_class.build_settings_page
    original_init = window_class.__init__
    open_theme_editor, open_theme_editor_record = _open_theme_editor_factory(app)

    def open_diagnostics(self, *_args) -> None:
        return _open_diagnostics_factory(app)(self, *_args)

    def build_settings_page(self):
        page = original_build_settings_page(self)
        if not _add_diagnostics_row(app, self, page):
            print(
                "[diagnostics] Settings page was built but no Diagnostics target was found",
                file=sys.stderr,
                flush=True,
            )
        return page

    def init_with_diagnostics(self, application):
        original_init(self, application)
        _install_theme_gallery_editor_route(self)
        # Safety net for builds where Settings was already constructed before
        # this wrapper became active. Walk the created window and patch the
        # existing Settings page directly.
        try:
            if not _add_diagnostics_row(app, self, self):
                print(
                    "[diagnostics] could not find Settings page after window init",
                    file=sys.stderr,
                    flush=True,
                )
        except Exception as exc:  # pragma: no cover - defensive startup guard
            print(
                f"[diagnostics] could not add Settings row after init: {exc}",
                file=sys.stderr,
                flush=True,
            )

    build_settings_page._diagnostics_integration_wrapper = True
    init_with_diagnostics._diagnostics_init_wrapper = True

    window_class.open_diagnostics = open_diagnostics
    window_class.open_theme_editor = open_theme_editor
    window_class.open_theme_editor_record = open_theme_editor_record
    window_class.build_settings_page = build_settings_page
    window_class.__init__ = init_with_diagnostics
    window_class._main_app_diagnostics_integration_installed = True
    window_class._diagnostics_integration_installed = True
