# SPDX-License-Identifier: GPL-3.0-or-later
from types import SimpleNamespace
import unittest

from library.frame_pipeline import FrameRegion
from library.rev_c_status_transport import (
    RevCStatusError,
    send_protocol_with_status,
)


class FakeClock:
    def __init__(self):
        self.value = 10.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class FakeDriver:
    def __init__(self, responses):
        self.responses = list(responses)
        self.writes = []
        self.read_sizes = []

    def WriteData(self, payload):
        self.writes.append(bytes(payload))

    def ReadData(self, size):
        self.read_sizes.append(size)
        if not self.responses:
            return b""
        return self.responses.pop(0)


def block(name, wire, read_size=0):
    return SimpleNamespace(name=name, wire=wire, read_size=read_size)


def protocol(exchanges, mode="partial", wire_bytes=None, valid=True):
    exchanges = tuple(exchanges)
    calculated = sum(
        len(item.wire)
        for exchange in exchanges
        for item in exchange.blocks
    )
    return SimpleNamespace(
        mode=mode,
        valid=valid,
        exchanges=exchanges,
        wire_bytes=calculated if wire_bytes is None else wire_bytes,
    )


class RevCStatusTransportTests(unittest.TestCase):
    def test_writes_exact_blocks_and_captures_status(self):
        first = SimpleNamespace(
            name="region-a",
            region=FrameRegion(1, 2, 3, 4),
            blocks=(
                block("header", b"abc"),
                block("pixels", b"def"),
                block("query-status", b"ghi", read_size=8),
            ),
        )
        second = SimpleNamespace(
            name="region-b",
            region=FrameRegion(8, 9, 2, 2),
            blocks=(
                block("header", b"jkl"),
                block("query-status", b"mno", read_size=8),
            ),
        )
        driver = FakeDriver((b"status-a", b"status-b"))
        sleeps = []

        batch = send_protocol_with_status(
            driver,
            protocol((first, second)),
            minimum_status_bytes=1,
            inter_exchange_delay=0.25,
            sleeper=sleeps.append,
        )

        self.assertEqual(driver.writes, [b"abc", b"def", b"ghi", b"jkl", b"mno"])
        self.assertEqual(driver.read_sizes, [8, 8])
        self.assertEqual(sleeps, [0.25])
        self.assertEqual(len(batch.samples), 2)
        self.assertEqual(batch.samples[0].response, b"status-a")
        self.assertEqual(batch.samples[1].region.as_dict(), {
            "x": 8,
            "y": 9,
            "width": 2,
            "height": 2,
        })
        self.assertEqual(batch.wire_bytes, 15)
        self.assertEqual(batch.minimum_received_bytes, 8)
        self.assertTrue(batch.fingerprint)

    def test_empty_status_response_is_rejected(self):
        exchange = SimpleNamespace(
            name="region",
            region=FrameRegion(0, 0, 1, 1),
            blocks=(block("query", b"wire", read_size=1024),),
        )
        driver = FakeDriver((b"",))

        with self.assertRaisesRegex(RevCStatusError, "returned 0 byte"):
            send_protocol_with_status(
                driver,
                protocol((exchange,)),
                minimum_status_bytes=1,
            )

    def test_minimum_status_size_is_enforced(self):
        exchange = SimpleNamespace(
            name="region",
            region=FrameRegion(0, 0, 1, 1),
            blocks=(block("query", b"wire", read_size=8),),
        )
        driver = FakeDriver((b"1234",))

        with self.assertRaisesRegex(RevCStatusError, "minimum is 5"):
            send_protocol_with_status(
                driver,
                protocol((exchange,)),
                minimum_status_bytes=5,
            )

    def test_declared_wire_size_must_match_written_bytes(self):
        exchange = SimpleNamespace(
            name="region",
            region=FrameRegion(0, 0, 1, 1),
            blocks=(block("query", b"wire", read_size=4),),
        )
        driver = FakeDriver((b"okay",))

        with self.assertRaisesRegex(RevCStatusError, "declares 99"):
            send_protocol_with_status(
                driver,
                protocol((exchange,), wire_bytes=99),
            )

    def test_invalid_protocol_is_rejected_before_writing(self):
        driver = FakeDriver(())

        with self.assertRaisesRegex(RevCStatusError, "not valid"):
            send_protocol_with_status(
                driver,
                protocol((), valid=False),
            )

        self.assertEqual(driver.writes, [])

    def test_read_elapsed_time_is_recorded(self):
        clock = FakeClock()

        class TimedDriver(FakeDriver):
            def ReadData(self, size):
                clock.advance(0.125)
                return super().ReadData(size)

        exchange = SimpleNamespace(
            name="region",
            region=FrameRegion(0, 0, 1, 1),
            blocks=(block("query", b"wire", read_size=4),),
        )
        driver = TimedDriver((b"okay",))

        batch = send_protocol_with_status(
            driver,
            protocol((exchange,)),
            clock=clock,
        )

        self.assertAlmostEqual(batch.samples[0].elapsed_ms, 125.0)
        self.assertAlmostEqual(batch.elapsed_ms, 125.0)


if __name__ == "__main__":
    unittest.main()
