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


class IntegratedSinkLimitsTests(unittest.TestCase):
    def test_validated_physical_limits_remain_fixed(self):
        self.assertEqual(MAX_REGIONS_PER_CYCLE, 8)
        self.assertEqual(MAX_WIRE_BYTES_PER_CYCLE, 300_000)
        self.assertEqual(REGION_PACING_SECONDS, 0.10)
        self.assertEqual(MINIMUM_STATUS_BYTES, 1)

    def test_serial_closes_when_initial_status_fails(self):
        created = []

        def factory(port):
            driver = FakeDriver(port, responses=[])
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
            )
        self.assertTrue(created[0].closed)


if __name__ == "__main__":
    unittest.main()
