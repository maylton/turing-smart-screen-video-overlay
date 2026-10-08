#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
GTK4 + Libadwaita configuration shell for turing-smart-screen-python.

Linux-first home screen that launches the theme editor, video manager and the
main monitor process.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
from pathlib import Path

from library.runtime_python import resolve_project_python

try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Adw, Gdk, Gio, GLib, Gtk
except Exception as exc:
    print(
        "GTK4/Libadwaita could not be imported.\n"
        "On Arch/CachyOS install: sudo pacman -S python-gobject gtk4 libadwaita\n"
        f"\nDetails: {exc}",
        file=sys.stderr,
    )
    raise SystemExit(1)

APP_ID = "io.github.turing.SmartScreen"
APP_NAME = "Turing Smart Screen"
TRAY_OBJECT_PATH = "/StatusNotifierItem"
DBUSMENU_OBJECT_PATH = "/StatusNotifierItem/Menu"
ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "config.yaml"
THEMES_DIR = ROOT / "res" / "themes"
ICON_FILE = ROOT / "res" / "icons" / "monitor-icon-17865" / "64.png"
THEME_EDITOR = ROOT / "theme-editor-gtk.py"
VIDEO_MANAGER = ROOT / "video-manager-gtk.py"
MAIN_PROGRAM = ROOT / "main.py"
SCREEN_CONTROL = ROOT / "screen-control.py"
GTK_CHECKUP = ROOT / "gtk-checkup.py"
DISPLAY_DETECTION = ROOT / "display-detection.py"
UI_SETTINGS_DIR = Path.home() / ".config" / "turing-smart-screen"
UI_SETTINGS_FILE = UI_SETTINGS_DIR / "ui-settings.conf"
START_MINIMIZED_FILE = UI_SETTINGS_DIR / "start-minimized.conf"



def load_saved_color_scheme() -> str:
    try:
        value = UI_SETTINGS_FILE.read_text(encoding="utf-8").strip().lower()
    except OSError:
        return "system"
    return value if value in {"system", "light", "dark"} else "system"


def save_color_scheme(value: str) -> None:
    UI_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    temporary = UI_SETTINGS_FILE.with_suffix(".tmp")
    temporary.write_text(value + "\n", encoding="utf-8")
    os.replace(temporary, UI_SETTINGS_FILE)



def load_start_minimized() -> bool:
    try:
        value = START_MINIMIZED_FILE.read_text(
            encoding="utf-8"
        ).strip().lower()
    except OSError:
        return False
    return value in {"1", "true", "yes", "on"}


def save_start_minimized(enabled: bool) -> None:
    UI_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    temporary = START_MINIMIZED_FILE.with_suffix(".tmp")
    temporary.write_text(
        "true\n" if enabled else "false\n",
        encoding="utf-8",
    )
    os.replace(temporary, START_MINIMIZED_FILE)


def apply_color_scheme(value: str) -> None:
    schemes = {
        "system": Adw.ColorScheme.DEFAULT,
        "light": Adw.ColorScheme.FORCE_LIGHT,
        "dark": Adw.ColorScheme.FORCE_DARK,
    }

    requested = schemes.get(value, Adw.ColorScheme.DEFAULT)
    Adw.StyleManager.get_default().set_color_scheme(requested)

    display = Gdk.Display.get_default()
    if display is not None:
        Adw.StyleManager.get_for_display(display).set_color_scheme(requested)


def project_python() -> str:
    """Return the dependency-complete interpreter for project subprocesses."""
    return resolve_project_python(ROOT)


def read_current_theme() -> str:
    if not CONFIG_FILE.is_file():
        return ""
    content = CONFIG_FILE.read_text(encoding="utf-8")
    try:
        import yaml

        payload = yaml.safe_load(content) or {}
        renderer = payload.get("renderer", {})
        if isinstance(renderer, dict):
            engine = str(renderer.get("engine") or "yaml").strip().lower()
            theme = str(renderer.get("theme") or "").strip()
            if engine == "html" and theme:
                return theme
    except Exception:
        # Preserve the long-standing text fallback when the optional YAML
        # parser cannot load a hand-edited config file.
        pass
    match = re.search(r"(?m)^\s*THEME\s*:\s*[\"']?([^\"'\n#]+)", content)
    return match.group(1).strip() if match else ""


