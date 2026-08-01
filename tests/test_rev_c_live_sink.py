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


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class FakeDriver:
    def __init__(self, port, fail_partial=False):
        self.port = port
        self.fail_partial = fail_partial
        self.calls = []
        self.closed = False

    def InitializeComm(self):
        self.calls.append(("initialize",))

    def SetOrientation(self, orientation):
        self.calls.append(("orientation", int(orientation)))

    def DisplayPILImage(self, image, **kwargs):
        self.calls.append(("display", image.size, kwargs))
        if self.fail_partial and image.size != (480, 480):
            raise RuntimeError("simulated partial failure")

    def closeSerial(self):
        self.calls.append(("close",))
        self.closed = True


def parity(sequence, mode="full", valid=True):
    wire = b"same-wire" if valid else b"different"
    return SimpleNamespace(
        sequence=sequence,
        valid=valid,
        physical_io=False,
        mode=mode,
        mismatch_offset=None if valid else 0,
        expected_wire=wire,
        production_wire=wire if valid else b"other",
    )


def partial_objects(sequence=2, regions=1, wire_bytes=10_000):
    packets = []
    exchanges = []
    for index in range(regions):
        region = FrameRegion(index * 16, 0, 16, 16)
        packets.append(SimpleNamespace(region=region))
        exchanges.append(SimpleNamespace(update_count=index))
    transport = SimpleNamespace(
        sequence=sequence,
        full_refresh=False,
        roundtrip_matches=True,
        packets=tuple(packets),
    )
    protocol = SimpleNamespace(
        sequence=sequence,
        mode="partial" if packets else "noop",
        valid=True,
        wire_bytes=wire_bytes,
        exchanges=tuple(exchanges),
    )
    return transport, protocol, parity(
        sequence,
        "partial" if packets else "noop",
    )


class RevCLiveSinkTests(unittest.TestCase):
    def setUp(self):
        self.frame = Image.new("RGBA", (480, 480), (20, 30, 40, 255))
        self.clock = FakeClock()

    def create_session(self, **overrides):
        created = []
        fail_partial = bool(overrides.pop("fail_partial", False))

        def factory(port):
            driver = FakeDriver(
                port,
                fail_partial=fail_partial,
            )
            created.append(driver)
            return driver

        temporary = TemporaryDirectory()
        arguments = {
            "initial_frame": self.frame,
            "initial_parity": parity(1),
            "port": "/dev/fake-rev-c",
            "confirmation": LIVE_CONFIRMATION_TEXT,
            "monitor_stopped": True,
            "max_partial_frames": 3,
            "max_duration": 20,
            "min_interval": 1.0,
            "max_regions": 4,
            "max_wire_bytes": 50_000,
            "driver_factory": factory,
            "lock_path": Path(temporary.name) / "physical.lock",
            "clock": self.clock,
        }
        arguments.update(overrides)
        session = GuardedRevCLiveSession(**arguments)
        return session, created, temporary

    def test_initial_frame_then_partial_regions_and_close(self):
        session, created, temporary = self.create_session()
        try:
            self.assertEqual(
                [call[0] for call in created[0].calls],
                ["initialize", "orientation", "display"],
            )
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
        finally:
            summary = session.close()
            temporary.cleanup()

        self.assertTrue(summary.serial_closed)
        self.assertTrue(created[0].closed)
        self.assertEqual(
            [call[0] for call in created[0].calls],
            ["initialize", "orientation", "display", "display", "display", "close"],
        )

    def test_wrong_confirmation_refuses_before_driver_creation(self):
        with self.assertRaisesRegex(LiveWriteRefused, "confirmation"):
            self.create_session(confirmation="wrong")

    def test_interval_is_enforced(self):
        session, _created, temporary = self.create_session()
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
        session, _created, temporary = self.create_session()
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
        session, _created, temporary = self.create_session()
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

    def test_serial_is_closed_when_partial_write_raises(self):
        session, created, temporary = self.create_session(fail_partial=True)
        try:
            self.clock.advance(1.0)
            transport, protocol, frame_parity = partial_objects()
            with self.assertRaisesRegex(RuntimeError, "partial failure"):
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


if __name__ == "__main__":
    unittest.main()
