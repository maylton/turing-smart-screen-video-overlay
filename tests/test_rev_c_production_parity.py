# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from library.frame_pipeline import FrameAnalysis, FrameRegion
from library.rev_c_production_parity import (
    compare_with_production_driver,
    write_production_parity_artifacts,
)
from library.rev_c_protocol_simulator import RevCProtocolSimulator
from library.simulated_display_transport import (
    SimulatedDisplayTransport,
    get_transport_profile,
)


class RevCProductionParityTests(unittest.TestCase):
    def setUp(self):
        self.size = (32, 24)
        self.profile = get_transport_profile("rev-c-2inch")
        self.transport = SimulatedDisplayTransport(self.profile)
        self.protocol = RevCProtocolSimulator(display_stride=self.size[1])

    def analysis(self, sequence, regions, full_refresh):
        width, height = self.size
        changed = sum(region.area for region in regions)
        return FrameAnalysis(
            sequence=sequence,
            width=width,
            height=height,
            changed_pixels=changed,
            total_pixels=width * height,
            change_ratio=changed / (width * height),
            regions=tuple(regions),
            full_refresh=full_refresh,
        )

    def submit_full(self, frame, sequence=1):
        region = FrameRegion(0, 0, *self.size)
        transport = self.transport.submit(
            frame,
            self.analysis(sequence, (region,), True),
        )
        protocol = self.protocol.submit(transport)
        return transport, protocol

    def test_full_frame_matches_production_driver_without_serial(self):
        frame = Image.new("RGBA", self.size, (26, 42, 80, 255))
        ImageDraw.Draw(frame).rectangle((3, 4, 20, 16), fill=(220, 80, 120, 190))
        transport, protocol = self.submit_full(frame)

        with patch(
            "library.lcd.lcd_comm_rev_c.serial.Serial",
            side_effect=AssertionError("serial must never be opened"),
        ):
            parity = compare_with_production_driver(frame, transport, protocol)

        self.assertTrue(parity.valid)
        self.assertFalse(parity.physical_io)
        self.assertEqual(parity.expected_wire, parity.production_wire)
        self.assertIsNone(parity.mismatch_offset)
        self.assertEqual(len(parity.exchanges), 1)
        self.assertEqual(len(parity.exchanges[0].blocks), 5)

    def test_multiple_partial_regions_match_production_driver(self):
        base = Image.new("RGBA", self.size, (12, 18, 30, 255))
        self.submit_full(base)

        current = base.copy()
        draw = ImageDraw.Draw(current)
        first = FrameRegion(2, 3, 7, 5)
        second = FrameRegion(18, 12, 9, 6)
        draw.rectangle(
            (first.x, first.y, first.right - 1, first.bottom - 1),
            fill=(230, 120, 70, 255),
        )
        draw.rectangle(
            (second.x, second.y, second.right - 1, second.bottom - 1),
            fill=(80, 210, 160, 255),
        )
        transport = self.transport.submit(
            current,
            self.analysis(2, (first, second), False),
        )
        protocol = self.protocol.submit(transport)

        with patch(
            "library.lcd.lcd_comm_rev_c.serial.Serial",
            side_effect=AssertionError("serial must never be opened"),
        ):
            parity = compare_with_production_driver(current, transport, protocol)

        self.assertTrue(parity.valid)
        self.assertEqual(parity.expected_wire, parity.production_wire)
        self.assertEqual(
            [exchange.blocks[0].expected_read_size for exchange in parity.exchanges],
            [0, 0],
        )
        self.assertEqual(
            [exchange.blocks[-1].production_read_size for exchange in parity.exchanges],
            [1024, 1024],
        )

    def test_tampered_simulator_wire_is_detected(self):
        frame = Image.new("RGBA", self.size, (40, 60, 90, 255))
        transport, protocol = self.submit_full(frame)
        exchange = protocol.exchanges[0]
        block = exchange.blocks[0]
        tampered_wire = bytes((block.wire[0] ^ 0x01,)) + block.wire[1:]
        tampered_block = replace(block, wire=tampered_wire)
        tampered_exchange = replace(
            exchange,
            blocks=(tampered_block,) + exchange.blocks[1:],
        )
        tampered_protocol = replace(protocol, exchanges=(tampered_exchange,))

        parity = compare_with_production_driver(
            frame,
            transport,
            tampered_protocol,
        )

        self.assertFalse(parity.valid)
        self.assertEqual(parity.mismatch_offset, 0)
        self.assertEqual(parity.exchanges[0].blocks[0].mismatch_offset, 0)

    def test_artifacts_are_written_atomically(self):
        frame = Image.new("RGBA", self.size, (15, 25, 35, 255))
        transport, protocol = self.submit_full(frame)
        parity = compare_with_production_driver(frame, transport, protocol)

        with TemporaryDirectory() as temporary:
            root = write_production_parity_artifacts(
                Path(temporary),
                parity,
            )
            self.assertEqual(
                (root / "rev-c-production-wire.bin").read_bytes(),
                protocol.wire,
            )
            text = (root / "rev-c-production-parity.txt").read_text(
                encoding="utf-8"
            )
            self.assertIn("valid=True", text)
            self.assertIn("physicalIo", parity.to_json())


if __name__ == "__main__":
    unittest.main()
