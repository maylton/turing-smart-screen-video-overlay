# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from library.frame_pipeline import FrameRegion
from library.rev_c_live_sink import (
    LIVE_CONFIRMATION_TEXT,
    GuardedRevCLiveSession,
    LiveWriteRefused,
)
from library.rev_c_status_transport import RevCStatusError


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class FakeDriver:
    def __init__(self, port, responses, fail_after_writes=None):
        self.port = port
        self.responses = list(responses)
        self.fail_after_writes = fail_after_writes
        self.calls = []
        self.writes = []
        self.read_sizes = []
        self.closed = False

    def InitializeComm(self):
        self.calls.append(("initialize",))

    def SetOrientation(self, orientation):
        self.calls.append(("orientation", int(orientation)))

    def WriteData(self, payload):
        if (
            self.fail_after_writes is not None
            and len(self.writes) >= self.fail_after_writes
        ):
            raise RuntimeError("simulated physical write failure")
        wire = bytes(payload)
        self.writes.append(wire)
        self.calls.append(("write", wire))

    def ReadData(self, size):
        self.read_sizes.append(size)
        self.calls.append(("read", size))
        if not self.responses:
            return b""
        return self.responses.pop(0)

    def closeSerial(self):
        self.calls.append(("close",))
        self.closed = True


def wire_block(name, wire, read_size=0):
    return SimpleNamespace(name=name, wire=wire, read_size=read_size)


def full_protocol(sequence=1):
    exchange = SimpleNamespace(
        name="full-frame",
        region=FrameRegion(0, 0, 480, 480),
        update_count=None,
        blocks=(
            wire_block("full-data", b"FULL-DATA", read_size=4),
            wire_block("query-status", b"FULL-QUERY", read_size=4),
        ),
    )
    wire = b"".join(block.wire for block in exchange.blocks)
    return SimpleNamespace(
        sequence=sequence,
        mode="full",
        valid=True,
        exchanges=(exchange,),
        wire=wire,
        wire_bytes=len(wire),
    )


def parity(sequence, mode, wire, valid=True):
    return SimpleNamespace(
        sequence=sequence,
        valid=valid,
        physical_io=False,
        mode=mode,
        mismatch_offset=None if valid else 0,
        expected_wire=wire,
        production_wire=wire if valid else b"other",
    )


def partial_objects(sequence=2, regions=1, wire_bytes=None):
    packets = []
    exchanges = []
    for index in range(regions):
        region = FrameRegion(index * 16, 0, 16, 16)
        packets.append(SimpleNamespace(region=region))
        exchanges.append(SimpleNamespace(
            name="partial-region",
            region=region,
            update_count=index,
            blocks=(
                wire_block("update-header", f"H{index}".encode()),
                wire_block("partial-records", f"P{index}".encode()),
                wire_block(
                    "query-status",
                    f"Q{index}".encode(),
                    read_size=4,
                ),
            ),
        ))
    mode = "partial" if packets else "noop"
    wire = b"".join(
        block.wire
        for exchange in exchanges
        for block in exchange.blocks
    )
    protocol = SimpleNamespace(
        sequence=sequence,
        mode=mode,
        valid=True,
        wire=wire,
        wire_bytes=len(wire) if wire_bytes is None else wire_bytes,
        exchanges=tuple(exchanges),
    )
    transport = SimpleNamespace(
        sequence=sequence,
        full_refresh=False,
        roundtrip_matches=True,
        packets=tuple(packets),
    )
    return transport, protocol, parity(sequence, mode, wire)


