#!/usr/bin/env python3
"""Apply read-only theme diagnostics dialog to theme-editor-gtk.py.

This implements the next slice from docs/THEME_EDITOR_ROADMAP_STATUS.md:
a supportability-oriented diagnostics report for the currently loaded theme.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()
TARGET = ROOT / "theme-editor-gtk.py"


def replace_once(text: str, old: str, new: str, marker: str) -> str:
    if marker in text:
        print(f"SKIP: {marker!r} already present")
        return text
    if old not in text:
        raise SystemExit(f"Could not find expected block for {marker!r}")
    print(f"OK: adding {marker}")
    return text.replace(old, new, 1)


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '''        overflow_box.append(
            popover_action_button(
                "Reload Theme From Disk",
                "view-refresh-symbolic",
                self.confirm_reload_theme_from_disk,
                overflow_popover,
            )
        )
        overflow_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
''',
        '''        overflow_box.append(
            popover_action_button(
                "Reload Theme From Disk",
                "view-refresh-symbolic",
                self.confirm_reload_theme_from_disk,
                overflow_popover,
            )
        )
        overflow_box.append(
            popover_action_button(
                "Theme Diagnostics",
                "dialog-information-symbolic",
                self.show_theme_diagnostics,
                overflow_popover,
            )
        )
        overflow_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
''',
        '"Theme Diagnostics"',
    )

    text = replace_once(
        text,
        '''    def copy_text_to_clipboard(self, text, label):
''',
        '''    def iter_theme_nodes(self, node=None, path=()):
        if node is None:
            node = self.theme_data

        yield path, node

        if isinstance(node, dict):
            for key, value in node.items():
                yield from self.iter_theme_nodes(value, path + (key,))
        elif isinstance(node, (list, tuple)):
            for index, value in enumerate(node):
                yield from self.iter_theme_nodes(value, path + (index,))

    @staticmethod
    def diagnostics_path_label(path):
        if not path:
            return "(root)"
        return " / ".join(str(part) for part in path)

    @staticmethod
    def diagnostics_bool_label(value):
        if value is True:
            return "yes"
        if value is False:
            return "no"
        if value is None:
            return "not set"
        return str(value)

    @staticmethod
    def looks_like_asset_reference(key, value):
        raw = str(value or "").strip()
        if not raw:
            return False
        if raw.startswith(("http://", "https://", "rtsp://")):
            return False

        lower = raw.lower()
        known_extensions = (
            ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp",
            ".mp4", ".mov", ".mkv", ".webm", ".avi",
            ".ttf", ".otf",
        )
        if lower.endswith(known_extensions):
            return True

        asset_keys = {
            "PATH",
            "BACKGROUND_IMAGE",
            "PREVIEW_BACKGROUND",
            "SOURCE",
            "SOURCE_PATH",
            "LOCAL_PATH",
            "IMAGE",
            "VIDEO",
            "MEDIA",
            "FILE",
        }
        upper_key = str(key or "").upper()
        return upper_key in asset_keys and (
            "/" in raw or "\\\\" in raw or "." in Path(raw).name
        )

    def theme_missing_asset_references(self):
        missing = []
        skipped_unsafe = []

        for path, node in self.iter_theme_nodes():
            if not isinstance(node, dict):
                continue
            for key, value in node.items():
                if not isinstance(value, str):
                    continue
                if not self.looks_like_asset_reference(key, value):
                    continue

                raw = value.strip()
                candidate = Path(raw).expanduser()
                if not candidate.is_absolute():
                    if any(part == ".." for part in candidate.parts):
                        skipped_unsafe.append(
                            f"{self.diagnostics_path_label(path + (key,))}: {raw}"
                        )
                        continue
                    candidate = self.theme_dir / candidate

                try:
                    exists = candidate.is_file()
                except OSError:
                    exists = False

                if not exists:
                    missing.append(
                        f"{self.diagnostics_path_label(path + (key,))}: {raw}"
                    )

        return missing, skipped_unsafe

    def build_theme_diagnostics_report(self):
        nodes = list(self.iter_theme_nodes())
        mapping_nodes = [node for _path, node in nodes if isinstance(node, dict)]
        sequence_nodes = [node for _path, node in nodes if isinstance(node, (list, tuple))]

        visible = hidden = enabled = disabled = overlay_enabled = overlay_disabled = 0
        text_nodes = image_nodes = video_reference_nodes = 0

        image_extensions = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
        video_extensions = (".mp4", ".mov", ".mkv", ".webm", ".avi")

        for _path, node in nodes:
            if not isinstance(node, dict):
                continue

            if isinstance(node.get("SHOW"), bool):
                if node.get("SHOW"):
                    visible += 1
                else:
                    hidden += 1
            if isinstance(node.get("ENABLED"), bool):
                if node.get("ENABLED"):
                    enabled += 1
                else:
                    disabled += 1
            if isinstance(node.get("OVERLAY"), bool):
                if node.get("OVERLAY"):
                    overlay_enabled += 1
                else:
                    overlay_disabled += 1

            if "TEXT" in node or "FORMAT" in node:
                text_nodes += 1

            string_values = [
                value.strip().lower()
                for value in node.values()
                if isinstance(value, str)
            ]
            if any(value.endswith(image_extensions) for value in string_values):
                image_nodes += 1
            if any(value.endswith(video_extensions) for value in string_values):
                video_reference_nodes += 1

        video_node = self.theme_data.get("video") if isinstance(self.theme_data, dict) else None
        video_lines = []
        if isinstance(video_node, dict):
            for key in ("SHOW", "ENABLED", "OVERLAY", "PATH", "MODE"):
                if key in video_node:
                    video_lines.append(f"  - {key}: {video_node[key]}")
        else:
            video_lines.append("  - video node: not present")

        external_change = self.theme_file_changed_on_disk()
        pending_edits = self.has_pending_property_edits()
        missing_assets, skipped_unsafe = self.theme_missing_asset_references()

        try:
            media_report = inspect_generated_media(self.theme_dir, self.theme_data)
        except Exception as exc:
            media_report = None
            media_error = str(exc)
        else:
            media_error = None

        lines = [
            "GTK Theme Editor Diagnostics",
            "============================",
            "",
            "Theme",
            "-----",
            f"Name: {self.theme_name}",
            f"Folder: {self.theme_dir}",
            f"YAML: {self.theme_file}",
            f"File signature: {self.theme_file_signature}",
            f"Changed externally: {self.diagnostics_bool_label(external_change)}",
            f"Pending property edits: {self.diagnostics_bool_label(pending_edits)}",
            f"Selected path: {self.diagnostics_path_label(self.selected_path or ())}",
            "",
            "Structure",
            "---------",
            f"Mapping nodes: {len(mapping_nodes)}",
            f"Sequence nodes: {len(sequence_nodes)}",
            f"Visible SHOW nodes: {visible}",
            f"Hidden SHOW nodes: {hidden}",
            f"Enabled nodes: {enabled}",
            f"Disabled nodes: {disabled}",
            f"Text-like nodes: {text_nodes}",
            f"Image-reference nodes: {image_nodes}",
            f"Video-reference nodes: {video_reference_nodes}",
            "",
            "Video",
            "-----",
            f"Overlay true nodes: {overlay_enabled}",
            f"Overlay false nodes: {overlay_disabled}",
            *video_lines,
            "",
            "Generated media",
            "---------------",
        ]

        if media_report is None:
            lines.append(f"Could not inspect generated media: {media_error}")
        else:
            status_counts = {
                GeneratedMediaStatus.IN_USE.value: 0,
                GeneratedMediaStatus.UNUSED.value: 0,
                GeneratedMediaStatus.ORPHANED.value: 0,
                GeneratedMediaStatus.UNMANAGED.value: 0,
            }
            records_with_issues = []
            for record in media_report.records:
                status_counts[record.status.value] = status_counts.get(record.status.value, 0) + 1
                if record.issues:
                    records_with_issues.append(record)

            lines.extend([
                f"Manifest: {media_report.manifest_path}",
                f"Manifest valid: {self.diagnostics_bool_label(media_report.manifest_valid)}",
                f"Records: {len(media_report.records)}",
                f"In use: {status_counts.get(GeneratedMediaStatus.IN_USE.value, 0)}",
                f"Unused: {status_counts.get(GeneratedMediaStatus.UNUSED.value, 0)}",
                f"Orphaned: {status_counts.get(GeneratedMediaStatus.ORPHANED.value, 0)}",
                f"Unmanaged: {status_counts.get(GeneratedMediaStatus.UNMANAGED.value, 0)}",
                f"Records with issues: {len(records_with_issues)}",
            ])
            if media_report.manifest_error:
                lines.append(f"Manifest error: {media_report.manifest_error}")
            if records_with_issues:
                lines.append("")
                lines.append("Generated-media issues:")
                for record in records_with_issues[:12]:
                    lines.append(f"- {record.reference}: {'; '.join(record.issues)}")
                if len(records_with_issues) > 12:
                    lines.append(f"- ... {len(records_with_issues) - 12} more")

        lines.extend([
            "",
            "Missing asset references",
            "------------------------",
            f"Missing references: {len(missing_assets)}",
        ])
        for item in missing_assets[:20]:
            lines.append(f"- {item}")
        if len(missing_assets) > 20:
            lines.append(f"- ... {len(missing_assets) - 20} more")
        if skipped_unsafe:
            lines.append("")
            lines.append("Skipped unsafe relative references:")
            for item in skipped_unsafe[:10]:
                lines.append(f"- {item}")
            if len(skipped_unsafe) > 10:
                lines.append(f"- ... {len(skipped_unsafe) - 10} more")

        lines.extend([
            "",
            "Editor state",
            "------------",
            f"Undo entries: {len(self.undo_stack)}",
            f"Redo entries: {len(self.redo_stack)}",
        ])

        return "\\n".join(lines)

    def show_theme_diagnostics(self):
        try:
            report = self.build_theme_diagnostics_report()
        except Exception as exc:
            self.error_dialog("Could not build diagnostics", str(exc))
            return

        dialog = Adw.AlertDialog(
            heading="Theme diagnostics",
            body=report,
        )
        dialog.add_response("close", "Close")
        dialog.add_response("copy", "Copy Report")
        dialog.set_close_response("close")
        dialog.set_default_response("close")
        dialog.set_response_appearance(
            "copy",
            Adw.ResponseAppearance.SUGGESTED,
        )

        def response(_dialog, response_id):
            if response_id == "copy":
                self.copy_text_to_clipboard(report, "Theme diagnostics report")

        dialog.connect("response", response)
        dialog.present(self)

    def copy_text_to_clipboard(self, text, label):
''',
        "def build_theme_diagnostics_report(self):",
    )

    TARGET.write_text(text, encoding="utf-8")
    print("Theme diagnostics dialog applied to theme-editor-gtk.py")


if __name__ == "__main__":
    main()
