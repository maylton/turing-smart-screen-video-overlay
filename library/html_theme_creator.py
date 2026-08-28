# SPDX-License-Identifier: GPL-3.0-or-later
"""Create and open a validated blank HTML theme from the main GTK app."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from library.html_theme_components import (
    HtmlGeneratedWidget,
    render_generated_widget_block,
)
from library.html_theme_visual_editor import (
    HtmlVisualElementStyle,
    load_visual_styles,
    save_visual_styles,
)
from library.theme_engine import ThemeManifest


DEFAULT_WIDTH = 480
DEFAULT_HEIGHT = 480
DEFAULT_REFRESH_RATE = 2
STARTER_ELEMENT_ID = "turing-starter-anchor"


def sanitize_theme_folder_name(value: str) -> str:
    value = str(value or "").strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    return re.sub(r"-{2,}", "-", value).strip("-._")


def normalize_theme_display_name(value: str) -> str:
    name = " ".join(str(value or "").split())
    if not name:
        raise ValueError("Enter a theme name.")
    if len(name) > 80:
        raise ValueError("Theme names can contain at most 80 characters.")
    if any(ord(character) < 32 for character in name):
        raise ValueError("Theme name contains unsupported control characters.")
    return name


def _manifest_payload(name: str, width: int, height: int) -> dict[str, object]:
    return {
        "engine": "html",
        "name": name,
        "version": 1,
        "display": {"width": width, "height": height},
        "refreshRate": DEFAULT_REFRESH_RATE,
        "entrypoint": "index.html",
        "permissions": ["sensors"],
        "network": False,
        "dataUpdateIntervals": {"default": 1},
        "atomicRegions": [],
    }


def _starter_style() -> HtmlVisualElementStyle:
    """Return an invisible generated widget that bootstraps the current editor."""
    return HtmlVisualElementStyle(
        element_id=STARTER_ELEMENT_ID,
        x=0,
        y=0,
        width=1,
        height=1,
        font_size=6,
        color="#ffffff",
        font_weight=400,
        text_align="left",
        opacity=0,
        z_index=1,
        visible=False,
        component_type="time",
        generated_widget=True,
        binding="system.time",
        formatter="time",
        sample="00:00",
        element_kind="text",
    )


def _index_html(name: str) -> str:
    widget = HtmlGeneratedWidget(
        element_id=STARTER_ELEMENT_ID,
        component_type="time",
        binding="system.time",
        formatter="time",
        sample="00:00",
        kind="text",
    )
    block = render_generated_widget_block((widget,))
    escaped_title = (
        name.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=480, height=480, initial-scale=1">
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'self' data:; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'none'; media-src 'self'; object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'">
  <title>{escaped_title}</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <main id="theme-canvas" aria-label="Blank theme canvas"></main>
  <script src="theme.js"></script>
{block}
</body>
</html>
"""


def _style_css(width: int, height: int) -> str:
    return f"""/* Author-owned stylesheet for a blank HTML theme. */
:root {{
  color-scheme: dark;
  font-family: system-ui, sans-serif;
}}

html,
body {{
  width: {width}px;
  height: {height}px;
  margin: 0;
  overflow: hidden;
  background: #090d10;
}}

body {{
  position: relative;
}}

#theme-canvas {{
  position: fixed;
  inset: 0;
}}

#turing-editor-widgets {{
  position: fixed;
  inset: 0;
  pointer-events: none;
}}
"""


def _theme_javascript() -> str:
    return """// Add optional author-owned behavior here. Sensor widgets added by the\n// visual editor are updated by theme-editor-widgets.js.\nwindow.TuringTheme = window.TuringTheme || {};\n"""


