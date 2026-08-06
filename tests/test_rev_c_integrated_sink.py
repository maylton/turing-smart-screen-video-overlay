import unittest

from PIL import Image

from library.rev_c_integrated_sink import (
    IntegratedRevCSink,
    MAX_REGIONS_PER_CYCLE,
    MAX_WIRE_BYTES_PER_CYCLE,
    MINIMUM_STATUS_BYTES,
    REGION_PACING_SECONDS,
)
from tests.test_rev_c_live_sink import FakeDriver, full_protocol, parity


class PowerAwareFakeDriver(FakeDriver):
    def __init__(self, port, responses):
        super().__init__(port, responses)
        self.update_queue = object()

    def ScreenOn(self):
        self.calls.append(("screen-on",))

    def ScreenOff(self):
        self.calls.append(("screen-off",))

    def SetBackplateLedColor(self, *, led_color):
        self.calls.append(("led", led_color))

    def SetBrightness(self, value):
        self.calls.append(("brightness", value))


class IntegratedSinkLimitsTests(unittest.TestCase):
    def test_validated_physical_limits_remain_fixed(self):
        self.assertEqual(MAX_REGIONS_PER_CYCLE, 8)
        self.assertEqual(MAX_WIRE_BYTES_PER_CYCLE, 300_000)
        self.assertEqual(REGION_PACING_SECONDS, 0.10)
        self.assertEqual(MINIMUM_STATUS_BYTES, 1)

    def test_serial_closes_when_initial_status_fails(self):
        created = []

        def factory(port):
            driver = PowerAwareFakeDriver(port, responses=[])
            created.append(driver)
            return driver

        protocol = full_protocol()
        with self.assertRaises(Exception):
            IntegratedRevCSink(
                Image.new("RGBA", (480, 480)),
                protocol,
                parity(1, "full", protocol.wire),
                port="/dev/fake",
                driver_factory=factory,
                sleeper=lambda _seconds: None,
            )
        self.assertTrue(created[0].closed)
        labels = [call[0] for call in created[0].calls]
        self.assertIn("screen-off", labels)
        self.assertLess(labels.index("screen-off"), labels.index("close"))

    def test_normal_close_powers_off_before_releasing_serial(self):
        created = []

        def factory(port):
            driver = PowerAwareFakeDriver(
                port,
                responses=[b"FULL", b"STATUS"],
            )
            created.append(driver)
            return driver

        protocol = full_protocol()
        sink = IntegratedRevCSink(
            Image.new("RGBA", (480, 480)),
            protocol,
            parity(1, "full", protocol.wire),
            port="/dev/fake",
            driver_factory=factory,
            sleeper=lambda _seconds: None,
        )
        sink.close()

        driver = created[0]
        labels = [call[0] for call in driver.calls]
        self.assertIsNone(driver.update_queue)
        self.assertLess(labels.index("screen-off"), labels.index("close"))
        self.assertIn(("led", (0, 0, 0)), driver.calls)


if __name__ == "__main__":
    unittest.main()
