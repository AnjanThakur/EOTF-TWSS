from pathlib import Path
import json
import queue
import tempfile
import threading
import time
import tkinter as tk
import unittest
from unittest.mock import patch

import numpy as np

from blink_emg_app.app import Application
from blink_emg_app.config import ROOT, Profile
from blink_emg_app.replay import replay_validation
from blink_emg_app.sources import Chunk, simulated_values, TimestampGuard
from blink_emg_app.storage import inspect_session


class FakeSource:
    def __init__(self):
        self.now = 0.0
        self.error = None
        self.messages = queue.Queue()

    def clock(self):
        return self.now

    def stop(self):
        pass


class DesktopFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "tests")
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = Application(self.root, Path(self.temp.name) / "data", Path(self.temp.name) / "profiles")
        self.app.audio_enabled.set(False)
        self.source = FakeSource()
        self.app.source = self.source
        self.app.on_ready(dict(name="Test stream", channels=6, sample_rate=500, source_id="test",
                               simulated=True, source_key="DEMO:v1:6:500"))
        self.sample_index = 0
        self.blink_times = []
        self.timing = None
        self.interrupt_label = None
        self.interrupt_mode = "gap"
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.app.close)

    def feed_until(self, end):
        end_index = int(round(end * 500))
        while self.sample_index < end_index:
            limit = min(end_index, self.sample_index + 125)
            t = np.arange(self.sample_index, limit) / 500
            self.source.now = float(t[-1] + .002)
            if self.timing is None:
                chunk = Chunk(simulated_values(t, self.blink_times), t)
            else:
                indices = np.arange(self.sample_index, limit)
                original = (indices // 10) * .02 + (indices % 10) * .000006
                original[indices % 10 == 5] -= .00003
                chunk = Chunk(simulated_values(t, self.blink_times), self.timing.process(original), original)
            self.app.on_chunk(chunk)
            self.sample_index = limit

    def follow_protocol(self, kind):
        self.app.start_protocol(kind)
        self.assertEqual(self.app.protocol_kind, kind)
        while self.app.protocol_kind:
            w = self.app.active_window
            if w is None:
                self.feed_until(self.source.now + .25)
                self.app.advance_protocol()
                continue
            count = {"SINGLE": 1, "NEXT": 2, "SELECT": 3}.get(w.label)
            if count:
                self.blink_times.extend(w.start + .7 + .48 * i for i in range(count))
            elif w.label == "NORMAL":
                self.blink_times.extend(np.arange(w.start + 4, w.end - 1, 5).tolist())
            if self.interrupt_label == w.label:
                self.interrupt_label = None
                self.feed_until(w.start + 1.2)
                if self.interrupt_mode == "gap":
                    self.sample_index += 60  # Real 120 ms gap, no invented samples.
                    self.feed_until(self.source.now + .5)
                else:
                    # One second of UI backlog: raw data remains continuous,
                    # but stale chunks must never enter detection or scoring.
                    self.source.now += 1
                    until = int(round(self.source.now * 500))
                    while self.sample_index < until:
                        end = min(until, self.sample_index + 125)
                        times = np.arange(self.sample_index, end) / 500
                        self.app.on_chunk(Chunk(simulated_values(times, self.blink_times), times))
                        self.sample_index = end
                self.assertEqual(self.app.protocol_kind, kind)
                self.assertIsNone(self.app.active_window)
                self.assertNotIn(w, self.app.windows)
                self.assertFalse(self.app.menu.armed)
                continue
            self.feed_until(w.end + .12)
            self.app.next_step()
        deadline = time.monotonic() + 5
        while self.app.analysis_job and time.monotonic() < deadline:
            # The real acquisition worker continues streaming during analysis.
            # Keep this fake source alive too: otherwise a slower calibration
            # makes the next protocol fail the unrelated 0.5 s freshness guard.
            self.feed_until(self.source.now + .025)
            self.app.collect_analysis_results()
            time.sleep(.005)
        self.assertIsNone(self.app.analysis_job, "Background analysis did not finish")

    def test_quick_check_scores_fresh_signals_and_replays_without_unlocking_control(self):
        self.feed_until(3)
        previous_profile = self.app.profile.to_dict()
        self.app.toggle_control()
        self.assertTrue(self.app.menu.armed)
        self.follow_protocol("quick")
        self.assertFalse(self.app.validated)
        self.assertFalse(self.app.menu.armed)
        self.assertEqual(self.app.profile.to_dict(), previous_profile)
        self.assertEqual(self.app.cue_title.cget("text"), "Quick check finished")
        self.assertIn("6/6 correct", self.app.cue_detail.cget("text"))
        self.assertEqual(self.app.arm_button.cget("state"), "disabled")
        self.app.toggle_control()
        self.assertFalse(self.app.menu.armed)
        folder = self.app.writer.folder
        self.app.disconnect()
        self.assertTrue((folder / "quick_check.json").exists())
        self.assertFalse((folder / "validation.json").exists())
        report = replay_validation(folder)
        self.assertEqual(report["check_type"], "quick")
        self.assertEqual(report["total_trials"], 6)
        self.assertEqual(report["correct_trials"], 6)
        self.assertFalse(report["passed"])

    def test_full_desktop_calibration_fresh_check_control_and_raw_replay(self):
        self.feed_until(3)
        self.follow_protocol("calibration")
        self.assertIsNotNone(self.app.profile, self.app.cue_detail.cget("text"))
        self.assertFalse(self.app.validated)
        self.app.toggle_control()
        self.assertFalse(self.app.menu.armed)
        self.follow_protocol("validation")
        self.assertTrue(self.app.validated, self.app.cue_detail.cget("text"))
        self.assertEqual(self.app.profile.validation["correct_trials"], 8)
        self.app.toggle_control()
        self.assertTrue(self.app.menu.armed)
        start = self.source.now + .5
        self.blink_times.extend([start, start + .48])
        self.feed_until(start + 1.8)
        self.assertEqual(self.app.menu.index, 1)
        start = self.source.now + .5
        self.blink_times.extend([start, start + .48, start + .96])
        self.feed_until(start + 2.1)
        self.assertEqual(self.app.spoken.cget("text"), "I would like food.")
        folder = self.app.writer.folder
        self.app.disconnect()
        report = inspect_session(folder)
        self.assertEqual(report["status"], "complete")
        self.assertTrue(report["simulated"])
        self.assertGreater(report["sample_count"], 65000)
        replay = replay_validation(folder)
        self.assertEqual(replay["correct_trials"], 8)
        self.assertTrue(replay["passed"])
        self.assertTrue(replay["simulated"])

    def test_delayed_data_is_saved_but_excluded_from_retaken_trial_and_replay(self):
        self.interrupt_mode = "delay"
        self.test_gap_retakes_only_interrupted_trial_and_saved_replay_agrees()

    def test_bluetooth_batch_timestamp_glitches_survive_full_calibration_and_check(self):
        self.app.disconnect()
        self.app.source = self.source
        self.app.on_ready(dict(name="Test stream", channels=6, sample_rate=500, source_id="test",
                               simulated=True, source_key="DEMO:v1:6:500",
                               timestamp_policy=dict(max_adjustment_seconds=.001)))
        self.timing = TimestampGuard(500)
        self.test_full_desktop_calibration_fresh_check_control_and_raw_replay()
        folders = list((Path(self.temp.name) / "data").glob("*/source_timestamps.csv"))
        self.assertEqual(len(folders), 1)
        self.assertGreater(folders[0].stat().st_size, 1000000)

    def test_gap_retakes_only_interrupted_trial_and_saved_replay_agrees(self):
        self.interrupt_label = "NEXT"
        self.test_full_desktop_calibration_fresh_check_control_and_raw_replay()
        reports = list((Path(self.temp.name) / "data").glob("*/validation.json"))
        self.assertEqual(len(reports), 1)
        # Legacy live cues used a second clock read; fake source tests had
        # hidden that tiny difference. Invalidation must match the active
        # attempt's index, not float equality between those clock reads.
        events_path = reports[0].parent / "events.jsonl"
        events = [json.loads(line) for line in events_path.read_text().splitlines()]
        for event in events:
            if event["kind"] == "cue":
                event["timestamp"] += .00005
            elif event["kind"] == "protocol_start":
                event.pop("detector_version", None)
        events_path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
        replay = replay_validation(reports[0].parent)
        self.assertEqual(replay["repeated_steps"], 1)
        self.assertEqual(replay["total_trials"], 8)
        self.assertTrue(replay["passed"])
        self.assertEqual(replay["recorded_detector_version"], "release_refractory_v1")

    def test_pause_cancel_settings_change_and_reconnect_remain_disarmed(self):
        self.feed_until(3)
        self.app.toggle_control()
        self.assertTrue(self.app.menu.armed)
        self.app.pause()
        self.assertFalse(self.app.menu.armed)
        self.app.sensitivity.set(1.2)
        old_id = self.app.profile.profile_id
        self.app.apply_settings()
        self.assertNotEqual(self.app.profile.profile_id, old_id)
        self.assertFalse(self.app.validated)
        self.app.start_protocol("calibration")
        self.app.pause()
        self.assertIsNone(self.app.protocol_kind)
        self.app.disconnect()
        self.assertFalse(self.app.menu.armed)
        self.assertIsNone(self.app.profile)

    def test_stale_input_and_flat_signal_cannot_operate_menu(self):
        self.feed_until(3)
        self.app.toggle_control()
        self.source.now = 10
        self.app.on_chunk(Chunk([[2000] * 6], [3.1]))
        self.assertIs(self.app.source, self.source)
        self.assertFalse(self.app.menu.armed)
        self.assertFalse(self.app.validated)
        self.assertFalse(self.app.is_fresh())
        # Fresh input resumes recording on the same connection. Old gestures
        # cannot cross the interruption or turn control back on.
        self.sample_index = 5000
        self.feed_until(12)
        self.assertTrue(self.app.is_fresh())
        self.assertIs(self.app.source, self.source)
        self.app.validated = True
        self.app.toggle_control()
        self.assertTrue(self.app.menu.armed)
        # A stuck channel also pauses and invalidates an already armed setup.
        t = np.arange(12, 14, .002)
        self.source.now = 14
        self.app.on_chunk(Chunk(np.full((len(t), 6), 2000), t))
        self.assertFalse(self.app.menu.armed)
        self.assertFalse(self.app.validated)

    def test_future_clock_is_rejected_and_delay_retries_until_user_cancels(self):
        self.feed_until(3)
        with self.assertRaisesRegex(ValueError, "ahead of the app"):
            self.app.on_chunk(Chunk([[2000] * 6], [4]))
        self.app.start_protocol("calibration")
        self.source.now = 4
        self.app.on_chunk(Chunk([[2000] * 6], [3.1]))
        self.assertEqual(self.app.protocol_kind, "calibration")
        self.assertIsNone(self.app.active_window)
        self.assertIsNotNone(self.app.retry_until)
        self.assertIsNone(self.app.analysis_job)
        self.assertIs(self.app.source, self.source)
        self.assertFalse(self.app.menu.armed)
        events = (self.app.writer.folder / "events.jsonl").read_text()
        self.assertIn('"kind": "delayed_chunk"', events)
        self.assertIn('"age_seconds":', events)
        self.assertNotIn('"kind": "protocol_complete"', events)
        self.app.pause()
        self.assertIsNone(self.app.protocol_kind)
        self.assertIsNone(self.app.retry_until)
        self.app.advance_protocol()
        self.assertIsNone(self.app.active_window)

    def wait_for(self, predicate, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.root.update()
            if predicate():
                return
            time.sleep(.005)
        self.fail("Timed out: " + self.app.status.cget("text"))

    def test_slow_calibration_keeps_receiving_live_samples(self):
        self.app.disconnect()
        self.app.practice()
        self.wait_for(self.app.is_fresh)
        gate = threading.Event()
        entered = threading.Event()
        self.addCleanup(gate.set)
        result = Profile(**self.app.profile.to_dict())
        result.calibration["correctly_counted"] = 8

        def slow_calibration(*args):
            entered.set()
            if not gate.wait(5):
                raise RuntimeError("Test worker was never released")
            return result

        with patch("blink_emg_app.app.calibrate", side_effect=slow_calibration):
            self.app.protocol_kind = "calibration"
            started = time.monotonic()
            self.app.finish_protocol()
            self.assertLess(time.monotonic() - started, .3)
            self.assertTrue(entered.wait(1))
            self.assertEqual(self.app.calibrate_button.cget("state"), "disabled")
            self.assertEqual(self.app.arm_button.cget("state"), "disabled")
            initial = self.app.writer.count
            # More than the old 0.5-second limit passes while fitting is held.
            self.wait_for(lambda: self.app.writer.count >= initial + 600, timeout=3)
            self.assertIsNotNone(self.app.analysis_job)
            self.assertTrue(self.app.is_fresh())
            self.assertIsNone(self.app.source.error)
            self.assertFalse(self.app.menu.armed)
            gate.set()
            self.wait_for(lambda: self.app.analysis_job is None)
        self.assertEqual(self.app.profile.profile_id, result.profile_id)
        self.assertIn("calibrated", self.app.cue_title.cget("text"))
        self.assertFalse(self.app.validated)
        self.assertNotIn('"kind": "delayed_chunk"', (self.app.writer.folder / "events.jsonl").read_text())

    def test_cancelled_analysis_cannot_change_a_reconnected_session(self):
        gate = threading.Event()
        self.addCleanup(gate.set)
        result = Profile(**self.app.profile.to_dict())
        result.profile_id = "cancelled-old-result"
        result.calibration["correctly_counted"] = 8

        def slow_calibration(*args):
            gate.wait(5)
            return result

        with patch("blink_emg_app.app.calibrate", side_effect=slow_calibration):
            self.app.protocol_kind = "calibration"
            self.app.finish_protocol()
            worker = next(t for t in threading.enumerate() if t.name == "blink-protocol-analysis")
            old_folder = self.app.writer.folder
            self.app.disconnect()
            self.app.source = self.source
            self.app.on_ready(dict(name="Test stream", channels=6, sample_rate=500,
                                   simulated=True, source_key="DEMO:v1:6:500"))
            new_id = self.app.profile.profile_id
            gate.set()
            worker.join(timeout=2)
            self.assertFalse(worker.is_alive())
            self.app.collect_analysis_results()
        self.assertEqual(self.app.profile.profile_id, new_id)
        self.assertIsNone(self.app.analysis_job)
        self.assertNotEqual(self.app.writer.folder, old_folder)
        self.assertNotIn('"kind": "protocol_complete"', (self.app.writer.folder / "events.jsonl").read_text())

    def test_controls_and_layout_have_room_at_default_size(self):
        self.root.attributes("-alpha", 0)
        self.root.deiconify()
        self.root.update()
        self.assertEqual(self.app.arm_button.cget("state"), "normal")
        self.assertEqual(len(self.app.tiles), 6)
        self.assertEqual(len(self.app.tabs.tabs()), 4)
        self.assertGreater(self.app.tiles[0].winfo_reqwidth(), 100)
        self.assertGreater(self.app.tiles[0].winfo_height(), 60)
        side = self.app.sidebar_hint.master
        self.assertGreater(self.app.pause_button.winfo_height(), 25)
        self.assertLessEqual(self.app.sidebar_hint.winfo_y() + self.app.sidebar_hint.winfo_height(), side.winfo_height())
        self.assertEqual(self.app.root.title(), "Blink to Speak | blink_emg")

    def test_real_practice_worker_drives_tk_polling_and_menu(self):
        self.app.disconnect()
        self.app.practice()
        self.root.attributes("-alpha", 0)
        self.root.deiconify()

        def wait_for(predicate, timeout):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                self.root.update()
                if predicate():
                    return
                time.sleep(.01)
            self.fail("Timed out: " + self.app.status.cget("text"))

        wait_for(self.app.is_fresh, 5)
        self.app.toggle_control()
        self.assertTrue(self.app.menu.armed)
        self.app.inject(2)
        wait_for(lambda: self.app.menu.index == 1, 3)
        self.app.inject(3)
        wait_for(lambda: self.app.spoken.cget("text") == "I would like food.", 4)
        self.assertIsNone(self.app.source.error)
        self.assertGreater(self.app.writer.count, 2000)

    def test_disk_failure_still_disconnects_and_disarms(self):
        self.feed_until(3)
        self.app.toggle_control()
        writer = self.app.writer
        with patch.object(writer, "event", side_effect=OSError("Disk is full")):
            self.app.disconnect(error="Disk is full")
        self.assertIsNone(self.app.source)
        self.assertIsNone(self.app.writer)
        self.assertFalse(self.app.menu.armed)
        self.assertTrue(writer.closed)
        self.assertIn("could not finish saving", self.app.status.cget("text"))


if __name__ == "__main__":
    unittest.main()