def write_current_theme(theme_name: str) -> None:
    """Update only config.THEME while preserving the existing YAML formatting."""
    if not CONFIG_FILE.is_file():
        raise FileNotFoundError(CONFIG_FILE)

    content = CONFIG_FILE.read_text(encoding="utf-8")
    pattern = re.compile(r"(?m)^(\s*THEME\s*:\s*).*$")

    if not pattern.search(content):
        raise RuntimeError("Could not find config.THEME in config.yaml")

    updated = pattern.sub(
        lambda match: f'{match.group(1)}"{theme_name}"',
        content,
        count=1,
    )

    temporary = CONFIG_FILE.with_suffix(".yaml.gtk.tmp")
    temporary.write_text(updated, encoding="utf-8")
    os.replace(temporary, CONFIG_FILE)



def normalize_display_size(value: str) -> str:
    """Normalize values such as 2.1, 2.1", 2,1 inch, and 5-inch."""
    value = str(value or "").strip().lower().replace(",", ".")
    match = re.search(r"(\d+(?:\.\d+)?)", value)
    return match.group(1) if match else ""


def read_scalar_from_yaml_text(path: Path, key: str) -> str:
    """Read a simple YAML scalar without requiring ruamel in system Python."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return ""

    pattern = re.compile(
        rf'(?m)^\s*{re.escape(key)}\s*:\s*[\"\']?([^\"\'\n#]+)'
    )
    match = pattern.search(content)
    return match.group(1).strip() if match else ""


def theme_yaml_path(theme_name: str) -> Path | None:
    theme_dir = THEMES_DIR / theme_name
    for filename in ("theme.yaml", "theme.yml"):
        candidate = theme_dir / filename
        if candidate.is_file():
            return candidate
    return None


def theme_display_size(theme_name: str) -> str:
    path = theme_yaml_path(theme_name)
    if path is None:
        return ""
    return normalize_display_size(
        read_scalar_from_yaml_text(path, "DISPLAY_SIZE")
    )


def selected_display_size() -> str:
    """
    Prefer the configured display size. Older config files may not contain
    DISPLAY_SIZE, so fall back to the currently active theme metadata.
    """
    for key in ("DISPLAY_SIZE", "SCREEN_SIZE", "SIZE"):
        value = normalize_display_size(
            read_scalar_from_yaml_text(CONFIG_FILE, key)
        )
        if value:
            return value

    current = read_current_theme()
    if current:
        return theme_display_size(current)

    return ""


def compatible_themes() -> tuple[list[str], str]:
    all_themes = available_themes()
    display_size = selected_display_size()

    if not display_size:
        return all_themes, ""

    matches = [
        name for name in all_themes
        if theme_display_size(name) == display_size
    ]
    return matches, display_size


def sanitize_theme_folder_name(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-._")
    return value


def available_themes() -> list[str]:
    """Return all immediate theme folders containing theme.yaml or theme.yml."""
    if not THEMES_DIR.exists():
        return []

    themes = []
    try:
        for path in THEMES_DIR.iterdir():
            if not path.is_dir():
                continue
            if (path / "theme.yaml").is_file() or (path / "theme.yml").is_file():
                themes.append(path.name)
    except OSError:
        return []

    return sorted(themes, key=str.casefold)


def theme_preview_path(theme_name: str) -> Path | None:
    theme_dir = THEMES_DIR / theme_name

    # These are auxiliary/editor media, not final theme previews.
    ignored_filenames = {
        "video-preview.png",
        "video_preview.png",
        "preview-background.png",
        "preview_background.png",
    }

    preferred = (
        theme_dir / "preview.png",
        theme_dir / "background.png",
    )
    for path in preferred:
        if path.is_file() and path.name.casefold() not in ignored_filenames:
            return path

    for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        matches = sorted(
            candidate
            for candidate in theme_dir.glob(pattern)
            if candidate.name.casefold() not in ignored_filenames
            and not candidate.name.startswith(".")
        )
        if matches:
            return matches[0]
    return None


class ThemeListRow(Gtk.ListBoxRow):
    def __init__(self, theme_name: str, active: bool = False):
        super().__init__()
        self.theme_name = theme_name

        row = Adw.ActionRow(
            title=theme_name,
            subtitle="Active theme" if active else "",
            icon_name="applications-graphics-symbolic",
        )
        row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
        self.set_child(row)


class SidebarRow(Gtk.ListBoxRow):
    def __init__(self, page_name: str, icon_name: str, title: str):
        super().__init__()
        self.page_name = page_name

        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_top=9,
            margin_bottom=9,
            margin_start=12,
            margin_end=12,
        )

        icon = Gtk.Image.new_from_icon_name(icon_name)
        label = Gtk.Label(label=title, xalign=0)
        label.set_hexpand(True)

        box.append(icon)
        box.append(label)
        self.set_child(box)


class SmartScreenWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(
            application=app,
            title="Turing Smart Screen",
            default_width=1280,
            default_height=780,
        )
        self.set_size_request(1020, 640)
        self.connect("close-request", self.on_close_request)

        self.current_theme = read_current_theme()
        self.monitor_process: subprocess.Popen | None = None
        self.saved_color_scheme = load_saved_color_scheme()
        self.detection_running = False
        apply_color_scheme(self.saved_color_scheme)

        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        toolbar_view = Adw.ToolbarView()
        self.toast_overlay.set_child(toolbar_view)

        header = Adw.HeaderBar()
        header.set_title_widget(
            Adw.WindowTitle(
                title="Turing Smart Screen",
                subtitle="Linux configuration center",
            )
        )
        toolbar_view.add_top_bar(header)

        menu = Gio.Menu()
        menu.append("About", "app.about")
        menu_button = Gtk.MenuButton(
            icon_name="open-menu-symbolic",
            menu_model=menu,
            tooltip_text="Main menu",
        )
        header.pack_end(menu_button)

        split = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        split.set_position(280)
        split.set_shrink_start_child(False)
        split.set_shrink_end_child(False)
        toolbar_view.set_content(split)

        sidebar = self.build_sidebar()
        split.set_start_child(sidebar)

        self.stack = Adw.ViewStack()
        self.stack.set_vexpand(True)
        self.stack.set_hexpand(True)
        split.set_end_child(self.stack)

        self.stack.add_named(self.build_overview_page(), "overview")
        self.stack.add_named(self.build_themes_page(), "themes")
        self.stack.add_named(self.build_settings_page(), "settings")

        self.sidebar.select_row(self.sidebar.get_row_at_index(0))
        self.refresh_overview()

        self.install_actions()
        GLib.idle_add(self.refresh_all)

        # Apply the theme stored in config.yaml automatically when the app
        # opens. This makes the application suitable for desktop autostart.
        GLib.timeout_add(220, self.auto_detect_display)
        GLib.timeout_add(1800, self.auto_apply_last_theme)

    def install_actions(self):
        actions = {
            "open-editor": self.open_theme_editor,
            "open-videos": self.open_video_manager,
            "start-monitor": self.start_monitor,
            "stop-monitor": self.stop_monitor,
            "turn-off-display": self.turn_off_display,
            "refresh": lambda *_: self.refresh_all(),
            "detect-display": self.detect_display,
        }

        for name, callback in actions.items():
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

    def auto_detect_display(self):
        self.detect_display()
        return False

    def detect_display(self, *_args):
        if self.detection_running:
            return
        self.detection_running = True
        self.detection_status_row.set_subtitle("Scanning USB and serial descriptors…")

        def worker():
            try:
                result = subprocess.run(
                    [project_python(), str(DISPLAY_DETECTION), "--json", "apply"],
                    cwd=str(ROOT),
                    text=True,
                    capture_output=True,
                    check=False,
                )
                import json
                payload = json.loads((result.stdout or "").strip())
                GLib.idle_add(
                    self.finish_display_detection,
                    result.returncode,
                    payload,
                    result.stderr,
                )
            except Exception as exc:
                GLib.idle_add(self.finish_display_detection, 1, None, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def finish_display_detection(self, code, payload, stderr):
        self.detection_running = False
        if code or not isinstance(payload, dict) or not payload.get("ok"):
            error = (payload or {}).get("error", {}) if isinstance(payload, dict) else {}
            message = error.get("message") or (stderr or "Detection failed").strip()
            self.detection_status_row.set_subtitle(message)
            return False

        data = payload.get("data") or {}
        selected = data.get("selected") or {}
        subtitle = (
            f"{selected.get('label', '')} · {selected.get('device') or ''}"
        ).strip(" ·")
        self.detection_status_row.set_subtitle(
            subtitle or data.get("message", "Detection completed")
        )
        self.current_theme = read_current_theme()
        self.refresh_all()
        self.toast_overlay.add_toast(
            Adw.Toast(title=data.get("message", "Detection completed"), timeout=4)
        )
        return False

    def build_sidebar(self) -> Gtk.Widget:
        wrap = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )
        wrap.add_css_class("navigation-sidebar")

        title = Gtk.Label(
            label="Navigation",
            xalign=0,
            margin_top=18,
            margin_bottom=8,
            margin_start=18,
            margin_end=18,
        )
        title.add_css_class("heading")
        wrap.append(title)

        self.sidebar = Gtk.ListBox(
            selection_mode=Gtk.SelectionMode.SINGLE,
        )
        self.sidebar.add_css_class("navigation-sidebar")
        self.sidebar.connect("row-selected", self.on_sidebar_selected)

        rows = (
            ("overview", "view-grid-symbolic", "Overview"),
            ("themes", "applications-graphics-symbolic", "Themes"),
            ("settings", "preferences-system-symbolic", "Settings"),
        )
        for page, icon, title_text in rows:
            self.sidebar.append(SidebarRow(page, icon, title_text))

        wrap.append(self.sidebar)

        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        wrap.append(spacer)

        version_label = Gtk.Label(
            label="Configuration app",
            xalign=0,
            margin_top=12,
            margin_bottom=16,
            margin_start=18,
            margin_end=18,
        )
        version_label.add_css_class("dim-label")
        wrap.append(version_label)

        return wrap

    def on_sidebar_selected(self, _listbox, row):
        if row is not None:
            self.stack.set_visible_child_name(row.page_name)
            if row.page_name == "themes":
                self.refresh_theme_list()

    def on_color_scheme_changed(self, row, _param):
        values = ("system", "light", "dark")
        selected = row.get_selected()
        if selected < 0 or selected >= len(values):
            return

        value = values[selected]
        self.saved_color_scheme = value

        try:
            save_color_scheme(value)
            apply_color_scheme(value)
        except Exception as exc:
            self.toast(f"Could not change appearance: {exc}")
            return

        # Re-apply on the next main-loop turn so already-created widgets are
        # restyled after the ComboRow notification finishes.
        GLib.idle_add(lambda: (apply_color_scheme(value), False)[1])

        labels = {
            "system": "Following system appearance",
            "light": "Light appearance enabled",
            "dark": "Dark appearance enabled",
        }
        self.toast(labels[value])


    def on_start_minimized_changed(self, row, _param):
        enabled = row.get_active()
        try:
            save_start_minimized(enabled)
        except Exception as exc:
            self.toast(f"Could not save startup preference: {exc}")
            return

        self.toast(
            "Application will start minimized to tray"
            if enabled
            else "Application will open normally"
        )

    def run_checkup(self):
        if not GTK_CHECKUP.is_file():
            self.toast("gtk-checkup.py was not found")
            return

        self.toast("Running program check…")

        def worker():
            result = subprocess.run(
                ["/usr/bin/python3", str(GTK_CHECKUP), str(ROOT)],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
                check=False,
            )
            GLib.idle_add(
                self.show_checkup_result,
                result.returncode,
                result.stdout,
                result.stderr,
            )

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def show_checkup_result(self, returncode, stdout, stderr):
        output = (stdout or stderr or "No output").strip()
        heading = (
            "Program check completed"
            if returncode == 0
            else "Program check found problems"
        )

        dialog = Adw.AlertDialog(
            heading=heading,
            body=output[-5000:],
        )
        dialog.add_response("close", "Close")
        dialog.present(self)
        return False

    def refresh_theme_list(self):
        while True:
            row = self.theme_list.get_row_at_index(0)
            if row is None:
                break
            self.theme_list.remove(row)

        themes, display_size = compatible_themes()

        if display_size:
            self.compatibility_label.set_label(
                f'Showing themes compatible with the selected {display_size}" display'
            )
        else:
            self.compatibility_label.set_label(
                "Display size could not be detected; showing all installed themes"
            )

        if not themes:
            empty = Gtk.ListBoxRow()
            empty.set_selectable(False)
            empty.set_activatable(False)

            box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=8,
                margin_top=28,
                margin_bottom=28,
                margin_start=18,
                margin_end=18,
            )
            icon = Gtk.Image.new_from_icon_name("folder-missing-symbolic")
            icon.set_pixel_size(42)
            label = Gtk.Label(
                label=(
                    f'No compatible themes found for the {display_size}" display'
                    if display_size
                    else "No themes found"
                ),
                wrap=True,
                justify=Gtk.Justification.CENTER,
            )
            label.add_css_class("title-4")
            path_label = Gtk.Label(
                label=f"Expected folder:\n{THEMES_DIR}",
                wrap=True,
                justify=Gtk.Justification.CENTER,
            )
            path_label.add_css_class("dim-label")
            box.append(icon)
            box.append(label)
            box.append(path_label)
            empty.set_child(box)
            self.theme_list.append(empty)
            self.selected_theme_label.set_label("No theme selected")
            self.theme_page_picture.set_paintable(None)
            return

        active_index = 0
        for index, theme_name in enumerate(themes):
            row = ThemeListRow(
                theme_name,
                active=(theme_name == self.current_theme),
            )
            self.theme_list.append(row)
            if theme_name == self.current_theme:
                active_index = index

        row = self.theme_list.get_row_at_index(active_index)
        if row is not None:
            self.theme_list.select_row(row)


    def on_theme_selected(self, _listbox, row):
        if row is None or not hasattr(row, "theme_name"):
            return
        self.selected_theme_label.set_label(row.theme_name)
        self.set_picture(self.theme_page_picture, theme_preview_path(row.theme_name))

    def refresh_all(self):
        self.refresh_overview()
        self.refresh_theme_list()

    def set_picture(self, picture: Gtk.Picture, path: Path | None):
        if path is None or not path.is_file():
            if ICON_FILE.is_file():
                try:
                    picture.set_paintable(
                        Gdk.Texture.new_from_filename(str(ICON_FILE))
                    )
                except GLib.Error:
                    picture.set_paintable(None)
            else:
                picture.set_paintable(None)
            return

        try:
            texture = Gdk.Texture.new_from_filename(str(path))
            picture.set_paintable(texture)
        except GLib.Error as exc:
            self.toast(f"Could not load preview: {exc}")

    def launch_script(
        self,
        path: Path,
        *arguments: str,
        use_system_python: bool = False,
    ):
        if not path.is_file():
            self.toast(f"File not found: {path.name}")
            return

        python_executable = (
            "/usr/bin/python3"
            if use_system_python
            else project_python()
        )

        try:
            return subprocess.Popen(
                [python_executable, str(path), *arguments],
                cwd=str(ROOT),
                start_new_session=True,
            )
        except Exception as exc:
            self.toast(f"Could not open {path.name}: {exc}")
            return None

    def open_video_manager(self, *_args):
        # PyGObject/GTK is installed by the system package manager on
        # Arch/CachyOS, so the GTK video manager must run with system Python.
        self.launch_script(
            VIDEO_MANAGER,
            use_system_python=True,
        )

    def finish_turn_off_display(self, returncode, stdout, stderr):
        self.refresh_overview()

        if returncode == 0:
            self.toast("Display turned off")
        else:
            detail = (stderr or stdout or "Unknown error").strip()
            self.toast(f"Could not turn off display: {detail[-180:]}")

        return False

    def on_close_request(self, *_args):
        # Hide instead of quitting. The monitor and tray remain active.
        self.set_visible(False)
        return True

    def toast(self, message: str):
        self.toast_overlay.add_toast(Adw.Toast(title=message, timeout=3))



STATUS_NOTIFIER_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="WindowId" type="u" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconThemePath" type="s" access="read"/>
    <property name="OverlayIconName" type="s" access="read"/>
    <property name="AttentionIconName" type="s" access="read"/>
    <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="Menu" type="o" access="read"/>

    <method name="Activate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="SecondaryActivate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="ContextMenu">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="Scroll">
      <arg name="delta" type="i" direction="in"/>
      <arg name="orientation" type="s" direction="in"/>
    </method>

    <signal name="NewTitle"/>
    <signal name="NewIcon"/>
    <signal name="NewAttentionIcon"/>
    <signal name="NewOverlayIcon"/>
    <signal name="NewToolTip"/>
    <signal name="NewStatus">
      <arg name="status" type="s"/>
    </signal>
  </interface>
</node>
"""

