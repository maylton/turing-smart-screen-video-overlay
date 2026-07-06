# SPDX-License-Identifier: GPL-3.0-or-later
"""Dashboard-style Overview polish for the GTK app shell.

This module is intentionally optional.  The stable launcher loads it through
``sitecustomize.py`` when ``configure-gtk.py`` imports ``configure_gtk_app.py``.
It keeps the visual polish separated from the runtime/video-safety code.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Iterable

from gi.repository import Pango


def _set_label(widget: Any, value: str) -> None:
    if widget is not None and hasattr(widget, "set_label"):
        widget.set_label(value)


def _set_subtitle(widget: Any, value: str) -> None:
    if widget is not None and hasattr(widget, "set_subtitle"):
        widget.set_subtitle(value)


def _add_classes(widget: Any, *classes: str) -> Any:
    for css_class in classes:
        try:
            widget.add_css_class(css_class)
        except Exception:
            pass
    return widget


def _iter_widget_children(widget: Any) -> Iterable[Any]:
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


def _find_titled_widget(root: Any, title: str) -> Any | None:
    for widget in _walk_widgets(root):
        if _widget_title(widget) == title:
            return widget
    return None


def _has_titled_widget(root: Any, title: str) -> bool:
    return _find_titled_widget(root, title) is not None


def _find_settings_content_box(app: Any, root: Any) -> Any | None:
    Gtk = app.Gtk
    for widget in _walk_widgets(root):
        if not isinstance(widget, Gtk.Box):
            continue
        for child in _iter_widget_children(widget):
            if _widget_label(child) == "Settings":
                return widget
    return None


def _read_text(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _theme_yaml_path(app: Any, theme_name: str) -> Path | None:
    theme_name = str(theme_name or "").strip()
    if not theme_name:
        return None
    theme_dir = app.THEMES_DIR / theme_name
    for file_name in ("theme.yaml", "theme.yml"):
        candidate = theme_dir / file_name
        if candidate.is_file():
            return candidate
    return None


def _theme_has_video(app: Any, theme_name: str) -> bool:
    text = _read_text(_theme_yaml_path(app, theme_name))
    if not text:
        return False
    video_match = re.search(r"(?ms)^video:\s*(.*?)(?:\n\S|\Z)", text)
    if video_match is None:
        return False
    block = video_match.group(1)
    enabled = re.search(r"(?mi)^\s*(ENABLED|SHOW)\s*:\s*(true|yes|on|1)", block)
    pathish = re.search(r"(?mi)^\s*(LOCAL_PATH|PATH)\s*:\s*\S+", block)
    return bool(enabled and pathish)


def _theme_has_turzx_hints(app: Any, theme_name: str) -> bool:
    yaml_text = _read_text(_theme_yaml_path(app, theme_name))
    if "WINDOWS_THEME_HINTS" in yaml_text:
        return True
    hints_json = app.THEMES_DIR / str(theme_name or "") / "assets" / "windows-theme-hints.json"
    return hints_json.is_file()


def _theme_stats_hint(app: Any, theme_name: str) -> str:
    text = _read_text(_theme_yaml_path(app, theme_name))
    if not text:
        return "No theme YAML"
    if re.search(r"(?m)^STATS:\s*\{\}\s*$", text):
        return "No active widgets"
    if re.search(r"(?m)^STATS:\s*$", text):
        return "Stats overlay configured"
    return "Theme YAML available"


def _call_if_available(window: Any, method_name: str, fallback: str) -> None:
    method = getattr(window, method_name, None)
    if callable(method):
        method()
        return
    toast = getattr(window, "toast", None)
    if callable(toast):
        toast(fallback)


def _open_themes_page(window: Any) -> None:
    stack = getattr(window, "stack", None)
    if stack is not None and hasattr(stack, "set_visible_child_name"):
        stack.set_visible_child_name("themes")
        sidebar = getattr(window, "sidebar", None)
        if sidebar is not None and hasattr(sidebar, "get_row_at_index"):
            row = sidebar.get_row_at_index(1)
            if row is not None and hasattr(sidebar, "select_row"):
                sidebar.select_row(row)


def _open_diagnostics_factory(app: Any):
    diagnostics_viewer = app.ROOT / "diagnostics-gtk.py"

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
            try:
                if diagnostics_viewer.is_file():
                    self.launch_script(diagnostics_viewer, use_system_python=True)
                    return
            except Exception:
                pass
            self.toast(f"Could not open diagnostics: {exc}")

    return open_diagnostics


def _make_diagnostics_row(app: Any, window: Any) -> Any:
    row = app.Adw.ActionRow(
        title="Diagnostics",
        subtitle=(
            "Inspect theme, video, runtime, and USB state without opening "
            "the serial port"
        ),
        icon_name="utilities-system-monitor-symbolic",
        activatable=True,
    )
    row.connect("activated", window.open_diagnostics)
    row.add_suffix(app.Gtk.Image.new_from_icon_name("go-next-symbolic"))
    return row


def _add_diagnostics_to_settings(app: Any, window: Any, page: Any) -> bool:
    if _has_titled_widget(page, "Diagnostics"):
        return True

    maintenance = _find_titled_widget(page, "Maintenance")
    if maintenance is not None:
        maintenance.add(_make_diagnostics_row(app, window))
        return True

    settings_box = _find_settings_content_box(app, page)
    if settings_box is None:
        return False

    group = app.Adw.PreferencesGroup(
        title="Diagnostics",
        description=(
            "Inspect theme, video, runtime, and USB state without opening "
            "the display serial port."
        ),
    )
    group.add(_make_diagnostics_row(app, window))
    settings_box.append(group)
    return True


def _install_dashboard_diagnostics_settings(app: Any) -> None:
    window_class = getattr(app, "SmartScreenWindow", None)
    if window_class is None or getattr(window_class, "_dashboard_diagnostics_installed", False):
        return

    original_build_settings_page = window_class.build_settings_page

    def build_settings_page_with_diagnostics(self):
        page = original_build_settings_page(self)
        if not hasattr(self, "open_diagnostics"):
            self.open_diagnostics = _open_diagnostics_factory(app).__get__(self, self.__class__)
        if not _add_diagnostics_to_settings(app, self, page):
            print(
                "[dashboard] could not add Diagnostics row to Settings page",
                file=sys.stderr,
                flush=True,
            )
        return page

    window_class.open_diagnostics = _open_diagnostics_factory(app)
    window_class.build_settings_page = build_settings_page_with_diagnostics
    window_class._dashboard_diagnostics_installed = True


def _install_main_app_integration_after_runtime_patches() -> None:
    """Run consolidated Main App integration after configure-gtk runtime patches."""

    main_module = sys.modules.get("__main__")
    runtime_patches = getattr(main_module, "install_runtime_patches", None)
    if runtime_patches is None or getattr(
        runtime_patches,
        "_main_app_integration_wrapper",
        False,
    ):
        return

    def install_runtime_patches_with_main_app_integration(app, *args, **kwargs):
        result = runtime_patches(app, *args, **kwargs)
        try:
            from library.main_app_diagnostics_integration import (
                install_main_app_diagnostics_integration,
            )

            install_main_app_diagnostics_integration(app)
        except Exception as exc:  # pragma: no cover - defensive startup guard
            print(
                f"[main-app-integration] could not install after runtime patches: {exc}",
                file=sys.stderr,
                flush=True,
            )
        return result

    install_runtime_patches_with_main_app_integration._main_app_integration_wrapper = True
    main_module.install_runtime_patches = install_runtime_patches_with_main_app_integration


def _apply_current_theme_sync_and_start_factory(app: Any):
    def apply_current_theme_sync_and_start(self) -> None:
        current = app.read_current_theme()
        if not current:
            self.toast("No active theme configured")
            return

        gallery = getattr(self, "theme_gallery", None)
        if gallery is None:
            self.toast("Open Themes once before applying the current theme")
            _open_themes_page(self)
            return

        try:
            gallery.reload_themes(show_toast=False)
        except TypeError:
            gallery.reload_themes()
        except Exception:
            pass

        record = None
        for candidate in getattr(gallery, "records", []):
            if getattr(candidate, "name", None) == current:
                record = candidate
                break

        if record is None:
            self.toast(f"Active theme was not found in the gallery: {current}")
            _open_themes_page(self)
            return

        apply_theme = getattr(self, "apply_set_current_theme_from_gallery", None)
        if callable(apply_theme):
            apply_theme(record)
            return

        self.toast("Apply + Sync is available from the Themes page")
        _open_themes_page(self)

    return apply_current_theme_sync_and_start


def _make_title(app: Any, title_text: str, subtitle_text: str) -> Any:
    Gtk = app.Gtk
    title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    title_box.set_hexpand(True)

    title = Gtk.Label(label=title_text, xalign=0)
    _add_classes(title, "title-1")
    title_box.append(title)

    subtitle = Gtk.Label(label=subtitle_text, xalign=0, wrap=True)
    _add_classes(subtitle, "dim-label")
    title_box.append(subtitle)
    return title_box


def _make_status_card(app: Any, title: str, icon_name: str) -> tuple[Any, Any, Any]:
    Gtk = app.Gtk
    card = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=0,
        margin_top=10,
        margin_bottom=10,
        margin_start=10,
        margin_end=10,
    )
    card.set_hexpand(True)
    card.set_valign(Gtk.Align.FILL)
    card.set_size_request(-1, 132)
    _add_classes(card, "card")

    inner = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=12,
        margin_top=18,
        margin_bottom=18,
        margin_start=20,
        margin_end=20,
    )
    card.append(inner)

    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    icon = Gtk.Image.new_from_icon_name(icon_name)
    row.append(icon)
    title_label = Gtk.Label(label=title, xalign=0)
    title_label.set_hexpand(True)
    _add_classes(title_label, "caption", "dim-label")
    row.append(title_label)
    inner.append(row)

    value = Gtk.Label(label="—", xalign=0, wrap=True)
    value.set_ellipsize(Pango.EllipsizeMode.END)
    _add_classes(value, "title-3")
    inner.append(value)

    subtitle = Gtk.Label(label="", xalign=0, wrap=True)
    _add_classes(subtitle, "caption", "dim-label")
    inner.append(subtitle)
    return card, value, subtitle


def _make_badge(app: Any, label: str) -> Any:
    Gtk = app.Gtk
    badge = Gtk.Label(label=label)
    badge.set_margin_top(2)
    badge.set_margin_bottom(2)
    badge.set_margin_start(8)
    badge.set_margin_end(8)
    _add_classes(badge, "caption", "accent")
    return badge


def _build_overview_page_factory(app: Any):
    def build_overview_page(self) -> Any:
        Gtk = app.Gtk
        Adw = app.Adw

        scrolled = Gtk.ScrolledWindow()
        clamp = Adw.Clamp(maximum_size=1180, tightening_threshold=760)
        scrolled.set_child(clamp)

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=28,
            margin_top=34,
            margin_bottom=36,
            margin_start=32,
            margin_end=32,
        )
        clamp.set_child(content)

        heading = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        heading.append(
            _make_title(
                app,
                "Overview",
                "Control the active theme, display state, video overlay, and monitor process from one place.",
            )
        )

        refresh_button = Gtk.Button(
            icon_name="view-refresh-symbolic",
            valign=Gtk.Align.CENTER,
        )
        refresh_button.set_tooltip_text("Refresh status and preview")
        refresh_button.connect("clicked", lambda *_: self.refresh_all())
        heading.append(refresh_button)
        content.append(heading)

        hero = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=34)
        hero.add_css_class("card")
        content.append(hero)

        preview_frame = Gtk.AspectFrame(
            ratio=1.0,
            obey_child=False,
            xalign=0.5,
            yalign=0.5,
            margin_top=28,
            margin_bottom=28,
            margin_start=28,
            margin_end=0,
        )
        preview_frame.set_size_request(390, 390)
        preview_frame.set_hexpand(False)
        preview_frame.set_vexpand(False)
        preview_frame.set_halign(Gtk.Align.START)
        preview_frame.set_valign(Gtk.Align.CENTER)
        preview_frame.add_css_class("card")

        self.overview_picture = Gtk.Picture()
        self.overview_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.overview_picture.set_can_shrink(True)
        self.overview_picture.add_css_class("display-preview")
        self.overview_picture.add_css_class("device-live-preview")
        preview_frame.set_child(self.overview_picture)
        hero.append(preview_frame)

        side = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
            margin_top=30,
            margin_bottom=30,
            margin_start=4,
            margin_end=34,
        )
        side.set_hexpand(True)
        hero.append(side)

        self.theme_status_row = Adw.ActionRow(
            title="Active theme",
            icon_name="applications-graphics-symbolic",
        )
        self.process_status_row = Adw.ActionRow(
            title="Monitor process",
            icon_name="media-playback-start-symbolic",
        )
        self.detection_status_row = Adw.ActionRow(
            title="Connected display",
            subtitle="Detection has not run yet",
            icon_name="video-display-symbolic",
        )

        def inline_status_card(title: str, icon_name: str):
            card = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=0,
                margin_top=12,
                margin_bottom=12,
                margin_start=12,
                margin_end=12,
            )
            card.add_css_class("card")
            card.set_hexpand(True)
            card.set_size_request(-1, 112)

            inner = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=10,
                margin_top=18,
                margin_bottom=18,
                margin_start=20,
                margin_end=20,
            )
            card.append(inner)

            top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            icon = Gtk.Image.new_from_icon_name(icon_name)
            top.append(icon)

            label = Gtk.Label(label=title, xalign=0)
            label.add_css_class("caption")
            label.add_css_class("dim-label")
            label.set_hexpand(True)
            top.append(label)
            inner.append(top)

            value = Gtk.Label(label="—", xalign=0, wrap=True)
            value.set_ellipsize(Pango.EllipsizeMode.END)
            value.add_css_class("title-3")
            inner.append(value)

            detail = Gtk.Label(label="", xalign=0, wrap=True)
            detail.add_css_class("caption")
            detail.add_css_class("dim-label")
            inner.append(detail)

            return card, value, detail

        status_stack = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        status_stack.set_margin_top(0)
        status_stack.set_margin_bottom(6)
        side.append(status_stack)

        theme_card, self.theme_status_value, self.theme_status_detail = inline_status_card(
            "Theme",
            "applications-graphics-symbolic",
        )
        monitor_card, self.monitor_status_value, self.monitor_status_detail = inline_status_card(
            "Monitor",
            "media-playback-start-symbolic",
        )
        display_card, self.display_status_value, self.display_status_detail = inline_status_card(
            "Display",
            "video-display-symbolic",
        )
        status_stack.append(theme_card)
        status_stack.append(monitor_card)
        status_stack.append(display_card)

        actions_grid = Gtk.Grid(
            column_spacing=10,
            row_spacing=10,
            margin_top=8,
        )
        actions_grid.set_hexpand(True)
        side.append(actions_grid)

        def attach_button(button: Any, column: int, row: int) -> None:
            button.set_hexpand(True)
            button.set_halign(Gtk.Align.FILL)
            actions_grid.attach(button, column, row, 1, 1)

        edit_button = Gtk.Button(label="Edit theme", icon_name="document-edit-symbolic")
        edit_button.set_tooltip_text("Open the active theme in the Theme Editor.")
        edit_button.set_action_name("win.open-editor")
        edit_button.add_css_class("suggested-action")
        attach_button(edit_button, 0, 0)

        sync_button = Gtk.Button(label="Sync video", icon_name="folder-download-symbolic")
        sync_button.set_tooltip_text("Sync the active theme video to the display")
        sync_button.connect(
            "clicked",
            lambda *_: _call_if_available(
                self,
                "sync_current_theme_video_from_gallery",
                "Sync is available from the Themes page",
            ),
        )
        attach_button(sync_button, 1, 0)

        apply_button = Gtk.Button(
            label="Apply + Start",
            icon_name="media-playback-start-symbolic",
        )
        apply_button.add_css_class("suggested-action")
        apply_button.set_tooltip_text("Apply, sync video, then start the monitor")
        apply_button.connect(
            "clicked",
            lambda *_: _call_if_available(
                self,
                "apply_current_theme_sync_and_start",
                "Apply + Sync is available from the Themes page",
            ),
        )
        attach_button(apply_button, 2, 0)

        gallery_button = Gtk.Button(
            label="Gallery",
            icon_name="applications-graphics-symbolic",
        )
        gallery_button.set_tooltip_text("Open the theme gallery to browse, import, edit, or manage themes.")
        gallery_button.connect("clicked", lambda *_: _open_themes_page(self))
        attach_button(gallery_button, 0, 1)

        video_button = Gtk.Button(
            label="Videos",
            icon_name="video-x-generic-symbolic",
        )
        video_button.set_tooltip_text("Open the video manager to upload, delete, or inspect display videos.")
        video_button.set_action_name("win.open-videos")
        attach_button(video_button, 1, 1)

        power_button = Gtk.Button(
            label="Turn off",
            icon_name="system-shutdown-symbolic",
        )
        power_button.set_tooltip_text("Stop the monitor and turn off the physical display safely.")
        power_button.add_css_class("destructive-action")
        power_button.set_action_name("win.turn-off-display")
        attach_button(power_button, 2, 1)

        return scrolled

    return build_overview_page


def _refresh_overview_factory(app: Any):
    def refresh_overview(self) -> None:
        current = app.read_current_theme()
        self.current_theme = current
        title = current or "No active theme"
        theme_path = app.THEMES_DIR / current if current else None
        has_video = _theme_has_video(app, current)
        has_turzx = _theme_has_turzx_hints(app, current)
        display_size = app.selected_display_size()

        _set_label(getattr(self, "theme_title", None), title)
        _set_label(
            getattr(self, "theme_summary_label", None),
            _theme_stats_hint(app, current)
            if current
            else "Choose a compatible theme from the gallery to begin.",
        )
        _set_label(getattr(self, "theme_path_label", None), str(theme_path) if theme_path else "")
        _set_label(getattr(self, "theme_badge", None), "CURRENT" if current else "NO THEME")
        _set_label(getattr(self, "video_badge", None), "VIDEO" if has_video else "STATIC")
        _set_label(getattr(self, "display_badge", None), f'{display_size}"' if display_size else "DISPLAY")

        _set_label(getattr(self, "theme_status_value", None), title)
        _set_label(
            getattr(self, "theme_status_detail", None),
            "TURZX import hints detected" if has_turzx else ("Native video configured" if has_video else "Ready"),
        )
        _set_subtitle(getattr(self, "theme_status_row", None), title)

        state = None
        controller = getattr(self, "runtime_controller", None)
        if controller is not None:
            try:
                state = controller.state()
            except Exception:
                state = None

        if state is not None and getattr(state, "monitor_running", False):
            owner = getattr(state, "owner", None)
            pid = getattr(owner, "pid", None)
            monitor_value = "Running"
            monitor_detail = f"PID {pid}" if pid else "Monitor owns the display"
        elif state is not None and getattr(state, "busy", False):
            owner = getattr(state, "owner", None)
            describe = getattr(owner, "describe", None)
            monitor_value = "Busy"
            monitor_detail = describe() if callable(describe) else "Display lock is owned"
        else:
            process = getattr(self, "monitor_process", None)
            if process is not None and process.poll() is None:
                monitor_value = "Starting"
                monitor_detail = "Process launched from this window"
            else:
                monitor_value = "Stopped"
                monitor_detail = "Display is free"

        _set_label(getattr(self, "monitor_status_value", None), monitor_value)
        _set_label(getattr(self, "monitor_status_detail", None), monitor_detail)
        _set_subtitle(getattr(self, "process_status_row", None), f"{monitor_value} · {monitor_detail}")

        detection_row = getattr(self, "detection_status_row", None)
        detection_text = "Detection has not run yet"
        if detection_row is not None and hasattr(detection_row, "get_subtitle"):
            detection_text = detection_row.get_subtitle() or detection_text
        _set_label(getattr(self, "display_status_value", None), f'{display_size}" display' if display_size else "Unknown")
        _set_label(getattr(self, "display_status_detail", None), detection_text)

        set_picture = getattr(self, "set_picture", None)
        picture = getattr(self, "overview_picture", None)
        if callable(set_picture) and picture is not None:
            set_picture(picture, app.theme_preview_path(current))

        try:
            from library.main_app_ui_polish import OverviewLivePreviewAnimator

            animator = getattr(self, "overview_preview_animator", None)
            if animator is None:
                animator = OverviewLivePreviewAnimator(app, self)
                self.overview_preview_animator = animator
            animator.show_theme(current)
        except Exception:
            pass

    return refresh_overview


def install_main_app_dashboard_polish(app: Any) -> None:
    """Install dashboard widgets before the main GTK window is constructed."""
    window_class = getattr(app, "SmartScreenWindow", None)
    if window_class is None or getattr(window_class, "_dashboard_polish_installed", False):
        _install_dashboard_diagnostics_settings(app)
        _install_main_app_integration_after_runtime_patches()
        return

    _install_dashboard_diagnostics_settings(app)
    window_class.build_overview_page = _build_overview_page_factory(app)
    window_class.refresh_overview = _refresh_overview_factory(app)

    if not hasattr(window_class, "apply_current_theme_sync_and_start"):
        window_class.apply_current_theme_sync_and_start = _apply_current_theme_sync_and_start_factory(app)

    window_class._dashboard_polish_installed = True
    _install_main_app_integration_after_runtime_patches()
