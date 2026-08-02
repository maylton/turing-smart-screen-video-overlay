from pathlib import Path
from tempfile import TemporaryDirectory
import json
import threading
import unittest

from library.renderer_lifecycle import (
    RendererConfigurationError,
    RendererController,
    select_renderer,
)


class FakeRunner:
    def __init__(self, events, fail=False):
        self.events = events
        self.fail = fail

    def start(self):
        self.events.append("start")
        if self.fail:
            raise RuntimeError("boom")

    def stop(self):
        self.events.append("stop")

    def wait(self):
        return 0


class RendererLifecycleTests(unittest.TestCase):
    def make_html_theme(self, root: Path, name="html-demo"):
        theme = root / name
        theme.mkdir()
        (theme / "index.html").write_text("<html></html>", encoding="utf-8")
        (theme / "manifest.json").write_text(json.dumps({
            "engine": "html", "name": "Demo", "version": 1,
            "display": {"width": 480, "height": 480},
            "entrypoint": "index.html", "permissions": ["sensors"],
            "network": False,
        }), encoding="utf-8")
        return theme

    def test_old_configuration_defaults_to_yaml(self):
        selection = select_renderer({"config": {"THEME": "gengar"}}, Path("/unused"))
        self.assertEqual((selection.engine, selection.theme), ("yaml", "gengar"))

    def test_explicit_html_is_discovered_and_validated(self):
        with TemporaryDirectory() as temporary:
            themes = Path(temporary)
            self.make_html_theme(themes)
            selection = select_renderer({"renderer": {"engine": "html", "theme": "html-demo"}}, themes)
            self.assertEqual(selection.manifest.width, 480)
            self.assertEqual(selection.engine, "html")

    def test_invalid_html_is_refused_before_runner_factory(self):
        calls = []
        with TemporaryDirectory() as temporary:
            with self.assertRaises(RendererConfigurationError):
                select_renderer({"renderer": {"engine": "html", "theme": "missing"}}, Path(temporary))
        self.assertEqual(calls, [])

    def test_only_one_renderer_and_reload_stops_first(self):
        events = []
        controller = RendererController({"yaml": lambda _selection: FakeRunner(events)})
        selection = select_renderer({"config": {"THEME": "x"}}, Path("/unused"))
        controller.start(selection)
        with self.assertRaises(RuntimeError):
            controller.start(selection)
        controller.reload(selection)
        self.assertEqual(events, ["start", "stop", "start"])

    def test_start_failure_closes_resources(self):
        events = []
        controller = RendererController({"yaml": lambda _selection: FakeRunner(events, fail=True)})
        selection = select_renderer({"config": {"THEME": "x"}}, Path("/unused"))
        with self.assertRaisesRegex(RuntimeError, "boom"):
            controller.start(selection)
        self.assertEqual(events, ["start", "stop"])
        self.assertFalse(controller.state.running)

    def test_wait_survives_renderer_reload(self):
        runners = []

        class BlockingRunner(FakeRunner):
            def __init__(self):
                super().__init__([])
                self.released = threading.Event()

            def stop(self):
                self.released.set()

            def wait(self):
                self.released.wait(timeout=2)
                return 0

        def factory(_selection):
            runner = BlockingRunner()
            runners.append(runner)
            return runner

        controller = RendererController({"yaml": factory})
        selection = select_renderer({"config": {"THEME": "x"}}, Path("/unused"))
        controller.start(selection)
        result = []
        waiter = threading.Thread(target=lambda: result.append(controller.wait()))
        waiter.start()

        controller.reload(selection)
        self.assertTrue(waiter.is_alive())
        self.assertEqual(len(runners), 2)

        controller.stop()
        waiter.join(timeout=2)
        self.assertFalse(waiter.is_alive())
        self.assertEqual(result, [0])


if __name__ == "__main__":
    unittest.main()