DBUSMENU_XML = """
<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="TextDirection" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconThemePath" type="as" access="read"/>

    <method name="GetLayout">
      <arg name="parentId" type="i" direction="in"/>
      <arg name="recursionDepth" type="i" direction="in"/>
      <arg name="propertyNames" type="as" direction="in"/>
      <arg name="revision" type="u" direction="out"/>
      <arg name="layout" type="(ia{sv}av)" direction="out"/>
    </method>

    <method name="GetGroupProperties">
      <arg name="ids" type="ai" direction="in"/>
      <arg name="propertyNames" type="as" direction="in"/>
      <arg name="properties" type="a(ia{sv})" direction="out"/>
    </method>

    <method name="GetProperty">
      <arg name="id" type="i" direction="in"/>
      <arg name="name" type="s" direction="in"/>
      <arg name="value" type="v" direction="out"/>
    </method>

    <method name="Event">
      <arg name="id" type="i" direction="in"/>
      <arg name="eventId" type="s" direction="in"/>
      <arg name="data" type="v" direction="in"/>
      <arg name="timestamp" type="u" direction="in"/>
    </method>

    <method name="EventGroup">
      <arg name="events" type="a(isvu)" direction="in"/>
      <arg name="idErrors" type="ai" direction="out"/>
    </method>

    <method name="AboutToShow">
      <arg name="id" type="i" direction="in"/>
      <arg name="needUpdate" type="b" direction="out"/>
    </method>

    <method name="AboutToShowGroup">
      <arg name="ids" type="ai" direction="in"/>
      <arg name="updatesNeeded" type="ai" direction="out"/>
      <arg name="idErrors" type="ai" direction="out"/>
    </method>

    <signal name="LayoutUpdated">
      <arg name="revision" type="u"/>
      <arg name="parent" type="i"/>
    </signal>
  </interface>
</node>
"""


