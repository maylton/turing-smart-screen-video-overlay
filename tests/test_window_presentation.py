from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from library import window_presentation


class WindowPresentationTests(unittest.TestCase):
    def test_detects_hyprland_in_desktop_list(self):
        self.assertTrue(
            window_presentation.is_hyprland_session(
                {"XDG_CURRENT_DESKTOP": "Caelestia:Hyprland"}
            )
        )
        self.assertFalse(
            window_presentation.is_hyprland_session(
                {"XDG_CURRENT_DESKTOP": "GNOME"}
            )
        )

    def test_finds_only_a_valid_address_for_the_requested_pid(self):
        clients = [
            {"pid": 4, "address": "0xbad"},
            {"pid": 9, "address": "not-an-address"},
            {"pid": "9", "address": "0x12aB"},
        ]
        self.assertEqual(
            window_presentation._window_address_for_pid(clients, 9),
            "0x12aB",
        )

    def test_move_expression_targets_workspace_and_follows_window(self):
        expression = window_presentation._move_window_expression("0x12ab", 3)
        self.assertIn('window = "address:0x12ab"', expression)
        self.assertIn("workspace = 3", expression)
        self.assertIn("follow = true", expression)

    @patch.object(window_presentation.threading, "Thread")
    @patch.object(window_presentation.shutil, "which", return_value="/usr/bin/hyprctl")
    def test_schedules_presentation_without_blocking(self, _which, thread):
        worker = SimpleNamespace(start=unittest.mock.Mock())
        thread.return_value = worker

        scheduled = window_presentation.present_child_window(
            SimpleNamespace(pid=123),
            workspace_id=2,
        )

        self.assertTrue(scheduled)
        thread.assert_called_once()
        worker.start.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
