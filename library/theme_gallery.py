# SPDX-License-Identifier: GPL-3.0-or-later
"""Reusable GTK theme gallery components."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk, Pango

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "config.yaml"
THEMES_DIR = ROOT / "res" / "themes"
THEME_EDITOR = ROOT / "theme-editor-gtk.py"

ThemeCallback = Callable[["ThemeRecord"], None]
DuplicateThemeCallback = Callable[["ThemeRecord", str], None]
RenameThemeCallback = Callable[["ThemeRecord", str], None]
DeleteThemeCallback = Callable[["ThemeRecord"], None]
ImportThemeCallback = Callable[[str], None]
ExportThemeCallback = Callable[["ThemeRecord", str], None]

IGNORE_PATTERNS = (
    "*.tmp",
    "*.editor-backup",
    "*.before-sequence-repair",
    "__pycache__",
)


@dataclass(frozen=True)
class ThemeRecord:
    name: str
    directory: Path
    yaml_file: Path | None
    preview_file: Path
    current: bool = False
    issue: str | None = None
    display_size: str = ""

    @property
    def editable(self) -> bool:
        return self.yaml_file is not None and self.issue is None

    @property
    def status_label(self) -> str:
        if self.issue:
            return self.issue
        if self.current:
            return "Current theme"
        return "Ready"

    @property
    def display_label(self) -> str:
        return f'{self.display_size}" display' if self.display_size else "Unknown display size"

    def search_text(self) -> str:
        parts = [self.name, self.status_label, self.display_label]
        try:
            parts.append(os.path.relpath(self.directory, ROOT))
        except ValueError:
            parts.append(str(self.directory))
        if self.yaml_file is not None:
            parts.append(self.yaml_file.name)
        return " ".join(parts).casefold()


def relative_path_label(path: Path) -> str:
    try:
        return os.path.relpath(path, ROOT)
    except ValueError:
        return str(path)


def normalize_display_size(value: str) -> str:
    value = str(value or "").strip().lower().replace(",", ".")
    match = re.search(r"(\d+(?:\.\d+)?)", value)
    return match.group(1) if match else ""


def sanitize_theme_folder_name(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-._")
    return value


def ensure_theme_child(path: Path) -> None:
    if path.resolve().parent != THEMES_DIR.resolve():
        raise RuntimeError(f"Refusing to modify a folder outside {THEMES_DIR}")


def next_available_theme_name(base_name: str, themes_dir: Path = THEMES_DIR) -> str:
    base = sanitize_theme_folder_name(base_name) or "theme"
    candidate = base
    index = 2
    while (themes_dir / candidate).exists():
        candidate = f"{base}-{index}"
        index += 1
    return candidate


def suggested_duplicate_name(theme_name: str, themes_dir: Path = THEMES_DIR) -> str:
    return next_available_theme_name(f"{theme_name}-copy", themes_dir)


def default_export_path(theme_name: str) -> Path:
    return Path.home() / "Downloads" / f"{theme_name}.zip"


def read_scalar_from_yaml_text(path: Path, key: str) -> str:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return ""

    pattern = re.compile(rf'(?m)^\s*{re.escape(key)}\s*:\s*["\']?([^"\'\n#]+)')
    match = pattern.search(content)
    return match.group(1).strip() if match else ""


def find_theme_file(theme_dir: Path) -> Path | None:
    for file_name in ("theme.yaml", "theme.yml"):
        candidate = theme_dir / file_name
        if candidate.is_file():
            return candidate
    return None



def read_current_theme(config_file: Path = CONFIG_FILE) -> str | None:
    try:
        content = config_file.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None

    match = re.search(r"(?m)^\s*THEME\s*:\s*['\"]?([^'\"\n#]+)", content)
    if match is None:
        return None
    return match.group(1).strip()


def replace_current_theme_name(
    old_name: str,
    new_name: str,
    config_file: Path = CONFIG_FILE,
) -> None:
    try:
        content = config_file.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Could not find {config_file}") from exc

    pattern = re.compile(r"(?m)^(\s*THEME\s*:\s*)([^#\n]*)(\s*(?:#.*)?)$")
    match = pattern.search(content)
    if match is None:
        raise RuntimeError("Could not find THEME in config.yaml")

    configured = match.group(2).strip().strip("'\"")
    if configured != old_name:
        raise RuntimeError(f"config.yaml THEME is {configured}, expected {old_name}.")

    replacement = f"{match.group(1)}{new_name}{match.group(3)}"
    new_content = content[: match.start()] + replacement + content[match.end() :]
    tmp_file = config_file.with_name(f"{config_file.name}.tmp")
    tmp_file.write_text(new_content, encoding="utf-8")
    os.replace(tmp_file, config_file)


def theme_display_size_from_yaml(yaml_file: Path | None) -> str:
    if yaml_file is None:
        return ""
    return normalize_display_size(read_scalar_from_yaml_text(yaml_file, "DISPLAY_SIZE"))


def selected_display_size(config_file: Path = CONFIG_FILE) -> str:
    for key in ("DISPLAY_SIZE", "SCREEN_SIZE", "SIZE"):
        value = normalize_display_size(read_scalar_from_yaml_text(config_file, key))
        if value:
            return value

    current = read_current_theme(config_file)
    if not current:
        return ""

    current_yaml = find_theme_file(THEMES_DIR / current)
    return theme_display_size_from_yaml(current_yaml)


def set_current_theme(record: ThemeRecord, config_file: Path = CONFIG_FILE) -> tuple[str | None, str]:
    if not record.editable:
        raise RuntimeError(
            f"{record.name} cannot be set as current because it has no theme.yaml/theme.yml."
        )

    try:
        content = config_file.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Could not find {config_file}") from exc

    old_theme = read_current_theme(config_file)
    pattern = re.compile(r"(?m)^(\s*THEME\s*:\s*)([^#\n]*)(\s*(?:#.*)?)$")
    match = pattern.search(content)
    if match is None:
        raise RuntimeError("Could not find THEME in config.yaml")

    replacement = f"{match.group(1)}{record.name}{match.group(3)}"
    new_content = content[: match.start()] + replacement + content[match.end() :]
    tmp_file = config_file.with_name(f"{config_file.name}.tmp")
    tmp_file.write_text(new_content, encoding="utf-8")
    os.replace(tmp_file, config_file)
    return old_theme, record.name


def duplicate_theme(record: ThemeRecord, requested_name: str) -> str:
    if not record.editable:
        raise RuntimeError(
            f"{record.name} cannot be duplicated because it has no theme.yaml/theme.yml."
        )
    ensure_theme_child(record.directory)

    target_name = sanitize_theme_folder_name(requested_name)
    if not target_name:
        raise ValueError("Choose a valid theme folder name.")

    target_dir = THEMES_DIR / target_name
    if target_dir.exists():
        raise FileExistsError(f"A theme named {target_name} already exists.")

    shutil.copytree(
        record.directory,
        target_dir,
        symlinks=False,
        ignore=shutil.ignore_patterns(*IGNORE_PATTERNS),
    )
    return target_name


def rename_theme(record: ThemeRecord, requested_name: str) -> str:
    if not record.directory.is_dir():
        raise FileNotFoundError(record.directory)
    ensure_theme_child(record.directory)

    target_name = sanitize_theme_folder_name(requested_name)
    if not target_name:
        raise ValueError("Choose a valid theme folder name.")
    if target_name == record.name:
        raise ValueError("Choose a different theme name.")

    target_dir = THEMES_DIR / target_name
    if target_dir.exists():
        raise FileExistsError(f"A theme named {target_name} already exists.")

    record.directory.rename(target_dir)
    if record.current:
        try:
            replace_current_theme_name(record.name, target_name)
        except Exception:
            if target_dir.exists() and not record.directory.exists():
                target_dir.rename(record.directory)
            raise
    return target_name


def delete_theme(record: ThemeRecord) -> None:
    if record.current:
        raise RuntimeError("The current theme cannot be deleted. Choose another theme first.")
    if not record.directory.is_dir():
        raise FileNotFoundError(record.directory)
    ensure_theme_child(record.directory)

    theme_file = Gio.File.new_for_path(str(record.directory))
    try:
        if theme_file.trash(None):
            return
    except Exception as exc:
        raise RuntimeError(f"Could not move theme to Trash: {exc}") from exc

    raise RuntimeError("Could not move theme to Trash.")


def validate_zip_members(zip_file: zipfile.ZipFile) -> None:
    for member in zip_file.infolist():
        member_path = Path(member.filename)
        if member_path.is_absolute() or ".." in member_path.parts:
            raise RuntimeError(f"Unsafe archive path: {member.filename}")


def resolve_import_theme_source(path: Path) -> Path:
    if find_theme_file(path) is not None:
        return path

    directories = [child for child in path.iterdir() if child.is_dir()]
    theme_directories = [child for child in directories if find_theme_file(child) is not None]
    if len(theme_directories) == 1:
        return theme_directories[0]
    if not theme_directories:
        raise RuntimeError("Imported folder/archive does not contain theme.yaml/theme.yml.")
    raise RuntimeError("Imported folder/archive contains multiple themes. Import one at a time.")


def copy_imported_theme(source_dir: Path) -> str:
    yaml_file = find_theme_file(source_dir)
    if yaml_file is None:
        raise RuntimeError("Imported theme does not contain theme.yaml/theme.yml.")

    target_name = next_available_theme_name(source_dir.name)
    target_dir = THEMES_DIR / target_name
    shutil.copytree(
        source_dir,
        target_dir,
        symlinks=False,
        ignore=shutil.ignore_patterns(*IGNORE_PATTERNS),
    )
    return target_name


def import_theme(source_path_text: str) -> str:
    source_path = Path(source_path_text).expanduser()
    if not source_path.exists():
        raise FileNotFoundError(source_path)

    if source_path.is_dir():
        return copy_imported_theme(resolve_import_theme_source(source_path))

    if source_path.is_file() and source_path.suffix.casefold() == ".zip":
        with tempfile.TemporaryDirectory(prefix="turing-theme-import-") as tmp_dir:
            tmp_path = Path(tmp_dir)
            with zipfile.ZipFile(source_path) as archive:
                validate_zip_members(archive)
                archive.extractall(tmp_path)
            return copy_imported_theme(resolve_import_theme_source(tmp_path))

    raise RuntimeError("Import expects a theme folder or a .zip archive.")


def should_skip_export_path(path: Path) -> bool:
    name = path.name
    if name == "__pycache__":
        return True
    return any(path.match(pattern) for pattern in IGNORE_PATTERNS)


def resolve_export_destination(record: ThemeRecord, destination_text: str) -> Path:
    value = destination_text.strip()
    if not value:
        destination = default_export_path(record.name)
    else:
        destination = Path(value).expanduser()
        if destination.exists() and destination.is_dir():
            destination = destination / f"{record.name}.zip"
        elif destination.suffix.casefold() != ".zip":
            destination = destination.with_suffix(".zip")

    if destination.exists():
        raise FileExistsError(f"Export already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


def export_theme(record: ThemeRecord, destination_text: str = "") -> Path:
    if not record.directory.is_dir():
        raise FileNotFoundError(record.directory)
    ensure_theme_child(record.directory)
    if find_theme_file(record.directory) is None:
        raise RuntimeError("Theme cannot be exported because it has no theme.yaml/theme.yml.")

    destination = resolve_export_destination(record, destination_text)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=str(destination.parent),
    )
    os.close(fd)
    tmp_path = Path(tmp_name)

    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(record.directory.rglob("*")):
                if any(should_skip_export_path(parent) for parent in [path, *path.parents]):
                    continue
                if path.is_dir():
                    continue
                relative = path.relative_to(record.directory)
                archive.write(path, Path(record.name) / relative)
        os.replace(tmp_path, destination)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    return destination


def discover_themes(
    themes_dir: Path = THEMES_DIR,
    config_file: Path = CONFIG_FILE,
    *,
    only_compatible: bool = True,
) -> list[ThemeRecord]:
    current_theme = read_current_theme(config_file)
    target_display_size = selected_display_size(config_file) if only_compatible else ""
    records: list[ThemeRecord] = []

    if not themes_dir.is_dir():
        return records

    for theme_dir in sorted(
        (path for path in themes_dir.iterdir() if path.is_dir()),
        key=lambda path: path.name.casefold(),
    ):
        yaml_file = find_theme_file(theme_dir)
        display_size = theme_display_size_from_yaml(yaml_file)

        if only_compatible and target_display_size and display_size != target_display_size:
            continue

        issue = None
        if yaml_file is None:
            issue = "Missing theme.yaml"
        elif target_display_size and not display_size:
            issue = "Missing DISPLAY_SIZE"

        records.append(
            ThemeRecord(
                name=theme_dir.name,
                directory=theme_dir,
                yaml_file=yaml_file,
                preview_file=theme_dir / "preview.png",
                current=theme_dir.name == current_theme,
                issue=issue,
                display_size=display_size,
            )
        )

    return sorted(records, key=lambda record: (not record.current, record.name.casefold()))


def filter_theme_records(records: list[ThemeRecord], query: str) -> list[ThemeRecord]:
    terms = [term.casefold() for term in query.split() if term.strip()]
    if not terms:
        return list(records)
    return [record for record in records if all(term in record.search_text() for term in terms)]


def build_theme_gallery_diagnostics_report(
    record: ThemeRecord,
    target_display_size: str = "",
) -> str:
    lines: list[str] = [
        "Theme Gallery Diagnostics",
        "=========================",
        "",
        f"Theme: {record.name}",
        f"Status: {record.status_label}",
        f"Current theme: {'yes' if record.current else 'no'}",
        f"Target display: {target_display_size or 'unknown'}",
        f"Theme display: {record.display_size or 'unknown'}",
        f"Theme folder: {relative_path_label(record.directory)}",
    ]

    if record.yaml_file is not None:
        lines.append(f"Theme YAML: {relative_path_label(record.yaml_file)}")
        try:
            stat = record.yaml_file.stat()
            lines.append(f"Theme YAML size: {stat.st_size} bytes")
        except OSError as exc:
            lines.append(f"Theme YAML status: stat failed: {exc}")
        try:
            yaml_text = record.yaml_file.read_text(encoding="utf-8")
            lines.append(f"Theme YAML lines: {len(yaml_text.splitlines())}")
        except OSError as exc:
            lines.append(f"Theme YAML status: read failed: {exc}")
        except UnicodeDecodeError as exc:
            lines.append(f"Theme YAML status: decode failed: {exc}")
    else:
        lines.append("Theme YAML: missing")

    if record.preview_file.is_file():
        lines.append(f"Preview: {relative_path_label(record.preview_file)}")
        try:
            stat = record.preview_file.stat()
            lines.append(f"Preview size: {stat.st_size} bytes")
        except OSError as exc:
            lines.append(f"Preview status: stat failed: {exc}")
    else:
        lines.append("Preview: missing")

    try:
        children = list(record.directory.iterdir())
        file_count = sum(1 for child in children if child.is_file())
        dir_count = sum(1 for child in children if child.is_dir())
        lines.append(f"Top-level files: {file_count}")
        lines.append(f"Top-level folders: {dir_count}")
    except OSError as exc:
        lines.append(f"Theme folder status: list failed: {exc}")

    lines.extend(
        [
            "",
            "Gallery checks:",
            f"- Compatible with target display: {'yes' if not target_display_size or record.display_size == target_display_size else 'no'}",
            f"- Editable in GTK Theme Editor: {'yes' if record.editable else 'no'}",
            f"- Has preview image: {'yes' if record.preview_file.is_file() else 'no'}",
            f"- Has theme.yaml/theme.yml: {'yes' if record.yaml_file is not None else 'no'}",
        ]
    )
    if record.issue:
        lines.append(f"- Blocking issue: {record.issue}")
    return "\n".join(lines)


def launch_theme_editor(record: ThemeRecord, theme_editor: Path = THEME_EDITOR) -> None:
    if not record.editable:
        raise RuntimeError(
            f"{record.name} cannot be opened because it has no theme.yaml/theme.yml."
        )
    if not theme_editor.is_file():
        raise FileNotFoundError(f"Could not find {theme_editor}")

    subprocess.Popen(
        [sys.executable, str(theme_editor), record.name],
        cwd=str(ROOT),
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def open_path_with_default_app(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)

    errors: list[str] = []
    uri = path.resolve().as_uri()
    try:
        launched = Gio.AppInfo.launch_default_for_uri(uri, None)
        if launched:
            return
        errors.append("Gio launch_default_for_uri returned false")
    except Exception as exc:
        errors.append(f"Gio launch_default_for_uri failed: {exc}")

    for command in (["gio", "open", str(path)], ["xdg-open", str(path)]):
        if shutil.which(command[0]) is None:
            errors.append(f"{command[0]} not found")
            continue
        try:
            result = subprocess.run(
                command,
                cwd=str(ROOT),
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )
        except Exception as exc:
            errors.append(f"{' '.join(command)} failed: {exc}")
            continue
        if result.returncode == 0:
            return
        stderr = result.stderr.strip() or result.stdout.strip()
        errors.append(f"{' '.join(command)} exited {result.returncode}: {stderr or 'no output'}")

    for command in (
        ["dolphin", str(path)],
        ["nautilus", str(path)],
        ["thunar", str(path)],
        ["nemo", str(path)],
        ["pcmanfm", str(path)],
    ):
        if shutil.which(command[0]) is None:
            continue
        try:
            subprocess.Popen(
                command,
                cwd=str(ROOT),
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except Exception as exc:
            errors.append(f"{' '.join(command)} failed: {exc}")
    raise RuntimeError("Could not open folder. " + " | ".join(errors))


def open_theme_folder(record: ThemeRecord) -> None:
    if not record.directory.is_dir():
        raise FileNotFoundError(record.directory)
    open_path_with_default_app(record.directory)


def show_theme_gallery_diagnostics_dialog(
    parent: Gtk.Widget,
    record: ThemeRecord,
    toast: Callable[[str], None] | None = None,
    target_display_size: str = "",
) -> None:
    report = build_theme_gallery_diagnostics_report(record, target_display_size)

    text_view = Gtk.TextView()
    text_view.set_editable(False)
    text_view.set_cursor_visible(False)
    text_view.set_monospace(True)
    text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
    text_view.get_buffer().set_text(report)

    scrolled = Gtk.ScrolledWindow()
    scrolled.set_min_content_width(520)
    scrolled.set_min_content_height(360)
    scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scrolled.set_child(text_view)

    dialog = Adw.AlertDialog(
        heading=f"Diagnostics — {record.name}",
        body="Review the gallery-level theme report below.",
    )
    dialog.set_extra_child(scrolled)
    dialog.add_response("copy", "Copy Report")
    dialog.add_response("ok", "OK")
    dialog.set_default_response("ok")
    dialog.set_close_response("ok")

    def on_response(_dialog: Adw.AlertDialog, response: str) -> None:
        if response != "copy":
            return
        parent.get_clipboard().set(report)
        if toast is not None:
            toast("Diagnostics report copied")

    dialog.connect("response", on_response)
    dialog.present(parent)


def show_set_current_theme_dialog(parent: Gtk.Widget, record: ThemeRecord, on_confirm: ThemeCallback) -> None:
    dialog = Adw.AlertDialog(
        heading=f"Use {record.name}?",
        body="This will update config.yaml so this theme becomes the current theme used by the app.",
    )
    dialog.add_response("cancel", "Cancel")
    dialog.add_response("use", "Use Theme")
    dialog.set_response_appearance("use", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("use")
    dialog.set_close_response("cancel")

    def on_response(_dialog: Adw.AlertDialog, response: str) -> None:
        if response == "use":
            on_confirm(record)

    dialog.connect("response", on_response)
    dialog.present(parent)


def show_duplicate_theme_dialog(parent: Gtk.Widget, record: ThemeRecord, on_confirm: DuplicateThemeCallback) -> None:
    entry = Gtk.Entry()
    entry.set_text(suggested_duplicate_name(record.name))
    entry.set_placeholder_text("new-theme-name")
    entry.set_activates_default(True)
    entry.set_margin_top(6)
    entry.set_margin_bottom(6)

    dialog = Adw.AlertDialog(
        heading=f"Duplicate {record.name}",
        body="Create a non-destructive copy of this theme. The copy will not become the current theme automatically.",
    )
    dialog.set_extra_child(entry)
    dialog.add_response("cancel", "Cancel")
    dialog.add_response("duplicate", "Duplicate")
    dialog.set_response_appearance("duplicate", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("duplicate")
    dialog.set_close_response("cancel")

    def on_response(_dialog: Adw.AlertDialog, response: str) -> None:
        if response == "duplicate":
            on_confirm(record, entry.get_text())

    dialog.connect("response", on_response)
    dialog.present(parent)


def show_rename_theme_dialog(parent: Gtk.Widget, record: ThemeRecord, on_confirm: RenameThemeCallback) -> None:
    entry = Gtk.Entry()
    entry.set_text(record.name)
    entry.set_placeholder_text("theme-name")
    entry.set_activates_default(True)
    entry.set_margin_top(6)
    entry.set_margin_bottom(6)

    dialog = Adw.AlertDialog(
        heading=f"Rename {record.name}",
        body="Rename the theme folder. If this is the current theme, config.yaml will be updated automatically.",
    )
    dialog.set_extra_child(entry)
    dialog.add_response("cancel", "Cancel")
    dialog.add_response("rename", "Rename")
    dialog.set_response_appearance("rename", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("rename")
    dialog.set_close_response("cancel")

    def on_response(_dialog: Adw.AlertDialog, response: str) -> None:
        if response == "rename":
            on_confirm(record, entry.get_text())

    dialog.connect("response", on_response)
    dialog.present(parent)


def show_delete_theme_dialog(parent: Gtk.Widget, record: ThemeRecord, on_confirm: DeleteThemeCallback) -> None:
    entry = Gtk.Entry()
    entry.set_placeholder_text(record.name)
    entry.set_activates_default(True)
    entry.set_margin_top(6)
    entry.set_margin_bottom(6)

    dialog = Adw.AlertDialog(
        heading=f"Delete {record.name}?",
        body="This will move the theme folder to Trash. To confirm, type the theme name exactly.",
    )
    dialog.set_extra_child(entry)
    dialog.add_response("cancel", "Cancel")
    dialog.add_response("delete", "Delete")
    dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
    dialog.set_default_response("cancel")
    dialog.set_close_response("cancel")

    def on_response(_dialog: Adw.AlertDialog, response: str) -> None:
        if response != "delete":
            return
        if entry.get_text().strip() != record.name:
            error = Adw.AlertDialog(
                heading="Theme name did not match",
                body=f"Type {record.name} exactly to delete this theme.",
            )
            error.add_response("ok", "OK")
            error.set_close_response("ok")
            error.set_default_response("ok")
            error.present(parent)
            return
        on_confirm(record)

    dialog.connect("response", on_response)
    dialog.present(parent)


def show_import_theme_dialog(parent: Gtk.Widget, on_confirm: ImportThemeCallback) -> None:
    entry = Gtk.Entry()
    entry.set_placeholder_text("/path/to/theme-folder or /path/to/theme.zip")
    entry.set_activates_default(True)
    entry.set_margin_top(6)
    entry.set_margin_bottom(6)

    dialog = Adw.AlertDialog(
        heading="Import Theme",
        body="Import a theme from a folder or .zip archive. Existing themes are never overwritten.",
    )
    dialog.set_extra_child(entry)
    dialog.add_response("cancel", "Cancel")
    dialog.add_response("import", "Import")
    dialog.set_response_appearance("import", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("import")
    dialog.set_close_response("cancel")

    def on_response(_dialog: Adw.AlertDialog, response: str) -> None:
        if response == "import":
            on_confirm(entry.get_text())

    dialog.connect("response", on_response)
    dialog.present(parent)


def show_export_theme_dialog(parent: Gtk.Widget, record: ThemeRecord, on_confirm: ExportThemeCallback) -> None:
    entry = Gtk.Entry()
    entry.set_text(str(default_export_path(record.name)))
    entry.set_placeholder_text("/path/to/theme.zip or /path/to/folder")
    entry.set_activates_default(True)
    entry.set_margin_top(6)
    entry.set_margin_bottom(6)

    dialog = Adw.AlertDialog(
        heading=f"Export {record.name}",
        body="Export this theme as a .zip archive. Existing files are never overwritten.",
    )
    dialog.set_extra_child(entry)
    dialog.add_response("cancel", "Cancel")
    dialog.add_response("export", "Export")
    dialog.set_response_appearance("export", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("export")
    dialog.set_close_response("cancel")

    def on_response(_dialog: Adw.AlertDialog, response: str) -> None:
        if response == "export":
            on_confirm(record, entry.get_text())

    dialog.connect("response", on_response)
    dialog.present(parent)


class ThemeGalleryPane(Gtk.Box):
    """Reusable gallery surface for app shell and developer window."""

    def __init__(
        self,
        *,
        on_open_theme: ThemeCallback,
        on_open_folder: ThemeCallback,
        on_theme_diagnostics: ThemeCallback | None = None,
        on_set_current_theme: ThemeCallback | None = None,
        on_sync_theme_video: ThemeCallback | None = None,
        on_duplicate_theme: DuplicateThemeCallback | None = None,
        on_rename_theme: RenameThemeCallback | None = None,
        on_delete_theme: DeleteThemeCallback | None = None,
        on_import_theme: ImportThemeCallback | None = None,
        on_export_theme: ExportThemeCallback | None = None,
        on_records_changed: Callable[[list[ThemeRecord]], None] | None = None,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.on_open_theme = on_open_theme
        self.on_open_folder = on_open_folder
        self.on_theme_diagnostics = on_theme_diagnostics
        self.on_set_current_theme = on_set_current_theme
        self.on_sync_theme_video = on_sync_theme_video
        self.on_duplicate_theme = on_duplicate_theme or self.apply_duplicate_theme
        self.on_rename_theme = on_rename_theme or self.apply_rename_theme
        self.on_delete_theme = on_delete_theme or self.apply_delete_theme
        self.on_import_theme = on_import_theme or self.apply_import_theme
        self.on_export_theme = on_export_theme or self.apply_export_theme
        self.on_records_changed = on_records_changed
        self.records: list[ThemeRecord] = []
        self.filtered_records: list[ThemeRecord] = []
        self.filter_query = ""
        self.target_display_size = ""

        controls = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_top=18,
            margin_bottom=6,
            margin_start=24,
            margin_end=24,
        )
        controls.set_hexpand(True)
        self.append(controls)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        self.search_entry.set_placeholder_text("Search compatible themes by name, path, or status")
        self.search_entry.connect("search-changed", self.on_search_changed)
        controls.append(self.search_entry)

        import_button = Gtk.Button(label="Import")
        import_button.set_tooltip_text("Import a theme folder or .zip archive")
        import_button.connect("clicked", lambda *_args: self.confirm_import_theme())
        controls.append(import_button)

        self.result_label = Gtk.Label(label="", xalign=1)
        self.result_label.add_css_class("dim-label")
        controls.append(self.result_label)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_hexpand(True)
        self.scrolled.set_vexpand(True)
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(self.scrolled)

        self.flow_box = Gtk.FlowBox(
            column_spacing=18,
            row_spacing=18,
            margin_top=18,
            margin_bottom=24,
            margin_start=24,
            margin_end=24,
        )
        self.flow_box.set_hexpand(True)
        self.flow_box.set_vexpand(True)
        self.flow_box.set_valign(Gtk.Align.START)
        self.flow_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flow_box.set_homogeneous(False)
        self.flow_box.set_min_children_per_line(2)
        self.flow_box.set_max_children_per_line(4)
        self.scrolled.set_child(self.flow_box)

        self.reload_themes(show_toast=False)

    def clear_flow_box(self) -> None:
        child = self.flow_box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.flow_box.remove(child)
            child = next_child

    def on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        self.filter_query = entry.get_text().strip()
        self.apply_filter()

    def reload_themes(self, show_toast: bool = True) -> None:
        del show_toast
        self.target_display_size = selected_display_size()
        self.records = discover_themes(only_compatible=True)
        self.apply_filter()
        if self.on_records_changed is not None:
            self.on_records_changed(list(self.records))

    def apply_filter(self) -> None:
        self.filtered_records = filter_theme_records(self.records, self.filter_query)
        self.render_records(self.filtered_records)
        self.update_result_label()

    def update_result_label(self) -> None:
        total = len(self.records)
        visible = len(self.filtered_records)
        if not total:
            display = f' for {self.target_display_size}"' if self.target_display_size else ""
            self.result_label.set_text(f"No compatible themes{display}")
            return
        if self.filter_query:
            self.result_label.set_text(f"{visible} of {total}")
            return
        display = f' · {self.target_display_size}"' if self.target_display_size else ""
        self.result_label.set_text(f"{total} compatible theme{'s' if total != 1 else ''}{display}")

    def render_records(self, records: list[ThemeRecord]) -> None:
        self.clear_flow_box()
        if not records:
            self.flow_box.append(self.empty_state())
            return
        for record in records:
            self.flow_box.append(self.theme_card(record))

    def empty_state(self) -> Gtk.Widget:
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            margin_top=80,
            margin_bottom=80,
            margin_start=80,
            margin_end=80,
        )
        box.set_size_request(320, 260)
        icon_name = "edit-find-symbolic" if self.filter_query else "folder-symbolic"
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(64)
        box.append(icon)

        title_text = "No matching compatible themes" if self.filter_query else "No compatible themes found"
        title = Gtk.Label(label=title_text)
        title.add_css_class("title-2")
        box.append(title)

        if self.filter_query:
            subtitle_text = f"No compatible theme matches “{self.filter_query}”."
        elif self.target_display_size:
            subtitle_text = f'No installed theme declares DISPLAY_SIZE {self.target_display_size}".'
        else:
            subtitle_text = "Could not detect a display size, so no compatibility filter could be applied."
        subtitle = Gtk.Label(label=subtitle_text, wrap=True, justify=Gtk.Justification.CENTER)
        subtitle.add_css_class("dim-label")
        box.append(subtitle)
        return box

    def preview_widget(self, record: ThemeRecord) -> Gtk.Widget:
        if record.preview_file.is_file():
            picture = Gtk.Picture.new_for_filename(str(record.preview_file))
            picture.set_size_request(256, 144)
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
        placeholder.set_size_request(256, 144)
        icon = Gtk.Image.new_from_icon_name("image-missing-symbolic")
        icon.set_pixel_size(48)
        placeholder.append(icon)
        label = Gtk.Label(label="No preview")
        label.add_css_class("dim-label")
        placeholder.append(label)
        return placeholder

    def theme_card(self, record: ThemeRecord) -> Gtk.Widget:
        card = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
        )
        card.add_css_class("card")
        card.set_size_request(292, 280)
        card.set_valign(Gtk.Align.START)

        preview_frame = Gtk.Frame()
        preview_frame.set_size_request(256, 144)
        preview_frame.set_child(self.preview_widget(record))
        card.append(preview_frame)

        name_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        name = Gtk.Label(label=record.name, xalign=0)
        name.set_ellipsize(Pango.EllipsizeMode.END)
        name.add_css_class("heading")
        name.set_hexpand(True)
        name_row.append(name)
        if record.current:
            badge = Gtk.Label(label="Current")
            badge.add_css_class("accent")
            name_row.append(badge)
        card.append(name_row)

        status = Gtk.Label(label=record.status_label, xalign=0, wrap=True)
        status.add_css_class("dim-label")
        card.append(status)

        display = Gtk.Label(label=record.display_label, xalign=0)
        display.add_css_class("caption")
        display.add_css_class("dim-label")
        card.append(display)

        path = Gtk.Label(label=relative_path_label(record.directory), xalign=0)
        path.set_ellipsize(Pango.EllipsizeMode.END)
        path.add_css_class("caption")
        path.add_css_class("dim-label")
        card.append(path)

        primary_actions = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_top=4,
        )

        if self.on_set_current_theme is not None and not record.current:
            use_button = Gtk.Button(label="Use")
            use_button.set_sensitive(record.editable)
            use_button.set_tooltip_text("Set this theme as current")
            use_button.connect("clicked", lambda *_args: self.on_set_current_theme(record))
            primary_actions.append(use_button)

        edit_button = Gtk.Button(label="Edit")
        edit_button.add_css_class("suggested-action")
        edit_button.set_hexpand(True)
        edit_button.set_sensitive(record.editable)
        edit_button.connect("clicked", lambda *_args: self.on_open_theme(record))
        primary_actions.append(edit_button)

        if self.on_sync_theme_video is not None:
            sync_button = Gtk.Button(label="Sync video")
            sync_button.set_sensitive(record.editable)
            sync_button.set_tooltip_text("Sync this theme video to the display")
            sync_button.connect("clicked", lambda *_args: self.on_sync_theme_video(record))
            primary_actions.append(sync_button)

        card.append(primary_actions)

        secondary_actions = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_top=2,
        )

        duplicate_button = Gtk.Button(icon_name="edit-copy-symbolic")
        duplicate_button.set_sensitive(record.editable)
        duplicate_button.set_tooltip_text("Duplicate theme")
        duplicate_button.connect("clicked", lambda *_args: self.confirm_duplicate_theme(record))
        secondary_actions.append(duplicate_button)

        rename_button = Gtk.Button(icon_name="document-edit-symbolic")
        rename_button.set_tooltip_text("Rename theme")
        rename_button.connect("clicked", lambda *_args: self.confirm_rename_theme(record))
        secondary_actions.append(rename_button)

        export_button = Gtk.Button(icon_name="document-save-symbolic")
        export_button.set_sensitive(record.editable)
        export_button.set_tooltip_text("Export theme")
        export_button.connect("clicked", lambda *_args: self.confirm_export_theme(record))
        secondary_actions.append(export_button)

        if not record.current:
            delete_button = Gtk.Button(icon_name="user-trash-symbolic")
            delete_button.add_css_class("destructive-action")
            delete_button.set_tooltip_text("Delete theme")
            delete_button.connect("clicked", lambda *_args: self.confirm_delete_theme(record))
            secondary_actions.append(delete_button)

        if self.on_theme_diagnostics is not None:
            diagnostics_button = Gtk.Button(icon_name="dialog-information-symbolic")
            diagnostics_button.set_tooltip_text("Show theme diagnostics")
            diagnostics_button.connect("clicked", lambda *_args: self.on_theme_diagnostics(record))
            secondary_actions.append(diagnostics_button)

        folder_button = Gtk.Button(icon_name="folder-open-symbolic")
        folder_button.set_tooltip_text("Open theme folder")
        folder_button.connect("clicked", lambda *_args: self.on_open_folder(record))
        secondary_actions.append(folder_button)

        card.append(secondary_actions)
        return card

    def current_theme_record(self) -> ThemeRecord | None:
        return next((record for record in self.records if record.current), None)

    def root_widget(self) -> Gtk.Widget:
        root = self.get_root()
        return root if isinstance(root, Gtk.Widget) else self

    def show_error_dialog(self, heading: str, body: str) -> None:
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("ok", "OK")
        dialog.set_close_response("ok")
        dialog.set_default_response("ok")
        dialog.present(self.root_widget())

    def show_info_dialog(self, heading: str, body: str) -> None:
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("ok", "OK")
        dialog.set_close_response("ok")
        dialog.set_default_response("ok")
        dialog.present(self.root_widget())

    def confirm_duplicate_theme(self, record: ThemeRecord) -> None:
        show_duplicate_theme_dialog(self.root_widget(), record, self.on_duplicate_theme)

    def apply_duplicate_theme(self, record: ThemeRecord, requested_name: str) -> None:
        try:
            duplicate_theme(record, requested_name)
        except Exception as exc:
            self.show_error_dialog("Could not duplicate theme", str(exc))
            return
        self.reload_themes()

    def confirm_rename_theme(self, record: ThemeRecord) -> None:
        show_rename_theme_dialog(self.root_widget(), record, self.on_rename_theme)

    def apply_rename_theme(self, record: ThemeRecord, requested_name: str) -> None:
        try:
            rename_theme(record, requested_name)
        except Exception as exc:
            self.show_error_dialog("Could not rename theme", str(exc))
            return
        self.reload_themes()

    def confirm_delete_theme(self, record: ThemeRecord) -> None:
        show_delete_theme_dialog(self.root_widget(), record, self.on_delete_theme)

    def apply_delete_theme(self, record: ThemeRecord) -> None:
        try:
            delete_theme(record)
        except Exception as exc:
            self.show_error_dialog("Could not delete theme", str(exc))
            return
        self.reload_themes()

    def confirm_import_theme(self) -> None:
        show_import_theme_dialog(self.root_widget(), self.on_import_theme)

    def apply_import_theme(self, source_path_text: str) -> None:
        try:
            import_theme(source_path_text)
        except Exception as exc:
            self.show_error_dialog("Could not import theme", str(exc))
            return
        self.reload_themes()

    def confirm_export_theme(self, record: ThemeRecord) -> None:
        show_export_theme_dialog(self.root_widget(), record, self.on_export_theme)

    def apply_export_theme(self, record: ThemeRecord, destination_text: str) -> None:
        try:
            destination = export_theme(record, destination_text)
        except Exception as exc:
            self.show_error_dialog("Could not export theme", str(exc))
            return
        self.show_info_dialog("Theme exported", str(destination))


class ThemeGalleryWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app, title="Theme Gallery", default_width=1180, default_height=760)
        self.set_size_request(860, 560)

        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        toolbar = Adw.ToolbarView()
        self.toast_overlay.set_child(toolbar)

        header = Adw.HeaderBar()
        self.window_title = Adw.WindowTitle(title="Theme Gallery", subtitle="Browse compatible themes")
        header.set_title_widget(self.window_title)
        toolbar.add_top_bar(header)

        refresh_button = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Reload the theme list")
        refresh_button.connect("clicked", lambda *_: self.reload_themes())
        header.pack_end(refresh_button)

        self.open_current_button = Gtk.Button(
            label="Open Current",
            tooltip_text="Open the current theme in the GTK Theme Editor",
        )
        self.open_current_button.add_css_class("suggested-action")
        self.open_current_button.connect("clicked", lambda *_: self.open_current_theme())
        header.pack_end(self.open_current_button)

        self.gallery = ThemeGalleryPane(
            on_open_theme=self.open_theme_editor,
            on_open_folder=self.open_theme_folder,
            on_theme_diagnostics=self.show_theme_diagnostics,
            on_set_current_theme=self.confirm_set_current_theme,
            on_records_changed=self.update_records_state,
        )
        toolbar.set_content(self.gallery)

    def toast(self, message: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast(title=message))

    def error_dialog(self, heading: str, body: str) -> None:
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("ok", "OK")
        dialog.set_close_response("ok")
        dialog.set_default_response("ok")
        dialog.present(self)

    def update_records_state(self, records: list[ThemeRecord]) -> None:
        target = self.gallery.target_display_size
        if records and target:
            subtitle = f'{len(records)} compatible theme{"s" if len(records) != 1 else ""} · {target}" display'
        elif records:
            subtitle = f'{len(records)} compatible theme{"s" if len(records) != 1 else ""}'
        elif target:
            subtitle = f'No compatible themes · {target}" display'
        else:
            subtitle = "No compatible themes found"
        self.window_title.set_subtitle(subtitle)
        self.open_current_button.set_sensitive(any(record.current for record in records))

    def reload_themes(self) -> None:
        self.gallery.reload_themes()
        self.toast("Theme list refreshed")

    def open_current_theme(self) -> None:
        record = self.gallery.current_theme_record()
        if record is None:
            self.error_dialog(
                "No current theme",
                "config.yaml does not point to a compatible theme that exists in res/themes.",
            )
            return
        self.open_theme_editor(record)

    def open_theme_editor(self, record: ThemeRecord) -> None:
        try:
            launch_theme_editor(record)
        except Exception as exc:
            self.error_dialog("Could not open theme editor", str(exc))
            return
        self.toast(f"Opening {record.name}")

    def open_theme_folder(self, record: ThemeRecord) -> None:
        try:
            open_theme_folder(record)
        except Exception as exc:
            self.error_dialog("Could not open theme folder", str(exc))
            return
        self.toast(f"Opening folder for {record.name}")

    def show_theme_diagnostics(self, record: ThemeRecord) -> None:
        show_theme_gallery_diagnostics_dialog(self, record, self.toast, self.gallery.target_display_size)

    def confirm_set_current_theme(self, record: ThemeRecord) -> None:
        show_set_current_theme_dialog(self, record, self.apply_set_current_theme)

    def apply_set_current_theme(self, record: ThemeRecord) -> None:
        try:
            old_theme, new_theme = set_current_theme(record)
        except Exception as exc:
            self.error_dialog("Could not set current theme", str(exc))
            return
        self.gallery.reload_themes()
        if old_theme and old_theme != new_theme:
            self.toast(f"Current theme changed: {old_theme} → {new_theme}")
        else:
            self.toast(f"Current theme set to {new_theme}")


class ThemeGalleryApplication(Adw.Application):
    def __init__(self, application_id: str = "io.github.turing.SmartScreen.ThemeGallery"):
        super().__init__(application_id=application_id)
        GLib.set_application_name("Theme Gallery")

    def do_activate(self):
        window = self.props.active_window
        if window is None:
            window = ThemeGalleryWindow(self)
        window.present()


def main(argv: list[str] | None = None) -> int:
    app = ThemeGalleryApplication()
    return app.run(argv or sys.argv)
