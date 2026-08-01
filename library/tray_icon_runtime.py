# SPDX-License-Identifier: GPL-3.0-or-later
"""Install the selected icon appearance on the GTK StatusNotifierItem."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from library.tray_icon import DEFAULT_SIZES, status_notifier_pixmaps
from library.tray_icon_preferences import (
    MODE_COLOR,
    load_tray_icon_mode,
    resolve_tray_icon_variant,
)


_INSTALLED = False


def _add_icon_pixmap_property(xml: str) -> str:
    if "IconPixmap" in xml:
        return xml

    pattern = re.compile(
        r'(?m)^(?P<indent>[ \t]*)'
        r'<property name="IconName" type="s" access="read"/>[ \t]*$'
    )

    def add_property(match: re.Match) -> str:
        indent = match.group("indent")
        return (
            match.group(0)
            + "\n"
            + indent
            + '<property name="IconPixmap" type="a(iiay)" access="read"/>'
        )

    updated, count = pattern.subn(add_property, xml, count=1)
    return updated if count else xml


def style_prefers_dark(app_module: Any) -> bool:
    adw = getattr(app_module, "Adw", None)
    manager_class = getattr(adw, "StyleManager", None)
    get_default = getattr(manager_class, "get_default", None)
    if callable(get_default):
        try:
            manager = get_default()
            get_dark = getattr(manager, "get_dark", None)
            if callable(get_dark):
                return bool(get_dark())
        except Exception:
            pass
    return True


def active_tray_icon_variant(app_module: Any) -> str:
    return resolve_tray_icon_variant(
        load_tray_icon_mode(),
        dark_theme=style_prefers_dark(app_module),
    )


def refresh_status_notifier_icon(app_module: Any, notifier: Any) -> bool:
    """Tell StatusNotifier hosts to request the current icon and tooltip again."""
    connection = getattr(notifier, "connection", None)
    if connection is None:
        return False

    object_path = getattr(app_module, "TRAY_OBJECT_PATH", "/StatusNotifierItem")
    try:
        connection.emit_signal(
            None,
            object_path,
            "org.kde.StatusNotifierItem",
            "NewIcon",
            None,
        )
        connection.emit_signal(
            None,
            object_path,
            "org.kde.StatusNotifierItem",
            "NewToolTip",
            None,
        )
        return True
    except Exception:
        return False


def install_status_notifier_tray_icon(app_module: Any) -> None:
    """Expose color or symbolic icon properties according to user preference.

    Caelestia uses Quickshell, which prefers ``IconName`` whenever it is
    non-empty. Color mode therefore returns the normal application icon name;
    symbolic modes intentionally return an empty name so Quickshell consumes
    the generated ``IconPixmap`` instead.
    """

    global _INSTALLED

    notifier_class = getattr(app_module, "StatusNotifierItem", None)
    glib = getattr(app_module, "GLib", None)
    project_root = Path(getattr(app_module, "ROOT", Path.cwd())).resolve()
    if notifier_class is None or glib is None:
        return

    current_get_property = getattr(notifier_class, "_on_get_property", None)
    installed_root = getattr(
        current_get_property,
        "_turing_tray_icon_project_root",
        "",
    )
    if (
        getattr(current_get_property, "_turing_tray_icon_runtime", False)
        and installed_root == str(project_root)
    ):
        _INSTALLED = True
        return
    if not callable(current_get_property):
        return

    app_module.STATUS_NOTIFIER_XML = _add_icon_pixmap_property(
        str(getattr(app_module, "STATUS_NOTIFIER_XML", ""))
    )

    pixmap_cache: Dict[str, List[Tuple[int, int, bytes]]] = {}
    original_get_property = getattr(
        current_get_property,
        "_turing_tray_icon_original_get_property",
        current_get_property,
    )

    def current_payload():
        variant = active_tray_icon_variant(app_module)
        pixmaps = pixmap_cache.get(variant)
        if pixmaps is None:
            pixmaps = status_notifier_pixmaps(
                project_root,
                sizes=DEFAULT_SIZES,
                variant=variant,
            )
            pixmap_cache[variant] = pixmaps
        return variant, pixmaps

    def get_property_with_selected_icon(
        self,
        connection,
        sender,
        object_path,
        interface_name,
        property_name,
    ):
        variant, pixmaps = current_payload()
        icon_name = (
            getattr(app_module, "APP_ID", "")
            if variant == MODE_COLOR
            else ""
        )

        if property_name == "IconName":
            return glib.Variant("s", icon_name)
        if property_name == "IconThemePath":
            return glib.Variant("s", "")
        if property_name == "IconPixmap":
            return glib.Variant("a(iiay)", pixmaps)
        if property_name == "ToolTip":
            return glib.Variant(
                "(sa(iiay)ss)",
                (
                    icon_name,
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

    get_property_with_selected_icon._turing_tray_icon_runtime = True
    get_property_with_selected_icon._turing_tray_icon_project_root = str(
        project_root
    )
    get_property_with_selected_icon._turing_tray_icon_original_get_property = (
        original_get_property
    )
    notifier_class._on_get_property = get_property_with_selected_icon
    _INSTALLED = True


# Keep the previous public name for installed checkouts and third-party hooks.
def install_status_notifier_grayscale_icon(app_module: Any) -> None:
    install_status_notifier_tray_icon(app_module)
