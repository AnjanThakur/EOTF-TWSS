import unittest

import numpy as np

from blink_emg_app.config import Profile
from blink_emg_app.control import MenuController
from blink_emg_app.detection import BlinkEngine, Blink, Gesture, GestureGrouper, PulseDetector
from blink_emg_app.sources import simulated_values


class DetectionTests(unittest.TestCase):
    def profile(self, **changes):
        values = dict(channel=0, threshold=35, sample_rate=500, source_key="test", noise_level=2, blink_level=110)
        values.update(changes)
        return Profile(**values)

    def replay(self, blink_times, *, chunks=71, polarity=1, channels=6, burst_size=None):
        times = np.arange(0, 14, 1 / 500)
        values = simulated_values(times, blink_times, channels=channels)
        if burst_size:
            indices = np.arange(len(times))
            times = (indices // burst_size) * (burst_size / 500) + (indices % burst_size) * .000006
        if polarity < 0:
            values = 4000 - values
        engine = BlinkEngine(500, channels, self.profile(polarity=polarity))
        filtered, blinks, gestures = [], [], []
        for start in range(0, len(times), chunks):
            f, b, g, gaps = engine.process(values[start:start + chunks], times[start:start + chunks])
            self.assertEqual(gaps, 0)
            filtered.extend(f)
            blinks.extend(b)
            gestures.extend(g)
        return np.asarray(filtered), blinks, gestures

    def test_single_double_triple_and_four_blinks(self):
        times = [3, 5, 5.48, 7, 7.48, 7.96, 10, 10.48, 10.96, 11.44]
        _, blinks, gestures = self.replay(times)
        self.assertEqual(len(blinks), len(times))
        self.assertEqual([g.command for g in gestures], ["SINGLE", "NEXT", "SELECT", "REJECT"])

    def test_chunk_boundaries_do_not_change_filter_or_gestures(self):
        a = self.replay([3, 3.48, 6, 6.48, 6.96], chunks=7000)
        b = self.replay([3, 3.48, 6, 6.48, 6.96], chunks=13)
        np.testing.assert_allclose(a[0], b[0], atol=1e-10)
        self.assertEqual(a[1:], b[1:])

    def test_distinct_rapid_blinks_survive_settling_but_overlapping_pulses_do_not_double_count(self):
        # Wide first blinks used to lock out the next blink by adding settling
        # and refractory waits. Exercise realistic filtered waves, both signs,
        # and different chunk boundaries rather than only instantaneous peaks.
        times = [3, 3.24, 5, 5.28, 5.56, 9, 9.12]
        for polarity in (1, -1):
            for chunks in (13, 7000):
                with self.subTest(polarity=polarity, chunks=chunks):
                    _, blinks, gestures = self.replay(times, chunks=chunks, polarity=polarity)
                    self.assertEqual(len(blinks), 6)
                    self.assertEqual([g.command for g in gestures], ["NEXT", "SELECT", "SINGLE"])

    def test_batched_clock_labels_do_not_change_blink_width_or_drop_third_blink(self):
        times = [3, 3.24, 5, 5.28, 5.56, 9, 9.12]
        for polarity in (1, -1):
            regular = self.replay(times, polarity=polarity)
            for chunks in (13, 7000):
                with self.subTest(polarity=polarity, chunks=chunks):
                    batched = self.replay(times, polarity=polarity, chunks=chunks, burst_size=40)
                    self.assertEqual([g.command for g in batched[2]], ["NEXT", "SELECT", "SINGLE"])
                    self.assertEqual([b.width for b in batched[1]], [b.width for b in regular[1]])
                    np.testing.assert_allclose(batched[0], regular[0], atol=1e-10)

    def test_inverted_signal_and_single_channel_supported(self):
        _, blinks, gestures = self.replay([3, 3.48, 6, 6.48, 6.96], polarity=-1, channels=1)
        self.assertEqual(len(blinks), 5)
        self.assertEqual([g.command for g in gestures], ["NEXT", "SELECT"])

    def test_triple_does_not_first_emit_double(self):
        grouper = GestureGrouper(0.8)
        grouper.add(Blink(1, 50, .1))
        grouper.add(Blink(1.5, 50, .1))
        self.assertEqual(grouper.flush(2.0), [])
        grouper.add(Blink(2.0, 50, .1))
        self.assertEqual([g.command for g in grouper.flush(2.81)], ["SELECT"])

    def test_cancel_drops_pending_gesture(self):
        grouper = GestureGrouper()
        grouper.add(Blink(1, 50, .1))
        grouper.add(Blink(1.5, 50, .1))
        grouper.reset()
        self.assertEqual(grouper.flush(3), [])

    def test_long_excursion_and_tiny_spike_rejected(self):
        for batched in (False, True):
            with self.subTest(batched=batched):
                detector = PulseDetector(self.profile())
                found = []
                for i, t in enumerate(np.arange(0, 4, .002)):
                    # The tiny spike straddles a delivery-batch boundary. Clock
                    # subtraction makes it look ~80 ms long instead of ~2 ms.
                    value = 100 if 0.5 <= t < 2 or 3.038 <= t < 3.042 else 0
                    stamp = (i // 40) * .08 + (i % 40) * .000006 if batched else t
                    blink = detector.push(stamp, value)
                    if blink:
                        found.append(blink)
                self.assertEqual(found, [])
                self.assertEqual(detector.rejected, 2)

    def test_startup_and_high_frequency_interference_do_not_control_menu(self):
        t = np.arange(0, 8, .002)
        values = (2000 + 150 * np.sin(2 * np.pi * 120 * t))[:, None]
        engine = BlinkEngine(500, 1, self.profile())
        _, _, gestures, _ = engine.process(values, t)
        self.assertEqual(gestures, [])

    def test_gap_cannot_join_two_sides_into_double(self):
        engine = BlinkEngine(500, 1, self.profile())
        t = np.arange(0, 3.3, .002)
        _, b, _, _ = engine.process(simulated_values(t, [3], channels=1), t)
        self.assertEqual(len(b), 1)
        t2 = np.arange(3.45, 6, .002)
        _, _, gestures, gaps = engine.process(simulated_values(t2, [3.6], channels=1), t2)
        self.assertEqual(gaps, 1)
        self.assertFalse(any(g.command == "NEXT" for g in gestures))

    def test_invalid_and_backwards_samples_fail(self):
        engine = BlinkEngine(500, 1, self.profile())
        engine.process([[1], [2]], [1, 1.002])
        for values, times in (([[3]], [1]), ([[np.nan]], [2]), ([[3], [4]], [2, 2]), ([[3, 4]], [2])):
            with self.assertRaises(ValueError):
                engine.process(values, times)

    def test_menu_only_acts_when_armed_and_select_has_cooldown(self):
        menu = MenuController()
        self.assertIsNone(menu.accept(Gesture(1, 2, 2, "NEXT")))
        menu.armed = True
        self.assertEqual(menu.accept(Gesture(2, 3, 2, "NEXT"))["word"], "Food")
        self.assertEqual(menu.accept(Gesture(3, 4, 3, "SELECT"))["phrase"], "I would like food.")
        self.assertIsNone(menu.accept(Gesture(4, 5, 3, "SELECT")))
        self.assertIsNone(menu.accept(Gesture(4, 7, 4, "REJECT")))
        menu.pause()
        self.assertIsNone(menu.accept(Gesture(5, 8, 3, "SELECT")))


if __name__ == "__main__":
    unittest.main()
