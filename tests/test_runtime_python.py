from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from library.runtime_python import (
    _decode_javascript_json,
    _evaluate_json_bridge,
    _javascript_json_script,
    _patch_html_editor_class,
    resolve_project_python,
)


class FakeJavascriptValue:
    def __init__(self, value: str):
        self.value = value

    def to_string(self) -> str:
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

        self.assertTrue(_patch_html_editor_class(FakeEditor))
        self.assertIs(FakeEditor._evaluate_json, _evaluate_json_bridge)
        self.assertTrue(FakeEditor._turing_json_bridge_installed)
        self.assertTrue(_patch_html_editor_class(FakeEditor))

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
