# SPDX-License-Identifier: GPL-3.0-or-later
"""Inline Diagnostics page for the main GTK configuration app."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import gi

gi.require_version("Pango", "1.0")
from gi.repository import Pango

from diagnostics import collect_diagnostics, render_text
from library.diagnostics_gtk_i18n import status_text, t as _, tr


ROOT = Path(__file__).resolve().parents[1]
GPU_SELECTOR = ROOT / "gpu-selection-gtk.py"


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

            title = Gtk.Label(label=_("Diagnostics"), xalign=0)
            title.add_css_class("title-1")
            title_box.append(title)

            subtitle = Gtk.Label(
                label=_(
                    "Safe display, theme, runtime, and serial report. "
                    "This page does not open the display serial port."
                ),
                xalign=0,
                wrap=True,
            )
            subtitle.add_css_class("dim-label")
            title_box.append(subtitle)

            back_button = Gtk.Button(
                label=_("Back to Settings"),
                icon_name="go-previous-symbolic",
                tooltip_text=_("Return to Settings"),
            )
            back_button.connect(
                "clicked",
                lambda *_: window.stack.set_visible_child_name("settings"),
            )
            header.append(back_button)

            gpu_button = Gtk.Button(
                label="GPU",
                tooltip_text=_("Configure GPU"),
            )
            gpu_button.connect("clicked", self.open_gpu_selector)
            header.append(gpu_button)

            refresh_button = Gtk.Button(
                icon_name="view-refresh-symbolic",
                tooltip_text=_("Refresh diagnostics"),
            )
            refresh_button.connect("clicked", lambda *_: self.refresh_diagnostics())
            header.append(refresh_button)

            copy_button = Gtk.Button(
                icon_name="edit-copy-symbolic",
                tooltip_text=_("Copy diagnostics report"),
            )
            copy_button.connect("clicked", lambda *_: self.copy_report())
            header.append(copy_button)

            copy_json_button = Gtk.Button(
                label="JSON",
                tooltip_text=_("Copy diagnostics JSON"),
            )
            copy_json_button.connect("clicked", lambda *_: self.copy_json_report())
            header.append(copy_json_button)

            self.summary_grid = Gtk.Grid(column_spacing=14, row_spacing=14)
            self.summary_grid.set_column_homogeneous(True)
            self.summary_grid.set_hexpand(True)
            content.append(self.summary_grid)

            self.lifecycle_card = self._summary_card(
                _("Display state"),
                "video-display-symbolic",
            )
            self.gpu_card = self._summary_card(_("GPU sensors"), "video-card-symbolic")
            self.theme_card = self._summary_card(_("Theme"), "applications-graphics-symbolic")
            self.video_card = self._summary_card(_("Video"), "video-x-generic-symbolic")
            self.runtime_card = self._summary_card(_("Runtime"), "media-playback-start-symbolic")
            self.serial_card = self._summary_card(_("Serial"), "network-wired-symbolic")

            self.summary_grid.attach(self.lifecycle_card["card"], 0, 0, 2, 1)
            self.summary_grid.attach(self.gpu_card["card"], 0, 1, 2, 1)
            self.summary_grid.attach(self.theme_card["card"], 0, 2, 1, 1)
            self.summary_grid.attach(self.video_card["card"], 1, 2, 1, 1)
            self.summary_grid.attach(self.runtime_card["card"], 0, 3, 1, 1)
            self.summary_grid.attach(self.serial_card["card"], 1, 3, 1, 1)

            report_group = Adw.PreferencesGroup(
                title=_("Full report"),
                description=_(
                    "Copy this report when filing bugs or comparing display states."
                ),
            )
            content.append(report_group)

            report_frame = Gtk.Frame()
            report_frame.add_css_class("card")
            report_group.add(report_frame)

            report_scroll = Gtk.ScrolledWindow()
            report_scroll.set_min_content_height(320)
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
            icon = Gtk.Image.new_from_icon_name(icon_name)
            row.append(icon)
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

            detail = Gtk.Label(label="", xalign=0, wrap=True)
            detail.add_css_class("caption")
            detail.add_css_class("dim-label")
            detail.set_ellipsize(Pango.EllipsizeMode.END)
            detail.set_lines(2)
            inner.append(detail)

            return {"card": card, "value": value, "detail": detail}

        def _set_card(self, card: dict[str, Any], value: str, detail: str) -> None:
            card["value"].set_label(value)
            card["detail"].set_label(detail)

        def open_gpu_selector(self, *_args) -> None:
            if not GPU_SELECTOR.is_file():
                window.toast(_("GPU selector was not found"))
                return
            python = app.project_python() if hasattr(app, "project_python") else sys.executable
            try:
                subprocess.Popen([python, str(GPU_SELECTOR)], cwd=str(ROOT))
            except Exception as exc:
                window.toast(tr("Could not open GPU selector: {error}", error=exc))

        def refresh_diagnostics(self, *_args) -> bool:
            try:
                payload = collect_diagnostics()
                self.latest_text = render_text(payload)
                self.latest_json = json.dumps(payload, indent=2, sort_keys=True)
                self._render_payload(payload)
                self.report_view.get_buffer().set_text(self.latest_text)
                window.toast(_("Diagnostics refreshed"))
            except Exception as exc:
                self.latest_text = tr("Diagnostics failed: {error}", error=exc)
                self.latest_json = ""
                self.report_view.get_buffer().set_text(self.latest_text)
                window.toast(self.latest_text)
            return False

        def _lifecycle_value(self, state: str) -> str:
            labels = {
                "running": _("Running"),
                "busy": _("Busy"),
                "tty_ready": _("Ready"),
                "usbmonitor_waking": _("Starting"),
                "disconnected": _("Disconnected"),
                "unknown": _("Unknown"),
            }
            return labels.get(str(state or "unknown"), _("Unknown"))

        def _render_payload(self, payload: dict[str, Any]) -> None:
            config = payload.get("config", {})
            theme = payload.get("theme", {})
            video = theme.get("video", {})
            lifecycle = payload.get("display_lifecycle", {})
            gpu = payload.get("gpu", {})
            runtime = payload.get("runtime", {})
            serial = payload.get("serial", {})

            lifecycle_detail = _(str(lifecycle.get("detail") or ""))
            devices = lifecycle.get("devices") or []
            owners = lifecycle.get("owner_pids") or []
            detail_parts = [lifecycle_detail] if lifecycle_detail else []
            if devices:
                detail_parts.append(
                    tr("Device(s): {devices}", devices=", ".join(devices))
                )
            if owners:
                detail_parts.append(
                    tr("Owner PID(s): {pids}", pids=", ".join(map(str, owners)))
                )
            self._set_card(
                self.lifecycle_card,
                self._lifecycle_value(str(lifecycle.get("state") or "unknown")),
                " · ".join(detail_parts),
            )

            preference = gpu.get("preference") or {}
            selected_label = str(gpu.get("selected_label") or _("No AMD GPU detected"))
            if preference.get("mode") == "index":
                gpu_detail = tr("Index {index}", index=preference.get("amd_index"))
            else:
                gpu_detail = _("Automatic selection")
            metrics = gpu.get("metrics") or {}
            load = metrics.get("load_percent")
            temperature = metrics.get("temperature_c")
            if load is not None or temperature is not None:
                gpu_detail += " · " + tr(
                    "Load {load}% · {temperature} °C",
                    load="—" if load is None else f"{float(load):.0f}",
                    temperature="—" if temperature is None else f"{float(temperature):.0f}",
                )
            self._set_card(self.gpu_card, selected_label, gpu_detail)

            theme_name = config.get("theme") or _("No theme")
            theme_ok = bool(theme.get("directory_exists") and theme.get("yaml_exists"))
            preview_text = _("preview OK") if theme.get("preview_exists") else _("preview missing")
            self._set_card(
                self.theme_card,
                theme_name,
                f"{status_text(theme_ok)} · {preview_text}",
            )

            if video.get("configured"):
                video_value = _("Configured")
                video_detail = _("local file OK") if video.get("local_exists") else _("local file missing")
            else:
                video_value = _("Not configured")
                video_detail = str(video.get("reason") or _("video block missing or disabled"))
            self._set_card(self.video_card, video_value, video_detail)

            running = bool(runtime.get("monitor_running"))
            pids = runtime.get("monitor_pids") or []
            self._set_card(
                self.runtime_card,
                _("Running") if running else _("Stopped"),
                tr("PID {pids}", pids=", ".join(map(str, pids)))
                if pids else _("No monitor process detected"),
            )

            real = serial.get("real_tty_acm") or []
            usb_monitor = serial.get("usb_monitor") or []
            if real:
                serial_value = ", ".join(real)
            elif usb_monitor:
                serial_value = _("UsbMonitor only")
            else:
                serial_value = _("No ttyACM display")
            self._set_card(
                self.serial_card,
                serial_value,
                tr(
                    "UsbMonitor: {devices}",
                    devices=", ".join(usb_monitor) if usb_monitor else _("none"),
                ),
            )

        def _copy_to_clipboard(self, text: str, message: str) -> None:
            display = Gdk.Display.get_default()
            if display is None:
                window.toast(_("Clipboard is not available"))
                return
            display.get_clipboard().set(text)
            window.toast(message)

        def copy_report(self, *_args) -> None:
            if not self.latest_text:
                self.refresh_diagnostics()
            self._copy_to_clipboard(self.latest_text, _("Diagnostics copied"))

        def copy_json_report(self, *_args) -> None:
            if not self.latest_json:
                self.refresh_diagnostics()
            self._copy_to_clipboard(self.latest_json, _("Diagnostics JSON copied"))

    return InlineDiagnosticsPage()
