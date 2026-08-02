from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from library.html_theme_authoring import inspect_native_video_artifact
from library.html_theme_visual_editor import (
    EDITOR_METADATA_FILENAME,
    EDITOR_SCHEMA_VERSION,
    EDITOR_STYLESHEET_FILENAME,
    LEGACY_EDITOR_METADATA_FILENAME,
    OVERLAY_DOCUMENT_FORMAT,
    OVERLAY_DOCUMENT_FORMAT_VERSION,
    HtmlVisualElementStyle,
    VisualStyleHistory,
    align_visual_style,
    ensure_visual_stylesheet_link,
    ensure_widget_runtime_script,
    find_visual_slot,
    load_persisted_visual_element_ids,
    load_visual_styles,
    nudge_visual_style,
    place_visual_style,
    render_visual_stylesheet,
    render_overlay_document,
    resize_visual_style,
    save_visual_styles,
    visual_style_snapshot,
)
from library.html_theme_components import WIDGET_RUNTIME_FILENAME
from library.theme_engine import ThemeManifest, ThemeValidationError


class HtmlThemeVisualEditorTests(unittest.TestCase):
    def make_theme(self, root: Path) -> ThemeManifest:
        root.mkdir()
        (root / "index.html").write_text(
            "<!doctype html><html><head></head><body>"
            '<span id="cpu" data-turing-overlay>--%</span>'
            '<span id="ram" data-turing-overlay>-- GB</span>'
            "</body></html>",
            encoding="utf-8",
        )
        (root / "background.mp4").write_bytes(b"old video")
        (root / "manifest.json").write_text(
            json.dumps(
                {
                    "engine": "html",
                    "name": "Visual Test",
                    "version": 1,
                    "display": {"width": 480, "height": 480},
                    "entrypoint": "index.html",
                    "permissions": ["sensors"],
                    "network": False,
                    "nativeVideoOverlay": {
                        "enabled": True,
                        "localPath": "background.mp4",
                        "devicePath": "/mnt/SDCARD/video/background.mp4",
                        "fps": 24,
                        "duration": 8,
                        "backgroundFrame": 0,
                    },
                }
            ),
            encoding="utf-8",
        )
        return ThemeManifest.load(root)

    def styles(self):
        return (
            HtmlVisualElementStyle("cpu", 20, 30, 100, 40, 24, "#ffffff"),
            HtmlVisualElementStyle("ram", 200, 300, 120, 42, 22, "#aabbcc"),
        )

    def test_renders_safe_fixed_coordinate_overrides(self):
        css = render_visual_stylesheet(self.styles())
        self.assertIn('[id="cpu"]', css)
        self.assertIn("position: fixed !important", css)
        self.assertIn("--turing-editor-x: 20px", css)
        self.assertIn("--turing-editor-y: 30px", css)
        self.assertIn("left: 20px !important", css)
        self.assertIn("color: #aabbcc !important", css)

        decorated = HtmlVisualElementStyle(
            "decorated",
            10,
            10,
            80,
            30,
            18,
            "#abcdef",
            font_weight=700,
            text_align="right",
            opacity=65,
            z_index=1200,
        )
        decorated_css = render_visual_stylesheet((decorated,))
        self.assertIn("font-weight: 700 !important", decorated_css)
        self.assertIn("text-align: right !important", decorated_css)
        self.assertIn("opacity: 0.65 !important", decorated_css)
        self.assertIn("z-index: 1200 !important", decorated_css)

        bar = HtmlVisualElementStyle(
            "turing-cpu-usage-bar-1",
            30,
            50,
            160,
            12,
            16,
            "#a8c7fa",
            component_type="cpu-usage-bar",
        )
        bar_css = render_visual_stylesheet((bar,))
        self.assertIn("background: currentColor !important", bar_css)
        self.assertIn("background: rgba(255, 255, 255, 0.18) !important", bar_css)
        self.assertIn("transition: none !important", bar_css)

        effects = HtmlVisualElementStyle(
            "effects",
            10,
            80,
            180,
            48,
            28,
            "#ffffff",
            effects_managed=True,
            gradient_enabled=True,
            gradient_start_color="#ff3366",
            gradient_end_color="#33ccff",
            gradient_direction="diagonal",
            outline_width=2,
            outline_color="#101020",
            glow_radius=12,
            glow_color="#9966ff",
        )
        effects_css = render_visual_stylesheet((effects,))
        self.assertIn(
            "linear-gradient(135deg, #ff3366, #33ccff)",
            effects_css,
        )
        self.assertIn("-webkit-text-fill-color: transparent", effects_css)
        self.assertIn("-webkit-text-stroke: 2px #101020", effects_css)
        self.assertIn("text-shadow: 0 0 12px #9966ff", effects_css)

        original_bar = replace(
            effects,
            element_id="original-bar",
            element_kind="bar",
            gradient_direction="vertical",
        )
        original_bar_css = render_visual_stylesheet((original_bar,))
        self.assertIn(
            "background: linear-gradient(180deg, #ff3366, #33ccff)",
            original_bar_css,
        )
        self.assertIn("border: 2px solid #101020", original_bar_css)
        self.assertIn("box-shadow: 0 0 12px #9966ff", original_bar_css)

    def test_stylesheet_link_is_inserted_once(self):
        original = "<html><head><title>x</title></head><body></body></html>"
        updated = ensure_visual_stylesheet_link(original)
        self.assertIn(EDITOR_STYLESHEET_FILENAME, updated)
        self.assertEqual(ensure_visual_stylesheet_link(updated), updated)

    def test_runtime_script_link_is_inserted_once(self):
        original = "<html><head></head><body><main></main></body></html>"
        updated = ensure_widget_runtime_script(original)
        self.assertIn(WIDGET_RUNTIME_FILENAME, updated)
        self.assertEqual(ensure_widget_runtime_script(updated), updated)

    def test_save_updates_css_metadata_regions_and_backups(self):
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self.make_theme(Path(temporary) / "theme")
            saved = save_visual_styles(manifest, self.styles())

            self.assertEqual(load_visual_styles(saved), self.styles())
            self.assertEqual(saved.overlay_document, EDITOR_METADATA_FILENAME)
            self.assertEqual(
                saved.overlay_document_path,
                saved.root / EDITOR_METADATA_FILENAME,
            )
            self.assertTrue((saved.root / EDITOR_METADATA_FILENAME).is_file())
            document = json.loads(
                (saved.root / EDITOR_METADATA_FILENAME).read_text(encoding="utf-8")
            )
            self.assertEqual(document["format"], OVERLAY_DOCUMENT_FORMAT)
            self.assertEqual(
                document["formatVersion"],
                OVERLAY_DOCUMENT_FORMAT_VERSION,
            )
            self.assertEqual(document["display"], {"width": 480, "height": 480})
            self.assertTrue((saved.root / EDITOR_STYLESHEET_FILENAME).is_file())
            self.assertIn(
                EDITOR_STYLESHEET_FILENAME,
                saved.entrypoint_path.read_text(encoding="utf-8"),
            )
            self.assertEqual(
                [region.name for region in saved.atomic_regions],
                ["overlay:cpu", "overlay:ram"],
            )
            self.assertTrue(
                (saved.root / "manifest.json.visual.editor-backup").is_file()
            )
            self.assertTrue(
                (saved.root / "index.html.visual.editor-backup").is_file()
            )
            self.assertEqual(inspect_native_video_artifact(saved).status, "stale")

    def test_save_adds_and_removes_generated_sensor_widgets(self):
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self.make_theme(Path(temporary) / "theme")
            generated = HtmlVisualElementStyle(
                "turing-cpu-temperature-1",
                180,
                210,
                120,
                38,
                24,
                "#ffffff",
                component_type="cpu-temperature",
            )
            saved = save_visual_styles(manifest, (*self.styles(), generated))
            html = saved.entrypoint_path.read_text(encoding="utf-8")
            self.assertIn('data-turing-binding="cpu.temperature"', html)
            self.assertTrue((saved.root / WIDGET_RUNTIME_FILENAME).is_file())
            self.assertIn(
                "turing-cpu-temperature-1",
                [style.element_id for style in load_visual_styles(saved)],
            )
            self.assertIn(
                "overlay:turing-cpu-temperature-1",
                [region.name for region in saved.atomic_regions],
            )

            saved = save_visual_styles(saved, self.styles())
            self.assertNotIn(
                "turing-cpu-temperature-1",
                saved.entrypoint_path.read_text(encoding="utf-8"),
            )
            self.assertTrue((saved.root / WIDGET_RUNTIME_FILENAME).is_file())
            self.assertIn(
                WIDGET_RUNTIME_FILENAME,
                saved.entrypoint_path.read_text(encoding="utf-8"),
            )

    def test_save_persists_generated_progress_bar_structure(self):
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self.make_theme(Path(temporary) / "theme")
            bar = HtmlVisualElementStyle(
                "turing-cpu-usage-bar-1",
                180,
                210,
                160,
                12,
                16,
                "#a8c7fa",
                component_type="cpu-usage-bar",
            )
            saved = save_visual_styles(manifest, (*self.styles(), bar))
            html = saved.entrypoint_path.read_text(encoding="utf-8")
            self.assertIn('data-turing-kind="bar"', html)
            self.assertIn("data-turing-bar-fill", html)
            self.assertIn("turing-cpu-usage-bar-1", load_persisted_visual_element_ids(saved))

    def test_persisted_element_ids_ignore_unsaved_session_widgets(self):
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self.make_theme(Path(temporary) / "theme")
            session_ids = list(load_persisted_visual_element_ids(manifest))
            session_ids.append("turing-time-1")

            self.assertEqual(
                load_persisted_visual_element_ids(manifest),
                ("cpu", "ram"),
            )

    def test_persisted_element_ids_restore_saved_generated_widgets(self):
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self.make_theme(Path(temporary) / "theme")
            generated = HtmlVisualElementStyle(
                "turing-time-1",
                180,
                210,
                120,
                38,
                24,
                "#ffffff",
                component_type="time",
            )
            saved = save_visual_styles(manifest, (*self.styles(), generated))

            self.assertEqual(
                load_persisted_visual_element_ids(saved),
                ("cpu", "ram", "turing-time-1"),
            )

    def test_hidden_original_overlay_is_reversible_and_not_atomic(self):
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self.make_theme(Path(temporary) / "theme")
            hidden = (replace(self.styles()[0], visible=False), self.styles()[1])
            saved = save_visual_styles(manifest, hidden)
            css = (saved.root / EDITOR_STYLESHEET_FILENAME).read_text(
                encoding="utf-8"
            )
            self.assertIn("opacity: 0 !important", css)
            self.assertEqual(
                [region.name for region in saved.atomic_regions],
                ["overlay:ram"],
            )
            restored = save_visual_styles(
                saved,
                (replace(hidden[0], visible=True), hidden[1]),
            )
            self.assertEqual(len(restored.atomic_regions), 2)

    def test_rejects_incomplete_or_out_of_bounds_layout(self):
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self.make_theme(Path(temporary) / "theme")
            with self.assertRaises(ThemeValidationError):
                save_visual_styles(manifest, self.styles()[:1])
            invalid = list(self.styles())
            invalid[1] = HtmlVisualElementStyle(
                "ram", 450, 300, 120, 42, 22, "#aabbcc"
            )
            with self.assertRaises(ThemeValidationError):
                save_visual_styles(manifest, invalid)

    def test_move_nudge_and_alignment_remain_inside_canvas(self):
        style = self.styles()[0]
        self.assertEqual(
            (place_visual_style(
                style,
                x=999,
                y=-20,
                display_width=480,
                display_height=480,
            ).x, place_visual_style(
                style,
                x=999,
                y=-20,
                display_width=480,
                display_height=480,
            ).y),
            (380, 0),
        )
        nudged = nudge_visual_style(
            style,
            dx=-50,
            dy=500,
            display_width=480,
            display_height=480,
        )
        self.assertEqual((nudged.x, nudged.y), (0, 440))
        centered = align_visual_style(
            style,
            "horizontal-center",
            display_width=480,
            display_height=480,
        )
        self.assertEqual((centered.x, centered.y), (190, 30))
        bottom = align_visual_style(
            centered,
            "bottom",
            display_width=480,
            display_height=480,
        )
        self.assertEqual((bottom.x, bottom.y), (190, 440))

        resized = resize_visual_style(
            style,
            x=450,
            y=-10,
            width=100,
            height=900,
            display_width=480,
            display_height=480,
        )
        self.assertEqual(
            (resized.x, resized.y, resized.width, resized.height),
            (450, 0, 30, 480),
        )

        slot = find_visual_slot(
            (HtmlVisualElementStyle("occupied", 0, 0, 120, 40, 16, "#ffffff"),),
            width=120,
            height=40,
            display_width=480,
            display_height=480,
        )
        self.assertEqual(slot, (120, 0))

    def test_loads_version_one_metadata_with_non_destructive_defaults(self):
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self.make_theme(Path(temporary) / "theme")
            (manifest.root / LEGACY_EDITOR_METADATA_FILENAME).write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "elements": [style.as_dict() for style in self.styles()],
                    }
                ),
                encoding="utf-8",
            )
            loaded = load_visual_styles(manifest)
            self.assertEqual(loaded[0].font_weight, 0)
            self.assertEqual(loaded[0].text_align, "inherit")
            self.assertEqual(loaded[0].opacity, 100)
            self.assertEqual(loaded[0].z_index, 1000)
            self.assertEqual(loaded[0].element_kind, "text")
            self.assertFalse(loaded[0].effects_managed)

    def test_loads_version_three_metadata_and_round_trips_effects(self):
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self.make_theme(Path(temporary) / "theme")
            legacy_elements = []
            for style in self.styles():
                value = style.as_dict()
                for key in (
                    "elementKind",
                    "effectsManaged",
                    "gradientEnabled",
                    "gradientStartColor",
                    "gradientEndColor",
                    "gradientDirection",
                    "outlineWidth",
                    "outlineColor",
                    "glowRadius",
                    "glowColor",
                ):
                    value.pop(key)
                legacy_elements.append(value)
            legacy_path = manifest.root / LEGACY_EDITOR_METADATA_FILENAME
            legacy_path.write_text(
                json.dumps({"schemaVersion": 3, "elements": legacy_elements}),
                encoding="utf-8",
            )
            legacy = load_visual_styles(manifest)
            self.assertFalse(legacy[0].effects_managed)

            styled = replace(
                legacy[0],
                effects_managed=True,
                gradient_enabled=True,
                gradient_start_color="#ff0000",
                gradient_end_color="#0000ff",
                gradient_direction="vertical",
                outline_width=1,
                outline_color="#222222",
                glow_radius=8,
                glow_color="#66e0ff",
            )
            saved = save_visual_styles(manifest, (styled, legacy[1]))
            metadata = json.loads(
                (saved.root / EDITOR_METADATA_FILENAME).read_text(encoding="utf-8")
            )
            self.assertEqual(metadata["schemaVersion"], EDITOR_SCHEMA_VERSION)
            self.assertFalse(legacy_path.exists())
            self.assertTrue(
                legacy_path.with_name(
                    f"{LEGACY_EDITOR_METADATA_FILENAME}.visual.editor-backup"
                ).is_file()
            )
            self.assertEqual(load_visual_styles(saved)[0], styled)

    def test_canonical_overlay_document_takes_precedence_over_legacy_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self.make_theme(Path(temporary) / "theme")
            legacy = (self.styles()[0], replace(self.styles()[1], color="#ff0000"))
            (manifest.root / LEGACY_EDITOR_METADATA_FILENAME).write_text(
                json.dumps(
                    {
                        "schemaVersion": 4,
                        "elements": [style.as_dict() for style in legacy],
                    }
                ),
                encoding="utf-8",
            )
            (manifest.root / EDITOR_METADATA_FILENAME).write_text(
                render_overlay_document(manifest, self.styles()),
                encoding="utf-8",
            )

            self.assertEqual(load_visual_styles(manifest), self.styles())

    def test_rejects_overlay_document_for_a_different_display(self):
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self.make_theme(Path(temporary) / "theme")
            payload = json.loads(render_overlay_document(manifest, self.styles()))
            payload["display"]["width"] = 320
            (manifest.root / EDITOR_METADATA_FILENAME).write_text(
                json.dumps(payload),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ThemeValidationError, "display"):
                load_visual_styles(manifest)

    def test_history_supports_bounded_undo_and_redo(self):
        first = {style.element_id: style for style in self.styles()}
        second = dict(first)
        second["cpu"] = nudge_visual_style(
            second["cpu"],
            dx=5,
            dy=0,
            display_width=480,
            display_height=480,
        )
        third = dict(second)
        third["cpu"] = nudge_visual_style(
            third["cpu"],
            dx=5,
            dy=0,
            display_width=480,
            display_height=480,
        )

        history = VisualStyleHistory(limit=2)
        history.record(first)
        history.record(second)
        self.assertEqual(history.undo(third), visual_style_snapshot(second))
        self.assertEqual(history.undo(second), visual_style_snapshot(first))
        self.assertIsNone(history.undo(first))
        self.assertEqual(history.redo(first), visual_style_snapshot(second))
        history.record(third)
        self.assertFalse(history.can_redo)

    def test_gtk_editor_exposes_direct_manipulation_contract(self):
        source = (
            Path(__file__).resolve().parents[1] / "html-theme-editor-gtk.py"
        ).read_text(encoding="utf-8")
        self.assertIn("turing-editor-drag:", source)
        self.assertIn("turing-editor-resize:", source)
        self.assertIn("turing-editor-nudge:", source)
        self.assertIn("pointerdown", source)
        self.assertIn("pointermove", source)
        self.assertIn("VisualStyleHistory(limit=100)", source)
        self.assertIn('application.set_accels_for_action("win.undo"', source)
        self.assertIn("_align_selected", source)
        self.assertIn("Alinhar arraste à grade de 5 px", source)
        self.assertIn("data-turing-resize-handle", source)
        self.assertIn("Peso da fonte", source)
        self.assertIn("Alinhamento do texto", source)
        self.assertIn("Opacidade (%)", source)
        self.assertIn("Camada", source)
        self.assertIn("Dados de teste", source)
        self.assertIn("Valores máximos", source)
        self.assertIn("Sensores indisponíveis", source)
        self.assertIn("Mostrar somente o overlay enviado ao dispositivo", source)
        self.assertIn("__turingEditorSetOverlayMode", source)
        self.assertIn("overlay-editor", source)
        self.assertIn('spin.connect("changed", self._on_spin_text_changed)', source)
        self.assertIn("def _on_spin_text_changed", source)
        self.assertIn("Adicionar elemento", source)
        self.assertIn("Excluir elemento criado", source)
        self.assertIn("Restaurar elemento", source)
        self.assertIn("_on_add_component", source)
        self.assertIn("_on_remove_element", source)
        self.assertIn("_sync_preview_elements", source)
        self.assertIn("_restore_persisted_element_structure", source)
        self.assertIn("__turingPositionEditorElement", source)
        self.assertIn("Usar degradê", source)
        self.assertIn("Cor inicial do degradê", source)
        self.assertIn("Contorno (px)", source)
        self.assertIn("Brilho (px)", source)
        self.assertIn("Aplicar efeitos como", source)
        self.assertIn("def _on_effect_changed", source)
        self.assertIn("effectsManaged", source)
        self.assertIn("Gtk.StackSwitcher", source)
        self.assertIn('"elements", "Elementos"', source)
        self.assertIn('"layout", "Layout"', source)
        self.assertIn('"style", "Estilo"', source)
        self.assertIn('"effects", "Efeitos"', source)
        self.assertIn("actions.set_column_homogeneous(True)", source)


if __name__ == "__main__":
    unittest.main()
