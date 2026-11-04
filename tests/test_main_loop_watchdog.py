from __future__ import annotations

import unittest

from library.main_loop_watchdog import MainLoopWatchdog


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class MainLoopWatchdogTests(unittest.TestCase):
    def make(self):
        self.clock = FakeClock()
        self.stalls = []
        return MainLoopWatchdog(30, clock=self.clock, on_stall=self.stalls.append)

    def test_unarmed_watchdog_never_fires(self):
        dog = self.make()
        self.clock.now += 1000
        self.assertFalse(dog.check())
        self.assertEqual(self.stalls, [])

    def test_regular_beats_keep_it_quiet(self):
        dog = self.make()
        dog.arm()
        for _ in range(10):
            self.clock.now += 20
            dog.beat()
            self.assertFalse(dog.check())

    def test_stall_fires_once_past_the_limit(self):
        dog = self.make()
        dog.arm()
        self.clock.now += 30
        self.assertFalse(dog.check())
        self.clock.now += 1
        self.assertTrue(dog.check())
        self.assertEqual(self.stalls, [31])

    def test_disarm_stops_counting(self):
        dog = self.make()
        dog.arm()
        dog.disarm()
        self.clock.now += 100
        self.assertFalse(dog.check())


if __name__ == "__main__":
    unittest.main()
