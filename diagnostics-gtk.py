#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""GTK diagnostics viewer for the Linux Turing Smart Screen app."""

from __future__ import annotations

import json
import sys
from typing import Any

try:
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    gi.require_version("Gdk", "4.0")
    gi.require_version("Pango", "1.0")
    from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango
except Exception as exc:  # pragma: no cover - startup guard
    print(
        "GTK4/Libadwaita could not be imported.\n"
        "On Arch/CachyOS install: sudo pacman -S python-gobject gtk4 libadwaita\n"
        f"\nDetails: {exc}",
        file=sys.stderr,
    )
    raise SystemExit(1)

from diagnostics import collect_diagnostics, render_text


APP_ID = "io.github.turing.SmartScreen.Diagnostics"


def _status_text(ok: bool, good: str = "OK", bad: str = "Needs attention") -> str:
    return good if ok else bad


class DiagnosticsWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(
            application=app,
            title="Turing Smart Screen Diagnostics",
            default_width=1040,
            default_height=760,
        )
        self.set_size_request(820, 560)
        self.latest_text = ""
        self.latest_json = ""

        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        toolbar = Adw.ToolbarView()
        self.toast_overlay.set_child(toolbar)

        header = Adw.HeaderBar()
        header.set_title_widget(
            Adw.WindowTitle(
                title="Diagnostics",
                subtitle="Safe display, theme, runtime, and serial report",
            )
        )
        toolbar.add_top_bar(header)

        refresh_button = Gtk.Button(
            icon_name="view-refresh-symbolic",
            tooltip_text="Refresh diagnostics",
        )
        refresh_button.connect("clicked", lambda *_: self.refresh_diagnostics())
        header.pack_end(refresh_button)

        copy_button = Gtk.Button(
            icon_name="edit-copy-symbolic",
            tooltip_text="Copy text diagnostics report",
        )
        copy_button.connect("clicked", lambda *_: self.copy_report())
        header.pack_end(copy_button)

        copy_json_button = Gtk.Button(
            label="JSON",
            tooltip_text="Copy machine-readable diagnostics JSON",
        )
        copy_json_button.connect("clicked", lambda *_: self.copy_json_report())
        header.pack_end(copy_json_button)

        scrolled = Gtk.ScrolledWindow()
        toolbar.set_content(scrolled)

        clamp = Adw.Clamp(maximum_size=1000, tightening_threshold=760)
        scrolled.set_child(clamp)

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=18,
            margin_top=24,
            margin_bottom=28,
            margin_start=28,
            margin_end=28,
        )
        content.set_vexpand(True)
        clamp.set_child(content)

        intro = Gtk.Label(
            label=(
                "This page reads configuration, theme metadata, monitor process "
                "state, and USB descriptors without opening the display serial port."
            ),
            xalign=0,
            wrap=True,
        )
        intro.add_css_class("dim-label")
        content.append(intro)

        self.summary_grid = Gtk.Grid(column_spacing=14, row_spacing=14)
        self.summary_grid.set_column_homogeneous(True)
        self.summary_grid.set_hexpand(True)
        content.append(self.summary_grid)

        self.lifecycle_card = self._summary_card("Display", "video-display-symbolic")
        self.theme_card = self._summary_card("Theme", "applications-graphics-symbolic")
        self.video_card = self._summary_card("Video", "video-x-generic-symbolic")
        self.runtime_card = self._summary_card("Runtime", "media-playback-start-symbolic")
        self.serial_card = self._summary_card("Serial", "network-wired-symbolic")

        self.summary_grid.attach(self.lifecycle_card["card"], 0, 0, 2, 1)
        self.summary_grid.attach(self.theme_card["card"], 0, 1, 1, 1)
        self.summary_grid.attach(self.video_card["card"], 1, 1, 1, 1)
        self.summary_grid.attach(self.runtime_card["card"], 0, 2, 1, 1)
        self.summary_grid.attach(self.serial_card["card"], 1, 2, 1, 1)

        report_group = Adw.PreferencesGroup(
            title="Full report",
            description="Copy this report when filing bugs or comparing display states.",
        )
        report_group.set_vexpand(True)
        content.append(report_group)

        report_frame = Gtk.Frame()
        report_frame.add_css_class("card")
        report_frame.set_vexpand(True)
        report_group.add(report_frame)

        report_scroll = Gtk.ScrolledWindow()
        report_scroll.set_min_content_height(360)
        report_scroll.set_vexpand(True)
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

    def _summary_card(self, title: str, icon_name: str) -> dict[str, Gtk.Widget]:
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
        inner.set_hexpand(True)
        card.append(inner)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.set_hexpand(True)
        icon = Gtk.Image.new_from_icon_name(icon_name)
        header.append(icon)

        title_label = Gtk.Label(label=title, xalign=0)
        title_label.add_css_class("caption")
        title_label.add_css_class("dim-label")
        title_label.set_hexpand(True)
        header.append(title_label)
        inner.append(header)

        value = Gtk.Label(label="—", xalign=0, wrap=True)
        value.add_css_class("heading")
        value.set_ellipsize(Pango.EllipsizeMode.END)
        value.set_lines(1)
        inner.append(value)

        detail = Gtk.Label(label="", xalign=0, wrap=True)
        detail.add_css_class("caption")
        detail.add_css_class("dim-label")
        detail.set_ellipsize(Pango.EllipsizeMode.END)
        detail.set_lines(1)
        inner.append(detail)

        return {"card": card, "value": value, "detail": detail}

    def _set_card(self, card: dict[str, Gtk.Widget], value: str, detail: str) -> None:
        card["value"].set_label(value)
        card["detail"].set_label(detail)

    def refresh_diagnostics(self, *_args) -> bool:
        try:
            payload = collect_diagnostics()
            self.latest_text = render_text(payload)
            self.latest_json = json.dumps(payload, indent=2, sort_keys=True)
            self._render_payload(payload)
            self.report_view.get_buffer().set_text(self.latest_text)
            self.toast("Diagnostics refreshed")
        except Exception as exc:
            self.latest_text = f"Diagnostics failed: {exc}"
            self.latest_json = ""
            self.report_view.get_buffer().set_text(self.latest_text)
            self.toast(self.latest_text)
        return False

    def _render_payload(self, payload: dict[str, Any]) -> None:
        config = payload.get("config", {})
        theme = payload.get("theme", {})
        video = theme.get("video", {})
        runtime = payload.get("runtime", {})
        serial = payload.get("serial", {})
        lifecycle = payload.get("display_lifecycle", {})

        lifecycle_label = str(lifecycle.get("label") or "Display: unknown")
        if lifecycle_label.casefold().startswith("display:"):
            lifecycle_label = lifecycle_label.split(":", 1)[1].strip().capitalize()
        self._set_card(
            self.lifecycle_card,
            lifecycle_label or str(lifecycle.get("state") or "Unknown"),
            str(lifecycle.get("details") or "No lifecycle details available"),
        )

        theme_name = config.get("theme") or "No theme"
        theme_ok = bool(theme.get("directory_exists") and theme.get("yaml_exists"))
        preview_text = "preview OK" if theme.get("preview_exists") else "preview missing"
        self._set_card(
            self.theme_card,
            theme_name,
            f"{_status_text(theme_ok)} · {preview_text}",
        )

        if video.get("configured"):
            value = "Configured"
            detail = "local file OK" if video.get("local_exists") else "local file missing"
        else:
            value = "Not configured"
            detail = str(video.get("reason") or "video block missing or disabled")
        self._set_card(self.video_card, value, detail)

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

    def copy_to_clipboard(self, text: str, message: str) -> None:
        display = Gdk.Display.get_default()
        if display is None:
            self.toast("Clipboard is not available")
            return
        display.get_clipboard().set(text)
        self.toast(message)

    def copy_report(self, *_args) -> None:
        if not self.latest_text:
            self.refresh_diagnostics()
        self.copy_to_clipboard(self.latest_text, "Diagnostics copied")

    def copy_json_report(self, *_args) -> None:
        if not self.latest_json:
            self.refresh_diagnostics()
        self.copy_to_clipboard(self.latest_json, "Diagnostics JSON copied")

    def toast(self, message: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast(title=message, timeout=3))


class DiagnosticsApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_activate(self):
        window = self.props.active_window
        if window is None:
            window = DiagnosticsWindow(self)
        window.present()


def main() -> int:
    app = DiagnosticsApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