def create_blank_html_theme(
    display_name: str,
    themes_dir: Path | str,
    *,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
) -> str:
    """Create a validated, visually empty HTML theme and return its folder name."""
    name = normalize_theme_display_name(display_name)
    folder_name = sanitize_theme_folder_name(name)
    if not folder_name:
        raise ValueError("Enter a theme name that can be used as a folder name.")
    width = int(width)
    height = int(height)
    if width <= 0 or height <= 0:
        raise ValueError("Theme dimensions must be positive.")

    themes_root = Path(themes_dir).expanduser().resolve()
    themes_root.mkdir(parents=True, exist_ok=True)
    target = themes_root / folder_name
    if target.exists():
        raise FileExistsError(f"A theme named {folder_name} already exists.")

    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{folder_name}.creating-",
            dir=str(themes_root),
        )
    )
    try:
        (staging / "assets").mkdir()
        (staging / "manifest.json").write_text(
            json.dumps(
                _manifest_payload(name, width, height),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (staging / "index.html").write_text(_index_html(name), encoding="utf-8")
        (staging / "style.css").write_text(
            _style_css(width, height),
            encoding="utf-8",
        )
        (staging / "theme.js").write_text(
            _theme_javascript(),
            encoding="utf-8",
        )

        manifest = ThemeManifest.load(staging)
        manifest = save_visual_styles(manifest, (_starter_style(),))
        styles = load_visual_styles(manifest)
        if len(styles) != 1 or styles[0].element_id != STARTER_ELEMENT_ID:
            raise RuntimeError("Blank theme validation did not preserve its starter anchor.")

        # New themes do not need restoration backups for files that have never
        # been published. Keep the created package clean.
        for backup in staging.glob("*.visual.editor-backup"):
            backup.unlink(missing_ok=True)

        # Validate once more after all derived files have been written.
        ThemeManifest.load(staging)
        os.replace(staging, target)
        return folder_name
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _find_gallery_record(window: Any, folder_name: str):
    gallery = getattr(window, "theme_gallery", None)
    if gallery is None:
        return None
    try:
        gallery.reload_themes(show_toast=False)
    except TypeError:
        gallery.reload_themes()
    return next(
        (
            record
            for record in getattr(gallery, "records", ())
            if getattr(record, "name", None) == folder_name
        ),
        None,
    )


def install_main_app_theme_creator(app: Any) -> bool:
    """Replace the legacy YAML blank-theme flow in the main GTK application."""
    window_class = getattr(app, "SmartScreenWindow", None)
    if window_class is None:
        return False
    if getattr(window_class, "_html_theme_creator_installed", False):
        return False

    Gtk = app.Gtk
    Adw = app.Adw
    GLib = app.GLib

    def create_empty_theme(
        self,
        display_name: str,
        _display_size: str = "",
    ) -> str | None:
        try:
            folder_name = create_blank_html_theme(
                display_name,
                app.THEMES_DIR,
            )
        except Exception as exc:
            self.toast(f"Could not create theme: {exc}")
            return None

        record = _find_gallery_record(self, folder_name)
        self.toast(f"Blank HTML theme created: {folder_name}")

        def open_created_theme() -> bool:
            if record is not None:
                callback = getattr(self, "open_theme_record_editor", None)
                if callable(callback):
                    callback(record)
                    return False
            launcher = getattr(self, "launch_script", None)
            editor = app.ROOT / "html-theme-editor-gtk.py"
            if callable(launcher) and editor.is_file():
                launcher(
                    editor,
                    folder_name,
                    use_system_python=True,
                )
            return False

        GLib.idle_add(open_created_theme)
        return folder_name

    def show_create_empty_theme_dialog(self) -> None:
        display_size = ""
        detector = getattr(app, "selected_display_size", None)
        if callable(detector):
            try:
                display_size = str(detector() or "")
            except Exception:
                display_size = ""

        name_entry = Adw.EntryRow(
            title="Theme name",
            text="My HTML Theme",
        )
        name_entry.set_activates_default(True)

        extra = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
        )
        extra.append(name_entry)
        note = Gtk.Label(
            label=(
                "Creates a blank 480×480 HTML canvas and opens it in the visual "
                "editor so you can add sensor texts, bars, images, videos, or GIFs."
            ),
            xalign=0,
            wrap=True,
        )
        note.add_css_class("dim-label")
        extra.append(note)

        detected = f' Detected display: {display_size}".' if display_size else ""
        dialog = Adw.AlertDialog(
            heading="Create new HTML theme",
            body=(
                "The new theme is created as a separate folder and does not "
                "replace any installed theme." + detected
            ),
        )
        dialog.set_extra_child(extra)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("create", "Create and Edit")
        dialog.set_default_response("create")
        dialog.set_close_response("cancel")
        dialog.set_response_appearance(
            "create",
            Adw.ResponseAppearance.SUGGESTED,
        )

        def on_response(_dialog, response_id: str) -> None:
            if response_id == "create":
                self.create_empty_theme(name_entry.get_text(), display_size)

        dialog.connect("response", on_response)
        dialog.present(self)

    window_class.create_empty_theme = create_empty_theme
    window_class.show_create_empty_theme_dialog = show_create_empty_theme_dialog
    window_class._html_theme_creator_installed = True
    return True
