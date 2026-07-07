import logging
import os
import unittest
from unittest import mock

from library.log import VideoOverlayNoiseFilter


class VideoOverlayNoiseFilterTests(unittest.TestCase):
    def make_record(self, message: str) -> logging.LogRecord:
        return logging.LogRecord(
            name="turing",
            level=logging.DEBUG,
            pathname=__file__,
            lineno=1,
            msg=message,
            args=(),
            exc_info=None,
        )

    def test_hides_overlay_frame_latency_debug_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            filt = VideoOverlayNoiseFilter()
            record = self.make_record("Video overlay latest frame sent in 0.42s")
            self.assertFalse(filt.filter(record))

    def test_allows_overlay_frame_latency_debug_when_explicitly_enabled(self):
        with mock.patch.dict(os.environ, {"TURING_VIDEO_OVERLAY_DEBUG": "1"}, clear=True):
            filt = VideoOverlayNoiseFilter()
            record = self.make_record("Video overlay latest frame sent in 0.42s")
            self.assertTrue(filt.filter(record))

    def test_keeps_unrelated_debug_messages(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            filt = VideoOverlayNoiseFilter()
            record = self.make_record("Display detection completed")
            self.assertTrue(filt.filter(record))


if __name__ == "__main__":
    unittest.main()
