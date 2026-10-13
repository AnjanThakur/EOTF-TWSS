import json
from pathlib import Path
import queue
import tempfile
import threading
import time
import unittest
import uuid

import numpy as np

from blink_emg_app.config import ROOT, Profile
from blink_emg_app.sources import DemoSource, LSLSource, TimestampGuard
from blink_emg_app.storage import SessionWriter, inspect_session


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "tests")
        self.addCleanup(self.temp.cleanup)

    def test_durable_raw_data_events_and_partial_status(self):
        writer = SessionWriter(dict(channels=2, sample_rate=500, simulated=True, source_key="test"), self.temp.name)
        folder = writer.folder
        writer.append([[2000, 2010], [2001, 2011], [2002, 2012]], [1, 1.002, 1.004])
        writer.event("cue", 1.003, label="SINGLE")
        writer.flush()
        while_open = inspect_session(folder)
        self.assertEqual(while_open["status"], "recording")
        self.assertEqual(while_open["sample_count"], 3)
        self.assertTrue(while_open["incomplete"])
        writer.close("error", "Lost Bluetooth")
        report = inspect_session(folder)
        self.assertEqual(report["status"], "error")
        self.assertEqual(report["checkpoint_sample_count"], 3)
        events = [json.loads(line) for line in (folder / "events.jsonl").read_text().splitlines()]
        self.assertEqual(events[1]["timestamp"], 1.003)
        metadata = json.loads((folder / "metadata.json").read_text())
        self.assertEqual(metadata["channels"], ["A0 / CH1", "A1 / CH2"])
        self.assertIn("not imagined speech", metadata["modality"])
        second = SessionWriter(dict(channels=2, sample_rate=500, simulated=True), self.temp.name)
        second.close()
        self.assertNotEqual(folder, second.folder)

    def test_invalid_samples_do_not_change_recording(self):
        writer = SessionWriter(dict(channels=1, sample_rate=500, simulated=True), self.temp.name)
        self.addCleanup(writer.close)
        for x, t in (([[1, 2]], [1]), ([[np.nan]], [1]), ([[1], [2]], [1, 1])):
            with self.assertRaises(ValueError):
                writer.append(x, t)
        self.assertEqual(writer.count, 0)

    def test_profile_roundtrip_and_invalid_profile(self):
        path = Path(self.temp.name) / "personal.json"
        p = Profile(0, 35, 500, "test", 2, 110)
        p.save(path)
        self.assertEqual(Profile.load(path).to_dict(), p.to_dict())
        for changes in (dict(threshold=0), dict(channel=7), dict(polarity=0), dict(sample_rate=0), dict(group_gap=float("nan"))):
            detail = p.to_dict()
            detail.update(changes)
            with self.assertRaises(ValueError):
                Profile(**detail)

    def test_original_lsl_timestamps_are_retained_alongside_repaired_data(self):
        original = np.array([100, 100.00005, 100.00004, 100.00006])
        fixed = TimestampGuard(500).process(original)
        writer = SessionWriter(dict(channels=1, sample_rate=500, simulated=False,
                                    timestamp_policy=dict(max_adjustment_seconds=.001)), self.temp.name)
        self.addCleanup(writer.close)
        with self.assertRaises(ValueError):
            writer.append([[1], [2], [3], [4]], fixed)
        self.assertEqual(writer.count, 0)
        writer.append([[1], [2], [3], [4]], fixed, original)
        writer.close()
        rows = (writer.folder / "source_timestamps.csv").read_text().splitlines()
        np.testing.assert_array_equal([float(row.split(",")[1]) for row in rows[1:]], original)
        self.assertEqual([int(row.split(",")[0]) for row in rows[1:]], [0, 1, 2, 3])
        self.assertEqual(inspect_session(writer.folder)["invalid_rows"], 0)


