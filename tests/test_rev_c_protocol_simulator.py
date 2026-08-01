# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from library.frame_pipeline import FrameRegion
from library.rev_c_protocol_simulator import (
    BLOCK_SIZE,
    DATA_CHUNK_SIZE,
    DISPLAY_BITMAP_2INCH,
    PRE_UPDATE_BITMAP,
    QUERY_STATUS,
    START_DISPLAY_BITMAP,
    TERMINATOR,
    UPDATE_BITMAP,
    RevCProtocolSimulator,
    frame_chunked_payload,
    frame_partial_records,
    pad_to_block,
    recover_chunked_payload,
    recover_partial_records,
    write_rev_c_protocol_artifacts,
)
from library.simulated_display_transport import (
    BGRA32,
    BGR24,
    SimulatedPacket,
    TransportAnalysis,
)


def _packet(
    *,
    sequence=1,
    region=FrameRegion(0, 0, 2, 2),
    encoding=BGRA32,
    payload=None,
    full_refresh=True,
):
    bytes_per_pixel = 4 if encoding == BGRA32 else 3
    if payload is None:
        payload = bytes(
            value % 256
            for value in range(region.area * bytes_per_pixel)
        )
    return SimulatedPacket(
        sequence=sequence,
        region=region,
        encoding=encoding,
        payload=payload,
        full_refresh=full_refresh,
        row_overhead_bytes=0 if full_refresh else 5,
    )


def _transport(
    packet,
    *,
    sequence=None,
    full_frame_bytes=16,
):
    sequence = packet.sequence if sequence is None else sequence
    return TransportAnalysis(
        sequence=sequence,
        profile="rev-c-2inch",
        encoding=packet.encoding,
        full_refresh=packet.full_refresh,
        packets=(packet,),
        pixel_bytes=len(packet.payload),
        overhead_bytes=(
            packet.region.height * packet.row_overhead_bytes
        ),
        simulated_bytes=(
            len(packet.payload)
            + packet.region.height * packet.row_overhead_bytes
        ),
        full_frame_bytes=full_frame_bytes,
        savings_ratio=0.0,
        roundtrip_matches=True,
        differing_pixels=0,
    )


