# SPDX-License-Identifier: GPL-3.0-or-later
"""Main GTK application i18n integration hooks."""

from __future__ import annotations


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