class RevCLiveSinkTests(unittest.TestCase):
    def setUp(self):
        self.frame = Image.new("RGBA", (480, 480), (20, 30, 40, 255))
        self.clock = FakeClock()

    def create_session(self, **overrides):
        created = []
        responses = overrides.pop(
            "responses",
            [b"INIT", b"BASE"] + [b"STAT"] * 16,
        )
        fail_after_writes = overrides.pop("fail_after_writes", None)
        sleeps = overrides.pop("sleeps", [])

        def factory(port):
            driver = FakeDriver(
                port,
                responses=responses,
                fail_after_writes=fail_after_writes,
            )
            created.append(driver)
            return driver

        initial_protocol = full_protocol()
        initial_parity = parity(
            1,
            "full",
            initial_protocol.wire,
        )
        temporary = TemporaryDirectory()
        arguments = {
            "initial_frame": self.frame,
            "initial_protocol": initial_protocol,
            "initial_parity": initial_parity,
            "port": "/dev/fake-rev-c",
            "confirmation": LIVE_CONFIRMATION_TEXT,
            "monitor_stopped": True,
            "max_partial_frames": 3,
            "max_duration": 20,
            "min_interval": 1.0,
            "max_regions": 4,
            "max_wire_bytes": 50_000,
            "region_pacing": 0.25,
            "minimum_status_bytes": 1,
            "driver_factory": factory,
            "lock_path": Path(temporary.name) / "physical.lock",
            "clock": self.clock,
            "sleeper": sleeps.append,
        }
        arguments.update(overrides)
        session = GuardedRevCLiveSession(**arguments)
        return session, created, temporary, sleeps

    def test_initial_and_partial_protocol_blocks_are_written_directly(self):
        session, created, temporary, sleeps = self.create_session()
        try:
            self.assertEqual(len(session.initial_status_batch.samples), 2)
            self.assertEqual(created[0].writes, [b"FULL-DATA", b"FULL-QUERY"])
            self.clock.advance(1.0)
            transport, protocol, frame_parity = partial_objects(regions=2)
            result = session.submit_partial(
                self.frame,
                transport,
                protocol,
                frame_parity,
            )
            self.assertEqual(result.region_count, 2)
            self.assertEqual(result.partial_frame_number, 1)
            self.assertEqual(len(result.status_batch.samples), 2)
            self.assertEqual(sleeps, [0.25])
            self.assertEqual(
                created[0].writes,
                [
                    b"FULL-DATA",
                    b"FULL-QUERY",
                    b"H0",
                    b"P0",
                    b"Q0",
                    b"H1",
                    b"P1",
                    b"Q1",
                ],
            )
        finally:
            summary = session.close()
            temporary.cleanup()

        self.assertTrue(summary.serial_closed)
        self.assertEqual(summary.status_responses, 4)
        self.assertTrue(created[0].closed)

    def test_wrong_confirmation_refuses_before_driver_creation(self):
        with self.assertRaisesRegex(LiveWriteRefused, "confirmation"):
            self.create_session(confirmation="wrong")

    def test_interval_is_enforced(self):
        session, _created, temporary, _sleeps = self.create_session()
        try:
            transport, protocol, frame_parity = partial_objects()
            with self.assertRaisesRegex(LiveWriteRefused, "interval"):
                session.submit_partial(
                    self.frame,
                    transport,
                    protocol,
                    frame_parity,
                )
        finally:
            session.close()
            temporary.cleanup()

    def test_unexpected_full_refresh_is_rejected(self):
        session, _created, temporary, _sleeps = self.create_session()
        try:
            self.clock.advance(1.0)
            transport, protocol, frame_parity = partial_objects()
            transport.full_refresh = True
            with self.assertRaisesRegex(LiveWriteRefused, "full refresh"):
                session.submit_partial(
                    self.frame,
                    transport,
                    protocol,
                    frame_parity,
                )
        finally:
            session.close()
            temporary.cleanup()

    def test_region_and_wire_budgets_are_enforced(self):
        session, _created, temporary, _sleeps = self.create_session()
        try:
            self.clock.advance(1.0)
            transport, protocol, frame_parity = partial_objects(regions=5)
            with self.assertRaisesRegex(LiveWriteRefused, "regions"):
                session.submit_partial(
                    self.frame,
                    transport,
                    protocol,
                    frame_parity,
                )

            transport, protocol, frame_parity = partial_objects(
                sequence=3,
                wire_bytes=60_000,
            )
            with self.assertRaisesRegex(LiveWriteRefused, "wire bytes"):
                session.submit_partial(
                    self.frame,
                    transport,
                    protocol,
                    frame_parity,
                )
        finally:
            session.close()
            temporary.cleanup()

    def test_protocol_must_match_production_parity(self):
        session, _created, temporary, _sleeps = self.create_session()
        try:
            self.clock.advance(1.0)
            transport, protocol, frame_parity = partial_objects()
            frame_parity.expected_wire = b"different"
            frame_parity.production_wire = b"different"
            with self.assertRaisesRegex(LiveWriteRefused, "differs"):
                session.submit_partial(
                    self.frame,
                    transport,
                    protocol,
                    frame_parity,
                )
        finally:
            session.close()
            temporary.cleanup()

    def test_empty_partial_status_response_is_detected(self):
        session, created, temporary, _sleeps = self.create_session(
            responses=[b"INIT", b"BASE", b""],
        )
        try:
            self.clock.advance(1.0)
            transport, protocol, frame_parity = partial_objects()
            with self.assertRaisesRegex(RevCStatusError, "returned 0 byte"):
                session.submit_partial(
                    self.frame,
                    transport,
                    protocol,
                    frame_parity,
                )
        finally:
            summary = session.close()
            temporary.cleanup()

        self.assertTrue(summary.serial_closed)
        self.assertTrue(created[0].closed)

    def test_serial_is_closed_when_direct_write_raises(self):
        session, created, temporary, _sleeps = self.create_session(
            fail_after_writes=2,
        )
        try:
            self.clock.advance(1.0)
            transport, protocol, frame_parity = partial_objects()
            with self.assertRaisesRegex(RuntimeError, "physical write failure"):
                session.submit_partial(
                    self.frame,
                    transport,
                    protocol,
                    frame_parity,
                )
        finally:
            summary = session.close()
            temporary.cleanup()

        self.assertTrue(summary.serial_closed)
        self.assertTrue(created[0].closed)

    def test_region_pacing_limits_are_validated(self):
        with self.assertRaisesRegex(LiveWriteRefused, "region_pacing"):
            self.create_session(region_pacing=0.0)

    def test_initial_empty_status_closes_serial(self):
        created = []

        def factory(port):
            driver = FakeDriver(port, responses=[b""], fail_after_writes=None)
            created.append(driver)
            return driver

        protocol = full_protocol()
        with TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RevCStatusError, "returned 0 byte"):
                GuardedRevCLiveSession(
                    self.frame,
                    protocol,
                    parity(1, "full", protocol.wire),
                    port="/dev/fake-rev-c",
                    confirmation=LIVE_CONFIRMATION_TEXT,
                    monitor_stopped=True,
                    driver_factory=factory,
                    lock_path=Path(temporary) / "physical.lock",
                    sleeper=lambda _seconds: None,
                )

        self.assertTrue(created[0].closed)


if __name__ == "__main__":
    unittest.main()
