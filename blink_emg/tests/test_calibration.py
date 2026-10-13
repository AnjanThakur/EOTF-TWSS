from dataclasses import asdict
import unittest

import numpy as np

from blink_emg_app.calibration import Window, calibrate, evaluate
from blink_emg_app.config import Profile
from blink_emg_app.detection import SignalFilter, Gesture
from blink_emg_app.sources import simulated_values


def synthetic_calibration(invert=False, first_flat=False):
    t = np.arange(0, 70, .002)
    blinks = [5, 10, 15, 20] + [25 + i * 5 + .7 for i in range(8)]
    raw = simulated_values(t, blinks)
    if invert:
        raw = 4000 - raw
    if first_flat:
        raw[:, 0] = 2000
    filtered = SignalFilter(500, 6).process(raw)
    windows = [Window("NORMAL", 3, 23)] + [Window("SINGLE", 25 + i * 5, 29 + i * 5) for i in range(8)]
    for w in windows:
        mask = (t >= w.start) & (t < w.end)
        w.timestamps = t[mask].tolist()
        w.filtered = filtered[mask].tolist()
    return windows


def validation_windows(trials_per_kind=6, normal_seconds=30):
    windows = [Window("NORMAL", 0, normal_seconds)]
    for i, label in enumerate(["NEXT", "SELECT"] * trials_per_kind):
        start = normal_seconds + 2 + i * 6
        windows.append(Window(label, start, start + 4,
                              gestures=[Gesture(start + .7, start + 2.7, 2 if label == "NEXT" else 3, label)]))
    for w in windows:
        w.timestamps = np.arange(w.start, w.end, .002).tolist()
        w.filtered = np.zeros((len(w.timestamps), 6)).tolist()
    return windows


class CalibrationTests(unittest.TestCase):
    def test_fits_channel_and_polarity_from_calibration(self):
        p = calibrate(synthetic_calibration(), 500, [0, 1], "test", "cal")
        self.assertEqual(p.channel, 0)
        self.assertEqual(p.polarity, 1)
        self.assertEqual(p.calibration["correctly_counted"], 8)
        self.assertFalse(p.validation)
        inverted = calibrate(synthetic_calibration(invert=True, first_flat=True), 500, [0, 1], "test", "cal2")
        self.assertEqual((inverted.channel, inverted.polarity), (1, -1))

    def test_flat_and_incomplete_calibration_rejected(self):
        windows = synthetic_calibration()
        for w in windows:
            w.filtered = np.zeros((len(w.timestamps), 6)).tolist()
        with self.assertRaises(ValueError):
            calibrate(windows, 500, [0, 1], "test", "flat")
        with self.assertRaises(ValueError):
            calibrate(windows[:3], 500, [0], "test", "short")

    def test_fresh_test_reports_real_counts_without_refitting(self):
        p = Profile(0, 35, 500, "test", 2, 110)
        frozen = asdict(p)
        windows = validation_windows()
        result = evaluate(windows, p, "new")
        self.assertTrue(result["passed"])
        self.assertEqual(result["correct_trials"], 12)
        self.assertEqual(asdict(p), frozen)
        quick = evaluate(windows, p, "practice", quick=True)
        self.assertEqual(quick["check_type"], "quick")
        self.assertEqual(quick["correct_trials"], 12)
        self.assertFalse(quick["passed"], "Quick feedback must never unlock control, even with enough correct trials")
        windows[1].gestures = []
        windows[2].gestures[0] = Gesture(windows[2].start, windows[2].start + 2, 2, "NEXT")
        windows[3].gestures *= 2
        result = evaluate(windows, p, "new2")
        self.assertEqual(result["correct_trials"], 9)
        self.assertEqual(result["extra_commands"], 1)
        self.assertFalse(result["passed"])
        self.assertEqual(result["confusion"]["NEXT"]["MISS"], 1)
        self.assertEqual(result["confusion"]["SELECT"]["NEXT"], 1)

    def test_false_commands_and_missing_data_fail_readiness(self):
        p = Profile(0, 35, 500, "test", 2, 110)
        windows = validation_windows()
        windows[0].gestures = [Gesture(5, 6, 2, "NEXT")]
        result = evaluate(windows, p, "new")
        self.assertFalse(result["passed"])
        self.assertEqual(result["accidental_commands_per_minute"], 2)
        windows[1].timestamps = windows[1].timestamps[:50]
        windows[1].filtered = windows[1].filtered[:50]
        with self.assertRaises(ValueError):
            evaluate(windows, p, "incomplete")

    def test_one_minute_readiness_requires_seven_of_eight_and_quiet_ordinary_activity(self):
        p = Profile(0, 35, 500, "test", 2, 110)
        windows = validation_windows(trials_per_kind=4, normal_seconds=15)
        windows[1].gestures = []
        result = evaluate(windows, p, "short")
        self.assertTrue(result["passed"])
        self.assertEqual((result["correct_trials"], result["total_trials"]), (7, 8))
        windows[0].gestures = [Gesture(5, 6, 2, "NEXT")]
        self.assertFalse(evaluate(windows, p, "accidental")["passed"])
        windows[0].gestures = []
        windows[2].gestures = []
        self.assertFalse(evaluate(windows, p, "six_of_eight")["passed"])
        self.assertFalse(evaluate(validation_windows(3, 15), p, "too_few_trials")["passed"])
        self.assertFalse(evaluate(validation_windows(4, 10), p, "too_little_ordinary_activity")["passed"])


if __name__ == "__main__":
    unittest.main()
