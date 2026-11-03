# SPDX-License-Identifier: GPL-3.0-or-later
"""Selected icon appearance for the GTK StatusNotifierItem."""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from gi.repository import Adw, GLib

from library.main_app_base import (
    APP_ID,
    APP_NAME,
    ROOT,
    STATUS_NOTIFIER_XML,
    read_current_theme,
)
from library.tray_icon import DEFAULT_SIZES, status_notifier_pixmaps
from library.tray_icon_preferences import (
    MODE_COLOR,
    load_tray_icon_mode,
    resolve_tray_icon_variant,
)




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


def style_prefers_dark() -> bool:
    try:
        return bool(Adw.StyleManager.get_default().get_dark())
    except Exception:
        return True


def active_tray_icon_variant() -> str:
    return resolve_tray_icon_variant(load_tray_icon_mode(), dark_theme=style_prefers_dark())


class TrayIconMixin:
    """Expose color or symbolic icon properties according to the saved mode.

    Caelestia uses Quickshell, which prefers ``IconName`` whenever it is
    non-empty. Color mode therefore returns the normal application icon name;
    symbolic modes return an empty name so Quickshell consumes the generated
    ``IconPixmap`` instead.
    """

    introspection_xml = _add_icon_pixmap_property(STATUS_NOTIFIER_XML)

    def _icon_payload(self) -> tuple[str, List[Tuple[int, int, bytes]]]:
        cache: Dict[str, List[Tuple[int, int, bytes]]] = self.__dict__.setdefault("_pixmap_cache", {})
        variant = active_tray_icon_variant()
        pixmaps = cache.get(variant)
        if pixmaps is None:
            pixmaps = status_notifier_pixmaps(ROOT, sizes=DEFAULT_SIZES, variant=variant)
            cache[variant] = pixmaps
        return variant, pixmaps

    def _on_get_property(self, connection, sender, object_path, interface_name, property_name):
        variant, pixmaps = self._icon_payload()
        icon_name = APP_ID if variant == MODE_COLOR else ""
        if property_name == "IconName":
            return GLib.Variant("s", icon_name)
        if property_name == "IconThemePath":
            return GLib.Variant("s", "")
        if property_name == "IconPixmap":
            return GLib.Variant("a(iiay)", pixmaps)
        if property_name == "ToolTip":
            return GLib.Variant(
                "(sa(iiay)ss)",
                (icon_name, pixmaps, APP_NAME, "Theme: " + (read_current_theme() or "not selected")),
            )
        return super()._on_get_property(connection, sender, object_path, interface_name, property_name)
