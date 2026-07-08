# SPDX-License-Identifier: GPL-3.0-or-later
"""Safe direct i18n wrappers for ThemeEditorWindow methods.

These wrappers replace only ThemeEditorWindow methods that create translated
user-facing rows. They do not monkeypatch GTK/Libadwaita classes, and they keep
canonical theme values separate from translated labels.
"""

from __future__ import annotations

from typing import Any, Iterable


DROPDOWN_CONTROL_WIDTH = 280
DROPDOWN_STACK_WIDTH = 320
DROPDOWN_TEXT_WIDTH_CHARS = 40


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


def _translate_widget_text(widget: Any) -> None:
    for getter_name, setter_name in (
        ("get_label", "set_label"),
        ("get_title", "set_title"),
        ("get_subtitle", "set_subtitle"),
        ("get_tooltip_text", "set_tooltip_text"),
        ("get_placeholder_text", "set_placeholder_text"),
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
        translated = _translate(current)
        if translated != current:
            try:
                setter(translated)
            except Exception:
                pass


def _translate_widget_tree(root: Any) -> None:
    for widget in _walk_widgets(root):
        _translate_widget_text(widget)


def _choice_title(window: Any, key: str) -> str:
    if key == "PATH" and getattr(window, "selected_path", None) == ("video",):
        return _translate("Video path")
    return _translate(key)


def _choice_subtitle(window: Any, key: str) -> str:
    if key == "PATH" and getattr(window, "selected_path", None) == ("video",):
        return _translate("Choose a video from the theme folder or display storage.")
    return _translate(window.choice_subtitle_for_property(key))


def _set_string_model(app_module: Any, dropdown: Any, labels: list[str]) -> None:
    selected = 0
    try:
        selected = dropdown.get_selected()
    except Exception:
        pass
    dropdown.set_model(app_module.Gtk.StringList.new([_translate(label) for label in labels]))
    try:
        dropdown.set_selected(selected)
    except Exception:
        pass


def _dropdown_title_label(app_module: Any, title: str):
    label = app_module.Gtk.Label(label=title, xalign=0, wrap=True)
    label.add_css_class("heading")
    if hasattr(label, "set_wrap_mode"):
        try:
            label.set_wrap_mode(app_module.Pango.WrapMode.WORD_CHAR)
        except Exception:
            pass
    if hasattr(label, "set_max_width_chars"):
        label.set_max_width_chars(DROPDOWN_TEXT_WIDTH_CHARS)
    return label


def _dropdown_description_label(app_module: Any, subtitle: str):
    label = app_module.Gtk.Label(label=subtitle, xalign=0, wrap=True)
    label.add_css_class("dim-label")
    if hasattr(label, "set_wrap_mode"):
        try:
            label.set_wrap_mode(app_module.Pango.WrapMode.WORD_CHAR)
        except Exception:
            pass
    if hasattr(label, "set_max_width_chars"):
        label.set_max_width_chars(DROPDOWN_TEXT_WIDTH_CHARS)
    return label


def _size_dropdown_control(control: Any) -> None:
    if hasattr(control, "set_hexpand"):
        control.set_hexpand(True)
    if hasattr(control, "set_size_request"):
        control.set_size_request(DROPDOWN_CONTROL_WIDTH, -1)


def _dropdown_suffix_stack(app_module: Any, title: str, subtitle: str, *controls: Any):
    Gtk = app_module.Gtk
    stack = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
    stack.set_valign(Gtk.Align.CENTER)
    stack.set_hexpand(True)
    stack.set_size_request(DROPDOWN_STACK_WIDTH, -1)

    if title:
        stack.append(_dropdown_title_label(app_module, title))
    if subtitle:
        stack.append(_dropdown_description_label(app_module, subtitle))

    if len(controls) == 1:
        control = controls[0]
        _size_dropdown_control(control)
        stack.append(control)
        return stack

    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    row.set_hexpand(True)
    for control in controls:
        if control is controls[0]:
            _size_dropdown_control(control)
        row.append(control)
    stack.append(row)
    return stack


def _install_elements_panel_i18n(app_module: Any, window_class: type) -> None:
    if getattr(window_class, "_theme_editor_safe_elements_i18n_installed", False):
        return

    original_build_elements_panel = getattr(window_class, "build_elements_panel", None)
    if not callable(original_build_elements_panel):
        return

    def build_elements_panel_i18n(self, *args, **kwargs):
        panel = original_build_elements_panel(self, *args, **kwargs)
        dropdown = getattr(self, "add_element_dropdown", None)
        labels = getattr(self, "catalog_labels", None)
        if dropdown is not None and isinstance(labels, list):
            try:
                _set_string_model(app_module, dropdown, labels)
            except Exception:
                pass
        state_dropdown = getattr(self, "state_filter_dropdown", None)
        state_labels = getattr(self, "state_filter_labels", None)
        if state_dropdown is not None and isinstance(state_labels, list):
            try:
                _set_string_model(app_module, state_dropdown, state_labels)
            except Exception:
                pass
        _translate_widget_tree(panel)
        return panel

    build_elements_panel_i18n._theme_editor_safe_i18n_wrapper = True
    build_elements_panel_i18n._theme_editor_original = original_build_elements_panel
    window_class.build_elements_panel = build_elements_panel_i18n
    window_class._theme_editor_safe_elements_i18n_installed = True


def _install_tree_item_i18n(window_class: type) -> None:
    if getattr(window_class, "_theme_editor_safe_tree_i18n_installed", False):
        return

    original_bind_tree_item = getattr(window_class, "bind_tree_item", None)
    if not callable(original_bind_tree_item):
        return

    def bind_tree_item_i18n(self, factory, list_item):
        result = original_bind_tree_item(self, factory, list_item)
        try:
            _translate_widget_tree(list_item.get_child())
        except Exception:
            pass
        return result

    bind_tree_item_i18n._theme_editor_safe_i18n_wrapper = True
    bind_tree_item_i18n._theme_editor_original = original_bind_tree_item
    window_class.bind_tree_item = bind_tree_item_i18n
    window_class._theme_editor_safe_tree_i18n_installed = True


def _install_property_rows_i18n(window_class: type) -> None:
    if getattr(window_class, "_theme_editor_safe_property_rows_i18n_installed", False):
        return

    original_build_property_rows = getattr(window_class, "build_property_rows", None)
    if not callable(original_build_property_rows):
        return

    def build_property_rows_i18n(self, *args, **kwargs):
        # During early GTK construction, selection notifications can fire before
        # the right-side property widgets exist. Skipping this early callback is
        # safer than letting the editor enter a repeated traceback loop.
        if not hasattr(self, "path_label") or not hasattr(self, "dynamic_group"):
            return None
        result = original_build_property_rows(self, *args, **kwargs)
        for row in getattr(self, "property_rows", []):
            try:
                _translate_widget_tree(row)
            except Exception:
                pass
        return result

    build_property_rows_i18n._theme_editor_safe_i18n_wrapper = True
    build_property_rows_i18n._theme_editor_original = original_build_property_rows
    window_class.build_property_rows = build_property_rows_i18n
    window_class._theme_editor_safe_property_rows_i18n_installed = True


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
        dropdown.set_size_request(DROPDOWN_CONTROL_WIDTH, -1)
        title = _choice_title(self, key)
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

        row = Adw.ActionRow()
        row.add_suffix(_dropdown_suffix_stack(app_module, title, subtitle, dropdown))
        return row, dropdown

    create_choice_row_i18n._theme_editor_safe_i18n_wrapper = True
    create_choice_row_i18n._theme_editor_original = original_create_choice_row
    window_class.create_choice_row = create_choice_row_i18n
    window_class._theme_editor_safe_choice_i18n_installed = True


def _install_property_preset_i18n(app_module: Any, window_class: type) -> None:
    if getattr(window_class, "_theme_editor_safe_property_preset_i18n_installed", False):
        return

    Gtk = app_module.Gtk
    original_create_property_preset_dropdown = getattr(
        window_class,
        "create_property_preset_dropdown",
        None,
    )
    if not callable(original_create_property_preset_dropdown):
        return

    def create_property_preset_dropdown_i18n(self, key, current_value, target_entry):
        options = self.property_preset_options(key, current_value)
        if len(options) < 2:
            return None

        labels = tuple(_translate(label) for label, _value in options)
        values = tuple(value for _label, value in options)
        dropdown = Gtk.DropDown.new_from_strings(labels)
        dropdown.set_size_request(DROPDOWN_CONTROL_WIDTH, -1)
        dropdown.set_valign(Gtk.Align.CENTER)
        dropdown.set_tooltip_text(
            _translate("Choose a common value, or type a custom value in the field.")
        )
        if hasattr(dropdown, "set_enable_search"):
            dropdown.set_enable_search(len(options) > 12)

        selected = 0
        for index, value in enumerate(values):
            if value == current_value:
                selected = index
                break
            if (
                isinstance(value, (int, float))
                and isinstance(current_value, (int, float))
                and not isinstance(value, bool)
                and not isinstance(current_value, bool)
                and float(value) == float(current_value)
            ):
                selected = index
                break

        dropdown.set_selected(selected)
        dropdown._theme_preset_values = values

        def preset_changed(widget, _param):
            index = widget.get_selected()
            if index == Gtk.INVALID_LIST_POSITION:
                return
            preset_values = widget._theme_preset_values
            if index < 0 or index >= len(preset_values):
                return
            target_entry.set_text(
                self.value_to_text(preset_values[index])
            )

        dropdown.connect("notify::selected", preset_changed)
        return dropdown

    create_property_preset_dropdown_i18n._theme_editor_safe_i18n_wrapper = True
    create_property_preset_dropdown_i18n._theme_editor_original = original_create_property_preset_dropdown
    window_class.create_property_preset_dropdown = create_property_preset_dropdown_i18n
    window_class._theme_editor_safe_property_preset_i18n_installed = True


def _install_text_style_preset_i18n(app_module: Any, window_class: type) -> None:
    if getattr(window_class, "_theme_editor_safe_text_style_i18n_installed", False):
        return

    Gtk = app_module.Gtk
    Adw = app_module.Adw
    text_style_preset_names = app_module.text_style_preset_names
    text_style_updates = app_module.text_style_updates

    original_create_text_style_preset_row = getattr(
        window_class,
        "create_text_style_preset_row",
        None,
    )
    if not callable(original_create_text_style_preset_row):
        return

    def create_text_style_preset_row_i18n(self, node):
        preset_names = text_style_preset_names(node, self.selected_path)
        if not preset_names:
            return None

        labels = [_translate("Choose a preset…")] + [
            _translate(name)
            for name in preset_names
        ]
        dropdown = Gtk.DropDown.new_from_strings(labels)
        dropdown.set_size_request(DROPDOWN_CONTROL_WIDTH, -1)
        dropdown.set_valign(Gtk.Align.CENTER)
        dropdown.set_tooltip_text(_translate("Fill available text fields"))
        dropdown._theme_resetting_text_style = False

        title = _translate("Text style preset")
        subtitle = _translate("Apply values to the current text fields.")
        row = Adw.ActionRow()
        row.add_suffix(_dropdown_suffix_stack(app_module, title, subtitle, dropdown))

        def preset_changed(widget, _param):
            if getattr(widget, "_theme_resetting_text_style", False):
                return
            index = widget.get_selected()
            if index in (0, Gtk.INVALID_LIST_POSITION):
                return
            if index - 1 >= len(preset_names):
                return

            updates = text_style_updates(preset_names[index - 1], node)
            for key, value in updates.items():
                self.set_property_widget_value(key, value)

            widget._theme_resetting_text_style = True
            widget.set_selected(0)
            widget._theme_resetting_text_style = False

        dropdown.connect("notify::selected", preset_changed)
        return row

    create_text_style_preset_row_i18n._theme_editor_safe_i18n_wrapper = True
    create_text_style_preset_row_i18n._theme_editor_original = original_create_text_style_preset_row
    window_class.create_text_style_preset_row = create_text_style_preset_row_i18n
    window_class._theme_editor_safe_text_style_i18n_installed = True


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
        dropdown.set_size_request(DROPDOWN_CONTROL_WIDTH, -1)
        dropdown.set_tooltip_text(
            _translate("Apply a starter layout to this component")
        )
        dropdown._theme_component_preset_updates = tuple(
            copy.deepcopy(updates)
            for _label, updates in options
        )

        button = Gtk.Button(
            label="",
            icon_name="emblem-ok-symbolic",
            valign=Gtk.Align.CENTER,
            sensitive=False,
        )
        button.set_tooltip_text(_translate("Apply preset"))

        title = _translate(
            component_preset_titles.get(
                self.component_kind_for_node(self.selected_path, node),
                "Component preset",
            )
        )
        subtitle = _translate("Apply a safe starter layout to this selected component.")
        row = Adw.ActionRow()
        row.add_suffix(_dropdown_suffix_stack(app_module, title, subtitle, dropdown, button))

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

    _install_elements_panel_i18n(app_module, window_class)
    _install_tree_item_i18n(window_class)
    _install_property_rows_i18n(window_class)
    _install_choice_row_i18n(app_module, window_class)
    _install_property_preset_i18n(app_module, window_class)
    _install_text_style_preset_i18n(app_module, window_class)
    _install_component_preset_i18n(app_module, window_class)
