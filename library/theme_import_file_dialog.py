# SPDX-License-Identifier: GPL-3.0-or-later
"""Native GTK file chooser integration for Theme Gallery imports."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlparse


_THEME_DEFINITION_NAMES = frozenset({"manifest.json", "theme.yaml", "theme.yml"})
_SUPPORTED_PATTERNS = (
    "*.theme",
    "*.THEME",
    "*.zip",
    "*.ZIP",
    "manifest.json",
    "MANIFEST.JSON",
    "theme.yaml",
    "THEME.YAML",
    "theme.yml",
    "THEME.YML",
)


def normalize_theme_import_path(value: str | Path) -> Path:
    """Resolve a selected package or definition file to an import source."""
    text = str(value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1:-1].strip()

    parsed = urlparse(text)
    if parsed.scheme.casefold() == "file":
        text = unquote(parsed.path)

    path = Path(text).expanduser()
    if path.is_file() and path.name.casefold() in _THEME_DEFINITION_NAMES:
        return path.parent
    return path


def install() -> bool:
    """Replace the text entry importer with a native GTK file chooser."""
    from library import theme_gallery as gallery

    pane_class = gallery.ThemeGalleryPane
    if getattr(pane_class, "_turing_native_import_dialog", False):
        return False

    Gtk = gallery.Gtk
    original_import_theme = gallery.import_theme

    def import_legacy_theme_archive(source: Path) -> str:
        """Import old ``.theme`` files that are plain validated ZIP archives."""
        with tempfile.TemporaryDirectory(prefix="turing-theme-import-") as tmp_dir:
            tmp_path = Path(tmp_dir)
            with zipfile.ZipFile(source) as archive:
                gallery.validate_zip_members(archive)
                archive.extractall(tmp_path)

            theme_source = gallery.resolve_import_theme_source(tmp_path)
            preferred_name = source.stem

            manifest_path = theme_source / "manifest.json"
            if manifest_path.is_file():
                try:
                    preferred_name = gallery.ThemeManifest.load(theme_source).name
                except gallery.ThemeValidationError:
                    # resolve_import_theme_source() already rejects invalid themes.
                    pass
            elif theme_source != tmp_path:
                preferred_name = theme_source.name

            return gallery.copy_imported_theme(theme_source, preferred_name)

    def import_theme_from_selection(source_path_text: str) -> str:
        source = normalize_theme_import_path(source_path_text)

        if source.is_file() and source.suffix.casefold() == gallery.PACKAGE_EXTENSION:
            with zipfile.ZipFile(source) as archive:
                gallery.validate_zip_members(archive)
                root_members = {
                    name.rstrip("/")
                    for name in archive.namelist()
                    if name and "/" not in name.rstrip("/")
                }
            if gallery.PACKAGE_FILENAME not in root_members:
                return import_legacy_theme_archive(source)

        return original_import_theme(str(source))

    def close_chooser(pane, chooser) -> None:
        if getattr(pane, "_theme_import_chooser", None) is chooser:
            pane._theme_import_chooser = None
        destroy = getattr(chooser, "destroy", None)
        if callable(destroy):
            destroy()
            return
        hide = getattr(chooser, "hide", None)
        if callable(hide):
            hide()

    def confirm_import_theme(self) -> None:
        existing = getattr(self, "_theme_import_chooser", None)
        if existing is not None:
            show = getattr(existing, "show", None)
            if callable(show):
                show()
            return

        root = self.root_widget()
        parent = root if isinstance(root, Gtk.Window) else None
        chooser = Gtk.FileChooserNative.new(
            "Import Theme",
            parent,
            Gtk.FileChooserAction.OPEN,
            "_Import",
            "_Cancel",
        )
        chooser.set_modal(True)

        supported = Gtk.FileFilter()
        supported.set_name("Theme packages and definitions")
        for pattern in _SUPPORTED_PATTERNS:
            supported.add_pattern(pattern)
        chooser.add_filter(supported)
        chooser.set_filter(supported)

        all_files = Gtk.FileFilter()
        all_files.set_name("All files")
        all_files.add_pattern("*")
        chooser.add_filter(all_files)

        def on_response(dialog, response) -> None:
            try:
                if response != Gtk.ResponseType.ACCEPT:
                    return
                selected = dialog.get_file()
                path = selected.get_path() if selected is not None else None
                if not path:
                    self.show_error_dialog(
                        "Could not import theme",
                        "Only local theme files can be imported.",
                    )
                    return
                self.on_import_theme(str(normalize_theme_import_path(path)))
            finally:
                close_chooser(self, dialog)

        chooser.connect("response", on_response)
        self._theme_import_chooser = chooser
        chooser.show()

    gallery.import_theme = import_theme_from_selection
    pane_class.confirm_import_theme = confirm_import_theme
    pane_class._turing_native_import_dialog = True
    return True
