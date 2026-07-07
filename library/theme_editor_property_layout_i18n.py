# SPDX-License-Identifier: GPL-3.0-or-later
"""Property panel layout/i18n helpers for the inline GTK Theme Editor."""

from __future__ import annotations

from typing import Any


def _translate(message: str) -> str:
    try:
        from library.theme_editor_preset_i18n import t

        return t(message)
    except Exception:
        return message


def _asset_title(key: str, window: Any) -> str:
    if key == "PATH" and getattr(window, "selected_path", None) == ("video",):
        return _translate("Video path")
    return _translate(key)


def _asset_subtitle(key: str, window: Any, original_subtitle: str) -> str:
    if key == "PATH" and getattr(window, "selected_path", None) == ("video",):
        return _translate("Choose a video from the theme folder or display storage.")
    return _translate(original_subtitle)


def _build_stacked_asset_choice_row(window: Any, key: str, value: Any):
    app_module = __import__(window.__class__.__module__)
    Gtk = app_module.Gtk

    options = window.choice_options_for_property(key, value)
    if not options:
        fallback_label = window.value_to_text(value) or "No value"
        options = [(f"Current — {fallback_label}", value)]

    labels = [_translate(label) for label, _option_value in options]
    values = [option_value for _label, option_value in options]
    dropdown = Gtk.DropDown.new_from_strings(labels)
    dropdown.set_hexpand(True)
    dropdown.set_valign(Gtk.Align.CENTER)
    dropdown.set_size_request(0, -1)

    subtitle = _asset_subtitle(key, window, window.choice_subtitle_for_property(key))
    dropdown.set_tooltip_text(subtitle)
    if hasattr(dropdown, "set_enable_search"):
        dropdown.set_enable_search(True)
    dropdown._theme_choice_values = tuple(values)

    selected = 0
    try:
        normalized = window.parse_value(key, value, value)
    except Exception:
        normalized = value
    for index, option_value in enumerate(values):
        if window.same_property_value(option_value, normalized):
            selected = index
            break
    dropdown.set_selected(selected)

    row = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=6,
        margin_top=10,
        margin_bottom=10,
        margin_start=12,
        margin_end=12,
    )
    title = Gtk.Label(label=_asset_title(key, window), xalign=0)
    title.add_css_class("heading")
    subtitle_label = Gtk.Label(label=subtitle, xalign=0, wrap=True)
    subtitle_label.add_css_class("dim-label")
    dropdown_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    dropdown_box.append(dropdown)

    row.append(title)
    row.append(subtitle_label)
    row.append(dropdown_box)
    return row, dropdown


def install_theme_editor_property_layout_i18n(app_module: Any) -> None:
    """Patch ThemeEditorWindow asset/path choices into readable stacked rows."""

    window_class = getattr(app_module, "ThemeEditorWindow", None)
    if window_class is None or getattr(
        window_class,
        "_theme_editor_property_layout_i18n_installed",
        False,
    ):
        return

    original_create_choice_row = getattr(window_class, "create_choice_row", None)
    if not callable(original_create_choice_row):
        return

    def create_choice_row_with_stacked_assets(self, key, value):
        asset_keys = getattr(app_module, "ASSET_CHOICE_KEYS", set())
        if key in asset_keys:
            return _build_stacked_asset_choice_row(self, key, value)
        row, widget = original_create_choice_row(self, key, value)
        try:
            from library.theme_editor_i18n import translate_widget_tree

            translate_widget_tree(row)
        except Exception:
            pass
        return row, widget

    create_choice_row_with_stacked_assets._theme_editor_property_layout_i18n = True
    window_class.create_choice_row = create_choice_row_with_stacked_assets
    window_class._theme_editor_property_layout_i18n_installed = True
