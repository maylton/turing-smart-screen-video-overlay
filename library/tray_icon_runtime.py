# SPDX-License-Identifier: GPL-3.0-or-later
"""Install the grayscale icon on the GTK StatusNotifierItem implementation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from library.tray_icon import status_notifier_pixmaps


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


def install_status_notifier_grayscale_icon(app_module: Any) -> None:
    """Force SNI hosts to consume the generated grayscale ``IconPixmap``.

    Quickshell, which powers Caelestia Shell, prefers ``IconName`` whenever it
    is non-empty and ignores ``IconPixmap`` in that case.  Returning an empty
    name is therefore intentional: it makes Quickshell use its tray image
    provider backed by the monochrome pixmaps.

    The installer checks the currently active method rather than relying only
    on a process-global flag.  This lets it repair the tray after another
    integration, such as the translation layer, replaces ``_on_get_property``.
    """

    global _INSTALLED

    notifier_class = getattr(app_module, "StatusNotifierItem", None)
    glib = getattr(app_module, "GLib", None)
    project_root = Path(getattr(app_module, "ROOT", Path.cwd())).resolve()
    if notifier_class is None or glib is None:
        return

    current_get_property = getattr(notifier_class, "_on_get_property", None)
    if getattr(current_get_property, "_turing_grayscale_tray_icon", False):
        _INSTALLED = True
        return
    if not callable(current_get_property):
        return

    app_module.STATUS_NOTIFIER_XML = _add_icon_pixmap_property(
        str(getattr(app_module, "STATUS_NOTIFIER_XML", ""))
    )

    pixmaps = status_notifier_pixmaps(project_root)
    original_get_property = current_get_property

    def get_property_with_grayscale_icon(
        self,
        connection,
        sender,
        object_path,
        interface_name,
        property_name,
    ):
        if property_name == "IconName":
            return glib.Variant("s", "")
        if property_name == "IconThemePath":
            return glib.Variant("s", "")
        if property_name == "IconPixmap":
            return glib.Variant("a(iiay)", pixmaps)
        if property_name == "ToolTip":
            return glib.Variant(
                "(sa(iiay)ss)",
                (
                    "",
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