class StatusNotifierMenu:
    """Small DBusMenu implementation for the StatusNotifier tray icon."""

    MENU_ITEMS = (
        (1, "show-hide-window"),
        (2, "start-screen"),
        (3, "turn-off-screen"),
        (4, "open-theme-editor"),
        (5, "open-video-manager"),
        (6, "quit"),
    )

    def __init__(self, app: "SmartScreenApplication"):
        self.app = app
        self.connection = None
        self.registration_id = 0
        self.revision = 1
        self.node_info = Gio.DBusNodeInfo.new_for_xml(DBUSMENU_XML)
        self.interface_info = self.node_info.interfaces[0]

    def register(self, connection):
        self.connection = connection
        try:
            self.registration_id = self.connection.register_object(
                DBUSMENU_OBJECT_PATH,
                self.interface_info,
                self._on_method_call,
                self._on_get_property,
                None,
            )
        except Exception as exc:
            self.registration_id = 0
            print(f"Tray menu registration failed: {exc}", file=sys.stderr)

    def stop(self):
        if self.connection is not None and self.registration_id:
            try:
                self.connection.unregister_object(self.registration_id)
            except Exception:
                pass
        self.registration_id = 0
        self.connection = None

    def window_visible(self) -> bool:
        window = self.app.props.active_window
        return bool(window is not None and window.get_visible())

    def action_for_id(self, item_id: int) -> str | None:
        for candidate_id, action in self.MENU_ITEMS:
            if candidate_id == item_id:
                return action
        return None

    def item_properties(self, item_id: int, property_names=()):
        properties = {}

        if item_id == 0:
            properties["children-display"] = GLib.Variant("s", "submenu")
            return self.filter_properties(properties, property_names)

        action = self.action_for_id(item_id)
        if action is None:
            return {}

        properties["label"] = GLib.Variant("s", self.menu_label(action))
        properties["enabled"] = GLib.Variant("b", True)
        properties["visible"] = GLib.Variant("b", True)

        return self.filter_properties(properties, property_names)

    @staticmethod
    def filter_properties(properties, property_names):
        if not property_names:
            return properties
        wanted = set(property_names)
        return {
            key: value
            for key, value in properties.items()
            if key in wanted
        }

    def layout_tuple(self, item_id: int = 0, property_names=()):
        properties = self.item_properties(item_id, property_names)

        if item_id == 0:
            children = [
                GLib.Variant(
                    "(ia{sv}av)",
                    self.layout_tuple(child_id, property_names),
                )
                for child_id, _action in self.MENU_ITEMS
            ]
        else:
            children = []

        return item_id, properties, children

    def emit_layout_updated(self):
        if self.connection is None or not self.registration_id:
            return
        self.revision += 1
        try:
            self.connection.emit_signal(
                None,
                DBUSMENU_OBJECT_PATH,
                "com.canonical.dbusmenu",
                "LayoutUpdated",
                GLib.Variant("(ui)", (self.revision, 0)),
            )
        except Exception:
            pass

    def _ensure_window(self):
        window = self.app.props.active_window
        if window is None:
            self.app.activate()
            window = self.app.props.active_window
        return window

    def _show_window(self):
        self.app.activate()
        window = self.app.props.active_window
        if window is not None:
            window.present()

    def _hide_window(self):
        window = self.app.props.active_window
        if window is not None:
            window.set_visible(False)

    def _toggle_window(self):
        if self.window_visible():
            self._hide_window()
        else:
            self._show_window()
        self.emit_layout_updated()

    def _run_window_action(self, method_name: str):
        window = self._ensure_window()
        if window is None:
            return
        method = getattr(window, method_name, None)
        if callable(method):
            method()

    def activate_item(self, item_id: int):
        action = self.action_for_id(item_id)
        if action is None:
            return

        def run():
            try:
                if action == "show-hide-window":
                    self._toggle_window()
                elif action == "start-screen":
                    self._run_window_action("start_monitor")
                elif action == "turn-off-screen":
                    self._run_window_action("turn_off_display")
                elif action == "open-theme-editor":
                    self._run_window_action("open_theme_editor")
                elif action == "open-video-manager":
                    self._run_window_action("open_video_manager")
                elif action == "quit":
                    self.app.quit()
            except Exception as exc:
                print(f"Tray menu action failed: {exc}", file=sys.stderr)
            return False

        GLib.idle_add(run)

    def _on_method_call(
        self,
        _connection,
        _sender,
        _object_path,
        _interface_name,
        method_name,
        parameters,
        invocation,
    ):
        if method_name == "GetLayout":
            _parent_id, _depth, property_names = parameters.unpack()
            invocation.return_value(
                GLib.Variant(
                    "(u(ia{sv}av))",
                    (self.revision, self.layout_tuple(0, property_names)),
                )
            )
            return

        if method_name == "GetGroupProperties":
            ids, property_names = parameters.unpack()
            result = [
                (int(item_id), self.item_properties(int(item_id), property_names))
                for item_id in ids
            ]
            invocation.return_value(GLib.Variant("(a(ia{sv}))", (result,)))
            return

        if method_name == "GetProperty":
            item_id, name = parameters.unpack()
            value = self.item_properties(int(item_id)).get(
                name,
                GLib.Variant("s", ""),
            )
            invocation.return_value(GLib.Variant("(v)", (value,)))
            return

        if method_name == "Event":
            item_id, event_id, _data, _timestamp = parameters.unpack()
            if event_id in {"clicked", "activated"}:
                self.activate_item(int(item_id))
            invocation.return_value(None)
            return

        if method_name == "EventGroup":
            events, = parameters.unpack()
            for item_id, event_id, _data, _timestamp in events:
                if event_id in {"clicked", "activated"}:
                    self.activate_item(int(item_id))
            invocation.return_value(GLib.Variant("(ai)", ([],)))
            return

        if method_name == "AboutToShow":
            _item_id, = parameters.unpack()
            invocation.return_value(GLib.Variant("(b)", (True,)))
            return

        if method_name == "AboutToShowGroup":
            ids, = parameters.unpack()
            invocation.return_value(GLib.Variant("(aiai)", (list(ids), [])))
            return

        invocation.return_error_literal(
            Gio.IOErrorEnum.quark(),
            Gio.IOErrorEnum.NOT_SUPPORTED,
            f"Unsupported DBusMenu method: {method_name}",
        )

    def _on_get_property(
        self,
        _connection,
        _sender,
        _object_path,
        _interface_name,
        property_name,
    ):
        values = {
            "Version": GLib.Variant("u", 4),
            "TextDirection": GLib.Variant("s", "ltr"),
            "Status": GLib.Variant("s", "normal"),
            "IconThemePath": GLib.Variant("as", []),
        }
        return values.get(property_name)


