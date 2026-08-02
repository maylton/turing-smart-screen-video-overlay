from __future__ import annotations

import builtins
import tempfile
import unittest
from pathlib import Path

from library.runtime_python import (
    DOM_INSPECT_HANDLER,
    _decode_javascript_json,
    _dom_inspection_script,
    _evaluate_json_bridge,
    _install_html_editor_build_class_hook,
    _javascript_json_script,
    _patch_html_editor_class,
    _patch_html_editor_instance,
    _query_dom_styles_message_bridge,
    _restore_build_class_hook,
    _script_message_text,
    resolve_project_python,
)


class FakeJavascriptValue:
    def __init__(self, value: str):
        self.value = value

    def to_string(self) -> str:
        return self.value


class FakeJavascriptResult:
    def __init__(self, value: str):
        self.value = FakeJavascriptValue(value)

    def get_js_value(self):
        return self.value


class RuntimePythonTests(unittest.TestCase):
    def executable(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/sh\n", encoding="utf-8")
        path.chmod(0o755)
        return path

    def test_wraps_structured_javascript_result_as_json_string(self):
        script = _javascript_json_script("(() => [{id: 'clock'}])();")
        self.assertTrue(script.startswith("JSON.stringify(("))
        self.assertIn("[{id: 'clock'}]", script)
        self.assertFalse(script.rstrip().endswith(";"))

    def test_dom_inspection_uses_native_script_message_transport(self):
        script = _dom_inspection_script(["clock", "cpu-card"])
        self.assertIn(
            f"window.webkit.messageHandlers", script
        )
        self.assertIn(f"handlers.{DOM_INSPECT_HANDLER}", script)
        self.assertIn("postMessage(JSON.stringify(message))", script)
        self.assertIn('"clock"', script)
        self.assertIn('"cpu-card"', script)
        self.assertNotIn("document.title", script)
        self.assertNotIn("evaluate_javascript_finish", script)

    def test_reads_direct_jsc_script_message(self):
        value = FakeJavascriptValue('{"payload":[]}')
        self.assertEqual(_script_message_text(value), '{"payload":[]}')

    def test_reads_legacy_webkit_javascript_result(self):
        value = FakeJavascriptResult('{"payload":[]}')
        self.assertEqual(_script_message_text(value), '{"payload":[]}')

    def test_rejects_missing_script_message(self):
        with self.assertRaises(RuntimeError):
            _script_message_text(None)

    def test_decodes_json_string_from_javascript_value(self):
        value = FakeJavascriptValue('[{"id":"clock","visible":true}]')
        self.assertEqual(
            _decode_javascript_json(value),
            [{"id": "clock", "visible": True}],
        )

    def test_rejects_missing_javascript_result(self):
        with self.assertRaises(RuntimeError):
            _decode_javascript_json(None)

    def test_patches_editor_class_before_instance_creation(self):
        class FakeEditor:
            def _evaluate_json(self, script, callback):
                raise AssertionError("legacy bridge should be replaced")

            def _query_dom_styles(self):
                raise AssertionError("legacy DOM query should be replaced")

        self.assertTrue(_patch_html_editor_class(FakeEditor))
        self.assertIs(FakeEditor._evaluate_json, _evaluate_json_bridge)
        self.assertIs(
            FakeEditor._query_dom_styles,
            _query_dom_styles_message_bridge,
        )
        self.assertTrue(FakeEditor._turing_editor_bridges_installed)
        self.assertTrue(_patch_html_editor_class(FakeEditor))

    def test_binds_bridges_directly_to_live_instance(self):
        class FakeEditor:
            def _evaluate_json(self, script, callback):
                raise AssertionError("legacy bridge should be replaced")

            def _query_dom_styles(self):
                raise AssertionError("legacy DOM query should be replaced")

        window = FakeEditor()
        self.assertTrue(_patch_html_editor_instance(window))
        self.assertIs(window._evaluate_json.__func__, _evaluate_json_bridge)
        self.assertIs(
            window._query_dom_styles.__func__,
            _query_dom_styles_message_bridge,
        )
        self.assertIs(window._evaluate_json.__self__, window)
        self.assertIs(window._query_dom_styles.__self__, window)
        self.assertTrue(window._turing_editor_bridges_instance_installed)

    def test_build_class_hook_patches_editor_synchronously(self):
        original_build_class = builtins.__build_class__
        try:
            self.assertTrue(
                _install_html_editor_build_class_hook(target_module=__name__)
            )

            class HtmlThemeEditorWindow:
                def _evaluate_json(self, script, callback):
                    raise AssertionError("legacy bridge should be replaced")

                def _query_dom_styles(self):
                    raise AssertionError("legacy DOM query should be replaced")

            self.assertIs(
                HtmlThemeEditorWindow._evaluate_json,
                _evaluate_json_bridge,
            )
            self.assertIs(
                HtmlThemeEditorWindow._query_dom_styles,
                _query_dom_styles_message_bridge,
            )
            self.assertTrue(
                HtmlThemeEditorWindow._turing_editor_bridges_installed
            )
            self.assertIs(builtins.__build_class__, original_build_class)
        finally:
            _restore_build_class_hook()
            builtins.__build_class__ = original_build_class

    def test_prefers_explicit_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            override = self.executable(root / "custom-python")
            selected = resolve_project_python(
                root,
                current="/usr/bin/python3",
                environment={"TURING_SMART_SCREEN_PYTHON": str(override)},
                user_data_home=root / "data",
            )
            self.assertEqual(selected, str(override))

    def test_prefers_local_venv_over_installed_venv(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            local = self.executable(root / "venv" / "bin" / "python3")
            self.executable(
                Path(temporary)
                / "data"
                / "turing-smart-screen"
                / "venv"
                / "bin"
                / "python3"
            )
            selected = resolve_project_python(
                root,
                current="/usr/bin/python3",
                environment={},
                user_data_home=Path(temporary) / "data",
            )
            self.assertEqual(selected, str(local))

    def test_source_tree_can_reuse_per_user_installation_venv(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            installed = self.executable(
                Path(temporary)
                / "data"
                / "turing-smart-screen"
                / "venv"
                / "bin"
                / "python3"
            )
            selected = resolve_project_python(
                root,
                current="/usr/bin/python3",
                environment={},
                user_data_home=Path(temporary) / "data",
            )
            self.assertEqual(selected, str(installed))

    def test_falls_back_to_current_python(self):
        with tempfile.TemporaryDirectory() as temporary:
            selected = resolve_project_python(
                Path(temporary) / "source",
                current="/usr/bin/python3",
                environment={},
                user_data_home=Path(temporary) / "data",
            )
            self.assertEqual(selected, "/usr/bin/python3")


if __name__ == "__main__":
    unittest.main()
