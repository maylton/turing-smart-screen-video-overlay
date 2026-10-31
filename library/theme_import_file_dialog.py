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
    """Replace the text entry importer with the native GTK file dialog."""
    from library import theme_gallery as gallery

    pane_class = gallery.ThemeGalleryPane
    if getattr(pane_class, "_turing_native_import_dialog", False):
        return False

    Gtk = gallery.Gtk
    Gio = gallery.Gio
    GLib = gallery.GLib
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

    def confirm_import_theme(self) -> None:
        if getattr(self, "_theme_import_dialog_open", False):
            return

        root = self.root_widget()
        parent = root if isinstance(root, Gtk.Window) else None

        supported = Gtk.FileFilter()
        supported.set_name("Theme packages and definitions")
        for pattern in _SUPPORTED_PATTERNS:
            supported.add_pattern(pattern)

        all_files = Gtk.FileFilter()
        all_files.set_name("All files")
        all_files.add_pattern("*")

        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(supported)
        filters.append(all_files)

        dialog = Gtk.FileDialog(title="Import Theme", accept_label="_Import", modal=True)
        dialog.set_filters(filters)
        dialog.set_default_filter(supported)

        def on_finished(source, result) -> None:
            self._theme_import_dialog_open = False
            try:
                selected = source.open_finish(result)
            except GLib.Error:
                # Cancelled or dismissed by the user.
                return
            path = selected.get_path() if selected is not None else None
            if not path:
                self.show_error_dialog(
                    "Could not import theme",
                    "Only local theme files can be imported.",
                )
                return
            self.on_import_theme(str(normalize_theme_import_path(path)))

        self._theme_import_dialog_open = True
        dialog.open(parent, None, on_finished)

    gallery.import_theme = import_theme_from_selection
    pane_class.confirm_import_theme = confirm_import_theme
    pane_class._turing_native_import_dialog = True
    return True
