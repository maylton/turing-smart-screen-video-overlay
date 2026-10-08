# SPDX-License-Identifier: GPL-3.0-or-later
"""The main GTK application, composed from its feature mixins.

Each mixin overrides methods of the classes after it and calls ``super()`` to
reach them, so the base order below is the order in which the features layer
on top of each other.
"""

from __future__ import annotations

import sys

from library import main_app_base as base
from library.html_theme_creator import ThemeCreatorMixin
from library.main_app_apply_status import ApplyStatusMixin
from library.main_app_dashboard_polish import DashboardMixin
from library.main_app_diagnostics_integration import DiagnosticsMixin
from library.main_app_i18n import I18nMixin, TrayItemI18nMixin, TrayMenuI18nMixin
from library.main_app_overview_refresh import OverviewRefreshMixin
from library.main_app_runtime import RuntimeMixin
from library.main_app_shutdown import ShutdownApplicationMixin, ShutdownTrayMenuMixin, ShutdownWindowMixin
from library.theme_gallery_i18n import install_theme_gallery_i18n
from library.tray_icon_runtime import TrayIconMixin


class SmartScreenWindow(
    ShutdownWindowMixin,
    DiagnosticsMixin,
    OverviewRefreshMixin,
    ApplyStatusMixin,
    I18nMixin,
    DashboardMixin,
    RuntimeMixin,
    ThemeCreatorMixin,
    base.SmartScreenWindow,
):
    pass


class StatusNotifierMenu(ShutdownTrayMenuMixin, TrayMenuI18nMixin, base.StatusNotifierMenu):
    pass


class StatusNotifierItem(TrayIconMixin, TrayItemI18nMixin, base.StatusNotifierItem):
    menu_class = StatusNotifierMenu


class SmartScreenApplication(ShutdownApplicationMixin, base.SmartScreenApplication):
    window_class = SmartScreenWindow
    tray_item_class = StatusNotifierItem


def main() -> int:
    # Translate every Adw.AlertDialog, wherever it is built.
    install_theme_gallery_i18n()
    app = SmartScreenApplication()
    try:
        return app.run(sys.argv)
    except KeyboardInterrupt:
        # Ctrl-C in the launching terminal: exit quietly with the shell's code.
        return 130
