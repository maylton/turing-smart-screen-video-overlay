# SPDX-License-Identifier: GPL-3.0-or-later
"""Safe widget-level i18n patch for the GTK Theme Editor.

This intentionally avoids the previous ``__build_class__`` hook. It only wraps
GTK/Libadwaita widget constructors, text setters, dialog response labels,
DropDown string factories, and StringList creation/updates while
``theme-editor-gtk.py`` is starting up.
"""

from __future__ import annotations

from typing import Any, Iterable


_INSTALLED = False
_TEXT_KWARGS = {
    "label",
    "title",
    "subtitle",
    "tooltip_text",
    "placeholder_text",
    "heading",
    "body",
}


def _translate(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return value
    try:
        from library.theme_editor_i18n import t

        translated = t(value)
        if translated != value:
            return translated
    except Exception:
        pass
    try:
        from library.theme_editor_preset_i18n import t as preset_t

        return preset_t(value)
    except Exception:
        return value


def _translated_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    if not kwargs:
        return kwargs
    translated = dict(kwargs)
    for key in _TEXT_KWARGS:
        if key in translated:
            translated[key] = _translate(translated[key])
    return translated


def _translated_strings(strings: Iterable[str] | None):
    if strings is None:
        return strings
    try:
        return [_translate(item) for item in strings]
    except Exception:
        return strings


def _patch_init(cls: Any) -> None:
    original = getattr(cls, "__init__", None)
    if not callable(original) or getattr(original, "_theme_editor_widget_i18n", False):
        return

    def init_with_i18n(self, *args, **kwargs):
        return original(self, *args, **_translated_kwargs(kwargs))

    init_with_i18n._theme_editor_widget_i18n = True
    try:
        cls.__init__ = init_with_i18n
    except Exception:
        pass


def _patch_text_method(cls: Any, method_name: str) -> None:
    original = getattr(cls, method_name, None)
    if not callable(original) or getattr(original, "_theme_editor_widget_i18n", False):
        return

    def method_with_i18n(self, text, *args, **kwargs):
        return original(self, _translate(text), *args, **kwargs)

    method_with_i18n._theme_editor_widget_i18n = True
    try:
        setattr(cls, method_name, method_with_i18n)
    except Exception:
        pass


def _patch_dialog_response(cls: Any) -> None:
    original = getattr(cls, "add_response", None)
    if not callable(original) or getattr(original, "_theme_editor_widget_i18n", False):
        return

    def add_response_with_i18n(self, response_id, label, *args, **kwargs):
        return original(self, response_id, _translate(label), *args, **kwargs)

    add_response_with_i18n._theme_editor_widget_i18n = True
    try:
        cls.add_response = add_response_with_i18n
    except Exception:
        pass


def _patch_dropdown_new_from_strings(Gtk: Any) -> None:
    cls = getattr(Gtk, "DropDown", None)
    if cls is None:
        return
    original = getattr(cls, "new_from_strings", None)
    if not callable(original) or getattr(original, "_theme_editor_widget_i18n", False):
        return

    def new_from_strings_with_i18n(strings: Iterable[str] | None = None):
        return original(_translated_strings(strings))

    new_from_strings_with_i18n._theme_editor_widget_i18n = True
    try:
        cls.new_from_strings = staticmethod(new_from_strings_with_i18n)
    except Exception:
        pass


def _patch_string_list(Gtk: Any) -> None:
    cls = getattr(Gtk, "StringList", None)
    if cls is None or getattr(cls, "_theme_editor_widget_i18n", False):
        return

    original_new = getattr(cls, "new", None)
    if callable(original_new):
        def new_with_i18n(strings: Iterable[str] | None = None):
            return original_new(_translated_strings(strings))

        new_with_i18n._theme_editor_widget_i18n = True
        try:
            cls.new = staticmethod(new_with_i18n)
        except Exception:
            pass

    original_append = getattr(cls, "append", None)
    if callable(original_append):
        def append_with_i18n(self, string, *args, **kwargs):
            return original_append(self, _translate(string), *args, **kwargs)

        append_with_i18n._theme_editor_widget_i18n = True
        try:
            cls.append = append_with_i18n
        except Exception:
            pass

    original_splice = getattr(cls, "splice", None)
    if callable(original_splice):
        def splice_with_i18n(self, position, n_removals, additions, *args, **kwargs):
            return original_splice(
                self,
                position,
                n_removals,
                _translated_strings(additions),
                *args,
                **kwargs,
            )

        splice_with_i18n._theme_editor_widget_i18n = True
        try:
            cls.splice = splice_with_i18n
        except Exception:
            pass

    cls._theme_editor_widget_i18n = True


def install() -> None:
    """Install narrowly-scoped text translation hooks for the Theme Editor."""

    global _INSTALLED
    if _INSTALLED:
        return

    try:
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw, Gtk
    except Exception:
        return

    classes = [
        getattr(Gtk, name, None)
        for name in (
            "ApplicationWindow",
            "Button",
            "CheckButton",
            "Entry",
            "Label",
            "MenuButton",
            "ToggleButton",
            "Window",
        )
    ] + [
        getattr(Adw, name, None)
        for name in (
            "ActionRow",
            "AlertDialog",
            "ApplicationWindow",
            "ComboRow",
            "EntryRow",
            "ExpanderRow",
            "PreferencesGroup",
            "PreferencesPage",
            "PreferencesRow",
            "SpinRow",
            "SwitchRow",
            "WindowTitle",
        )
    ]

    for cls in classes:
        if cls is None:
            continue
        _patch_init(cls)
        for method_name in (
            "set_label",
            "set_title",
            "set_subtitle",
            "set_tooltip_text",
            "set_placeholder_text",
            "set_heading",
            "set_body",
        ):
            _patch_text_method(cls, method_name)

    alert_dialog = getattr(Adw, "AlertDialog", None)
    if alert_dialog is not None:
        _patch_dialog_response(alert_dialog)

    _patch_dropdown_new_from_strings(Gtk)
    _patch_string_list(Gtk)
    _INSTALLED = True
