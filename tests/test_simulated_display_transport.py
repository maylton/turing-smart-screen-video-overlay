from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from library.frame_pipeline import FrameAnalysis, FrameRegion
from library.simulated_display_transport import (
    BGRA32,
    BGR24,
    RGB565_BE,
    RGB565_LE,
    SimulatedDisplayTransport,
    TransportProfile,
    decode_pixels,
    encode_pixels,
    get_transport_profile,
    write_transport_artifacts,
)


class SimulatedDisplayTransportTests(unittest.TestCase):
    def test_known_rgb565_vectors_match_project_byte_order(self):
        image = Image.new("RGB", (5, 1))
        image.putdata(
            [
                (255, 0, 0),
                (0, 255, 0),
                (0, 0, 255),
                (255, 255, 255),
                (0, 0, 0),
            ]
        )

        self.assertEqual(
            encode_pixels(image, RGB565_BE),
            bytes.fromhex("f80007e0001fffff0000"),
        )
        self.assertEqual(
            encode_pixels(image, RGB565_LE),
            bytes.fromhex("00f8e0071f00ffff0000"),
        )

    def test_bgr_and_bgra_match_revision_c_layout(self):
        rgb = Image.new("RGB", (1, 1), (10, 20, 30))
        rgba = Image.new("RGBA", (1, 1), (10, 20, 30, 40))

        self.assertEqual(encode_pixels(rgb, BGR24), bytes((30, 20, 10)))
        self.assertEqual(
            encode_pixels(rgba, BGRA32),
            bytes((30, 20, 10, 40)),
        )

    def test_rgb565_roundtrip_quantizes_as_expected(self):
        image = Image.new("RGB", (1, 1), (250, 130, 65))
        payload = encode_pixels(image, RGB565_BE)
        decoded = decode_pixels(payload, (1, 1), RGB565_BE)

        red, green, blue, alpha = decoded.getpixel((0, 0))
        self.assertEqual(alpha, 255)
        self.assertLessEqual(abs(red - 250), 7)
        self.assertLessEqual(abs(green - 130), 3)
        self.assertLessEqual(abs(blue - 65), 7)

    def test_revision_c_first_frame_uses_bgra_full_payload(self):
        profile = get_transport_profile("rev-c-2inch")
        transport = SimulatedDisplayTransport(profile)
        frame = Image.new("RGBA", (4, 3), (10, 20, 30, 255))
        analysis = FrameAnalysis(
            sequence=1,
            width=4,
            height=3,
            changed_pixels=12,
            total_pixels=12,
            change_ratio=1.0,
            regions=(FrameRegion(0, 0, 4, 3),),
            full_refresh=True,
        )

        result = transport.submit(frame, analysis)

        self.assertEqual(result.encoding, BGRA32)
        self.assertEqual(result.pixel_bytes, 4 * 3 * 4)
        self.assertEqual(result.simulated_bytes, result.full_frame_bytes)
        self.assertTrue(result.roundtrip_matches)
        self.assertEqual(
            transport.framebuffer.getpixel((0, 0)),
            (10, 20, 30, 255),
        )

    def test_revision_c_partial_regions_use_bgr_and_row_metadata(self):
        profile = get_transport_profile("rev-c-2inch")
        transport = SimulatedDisplayTransport(profile, (8, 8))
        first = Image.new("RGBA", (8, 8), (0, 0, 0, 255))
        full = FrameAnalysis(
            sequence=1,
            width=8,
            height=8,
            changed_pixels=64,
            total_pixels=64,
            change_ratio=1.0,
            regions=(FrameRegion(0, 0, 8, 8),),
            full_refresh=True,
        )
        transport.submit(first, full)

        second = first.copy()
        for y in range(2, 4):
            for x in range(1, 5):
                second.putpixel((x, y), (240, 80, 40, 255))
        partial = FrameAnalysis(
            sequence=2,
            width=8,
            height=8,
            changed_pixels=8,
            total_pixels=64,
            change_ratio=0.125,
            regions=(FrameRegion(1, 2, 4, 2),),
            full_refresh=False,
        )

        result = transport.submit(second, partial)

        self.assertEqual(result.encoding, BGR24)
        self.assertEqual(result.pixel_bytes, 4 * 2 * 3)
        self.assertEqual(result.overhead_bytes, 2 * 5)
        self.assertEqual(result.simulated_bytes, 34)
        self.assertGreater(result.savings_ratio, 0.8)
        self.assertTrue(result.roundtrip_matches)
        self.assertEqual(
            transport.framebuffer.getpixel((1, 2)),
            (240, 80, 40, 255),
        )

    def test_multiple_packets_reconstruct_the_virtual_display(self):
        profile = get_transport_profile("rev-b-rgb565be")
        transport = SimulatedDisplayTransport(profile, (6, 4))
        frame = Image.new("RGBA", (6, 4), (0, 0, 0, 255))
        frame.paste((255, 0, 0, 255), (0, 0, 2, 2))
        frame.paste((0, 255, 0, 255), (4, 2, 6, 4))
        analysis = FrameAnalysis(
            sequence=2,
            width=6,
            height=4,
            changed_pixels=8,
            total_pixels=24,
            change_ratio=1 / 3,
            regions=(
                FrameRegion(0, 0, 2, 2),
                FrameRegion(4, 2, 2, 2),
            ),
            full_refresh=False,
        )

        result = transport.submit(frame, analysis)

        self.assertEqual(len(result.packets), 2)
        self.assertTrue(result.roundtrip_matches)
        self.assertEqual(
            transport.framebuffer.getpixel((0, 0))[:3],
            (255, 0, 0),
        )
        self.assertEqual(
            transport.framebuffer.getpixel((5, 3))[:3],
            (0, 255, 0),
        )

    def test_empty_update_sends_no_payload(self):
        profile = get_transport_profile("rev-a-rgb565le")
        transport = SimulatedDisplayTransport(profile, (3, 3))
        analysis = FrameAnalysis(
            sequence=2,
            width=3,
            height=3,
            changed_pixels=0,
            total_pixels=9,
            change_ratio=0.0,
            regions=(),
            full_refresh=False,
        )

        result = transport.submit(
            Image.new("RGBA", (3, 3), (0, 0, 0, 255)),
            analysis,
        )

        self.assertEqual(result.simulated_bytes, 0)
        self.assertEqual(result.savings_ratio, 1.0)
        self.assertFalse(result.packets)

    def test_artifacts_are_written_atomically(self):
        profile = get_transport_profile("rev-c-2inch")
        transport = SimulatedDisplayTransport(profile)
        frame = Image.new("RGBA", (2, 2), (1, 2, 3, 255))
        frame_analysis = FrameAnalysis(
            sequence=1,
            width=2,
            height=2,
            changed_pixels=4,
            total_pixels=4,
            change_ratio=1.0,
            regions=(FrameRegion(0, 0, 2, 2),),
            full_refresh=True,
        )
        analysis = transport.submit(frame, frame_analysis)

        with tempfile.TemporaryDirectory() as temporary:
            root = write_transport_artifacts(
                Path(temporary),
                frame,
                transport.framebuffer,
                analysis,
            )
            metrics = json.loads(
                (root / "transport-metrics.json").read_text(encoding="utf-8")
            )
            self.assertTrue((root / "latest-transport.png").is_file())
            self.assertTrue((root / "latest-transport-diff.png").is_file())
            self.assertEqual(metrics["profile"], "rev-c-2inch")
            self.assertTrue(metrics["roundtripMatches"])

    def test_invalid_profile_is_rejected(self):
        with self.assertRaises(ValueError):
            get_transport_profile("missing")
        with self.assertRaises(ValueError):
            TransportProfile("bad", "not-a-format", RGB565_LE)


if __name__ == "__main__":
    unittest.main()
