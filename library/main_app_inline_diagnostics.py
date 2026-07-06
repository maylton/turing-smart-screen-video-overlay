# SPDX-License-Identifier: GPL-3.0-or-later
"""Inline Diagnostics page for the main GTK configuration app."""

from __future__ import annotations

import json
from typing import Any

import gi

gi.require_version("Pango", "1.0")
from gi.repository import Pango

from diagnostics import collect_diagnostics, render_text


def build_inline_diagnostics_page(app: Any, window: Any):
    """Build an embeddable diagnostics page for ``SmartScreenWindow.stack``."""
    Gtk = app.Gtk
    Adw = app.Adw
    Gdk = app.Gdk
    GLib = app.GLib

    class InlineDiagnosticsPage(Gtk.ScrolledWindow):
        def __init__(self):
            super().__init__()
            self.latest_text = ""
            self.latest_json = ""

            clamp = Adw.Clamp(maximum_size=980, tightening_threshold=760)
            self.set_child(clamp)

            content = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=18,
                margin_top=28,
                margin_bottom=30,
                margin_start=24,
                margin_end=24,
            )
            clamp.set_child(content)

            header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            header.set_hexpand(True)
            content.append(header)

            title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            title_box.set_hexpand(True)
            header.append(title_box)

            title = Gtk.Label(label="Diagnostics", xalign=0)
            title.add_css_class("title-1")
            title_box.append(title)

            subtitle = Gtk.Label(
                label=(
                    "Safe display, theme, runtime, and serial report. "
                    "This page does not open the display serial port."
                ),
                xalign=0,
                wrap=True,
            )
            subtitle.add_css_class("dim-label")
            title_box.append(subtitle)

            back_button = Gtk.Button(
                label="Back to Settings",
                icon_name="go-previous-symbolic",
                tooltip_text="Return to Settings",
            )
            back_button.connect("clicked", lambda *_: window.stack.set_visible_child_name("settings"))
            header.append(back_button)

            refresh_button = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Refresh diagnostics")
            refresh_button.connect("clicked", lambda *_: self.refresh_diagnostics())
            header.append(refresh_button)

            copy_button = Gtk.Button(icon_name="edit-copy-symbolic", tooltip_text="Copy diagnostics report")
            copy_button.connect("clicked", lambda *_: self.copy_report())
            header.append(copy_button)

            copy_json_button = Gtk.Button(label="JSON", tooltip_text="Copy diagnostics JSON")
            copy_json_button.connect("clicked", lambda *_: self.copy_json_report())
            header.append(copy_json_button)

            self.summary_grid = Gtk.Grid(column_spacing=14, row_spacing=14)
            self.summary_grid.set_column_homogeneous(True)
            self.summary_grid.set_hexpand(True)
            content.append(self.summary_grid)

            self.theme_card = self._summary_card("Theme", "applications-graphics-symbolic")
            self.video_card = self._summary_card("Video", "video-x-generic-symbolic")
            self.runtime_card = self._summary_card("Runtime", "media-playback-start-symbolic")
            self.serial_card = self._summary_card("Serial", "network-wired-symbolic")

            self.summary_grid.attach(self.theme_card["card"], 0, 0, 1, 1)
            self.summary_grid.attach(self.video_card["card"], 1, 0, 1, 1)
            self.summary_grid.attach(self.runtime_card["card"], 0, 1, 1, 1)
            self.summary_grid.attach(self.serial_card["card"], 1, 1, 1, 1)

            report_group = Adw.PreferencesGroup(
                title="Full report",
                description="Copy this report when filing bugs or comparing display states.",
            )
            content.append(report_group)

            report_frame = Gtk.Frame()
            report_frame.add_css_class("card")
            report_group.add(report_frame)

            report_scroll = Gtk.ScrolledWindow()
            report_scroll.set_min_content_height(360)
            report_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            report_frame.set_child(report_scroll)

            self.report_view = Gtk.TextView()
            self.report_view.set_editable(False)
            self.report_view.set_cursor_visible(False)
            self.report_view.set_monospace(True)
            self.report_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            self.report_view.set_top_margin(12)
            self.report_view.set_bottom_margin(12)
            self.report_view.set_left_margin(12)
            self.report_view.set_right_margin(12)
            report_scroll.set_child(self.report_view)

            GLib.idle_add(self.refresh_diagnostics)

        def _summary_card(self, title: str, icon_name: str) -> dict[str, Any]:
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            card.add_css_class("card")
            card.set_hexpand(True)
            card.set_size_request(-1, 108)

            inner = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=6,
                margin_top=12,
                margin_bottom=12,
                margin_start=16,
                margin_end=16,
            )
            card.append(inner)

            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.append(Gtk.Image.new_from_icon_name(icon_name))
            label = Gtk.Label(label=title, xalign=0)
            label.add_css_class("caption")
            label.add_css_class("dim-label")
            label.set_hexpand(True)
            row.append(label)
            inner.append(row)

            value = Gtk.Label(label="—", xalign=0)
            value.add_css_class("heading")
            value.set_ellipsize(Pango.EllipsizeMode.END)
            value.set_lines(1)
            inner.append(value)

            detail = Gtk.Label(label="", xalign=0)
            detail.add_css_class("caption")
            detail.add_css_class("dim-label")
            detail.set_ellipsize(Pango.EllipsizeMode.END)
            detail.set_lines(1)
            inner.append(detail)

            return {"card": card, "value": value, "detail": detail}

        def _set_card(self, card: dict[str, Any], value: str, detail: str) -> None:
            card["value"].set_label(value)
            card["detail"].set_label(detail)

        def refresh_diagnostics(self, *_args) -> bool:
            try:
                payload = collect_diagnostics()
                self.latest_text = render_text(payload)
                self.latest_json = json.dumps(payload, indent=2, sort_keys=True)
                self._render_payload(payload)
                self.report_view.get_buffer().set_text(self.latest_text)
                window.toast("Diagnostics refreshed")
            except Exception as exc:
                self.latest_text = f"Diagnostics failed: {exc}"
                self.latest_json = ""
                self.report_view.get_buffer().set_text(self.latest_text)
                window.toast(self.latest_text)
            return False

        def _render_payload(self, payload: dict[str, Any]) -> None:
            config = payload.get("config", {})
            theme = payload.get("theme", {})
            video = theme.get("video", {})
            runtime = payload.get("runtime", {})
            serial = payload.get("serial", {})

            theme_name = config.get("theme") or "No theme"
            theme_ok = bool(theme.get("directory_exists") and theme.get("yaml_exists"))
            preview_text = "preview OK" if theme.get("preview_exists") else "preview missing"
            self._set_card(self.theme_card, theme_name, f"{'OK' if theme_ok else 'Needs attention'} · {preview_text}")

            if video.get("configured"):
                video_value = "Configured"
                video_detail = "local file OK" if video.get("local_exists") else "local file missing"
            else:
                video_value = "Not configured"
                video_detail = str(video.get("reason") or "video block missing or disabled")
            self._set_card(self.video_card, video_value, video_detail)

            running = bool(runtime.get("monitor_running"))
            pids = runtime.get("monitor_pids") or []
            self._set_card(
                self.runtime_card,
                "Running" if running else "Stopped",
                "PID " + ", ".join(map(str, pids)) if pids else "No monitor process detected",
            )

            real = serial.get("real_tty_acm") or []
            usb_monitor = serial.get("usb_monitor") or []
            if real:
                serial_value = ", ".join(real)
            elif usb_monitor:
                serial_value = "UsbMonitor only"
            else:
                serial_value = "No ttyACM display"
            self._set_card(
                self.serial_card,
                serial_value,
                f"UsbMonitor: {', '.join(usb_monitor) if usb_monitor else 'none'}",
            )

        def _copy_to_clipboard(self, text: str, message: str) -> None:
            display = Gdk.Display.get_default()
            if display is None:
                window.toast("Clipboard is not available")
                return
            display.get_clipboard().set(text)
            window.toast(message)

        def copy_report(self, *_args) -> None:
            if not self.latest_text:
                self.refresh_diagnostics()
            self._copy_to_clipboard(self.latest_text, "Diagnostics copied")

        def copy_json_report(self, *_args) -> None:
            if not self.latest_json:
                self.refresh_diagnostics()
            self._copy_to_clipboard(self.latest_json, "Diagnostics JSON copied")

    return InlineDiagnosticsPage()
