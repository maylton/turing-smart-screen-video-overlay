import tempfile
import unittest
from pathlib import Path

from library import display_health


class DisplayHealthTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / display_health.HEALTH_FILENAME

    def tearDown(self):
        self.directory.cleanup()

    def test_missing_file_has_no_age(self):
        self.assertIsNone(display_health.frame_age(self.path))

    def test_age_is_measured_from_last_ack(self):
        display_health.write_frame_ack(1000.0, self.path)
        self.assertEqual(display_health.frame_age(self.path, now=1012.5), 12.5)

    def test_write_replaces_previous_ack_without_leftovers(self):
        display_health.write_frame_ack(1000.0, self.path)
        display_health.write_frame_ack(1005.0, self.path)
        self.assertEqual(display_health.last_frame_ack(self.path), 1005.0)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_clear_is_idempotent(self):
        display_health.write_frame_ack(1000.0, self.path)
        display_health.clear(self.path)
        display_health.clear(self.path)
        self.assertIsNone(display_health.last_frame_ack(self.path))

    def test_corrupt_file_is_ignored(self):
        self.path.write_text("{not json", encoding="utf-8")
        self.assertIsNone(display_health.frame_age(self.path))