class SourceTests(unittest.TestCase):
    def test_practice_source_is_explicitly_simulated_and_timestamped(self):
        source = DemoSource()
        source.start()
        self.addCleanup(source.stop)
        kind, meta = source.messages.get(timeout=2)
        self.assertEqual(kind, "ready")
        self.assertTrue(meta["simulated"])
        kind, chunk = source.messages.get(timeout=2)
        self.assertEqual(kind, "chunk")
        self.assertEqual(chunk.values.shape[1], 6)
        self.assertTrue(np.isfinite(chunk.values).all())
        self.assertTrue(np.all(np.diff(chunk.timestamps) > 0))

    def test_local_lsl_capture_metadata_values_and_clock(self):
        import pylsl
        name = "blink-emg-test-" + uuid.uuid4().hex
        outlet = pylsl.StreamOutlet(pylsl.StreamInfo(name, "EXG", 6, 500, pylsl.cf_float32, name))
        stop = threading.Event()

        def publish():
            while not stop.is_set():
                now = pylsl.local_clock()
                # Bluetooth-like batches, including the microsecond backwards
                # step observed in the user's actual NPG stream.
                for offset in (0, .00005, .00004, .00006, .00007):
                    outlet.push_sample([10, 20, 30, 40, 50, 60], timestamp=now + offset)
                stop.wait(.01)
        publisher = threading.Thread(target=publish, daemon=True)
        publisher.start()
        matches = pylsl.resolve_byprop("name", name, timeout=3)
        self.assertEqual(len(matches), 1, "Local LSL stream discovery failed")
        source = LSLSource(matches[0])
        try:
            source.start()
            kind, meta = source.messages.get(timeout=8)
            self.assertEqual(kind, "ready", source.error)
            self.assertFalse(meta["simulated"])
            self.assertEqual(meta["channels"], 6)
            self.assertEqual(meta["timestamp_policy"]["name"], "bounded_monotonic_v1")
            kind, chunk = source.messages.get(timeout=4)
            self.assertEqual(kind, "chunk", source.error)
            np.testing.assert_array_equal(chunk.values[0], [10, 20, 30, 40, 50, 60])
            self.assertLess(abs(source.clock() - chunk.timestamps[-1]), .5)
            self.assertTrue(np.all(np.diff(chunk.timestamps) > 0))
            self.assertIsNotNone(chunk.source_timestamps)
            self.assertTrue(np.any(np.diff(chunk.source_timestamps) <= 0))
        finally:
            source.stop()
            stop.set()
            publisher.join(timeout=2)

    def test_queue_overrun_is_an_explicit_error(self):
        source = DemoSource()
        for _ in range(41):
            source.send("chunk", None)
        self.assertIsNotNone(source.error)
        self.assertTrue(source.stop_event.is_set())


class TimestampTests(unittest.TestCase):
    def test_real_microsecond_overlap_and_duplicates_are_chunk_invariant(self):
        times = np.array([585458.9093485, 585458.9094241, 585458.9094415,
                          585458.9094483, 585458.90942155, 585458.90942765,
                          585458.90942765, 585458.93])
        original = times.copy()
        whole = TimestampGuard(500).process(times)
        guard = TimestampGuard(500)
        split = np.r_[guard.process(times[:4]), guard.process(times[4:6]), guard.process(times[6:])]
        np.testing.assert_array_equal(whole, split)
        np.testing.assert_array_equal(times, original)
        self.assertTrue(np.all(np.diff(whole) > 0))
        self.assertLess(np.max(whole - times), .001)

    def test_real_gaps_stay_visible_and_large_clock_jumps_are_rejected(self):
        times = np.array([1, .9995, 1.0996, 1.102])
        guard = TimestampGuard(500)
        fixed = np.r_[guard.process(times[:2]), guard.process(times[2:])]
        self.assertGreater(fixed[2] - fixed[1], .1)
        self.assertGreaterEqual(fixed[2] - fixed[1], times[2] - times[1])
        for invalid in ([1.09], [np.nan], [], [[1.103]]):
            with self.assertRaises(ValueError):
                guard.process(invalid)
        # A rejected chunk must not poison the last good timestamp.
        self.assertEqual(guard.process([1.104])[0], 1.104)


if __name__ == "__main__":
    unittest.main()
