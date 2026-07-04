# SPDX-License-Identifier: GPL-3.0-or-later
"""Embedded Video Manager surface for the main GTK application."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk


class EmbeddedVideoManagerPage(Gtk.Box):
    """Host the existing VideoManagerWindow content inside the main app stack."""

    def __init__(
        self,
        *,
        root: Path,
        application: Adw.Application,
        on_back: Callable[[], None],
        on_open_external: Callable[[], None],
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.root = root
        self.application = application
        self.on_back = on_back
        self.on_open_external = on_open_external
        self._launcher_module = None
        self._video_module = None
        self._video_window = None
        self._embedded_content = None

        header = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_top=12,
            margin_bottom=12,
            margin_start=18,
            margin_end=18,
        )
        header.add_css_class("toolbar")
        self.append(header)

        back_button = Gtk.Button(
            label="Overview",
            icon_name="go-previous-symbolic",
            tooltip_text="Back to Overview",
            valign=Gtk.Align.CENTER,
        )
        back_button.connect("clicked", lambda *_: self.on_back())
        header.append(back_button)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title_box.set_hexpand(True)
        title = Gtk.Label(label="Video Manager", xalign=0)
        title.add_css_class("title-2")
        subtitle = Gtk.Label(
            label="Manage videos from the main app window.",
            xalign=0,
        )
        subtitle.add_css_class("dim-label")
        title_box.append(title)
        title_box.append(subtitle)
        header.append(title_box)

        external_button = Gtk.Button(
            label="Open separate window",
            icon_name="window-new-symbolic",
            tooltip_text="Open the standalone GTK Video Manager",
            valign=Gtk.Align.CENTER,
        )
        external_button.connect("clicked", lambda *_: self.on_open_external())
        header.append(external_button)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.append(separator)

        self.video_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.video_container.set_hexpand(True)
        self.video_container.set_vexpand(True)
        self.append(self.video_container)
        self.show_empty_state()

    def clear_video_container(self) -> None:
        child = self.video_container.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.video_container.remove(child)
            child = next_child

    def show_empty_state(self, message: str | None = None) -> None:
        self.clear_video_container()
        empty = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            margin_top=80,
            margin_bottom=80,
            margin_start=80,
            margin_end=80,
        )
        empty.set_vexpand(True)
        icon = Gtk.Image.new_from_icon_name("video-x-generic-symbolic")
        icon.set_pixel_size(64)
        empty.append(icon)

        title = Gtk.Label(label="Video Manager is not open")
        title.add_css_class("title-2")
        empty.append(title)

        subtitle = Gtk.Label(
            label=message or "Use a Video Manager action to load this page.",
            wrap=True,
            justify=Gtk.Justification.CENTER,
        )
        subtitle.add_css_class("dim-label")
        empty.append(subtitle)
        self.video_container.append(empty)

    def load_launcher_module(self):
        if self._launcher_module is not None:
            return self._launcher_module

        launcher_file = self.root / "video-manager-gtk.py"
        spec = importlib.util.spec_from_file_location(
            "turing_smart_screen_embedded_video_manager_launcher",
            launcher_file,
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not load {launcher_file.name}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        self._launcher_module = module
        return module

    def load_video_module(self):
        if self._video_module is not None:
            return self._video_module

        launcher = self.load_launcher_module()
        module = launcher.load_app_module()
        launcher.install_structured_backend(module)
        self._video_module = module
        return module

    def open_manager(self) -> None:
        if self._embedded_content is not None:
            return

        module = self.load_video_module()
        video_window = module.VideoManagerWindow(self.application)

        if hasattr(video_window, "get_content"):
            content = video_window.get_content()
            video_window.set_content(None)
        else:
            content = video_window.get_child()
            video_window.set_child(None)

        if content is None:
            raise RuntimeError("Video Manager did not expose embeddable content.")

        self.clear_video_container()
        self._video_window = video_window
        self._embedded_content = content
        self.video_container.append(content)

    def refresh(self) -> None:
        window = self._video_window
        if window is not None and hasattr(window, "refresh_videos"):
            window.refresh_videos()
