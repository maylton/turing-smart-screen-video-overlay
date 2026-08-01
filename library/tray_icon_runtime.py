# SPDX-License-Identifier: GPL-3.0-or-later
"""Install the grayscale icon on the GTK StatusNotifierItem implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from library.tray_icon import (
    TRAY_ICON_NAME,
    ensure_status_icon_theme,
    status_notifier_pixmaps,
)


_INSTALLED = False


def install_status_notifier_grayscale_icon(app_module: Any) -> None:
    """Expose both IconName and IconPixmap grayscale variants to SNI hosts."""
    global _INSTALLED
    if _INSTALLED:
        return

    notifier_class = getattr(app_module, "StatusNotifierItem", None)
    glib = getattr(app_module, "GLib", None)
    project_root = Path(getattr(app_module, "ROOT", Path.cwd())).resolve()
    if notifier_class is None or glib is None:
        return

    xml = str(getattr(app_module, "STATUS_NOTIFIER_XML", ""))
    if "IconPixmap" not in xml:
        marker = '    <property name="IconName" type="s" access="read"/>\n'
        replacement = marker + '    <property name="IconPixmap" type="a(iiay)" access="read"/>\n'
        if marker in xml:
            app_module.STATUS_NOTIFIER_XML = xml.replace(marker, replacement, 1)

    icon_theme_path = ensure_status_icon_theme(str(project_root))
    pixmaps = status_notifier_pixmaps(project_root)
    original_get_property = notifier_class._on_get_property

    def get_property_with_grayscale_icon(
        self,
        connection,
        sender,
        object_path,
        interface_name,
        property_name,
    ):
        if property_name == "IconName":
            return glib.Variant("s", TRAY_ICON_NAME)
        if property_name == "IconThemePath":
            return glib.Variant("s", str(icon_theme_path))
        if property_name == "IconPixmap":
            return glib.Variant("a(iiay)", pixmaps)
        if property_name == "ToolTip":
            return glib.Variant(
                "(sa(iiay)ss)",
                (
                    TRAY_ICON_NAME,
                    pixmaps,
                    getattr(app_module, "APP_NAME", "Turing Smart Screen"),
                    (
                        "Theme: "
                        + (app_module.read_current_theme() or "not selected")
                    ),
                ),
            )
        return original_get_property(
            self,
            connection,
            sender,
            object_path,
            interface_name,
            property_name,
        )

    get_property_with_grayscale_icon._turing_grayscale_tray_icon = True
    notifier_class._on_get_property = get_property_with_grayscale_icon
    _INSTALLED = True