class RevCProtocolSimulatorTests(unittest.TestCase):
    def test_command_padding_matches_250_byte_protocol_blocks(self):
        pre = pad_to_block(PRE_UPDATE_BITMAP)
        start = pad_to_block(
            START_DISPLAY_BITMAP,
            START_DISPLAY_BITMAP[0],
        )
        self.assertEqual(len(pre), BLOCK_SIZE)
        self.assertEqual(pre[: len(PRE_UPDATE_BITMAP)], PRE_UPDATE_BITMAP)
        self.assertEqual(set(pre[len(PRE_UPDATE_BITMAP) :]), {0})
        self.assertEqual(start, bytes((0x2C,)) * BLOCK_SIZE)

    def test_full_payload_chunking_round_trips_boundaries(self):
        for length in (
            1,
            DATA_CHUNK_SIZE,
            DATA_CHUNK_SIZE + 1,
            DATA_CHUNK_SIZE * 2,
            DATA_CHUNK_SIZE * 2 + 17,
        ):
            with self.subTest(length=length):
                payload = bytes(value % 251 for value in range(length))
                wire = frame_chunked_payload(payload)
                self.assertEqual(len(wire) % BLOCK_SIZE, 0)
                self.assertEqual(
                    recover_chunked_payload(wire, len(payload)),
                    payload,
                )

    def test_invalid_full_separator_is_rejected(self):
        payload = bytes(value % 251 for value in range(300))
        wire = bytearray(frame_chunked_payload(payload))
        wire[DATA_CHUNK_SIZE] = 1
        with self.assertRaisesRegex(ValueError, "separator"):
            recover_chunked_payload(bytes(wire), len(payload))

    def test_small_partial_payload_does_not_add_249_separator(self):
        records = bytes(value % 251 for value in range(250))
        wire = frame_partial_records(records)
        self.assertEqual(wire[:250], records)
        self.assertEqual(wire[250:252], TERMINATOR)
        self.assertEqual(
            recover_partial_records(wire, len(records)),
            records,
        )

    def test_large_partial_payload_validates_separator_and_terminator(self):
        records = bytes(value % 251 for value in range(400))
        wire = frame_partial_records(records)
        self.assertEqual(wire[DATA_CHUNK_SIZE], 0)
        self.assertEqual(
            recover_partial_records(wire, len(records)),
            records,
        )
        corrupted = bytearray(wire)
        corrupted[DATA_CHUNK_SIZE] = 7
        with self.assertRaisesRegex(ValueError, "separator"):
            recover_partial_records(bytes(corrupted), len(records))

    def test_full_exchange_contains_real_command_sequence(self):
        packet = _packet()
        result = RevCProtocolSimulator().submit(_transport(packet))
        self.assertTrue(result.valid)
        self.assertEqual(result.mode, "full")
        exchange = result.exchanges[0]
        self.assertEqual(
            [block.name for block in exchange.blocks],
            [
                "pre-update",
                "start-display",
                "display-bitmap-2inch",
                "full-pixels",
                "query-status",
            ],
        )
        self.assertEqual(exchange.blocks[0].wire[:7], PRE_UPDATE_BITMAP)
        self.assertEqual(
            exchange.blocks[1].wire,
            bytes((0x2C,)) * BLOCK_SIZE,
        )
        self.assertEqual(
            exchange.blocks[2].wire[:6],
            DISPLAY_BITMAP_2INCH,
        )
        self.assertEqual(exchange.blocks[-1].wire[:7], QUERY_STATUS)
        self.assertEqual(exchange.wire_bytes, 5 * BLOCK_SIZE)

    def test_real_480_square_full_frame_wire_size(self):
        region = FrameRegion(0, 0, 480, 480)
        packet = _packet(
            region=region,
            payload=bytes(region.area * 4),
        )
        result = RevCProtocolSimulator().submit(
            _transport(
                packet,
                full_frame_bytes=region.area * 4,
            )
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.wire_bytes, 926500)
        self.assertEqual(result.full_frame_wire_bytes, 926500)
        self.assertEqual(result.wire_savings_ratio, 0.0)

    def test_partial_exchange_encodes_row_addresses_and_count(self):
        region = FrameRegion(3, 4, 2, 2)
        payload = bytes(range(region.area * 3))
        packet = _packet(
            sequence=2,
            region=region,
            encoding=BGR24,
            payload=payload,
            full_refresh=False,
        )
        simulator = RevCProtocolSimulator(display_stride=480)
        result = simulator.submit(
            _transport(
                packet,
                full_frame_bytes=480 * 480 * 4,
            )
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.mode, "partial")
        exchange = result.exchanges[0]
        self.assertEqual(exchange.update_count, 0)

        header = exchange.blocks[0].wire[:14]
        self.assertEqual(header[:4], UPDATE_BITMAP)
        record_bytes = region.height * (5 + region.width * 3)
        self.assertEqual(
            int.from_bytes(header[4:7], "big"),
            record_bytes + len(TERMINATOR),
        )
        self.assertEqual(int.from_bytes(header[10:14], "big"), 0)

        records = recover_partial_records(
            exchange.blocks[1].wire,
            record_bytes,
        )
        first_start = int.from_bytes(records[:3], "big")
        second_offset = 5 + region.width * 3
        second_start = int.from_bytes(
            records[second_offset : second_offset + 3],
            "big",
        )
        self.assertEqual(first_start, 4 * 480 + 3)
        self.assertEqual(second_start, 5 * 480 + 3)

    def test_partial_update_count_increments_across_exchanges(self):
        simulator = RevCProtocolSimulator()
        counts = []
        for sequence in (2, 3):
            packet = _packet(
                sequence=sequence,
                encoding=BGR24,
                full_refresh=False,
            )
            result = simulator.submit(
                _transport(
                    packet,
                    full_frame_bytes=480 * 480 * 4,
                )
            )
            counts.append(result.exchanges[0].update_count)
        self.assertEqual(counts, [0, 1])
        simulator.reset()
        packet = _packet(
            sequence=4,
            encoding=BGR24,
            full_refresh=False,
        )
        result = simulator.submit(
            _transport(packet, full_frame_bytes=480 * 480 * 4)
        )
        self.assertEqual(result.exchanges[0].update_count, 0)

    def test_noop_frame_is_valid_and_emits_no_wire_bytes(self):
        result = RevCProtocolSimulator().submit(
            TransportAnalysis(
                sequence=7,
                profile="rev-c-2inch",
                encoding=BGR24,
                full_refresh=False,
                packets=(),
                pixel_bytes=0,
                overhead_bytes=0,
                simulated_bytes=0,
                full_frame_bytes=480 * 480 * 4,
                savings_ratio=1.0,
                roundtrip_matches=True,
                differing_pixels=0,
            )
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.mode, "noop")
        self.assertEqual(result.wire_bytes, 0)
        self.assertEqual(result.wire_savings_ratio, 1.0)

    def test_artifacts_include_binary_metrics_and_layout(self):
        packet = _packet()
        result = RevCProtocolSimulator().submit(_transport(packet))
        with TemporaryDirectory() as directory:
            root = write_rev_c_protocol_artifacts(
                Path(directory),
                result,
            )
            self.assertEqual(
                (root / "rev-c-protocol.bin").read_bytes(),
                result.wire,
            )
            metrics = (root / "rev-c-protocol.json").read_text()
            layout = (root / "rev-c-protocol-layout.txt").read_text()
            self.assertIn('"physicalIo": false', metrics)
            self.assertIn('"valid": true', metrics)
            self.assertIn("display-bitmap-2inch", layout)


if __name__ == "__main__":
    unittest.main()
