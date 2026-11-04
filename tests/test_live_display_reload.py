from __future__ import annotations

import os
import signal
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from library import live_display_reload as live


class ActiveThemeTests(unittest.TestCase):
    def write(self, text: str) -> Path:
        handle = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
        handle.write(text)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return Path(handle.name)

    def test_html_renderer_theme(self):
        path = self.write('renderer:\n  engine: html\n  theme: "html-elven-reverie"\n')
        self.assertEqual(live.active_html_theme(path), "html-elven-reverie")

    def test_yaml_renderer_has_no_html_theme(self):
        path = self.write("renderer:\n  engine: yaml\n  theme: 3.5inchTheme2\n")
        self.assertEqual(live.active_html_theme(path), "")

    def test_missing_config(self):
        self.assertEqual(live.active_html_theme(Path("/nonexistent/config.yaml")), "")


class CatchesSignalTests(unittest.TestCase):
    def test_reads_sigcgt_for_this_process(self):
        previous = signal.signal(signal.SIGUSR1, lambda *_: None)
        try:
            self.assertTrue(live.catches_signal(os.getpid(), signal.SIGUSR1))
        finally:
            signal.signal(signal.SIGUSR1, previous)

    def test_default_disposition_is_not_caught(self):
        previous = signal.signal(signal.SIGUSR2, signal.SIG_DFL)
        try:
            self.assertFalse(live.catches_signal(os.getpid(), signal.SIGUSR2))
        finally:
            signal.signal(signal.SIGUSR2, previous)

    def test_unknown_process(self):
        with tempfile.TemporaryDirectory() as proc:
            self.assertFalse(live.catches_signal(12345, signal.SIGUSR1, Path(proc)))


class RequestReloadTests(unittest.TestCase):
    def test_no_monitor_running(self):
        with mock.patch.object(live, "running_monitor_pid", return_value=None), mock.patch.object(live.os, "kill") as kill:
            self.assertFalse(live.request_monitor_reload())
        kill.assert_not_called()

    def test_monitor_without_handler_is_left_alone(self):
        with mock.patch.object(live, "running_monitor_pid", return_value=4242), \
                mock.patch.object(live, "catches_signal", return_value=False), \
                mock.patch.object(live.os, "kill") as kill:
            self.assertFalse(live.request_monitor_reload())
        kill.assert_not_called()

    def test_monitor_with_handler_gets_sigusr1(self):
        with mock.patch.object(live, "running_monitor_pid", return_value=4242), \
                mock.patch.object(live, "catches_signal", return_value=True), \
                mock.patch.object(live.os, "kill") as kill:
            self.assertTrue(live.request_monitor_reload())
        kill.assert_called_once_with(4242, signal.SIGUSR1)


if __name__ == "__main__":
    unittest.main()
