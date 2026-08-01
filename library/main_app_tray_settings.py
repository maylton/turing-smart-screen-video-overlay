# SPDX-License-Identifier: GPL-3.0-or-later
"""Tray icon appearance controls for the main GTK Settings page."""

from __future__ import annotations

from typing import Any, Optional

from library.tray_icon_preferences import (
    MODE_COLOR,
    MODE_DARK_THEME,
    MODE_FOLLOW_THEME,
    MODE_LIGHT_THEME,
    load_tray_icon_mode,
    save_tray_icon_mode,
)
from library.tray_icon_runtime import (
    install_status_notifier_tray_icon,
    refresh_status_notifier_icon,
)


MODES = (
    MODE_FOLLOW_THEME,
    MODE_COLOR,
    MODE_DARK_THEME,
    MODE_LIGHT_THEME,
)


def _is_pt_br() -> bool:
    try:
        from library.i18n import active_language

        return active_language() == "pt_BR"
    except Exception:
        return False


def _copy() -> dict:
    if _is_pt_br():
        return {
            "group_title": "Ícone da bandeja",
            "group_description": (
                "Escolha como o ícone aparece no Caelestia e em outras "
                "bandejas compatíveis com StatusNotifier."
            ),
            "row_title": "Aparência do ícone",
            "row_subtitle": (
                "Seguir tema alterna automaticamente entre o ícone claro e "
                "o escuro."
            ),
            "labels": (
                "Seguir tema",
                "Colorido",
                "Para temas escuros",
                "Para temas claros",
            ),
            "saved": "Ícone da bandeja atualizado",
            "save_error": "Não foi possível salvar o ícone da bandeja: {error}",
        }
    return {
        "group_title": "Tray icon",
        "group_description": (
            "Choose how the icon appears in Caelestia and other "
            "StatusNotifier-compatible trays."
        ),
        "row_title": "Icon appearance",
        "row_subtitle": (
            "Follow theme switches automatically between the light and dark "
            "symbolic icons."
        ),
        "labels": (
            "Follow theme",
            "Color",
            "For dark themes",
            "For light themes",
        ),
        "saved": "Tray icon updated",
        "save_error": "Could not save tray icon preference: {error}",
    }


def _settings_box(page: Any) -> Optional[Any]:
    """Return the vertical box inside ScrolledWindow → Clamp → Box."""
    try:
        clamp = page.get_child()
        return clamp.get_child() if clamp is not None else None
    except Exception:
        return None


def _application_for_window(window: Any) -> Optional[Any]:
    getter = getattr(window, "get_application", None)
    if callable(getter):
        try:
            return getter()
        except Exception:
            pass
    props = getattr(window, "props", None)
    return getattr(props, "application", None)


def _refresh_window_tray_icon(app_module: Any, window: Any) -> bool:
    application = _application_for_window(window)
    notifier = getattr(application, "tray_item", None)
    if notifier is None:
        return False
    return refresh_status_notifier_icon(app_module, notifier)


def _toast(window: Any, message: str) -> None:
    show = getattr(window, "toast", None)
    if callable(show):
        try:
            show(message)
        except Exception:
            pass


def install_main_app_tray_settings(app_module: Any) -> None:
    """Add the tray icon ComboRow after all runtime UI patches are installed."""
    install_status_notifier_tray_icon(app_module)

    window_class = getattr(app_module, "SmartScreenWindow", None)
    if window_class is None or getattr(
        window_class,
        "_tray_icon_settings_installed",
        False,
    ):
        return

    original_build_settings_page = getattr(window_class, "build_settings_page", None)
    original_init = getattr(window_class, "__init__", None)
    if not callable(original_build_settings_page) or not callable(original_init):
        return

    def on_tray_icon_mode_changed(self, row, _param=None):
        try:
            selected = int(row.get_selected())
        except Exception:
            selected = 0
        selected = max(0, min(len(MODES) - 1, selected))

        text = _copy()
        try:
            save_tray_icon_mode(MODES[selected])
        except Exception as exc:
            _toast(self, text["save_error"].format(error=exc))
            return

        _refresh_window_tray_icon(app_module, self)
        _toast(self, text["saved"])

    def build_settings_page_with_tray_icon(self):
        page = original_build_settings_page(self)
        box = _settings_box(page)
        if box is None:
            return page

        text = _copy()
        group = app_module.Adw.PreferencesGroup()
        group.set_title(text["group_title"])
        group.set_description(text["group_description"])

        row = app_module.Adw.ComboRow()
        row.set_title(text["row_title"])
        row.set_subtitle(text["row_subtitle"])
        row.set_model(app_module.Gtk.StringList.new(list(text["labels"])))
        try:
            row.set_selected(MODES.index(load_tray_icon_mode()))
        except ValueError:
            row.set_selected(0)
        row.connect("notify::selected", self.on_tray_icon_mode_changed)
        group.add(row)
        self.tray_icon_mode_row = row

        # The Settings layout starts with title → Appearance. Keep the tray
        # choice alongside Appearance, before Runtime and Maintenance.
        try:
            title = box.get_first_child()
            appearance = title.get_next_sibling() if title is not None else None
            box.insert_child_after(group, appearance)
        except Exception:
            box.append(group)
        return page

    def init_with_tray_icon_theme_tracking(self, application):
        original_init(self, application)
        try:
            manager = app_module.Adw.StyleManager.get_default()

            def on_dark_changed(_manager, _param):
                if load_tray_icon_mode() == MODE_FOLLOW_THEME:
                    _refresh_window_tray_icon(app_module, self)

            self._tray_icon_dark_handler = manager.connect(
                "notify::dark",
                on_dark_changed,
            )
        except Exception:
            pass

    on_tray_icon_mode_changed._tray_icon_settings_wrapper = True
    build_settings_page_with_tray_icon._tray_icon_settings_wrapper = True
    init_with_tray_icon_theme_tracking._tray_icon_settings_wrapper = True

    window_class.on_tray_icon_mode_changed = on_tray_icon_mode_changed
    window_class.build_settings_page = build_settings_page_with_tray_icon
    window_class.__init__ = init_with_tray_icon_theme_tracking
    window_class._tray_icon_settings_installed = True
