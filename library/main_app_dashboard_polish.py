# SPDX-License-Identifier: GPL-3.0-or-later
"""Dashboard-style Overview polish for the GTK app shell.

This module is intentionally optional.  The stable launcher loads it through
``sitecustomize.py`` when ``configure-gtk.py`` imports ``configure_gtk_app.py``.
It keeps the visual polish separated from the runtime/video-safety code.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

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
        spacing=8,
        margin_top=14,
        margin_bottom=14,
        margin_start=14,
        margin_end=14,
    )
    card.set_hexpand(True)
    card.set_valign(Gtk.Align.FILL)
    _add_classes(card, "card")

    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    icon = Gtk.Image.new_from_icon_name(icon_name)
    row.append(icon)
    title_label = Gtk.Label(label=title, xalign=0)
    title_label.set_hexpand(True)
    _add_classes(title_label, "caption", "dim-label")
    row.append(title_label)
    card.append(row)

    value = Gtk.Label(label="—", xalign=0, wrap=True)
    value.set_ellipsize(Pango.EllipsizeMode.END)
    _add_classes(value, "title-3")
    card.append(value)

    subtitle = Gtk.Label(label="", xalign=0, wrap=True)
    _add_classes(subtitle, "caption", "dim-label")
    card.append(subtitle)
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
            spacing=22,
            margin_top=28,
            margin_bottom=28,
            margin_start=24,
            margin_end=24,
        )
        clamp.set_child(content)

        heading = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        heading.append(
            _make_title(
                app,
                "Overview",
                "Control the display, active theme, native video overlay, and monitor process from one dashboard.",
            )
        )
        refresh_button = Gtk.Button(icon_name="view-refresh-symbolic", valign=Gtk.Align.CENTER)
        refresh_button.set_tooltip_text("Refresh status and preview")
        refresh_button.connect("clicked", lambda *_: self.refresh_all())
        heading.append(refresh_button)
        content.append(heading)

        hero = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=26)
        hero.add_css_class("card")
        hero.set_margin_top(2)
        hero.set_margin_bottom(2)
        hero.set_margin_start(0)
        hero.set_margin_end(0)
        content.append(hero)

        preview_frame = Gtk.AspectFrame(
            ratio=1.0,
            obey_child=False,
            xalign=0.5,
            yalign=0.5,
            margin_top=22,
            margin_bottom=22,
            margin_start=22,
            margin_end=0,
        )
        preview_frame.set_size_request(360, 360)
        preview_frame.add_css_class("card")

        self.overview_picture = Gtk.Picture()
        self.overview_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.overview_picture.add_css_class("display-preview")
        self.overview_picture.add_css_class("device-live-preview")
        preview_frame.set_child(self.overview_picture)
        hero.append(preview_frame)

        info = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=14,
            margin_top=30,
            margin_bottom=30,
            margin_start=2,
            margin_end=30,
        )
        info.set_hexpand(True)
        hero.append(info)

        self.theme_title = Gtk.Label(label="No active theme", xalign=0, wrap=True)
        self.theme_title.add_css_class("title-1")
        info.append(self.theme_title)

        self.theme_summary_label = Gtk.Label(
            label="Choose a theme from the gallery to start.",
            xalign=0,
            wrap=True,
        )
        self.theme_summary_label.add_css_class("dim-label")
        info.append(self.theme_summary_label)

        badge_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.theme_badge = _make_badge(app, "THEME")
        self.video_badge = _make_badge(app, "VIDEO")
        self.display_badge = _make_badge(app, "DISPLAY")
        badge_row.append(self.theme_badge)
        badge_row.append(self.video_badge)
        badge_row.append(self.display_badge)
        info.append(badge_row)

        self.theme_path_label = Gtk.Label(label="", xalign=0, wrap=True)
        self.theme_path_label.add_css_class("caption")
        self.theme_path_label.add_css_class("dim-label")
        info.append(self.theme_path_label)

        primary_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        primary_actions.set_margin_top(8)

        edit_button = Gtk.Button(label="Edit theme", icon_name="document-edit-symbolic")
        edit_button.set_action_name("win.open-editor")
        edit_button.add_css_class("suggested-action")
        primary_actions.append(edit_button)

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
        primary_actions.append(sync_button)

        apply_button = Gtk.Button(label="Apply + Sync + Start", icon_name="media-playback-start-symbolic")
        apply_button.add_css_class("suggested-action")
        apply_button.set_tooltip_text("Stop monitor if needed, sync video, then restart monitor")
        apply_button.connect(
            "clicked",
            lambda *_: _call_if_available(
                self,
                "apply_current_theme_sync_and_start",
                "Apply + Sync is available from the Themes page",
            ),
        )
        primary_actions.append(apply_button)
        info.append(primary_actions)

        secondary_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        open_themes = Gtk.Button(label="Open gallery", icon_name="applications-graphics-symbolic")
        open_themes.connect("clicked", lambda *_: _open_themes_page(self))
        secondary_actions.append(open_themes)

        video_manager = Gtk.Button(label="Video manager", icon_name="video-x-generic-symbolic")
        video_manager.set_action_name("win.open-videos")
        secondary_actions.append(video_manager)

        power_button = Gtk.Button(label="Turn off", icon_name="system-shutdown-symbolic")
        power_button.add_css_class("destructive-action")
        power_button.set_action_name("win.turn-off-display")
        secondary_actions.append(power_button)
        info.append(secondary_actions)

        status_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        status_row.set_homogeneous(True)
        content.append(status_row)

        theme_card, self.theme_status_value, self.theme_status_detail = _make_status_card(
            app,
            "Theme",
            "applications-graphics-symbolic",
        )
        monitor_card, self.monitor_status_value, self.monitor_status_detail = _make_status_card(
            app,
            "Monitor",
            "media-playback-start-symbolic",
        )
        display_card, self.display_status_value, self.display_status_detail = _make_status_card(
            app,
            "Display",
            "video-display-symbolic",
        )
        status_row.append(theme_card)
        status_row.append(monitor_card)
        status_row.append(display_card)

        status_group = Adw.PreferencesGroup(
            title="Runtime details",
            description="Live state from the theme config, display detection, and monitor lock owner.",
        )
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
        detect_button = Gtk.Button(
            label="Detect now",
            valign=Gtk.Align.CENTER,
            action_name="win.detect-display",
        )
        self.detection_status_row.add_suffix(detect_button)
        status_group.add(self.theme_status_row)
        status_group.add(self.process_status_row)
        status_group.add(self.detection_status_row)
        content.append(status_group)

        quick_group = Adw.PreferencesGroup(
            title="Quick actions",
            description="Use these when you want the older row-based workflow.",
        )
        for title, subtitle, icon, action in (
            (
                "Theme editor",
                "Edit the active theme layout and components.",
                "document-edit-symbolic",
                "win.open-editor",
            ),
            (
                "Start monitor",
                "Run main.py using the project environment.",
                "media-playback-start-symbolic",
                "win.start-monitor",
            ),
            (
                "Stop monitor",
                "Stop the process started by this app or owned by the runtime lock.",
                "media-playback-stop-symbolic",
                "win.stop-monitor",
            ),
        ):
            row = Adw.ActionRow(title=title, subtitle=subtitle, icon_name=icon, activatable=True)
            row.set_action_name(action)
            row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
            quick_group.add(row)
        content.append(quick_group)

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
        return

    window_class.build_overview_page = _build_overview_page_factory(app)
    window_class.refresh_overview = _refresh_overview_factory(app)

    if not hasattr(window_class, "apply_current_theme_sync_and_start"):
        window_class.apply_current_theme_sync_and_start = _apply_current_theme_sync_and_start_factory(app)

    window_class._dashboard_polish_installed = True
