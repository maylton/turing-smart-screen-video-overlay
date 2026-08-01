#!/usr/bin/env python3
"""GTK selector for the AMD adapter used by Turing Smart Screen sensors."""

from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk

from library.gpu_selection import (
    GpuPreference,
    enumerate_amd_gpus,
    load_preference,
    save_preference,
)
from library.i18n import active_language

try:
    import pyamdgpuinfo
except Exception:
    pyamdgpuinfo = None


APP_ID = "io.github.turing.SmartScreen.GpuSelection"


_PT_BR = {
    "GPU Selection": "Seleção de GPU",
    "AMD sensor adapter": "Adaptador AMD dos sensores",
    "Choose which AMD GPU supplies load, temperature, VRAM, and clock metrics.": (
        "Escolha qual GPU AMD fornece carga, temperatura, VRAM e frequência."
    ),
    "Automatic — prefer the largest VRAM": "Automática — priorizar a maior VRAM",
    "No AMD adapters were detected by pyamdgpuinfo.": (
        "Nenhum adaptador AMD foi detectado pelo pyamdgpuinfo."
    ),
    "Save selection": "Salvar seleção",
    "Selection saved. Restart the monitor to apply it.": (
        "Seleção salva. Reinicie o monitor para aplicá-la."
    ),
    "The configured GPU is not currently available; automatic selection will be used.": (
        "A GPU configurada não está disponível; a seleção automática será usada."
    ),
}


def _(message: str) -> str:
    return _PT_BR.get(message, message) if active_language() == "pt_BR" else message


class GpuSelectionWindow(Adw.ApplicationWindow):
    def __init__(self, application: Adw.Application):
        super().__init__(
            application=application,
            title=_("GPU Selection"),
            default_width=620,
            default_height=360,
        )

        self.candidates = enumerate_amd_gpus(pyamdgpuinfo)
        self.preference = load_preference()

        toast_overlay = Adw.ToastOverlay()
        self.toast_overlay = toast_overlay
        self.set_content(toast_overlay)

        toolbar = Adw.ToolbarView()
        toast_overlay.set_child(toolbar)

        header = Adw.HeaderBar()
        header.set_title_widget(
            Adw.WindowTitle(
                title=_("GPU Selection"),
                subtitle=_("AMD sensor adapter"),
            )
        )
        toolbar.add_top_bar(header)

        clamp = Adw.Clamp(maximum_size=680, tightening_threshold=500)
        toolbar.set_content(clamp)

        page = Adw.PreferencesPage(
            margin_top=18,
            margin_bottom=24,
            margin_start=18,
            margin_end=18,
        )
        clamp.set_child(page)

        group = Adw.PreferencesGroup(
            title=_("AMD sensor adapter"),
            description=_(
                "Choose which AMD GPU supplies load, temperature, VRAM, and clock metrics."
            ),
        )
        page.add(group)

        labels = [_("Automatic — prefer the largest VRAM")]
        labels.extend(candidate.label for candidate in self.candidates)
        self.dropdown = Adw.ComboRow(
            title=_("AMD sensor adapter"),
            model=Gtk.StringList.new(labels),
        )
        group.add(self.dropdown)

        selected = 0
        if self.preference.mode == "index" and self.preference.amd_index is not None:
            for position, candidate in enumerate(self.candidates, start=1):
                if candidate.index == self.preference.amd_index:
                    selected = position
                    break
            else:
                warning = Adw.ActionRow(
                    title=_(
                        "The configured GPU is not currently available; automatic selection will be used."
                    )
                )
                warning.add_css_class("warning")
                group.add(warning)
        self.dropdown.set_selected(selected)

        if not self.candidates:
            self.dropdown.set_sensitive(False)
            group.add(
                Adw.ActionRow(
                    title=_("No AMD adapters were detected by pyamdgpuinfo.")
                )
            )

        save_button = Gtk.Button(
            label=_("Save selection"),
            margin_top=18,
            halign=Gtk.Align.END,
        )
        save_button.add_css_class("suggested-action")
        save_button.connect("clicked", self.on_save)
        page.add(save_button)

    def on_save(self, *_args) -> None:
        selected = int(self.dropdown.get_selected())
        if selected <= 0:
            preference = GpuPreference()
        else:
            candidate = self.candidates[selected - 1]
            preference = GpuPreference(mode="index", amd_index=candidate.index)
        save_preference(preference)
        self.toast_overlay.add_toast(
            Adw.Toast(
                title=_("Selection saved. Restart the monitor to apply it."),
                timeout=4,
            )
        )


class GpuSelectionApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_activate(self) -> None:
        window = self.props.active_window
        if window is None:
            window = GpuSelectionWindow(self)
        window.present()


def main() -> int:
    return GpuSelectionApp().run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
