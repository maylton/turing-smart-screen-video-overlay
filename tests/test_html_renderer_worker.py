from __future__ import annotations

import io
import re
import sys
import types
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

from library import html_renderer_worker
from library.html_renderer_worker import CAIRO_BRIDGE_HINT, require_cairo_bridge


WORKER_SOURCE = Path(html_renderer_worker.__file__).read_text(encoding="utf-8")


class CairoBridgePreflightTests(unittest.TestCase):
    def test_missing_converter_module_is_reported_with_install_hint(self):
        with mock.patch.dict(sys.modules, {"gi._gi_cairo": None}):
            with self.assertRaises(RuntimeError) as raised:
                require_cairo_bridge()
        message = str(raised.exception)
        self.assertIn("gi._gi_cairo", message)
        for package in ("python3-gi-cairo", "python3-gobject", "python-cairo"):
            self.assertIn(package, message)

    def test_available_converter_module_passes(self):
        gi = types.ModuleType("gi")
        gi.__path__ = []
        bridge = types.ModuleType("gi._gi_cairo")
        with mock.patch.dict(sys.modules, {"gi": gi, "gi._gi_cairo": bridge}):
            require_cairo_bridge()

    def test_preflight_runs_before_the_renderer_starts(self):
        run_body = WORKER_SOURCE.split("def run(", 1)[1]
        self.assertLess(
            run_body.index("require_cairo_bridge()"),
            run_body.index("engine = _safe_engine("),
        )

    def test_startup_failure_exits_non_zero_with_the_hint(self):
        stderr = io.StringIO()
        with (
            mock.patch.object(
                html_renderer_worker,
                "run",
                side_effect=RuntimeError(CAIRO_BRIDGE_HINT),
            ),
            redirect_stderr(stderr),
        ):
            code = html_renderer_worker.main(["--theme", "/tmp/theme"])
        self.assertEqual(code, 2)
        self.assertIn("python3-gi-cairo", stderr.getvalue())


class WorkerExitStatusContractTests(unittest.TestCase):
    def test_error_paths_mark_the_worker_as_failed(self):
        # Every diagnostic stop must go through fail(), which records a
        # non-zero exit status before quitting the GTK application.
        self.assertIsNone(
            re.search(r"print\([^\n]*\)\n\s+self\.stop\(\)", WORKER_SOURCE)
        )
        self.assertGreaterEqual(WORKER_SOURCE.count("self.fail("), 6)
        self.assertIn("self.exit_code = 1", WORKER_SOURCE)
        self.assertIn("return status or worker.exit_code", WORKER_SOURCE)


if __name__ == "__main__":
    unittest.main()
