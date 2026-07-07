import unittest

from library.main_app_apply_status import _update_known_status_widgets


class Label:
    def __init__(self):
        self.text = None

    def set_label(self, text):
        self.text = text


class Window:
    pass


class MainAppApplyStatusTests(unittest.TestCase):
    def test_operation_status_only_updates_monitor_card(self):
        window = Window()
        window.theme_status_value = Label()
        window.theme_status_detail = Label()
        window.monitor_status_value = Label()
        window.monitor_status_detail = Label()
        window.display_status_value = Label()
        window.display_status_detail = Label()

        _update_known_status_widgets(
            window,
            "Starting monitor…",
            "The monitor will restart after the display is stable.",
        )

        self.assertIsNone(window.theme_status_value.text)
        self.assertIsNone(window.theme_status_detail.text)

        self.assertEqual(window.monitor_status_value.text, "Starting monitor…")
        self.assertEqual(
            window.monitor_status_detail.text,
            "The monitor will restart after the display is stable.",
        )

        self.assertIsNone(window.display_status_value.text)
        self.assertIsNone(window.display_status_detail.text)


if __name__ == "__main__":
    unittest.main()
