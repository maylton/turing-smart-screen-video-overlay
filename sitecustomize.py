# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime UI polish hooks for the GTK configuration app.

Python imports this module automatically when it is present on sys.path. Keep
this file narrowly scoped so normal monitor/runtime commands are not affected.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

_TARGET_ENTRY_POINTS = {
    "configure-gtk.py",
    "theme-gallery-gtk.py",
    "turing-smart-screen-gtk.py",
    "turing-smart-screen-main.py",
}


def _should_patch_theme_gallery() -> bool:
    return Path(sys.argv[0]).name in _TARGET_ENTRY_POINTS


def _install_theme_gallery_card_polish() -> None:
    from library import theme_gallery as gallery

    Gtk = gallery.Gtk
    Pango = gallery.Pango
    ThemeGalleryPane = gallery.ThemeGalleryPane
    ThemeRecord = gallery.ThemeRecord
    relative_path_label = gallery.relative_path_label

    def menu_action_button(
        self: ThemeGalleryPane,
        label: str,
        callback: Callable[[], None],
        *,
        sensitive: bool = True,
        destructive: bool = False,
        popover: Gtk.Popover | None = None,
    ) -> Gtk.Button:
        button = Gtk.Button(label=label)
        button.set_halign(Gtk.Align.FILL)
        button.set_hexpand(True)
        button.add_css_class("flat")
        button.set_sensitive(sensitive)
        if destructive:
            button.add_css_class("destructive-action")

        def on_clicked(_button: Gtk.Button) -> None:
            if popover is not None:
                popover.popdown()
            callback()

        button.connect("clicked", on_clicked)
        return button

    def theme_actions_popover(
        self: ThemeGalleryPane,
        record: ThemeRecord,
    ) -> Gtk.Popover:
        popover = Gtk.Popover()
        popover.set_has_arrow(True)

        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            margin_top=8,
            margin_bottom=8,
            margin_start=8,
            margin_end=8,
        )
        box.set_size_request(220, -1)

        box.append(
            self._menu_action_button(
                "Duplicate",
                lambda: self.confirm_duplicate_theme(record),
                sensitive=record.editable,
                popover=popover,
            )
        )
        box.append(
            self._menu_action_button(
                "Rename",
                lambda: self.confirm_rename_theme(record),
                popover=popover,
            )
        )
        box.append(
            self._menu_action_button(
                "Export",
                lambda: self.confirm_export_theme(record),
                sensitive=record.editable,
                popover=popover,
            )
        )
        box.append(
            self._menu_action_button(
                "Open folder",
                lambda: self.on_open_folder(record),
                popover=popover,
            )
        )

        if self.on_theme_diagnostics is not None:
            box.append(
                self._menu_action_button(
                    "Diagnostics",
                    lambda: self.on_theme_diagnostics(record),
                    popover=popover,
                )
            )

        if not record.current:
            box.append(
                self._menu_action_button(
                    "Delete",
                    lambda: self.confirm_delete_theme(record),
                    destructive=True,
                    popover=popover,
                )
            )

        popover.set_child(box)
        return popover

    def compact_preview_widget(
        self: ThemeGalleryPane,
        record: ThemeRecord,
    ) -> Gtk.Widget:
        if record.preview_file.is_file():
            picture = Gtk.Picture.new_for_filename(str(record.preview_file))
            picture.set_size_request(256, 126)
            picture.set_hexpand(True)
            picture.set_can_shrink(True)
            if hasattr(picture, "set_content_fit"):
                picture.set_content_fit(Gtk.ContentFit.CONTAIN)
            return picture

        placeholder = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
        )
        placeholder.set_size_request(256, 126)
        icon = Gtk.Image.new_from_icon_name("image-missing-symbolic")
        icon.set_pixel_size(42)
        placeholder.append(icon)
        label = Gtk.Label(label="No preview")
        label.add_css_class("dim-label")
        placeholder.append(label)
        return placeholder

    def compact_theme_card(
        self: ThemeGalleryPane,
        record: ThemeRecord,
    ) -> Gtk.Widget:
        card = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=9,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
        )
        card.add_css_class("card")
        card.set_size_request(292, 260)
        card.set_valign(Gtk.Align.START)

        preview_frame = Gtk.Frame()
        preview_frame.set_size_request(256, 126)
        preview_frame.set_child(self.preview_widget(record))
        card.append(preview_frame)

        header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header_row.set_hexpand(True)

        name = Gtk.Label(label=record.name, xalign=0)
        name.set_ellipsize(Pango.EllipsizeMode.END)
        name.add_css_class("heading")
        name.set_hexpand(True)
        header_row.append(name)

        if record.current:
            badge = Gtk.Label(label="Current")
            badge.add_css_class("accent")
            badge.add_css_class("caption")
            header_row.append(badge)

        card.append(header_row)

        meta_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        meta_box.set_hexpand(True)

        status = Gtk.Label(label=record.status_label, xalign=0, wrap=False)
        status.set_ellipsize(Pango.EllipsizeMode.END)
        status.add_css_class("dim-label")
        meta_box.append(status)

        display = Gtk.Label(label=record.display_label, xalign=0)
        display.add_css_class("caption")
        display.add_css_class("dim-label")
        meta_box.append(display)

        path = Gtk.Label(label=relative_path_label(record.directory), xalign=0)
        path.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        path.set_lines(1)
        path.add_css_class("caption")
        path.add_css_class("dim-label")
        meta_box.append(path)
        card.append(meta_box)

        actions = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_top=6,
        )
        actions.set_hexpand(True)

        if self.on_set_current_theme is not None and not record.current:
            use_button = Gtk.Button(label="Use")
            use_button.set_sensitive(record.editable)
            use_button.set_tooltip_text("Set this theme as current")
            use_button.connect(
                "clicked",
                lambda *_args: self.on_set_current_theme(record),
            )
            actions.append(use_button)

        edit_button = Gtk.Button(label="Edit")
        edit_button.add_css_class("suggested-action")
        edit_button.set_hexpand(True)
        edit_button.set_sensitive(record.editable)
        edit_button.connect("clicked", lambda *_args: self.on_open_theme(record))
        actions.append(edit_button)

        more_button = Gtk.MenuButton()
        more_button.set_icon_name("view-more-symbolic")
        more_button.set_tooltip_text("More actions")
        more_button.set_popover(self.theme_actions_popover(record))
        actions.append(more_button)

        card.append(actions)
        return card

    ThemeGalleryPane._menu_action_button = menu_action_button
    ThemeGalleryPane.theme_actions_popover = theme_actions_popover
    ThemeGalleryPane.preview_widget = compact_preview_widget
    ThemeGalleryPane.theme_card = compact_theme_card


if _should_patch_theme_gallery():
    try:
        _install_theme_gallery_card_polish()
    except Exception as exc:
        print(
            f"[theme-gallery] could not install card polish: {exc}",
            file=sys.stderr,
            flush=True,
        )
