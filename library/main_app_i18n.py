# SPDX-License-Identifier: GPL-3.0-or-later
"""Main GTK application i18n integration hooks."""

from __future__ import annotations

from typing import Any, Iterable


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


def _translate_widget_text(widget: Any, translate) -> None:
    for getter_name, setter_name in (
        ("get_label", "set_label"),
        ("get_title", "set_title"),
        ("get_subtitle", "set_subtitle"),
        ("get_tooltip_text", "set_tooltip_text"),
    ):
        getter = getattr(widget, getter_name, None)
        setter = getattr(widget, setter_name, None)
        if not callable(getter) or not callable(setter):
            continue
        try:
            current = getter()
        except Exception:
            continue
        if not isinstance(current, str) or not current:
            continue
        translated = translate(current)
        if translated != current:
            try:
                setter(translated)
            except Exception:
                pass


def translate_widget_tree(root: Any) -> None:
    """Translate exact stable English strings in an already-built GTK tree."""

    from library.i18n import t as _

    for widget in _walk_widgets(root):
        _translate_widget_text(widget, _)


def install_main_app_tray_i18n(app) -> None:
    """Localize the StatusNotifier tray menu without changing tray behavior."""

    from library.i18n import t as _, tr

    StatusNotifierMenu = getattr(app, "StatusNotifierMenu", None)
    StatusNotifierItem = getattr(app, "StatusNotifierItem", None)
    if StatusNotifierMenu is None or StatusNotifierItem is None:
        return

    def menu_label(self, action: str) -> str:
        labels = {
            "show-hide-window": (
                _("Hide window") if self.window_visible() else _("Show window")
            ),
            "start-screen": _("Start screen"),
            "turn-off-screen": _("Turn off screen"),
            "open-theme-editor": _("Open theme editor"),
            "open-video-manager": _("Open video manager"),
            "quit": _("Quit"),
        }
        return labels.get(action, action)

    def status_notifier_get_property(
        self,
        _connection,
        _sender,
        _object_path,
        _interface_name,
        property_name,
    ):
        theme = app.read_current_theme() or _("not selected")
        values = {
            "Category": app.GLib.Variant("s", "Hardware"),
            "Id": app.GLib.Variant("s", app.APP_ID),
            "Title": app.GLib.Variant("s", app.APP_NAME),
            "Status": app.GLib.Variant("s", "Active"),
            "WindowId": app.GLib.Variant("u", 0),
            "IconName": app.GLib.Variant("s", app.APP_ID),
            "IconThemePath": app.GLib.Variant("s", ""),
            "OverlayIconName": app.GLib.Variant("s", ""),
            "AttentionIconName": app.GLib.Variant("s", ""),
            "ToolTip": app.GLib.Variant(
                "(sa(iiay)ss)",
                (
                    app.APP_ID,
                    [],
                    app.APP_NAME,
                    tr("Theme: {theme}", theme=theme),
                ),
            ),
            "ItemIsMenu": app.GLib.Variant("b", False),
            "Menu": app.GLib.Variant("o", app.DBUSMENU_OBJECT_PATH),
        }
        return values.get(property_name)

    StatusNotifierMenu.menu_label = menu_label
    StatusNotifierItem._on_get_property = status_notifier_get_property
    setattr(app, "_tray_i18n_installed", True)


def install_main_app_shell_i18n(app) -> None:
    """Localize the main GTK shell after each affected UI build/refresh."""

    install_main_app_tray_i18n(app)

    window_class = getattr(app, "SmartScreenWindow", None)
    if window_class is None or getattr(window_class, "_main_app_shell_i18n_installed", False):
        return

    original_init = window_class.__init__
    original_build_settings_page = window_class.build_settings_page
    original_refresh_overview = window_class.refresh_overview

    def init_with_i18n(self, application):
        original_init(self, application)
        translate_widget_tree(self)

    def build_settings_page_with_i18n(self):
        page = original_build_settings_page(self)
        translate_widget_tree(page)
        return page

    def refresh_overview_with_i18n(self):
        result = original_refresh_overview(self)
        translate_widget_tree(self)
        return result

    init_with_i18n._main_app_shell_i18n_wrapper = True
    build_settings_page_with_i18n._main_app_shell_i18n_wrapper = True
    refresh_overview_with_i18n._main_app_shell_i18n_wrapper = True

    window_class.__init__ = init_with_i18n
    window_class.build_settings_page = build_settings_page_with_i18n
    window_class.refresh_overview = refresh_overview_with_i18n
    window_class._main_app_shell_i18n_installed = True
