# SPDX-License-Identifier: GPL-3.0-or-later
"""Safe direct i18n wrappers for ThemeEditorWindow methods.

These wrappers replace only ThemeEditorWindow methods that create translated
user-facing rows. They do not monkeypatch GTK/Libadwaita classes, and they keep
canonical theme values separate from translated labels.
"""

from __future__ import annotations

from typing import Any


def _translate(message: Any) -> Any:
    if not isinstance(message, str) or not message:
        return message
    try:
        from library.theme_editor_i18n import t as theme_t

        translated = theme_t(message)
        if translated != message:
            return translated
    except Exception:
        pass
    try:
        from library.theme_editor_preset_i18n import t as preset_t

        return preset_t(message)
    except Exception:
        return message


def _choice_title(window: Any, key: str) -> str:
    if key == "PATH" and getattr(window, "selected_path", None) == ("video",):
        return _translate("Video path")
    return _translate(key)


def _choice_subtitle(window: Any, key: str) -> str:
    if key == "PATH" and getattr(window, "selected_path", None) == ("video",):
        return _translate("Choose a video from the theme folder or display storage.")
    return _translate(window.choice_subtitle_for_property(key))


def _install_choice_row_i18n(app_module: Any, window_class: type) -> None:
    if getattr(window_class, "_theme_editor_safe_choice_i18n_installed", False):
        return

    Gtk = app_module.Gtk
    Adw = app_module.Adw
    asset_choice_keys = getattr(app_module, "ASSET_CHOICE_KEYS", set())

    original_create_choice_row = getattr(window_class, "create_choice_row", None)
    if not callable(original_create_choice_row):
        return

    def create_choice_row_i18n(self, key, value):
        options = self.choice_options_for_property(key, value)
        if not options:
            fallback_label = self.value_to_text(value) or "No value"
            options = [(f"Current — {fallback_label}", value)]

        labels = [_translate(label) for label, _option_value in options]
        values = [option_value for _label, option_value in options]
        dropdown = Gtk.DropDown.new_from_strings(labels)
        dropdown.set_valign(Gtk.Align.CENTER)
        dropdown.set_size_request(220, -1)
        subtitle = _choice_subtitle(self, key)
        dropdown.set_tooltip_text(subtitle)
        if hasattr(dropdown, "set_enable_search"):
            dropdown.set_enable_search(key in asset_choice_keys or len(options) > 12)
        dropdown._theme_choice_values = tuple(values)

        selected = 0
        try:
            normalized = self.parse_value(key, value, value)
        except Exception:
            normalized = value
        for index, option_value in enumerate(values):
            if self.same_property_value(option_value, normalized):
                selected = index
                break
        dropdown.set_selected(selected)

        row = Adw.ActionRow(
            title=_choice_title(self, key),
            subtitle=subtitle,
        )
        row.add_suffix(dropdown)
        return row, dropdown

    create_choice_row_i18n._theme_editor_safe_i18n_wrapper = True
    create_choice_row_i18n._theme_editor_original = original_create_choice_row
    window_class.create_choice_row = create_choice_row_i18n
    window_class._theme_editor_safe_choice_i18n_installed = True


def _install_component_preset_i18n(app_module: Any, window_class: type) -> None:
    if getattr(window_class, "_theme_editor_safe_component_preset_i18n_installed", False):
        return

    Gtk = app_module.Gtk
    Adw = app_module.Adw
    GLib = app_module.GLib
    copy = app_module.copy
    component_preset_titles = getattr(app_module, "COMPONENT_PRESET_TITLES", {})

    original_create_component_preset_row = getattr(
        window_class,
        "create_component_preset_row",
        None,
    )
    if not callable(original_create_component_preset_row):
        return

    def create_component_preset_row_i18n(self, node):
        options = self.component_preset_options(node)
        if not options:
            return None

        labels = [_translate("Choose a preset…")] + [
            _translate(label)
            for label, _updates in options
        ]
        dropdown = Gtk.DropDown.new_from_strings(labels)
        dropdown.set_valign(Gtk.Align.CENTER)
        dropdown.set_size_request(220, -1)
        dropdown.set_tooltip_text(
            _translate("Apply a starter layout to this component")
        )
        dropdown._theme_component_preset_updates = tuple(
            copy.deepcopy(updates)
            for _label, updates in options
        )

        button = Gtk.Button(
            label=_translate("Apply preset"),
            icon_name="emblem-ok-symbolic",
            valign=Gtk.Align.CENTER,
            sensitive=False,
        )

        row = Adw.ActionRow(
            title=_translate(
                component_preset_titles.get(
                    self.component_kind_for_node(self.selected_path, node),
                    "Component preset",
                )
            ),
            subtitle=_translate(
                "Apply a safe starter layout to this selected component."
            ),
        )
        row.add_suffix(dropdown)
        row.add_suffix(button)

        def preset_changed(widget, _param):
            index = widget.get_selected()
            button.set_sensitive(index not in (0, Gtk.INVALID_LIST_POSITION))

        def apply_preset(*_args):
            if self.selected_path is None:
                return
            index = dropdown.get_selected()
            updates = dropdown._theme_component_preset_updates
            if index in (0, Gtk.INVALID_LIST_POSITION) or index - 1 >= len(updates):
                self.toast("Choose a component preset first")
                return

            try:
                current = self.node_at_path(self.selected_path)
            except Exception:
                self.toast("Selected component is no longer available")
                return
            if not isinstance(current, dict):
                return

            self.push_undo()
            for key, value in updates[index - 1].items():
                current[key] = copy.deepcopy(value)

            if not self.save_theme_data():
                return

            self.populate_elements()
            GLib.idle_add(self.restore_tree_selection, self.selected_path)
            self.build_property_rows()
            self.refresh_preview()
            dropdown.set_selected(0)
            button.set_sensitive(False)
            self.toast("Component preset applied")

        dropdown.connect("notify::selected", preset_changed)
        button.connect("clicked", apply_preset)
        return row

    create_component_preset_row_i18n._theme_editor_safe_i18n_wrapper = True
    create_component_preset_row_i18n._theme_editor_original = original_create_component_preset_row
    window_class.create_component_preset_row = create_component_preset_row_i18n
    window_class._theme_editor_safe_component_preset_i18n_installed = True


def install_theme_editor_safe_i18n(app_module: Any) -> None:
    """Install direct, non-global i18n wrappers on ThemeEditorWindow."""

    window_class = getattr(app_module, "ThemeEditorWindow", None)
    if window_class is None:
        return

    _install_choice_row_i18n(app_module, window_class)
    _install_component_preset_i18n(app_module, window_class)