class StatusNotifierItem:
    """Minimal StatusNotifierItem understood by Noctalia and other SNI trays."""

    menu_class = StatusNotifierMenu
    introspection_xml = STATUS_NOTIFIER_XML

    def __init__(self, app: "SmartScreenApplication"):
        self.app = app
        self.connection = None
        self.registration_id = 0
        self.name_owner_id = 0
        self.bus_name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
        self.node_info = Gio.DBusNodeInfo.new_for_xml(self.introspection_xml)
        self.interface_info = self.node_info.interfaces[0]
        self.menu = self.menu_class(app)

    def start(self):
        Gio.bus_get(
            Gio.BusType.SESSION,
            None,
            self._on_bus_ready,
        )

    def stop(self):
        self.menu.stop()

        if self.connection is not None and self.registration_id:
            try:
                self.connection.unregister_object(self.registration_id)
            except Exception:
                pass
            self.registration_id = 0

        if self.name_owner_id:
            Gio.bus_unown_name(self.name_owner_id)
            self.name_owner_id = 0

        self.connection = None

    def _on_bus_ready(self, _source, result):
        try:
            self.connection = Gio.bus_get_finish(result)
            self.menu.register(self.connection)

            self.registration_id = self.connection.register_object(
                TRAY_OBJECT_PATH,
                self.interface_info,
                self._on_method_call,
                self._on_get_property,
                None,
            )

            self.name_owner_id = Gio.bus_own_name_on_connection(
                self.connection,
                self.bus_name,
                Gio.BusNameOwnerFlags.NONE,
                self._on_name_acquired,
                self._on_name_lost,
            )
        except Exception as exc:
            print(f"System tray registration failed: {exc}", file=sys.stderr)

    def _on_name_acquired(self, _connection, _name):
        self._register_with_watcher()

    def _on_name_lost(self, _connection, _name):
        print("System tray D-Bus name was lost", file=sys.stderr)

    def _register_with_watcher(self):
        if self.connection is None:
            return

        self.connection.call(
            "org.kde.StatusNotifierWatcher",
            "/StatusNotifierWatcher",
            "org.kde.StatusNotifierWatcher",
            "RegisterStatusNotifierItem",
            GLib.Variant("(s)", (self.bus_name,)),
            None,
            Gio.DBusCallFlags.NONE,
            3000,
            None,
            self._on_watcher_registered,
        )

    def _on_watcher_registered(self, connection, result):
        try:
            connection.call_finish(result)
        except Exception as exc:
            print(
                f"StatusNotifierWatcher is not available yet: {exc}",
                file=sys.stderr,
            )

    def _toggle_app_window(self):
        window = self.app.props.active_window
        if window is not None and window.get_visible():
            window.set_visible(False)
        else:
            self.app.activate()
            window = self.app.props.active_window
            if window is not None:
                window.present()

        self.menu.emit_layout_updated()

    def _toggle_monitor(self):
        self.app.activate()
        window = self.app.props.active_window
        if window is None:
            return
        running = (
            window.monitor_process is not None
            and window.monitor_process.poll() is None
        )
        if running:
            window.stop_monitor()
        else:
            window.start_monitor()

    def _on_method_call(
        self,
        _connection,
        _sender,
        _object_path,
        _interface_name,
        method_name,
        _parameters,
        invocation,
    ):
        if method_name == "Activate":
            GLib.idle_add(lambda: (self._toggle_app_window(), False)[1])
        elif method_name == "SecondaryActivate":
            GLib.idle_add(lambda: (self._toggle_monitor(), False)[1])
        elif method_name == "ContextMenu":
            # The shell opens DBusMenu through the Menu property.
            pass

        invocation.return_value(None)

