# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from PIL import Image

from library.frame_pipeline import FrameRegion
from library.rev_c_live_sink import (
    LIVE_CONFIRMATION_TEXT,
    GuardedRevCLiveSession,
)
from library.rev_c_status_transport import send_protocol_with_status


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class FakeDriver:
    def __init__(self, port="/dev/fake", responses=()):
        self.port = port
        self.responses = list(responses)
        self.writes = []
        self.closed = False

    def InitializeComm(self):
        return None

    def SetOrientation(self, _orientation):
        return None

    def WriteData(self, payload):
        self.writes.append(bytes(payload))

    def ReadData(self, _size):
        return self.responses.pop(0) if self.responses else b""

    def closeSerial(self):
        self.closed = True


def wire_block(name, wire, read_size=0):
    return SimpleNamespace(name=name, wire=wire, read_size=read_size)


def protocol_for_regions(sequence, count, mode="partial"):
    exchanges = []
    for index in range(count):
        region = FrameRegion(index * 8, 0, 8, 8)
        exchanges.append(
            SimpleNamespace(
                name="partial-region" if mode == "partial" else "full-frame",
                region=region,
                update_count=index if mode == "partial" else None,
                blocks=(
                    wire_block("pixels", f"P{index}".encode()),
                    wire_block("query-status", f"Q{index}".encode(), read_size=4),
                ),
            )
        )
    wire = b"".join(
        block.wire for exchange in exchanges for block in exchange.blocks
    )
    return SimpleNamespace(
        sequence=sequence,
        mode=mode,
        valid=True,
        exchanges=tuple(exchanges),
        wire=wire,
        wire_bytes=len(wire),
    )


def parity_for(protocol):
    return SimpleNamespace(
        sequence=protocol.sequence,
        valid=True,
        physical_io=False,
        mode=protocol.mode,
        mismatch_offset=None,
        expected_wire=protocol.wire,
        production_wire=protocol.wire,
    )


class RevCBatchedUpdateTests(unittest.TestCase):
    def test_status_transport_pauses_between_exchange_batches(self):
        protocol = protocol_for_regions(2, 5)
        driver = FakeDriver(responses=[b"STAT"] * 5)
        sleeps = []

        batch = send_protocol_with_status(
            driver,
            protocol,
            inter_exchange_delay=0.10,
            exchange_batch_size=2,
            inter_batch_delay=0.50,
            sleeper=sleeps.append,
        )

        self.assertEqual(batch.batch_count, 3)
        self.assertEqual(sleeps, [0.10, 0.50, 0.10, 0.50])
        self.assertEqual(len(batch.samples), 5)

    def test_live_session_accepts_more_regions_than_one_physical_batch(self):
        frame = Image.new("RGBA", (480, 480), (20, 30, 40, 255))
        initial = protocol_for_regions(1, 1, mode="full")
        partial = protocol_for_regions(2, 5)
        transport = SimpleNamespace(
            sequence=2,
            full_refresh=False,
            roundtrip_matches=True,
            packets=tuple(
                SimpleNamespace(region=exchange.region)
                for exchange in partial.exchanges
            ),
        )
        clock = FakeClock()
        sleeps = []
        created = []

        def factory(port):
            driver = FakeDriver(port, responses=[b"STAT"] * 6)
            created.append(driver)
            return driver

        with TemporaryDirectory() as temporary:
            session = GuardedRevCLiveSession(
                frame,
                initial,
                parity_for(initial),
                port="/dev/fake",
                confirmation=LIVE_CONFIRMATION_TEXT,
                monitor_stopped=True,
                max_partial_frames=2,
                max_duration=20,
                min_interval=1.0,
                max_regions=8,
                batch_regions=4,
                max_wire_bytes=50_000,
                region_pacing=0.10,
                batch_pacing=0.50,
                minimum_status_bytes=1,
                driver_factory=factory,
                lock_path=Path(temporary) / "physical.lock",
                clock=clock,
                sleeper=sleeps.append,
            )
            try:
                clock.advance(1.0)
                result = session.submit_partial(
                    frame,
                    transport,
                    partial,
                    parity_for(partial),
                )
            finally:
                summary = session.close()

        self.assertEqual(result.region_count, 5)
        self.assertEqual(result.batch_count, 2)
        self.assertEqual(sleeps, [0.10, 0.10, 0.10, 0.50])
        self.assertTrue(summary.serial_closed)
        self.assertTrue(created[0].closed)


if __name__ == "__main__":
    unittest.main()