class SmartScreenApplication(Adw.Application):
    window_class = SmartScreenWindow
    tray_item_class = StatusNotifierItem

    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )

        self.force_minimized_once = False
        self.force_show_once = False

        self.add_main_option(
            "minimized",
            0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            "Start minimized to the system tray",
            None,
        )
        self.add_main_option(
            "show",
            0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            "Open and show the main window",
            None,
        )

        GLib.set_application_name(APP_NAME)
        GLib.set_prgname(APP_ID)
        self.tray_item = self.tray_item_class(self)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.show_about)
        self.add_action(about_action)

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_: self.quit())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<primary>q"])

    def do_startup(self):
        Adw.Application.do_startup(self)

        # Apply the saved Libadwaita scheme before any window/widget exists.
        # Doing this in startup avoids desktop GTK settings overriding the
        # first rendered frame.
        apply_color_scheme(load_saved_color_scheme())

        # Do not load a global application stylesheet here.
        # The previous style.css contained fixed surface/background colors,
        # which overrode Libadwaita and made Light/Dark appear not to work.
        # Native Libadwaita style classes are used throughout the interface.

        self.tray_item.start()

    def do_shutdown(self):
        self.tray_item.stop()
        Adw.Application.do_shutdown(self)

    def do_command_line(self, command_line):
        options = command_line.get_options_dict()

        self.force_minimized_once = bool(
            options.contains("minimized")
        )
        self.force_show_once = bool(options.contains("show"))

        self.activate()
        return 0

    def do_activate(self):
        window = self.props.active_window
        first_activation = window is None

        if window is None:
            window = self.window_class(self)

        should_minimize = (
            self.force_minimized_once
            or (
                first_activation
                and load_start_minimized()
                and not self.force_show_once
            )
        )

        self.force_minimized_once = False
        force_show = self.force_show_once
        self.force_show_once = False

        if should_minimize and not force_show:
            window.set_visible(False)
        else:
            window.present()

    def show_about(self, *_args):
        window = self.props.active_window
        about = Adw.AboutDialog(
            application_name="Turing Smart Screen",
            application_icon=APP_ID,
            developer_name="Turing Smart Screen community",
            version="GTK preview 0.1",
            comments=(
                "A modern GTK4 + Libadwaita configuration interface "
                "for turing-smart-screen-python."
            ),
            website="https://github.com/mathoudebine/turing-smart-screen-python",
            license_type=Gtk.License.GPL_3_0,
        )
        about.present(window)
