"""Regression checks for the October repository/acquisition review."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import numpy as np

from src.acquisition.beast_stream import BeastStreamer
from src.acquisition.calibration import CalibrationRunner
from src.features.spatial import extract_spatial_features
from src.features.spectral import extract_spectral_features
from src.features.temporal import extract_temporal_features
from src.datasets.srm import load_srm_dataset
from src.models.fbcsp import FBCSPPipeline
from src.models.phase1_config import load_phase1_config, validate_runs
from src.realtime.dataset_stream import RawDatasetStreamer
from src.realtime.heldout_demo import heldout_trials
from tests.test_acquisition import FakeSource


class ReviewRegressions(unittest.TestCase):
    def test_srm_window_parameters_rejected_before_loading(self):
        for options in ({"window_duration": 0}, {"overlap": 1}, {"max_subjects": 0}):
            with self.assertRaises(ValueError): load_srm_dataset("missing", **options)

    def test_srm_short_file_and_inconsistent_metadata(self):
        import mne
        first = mne.io.RawArray(np.ones((2, 640)), mne.create_info(["C3", "C4"], 160, "eeg"), verbose=False)
        second = mne.io.RawArray(np.ones((2, 640)), mne.create_info(["C4", "C3"], 160, "eeg"), verbose=False)
        with tempfile.TemporaryDirectory() as temp:
            for name in ("sub-001_a.edf", "sub-001_b.edf"): (Path(temp) / name).write_bytes(b"test double")
            with patch("src.datasets.srm.mne.io.read_raw_edf", return_value=first):
                self.assertEqual(load_srm_dataset(temp, max_recordings=1).X.shape, (2, 2, 320))
            with patch("src.datasets.srm.mne.io.read_raw_edf", side_effect=[first, second]):
                with self.assertRaisesRegex(ValueError, "inconsistent"):
                    load_srm_dataset(temp)

    def test_duplicate_and_wrong_run_splits_rejected(self):
        for runs in (("R04", "R04", "R12"), ("R04", "R08", "R10")):
            with self.assertRaises(ValueError):
                validate_runs(runs)
            with self.assertRaises(ValueError):
                next(heldout_trials("missing", runs=runs))

    def test_config_cannot_silently_change_frozen_filter(self):
        config = Path("configs/phase1_config.yaml").read_text()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.yaml"
            path.write_text(config.replace("[8, 30]", "[4, 40]"))
            with self.assertRaisesRegex(ValueError, "filter"):
                load_phase1_config(path)

    def test_fbcsp_mutual_information_uses_seed(self):
        rng = np.random.default_rng(42)
        X = rng.normal(size=(20, 2, 6, 100))
        y = np.tile([1, 2], 10)
        first = FBCSPPipeline(random_state=17, n_features_to_select=3).fit(X, y)
        np.random.seed(999)
        second = FBCSPPipeline(random_state=17, n_features_to_select=3).fit(X, y)
        np.testing.assert_array_equal(first.selector_.get_support(), second.selector_.get_support())
        np.testing.assert_allclose(first.predict_proba(X), second.predict_proba(X))
        self.assertEqual(first.selector_.score_func.keywords["random_state"], 17)

    def test_small_amplitude_relative_power_is_scale_invariant(self):
        X = np.sin(2 * np.pi * 10 * np.arange(640) / 160)[None, :]
        normal = extract_spectral_features(X, 160)
        tiny = extract_spectral_features(X * 1e-9, 160)
        np.testing.assert_allclose(normal[:, 5:], tiny[:, 5:], atol=1e-12)
        self.assertGreater(tiny[:, 5:].max(), 0.9)

    def test_constant_channels_have_zero_cross_correlation(self):
        self.assertTrue(np.all(extract_spatial_features(np.ones((3, 100)))[:, 1] == 0))

    def test_nonfinite_features_rejected(self):
        X = np.ones((2, 100)); X[0, 0] = np.inf
        for extract in (extract_temporal_features, extract_spatial_features):
            with self.assertRaises(ValueError): extract(X)
        with self.assertRaises(ValueError): extract_spectral_features(X, 160)

    def test_invalid_spectral_nyquist_rejected(self):
        with self.assertRaisesRegex(ValueError, "Nyquist"):
            extract_spectral_features(np.ones((2, 100)), 50)

    def test_calibration_flow_clears_before_cue_and_saves_after_rest(self):
        events = []
        source = FakeSource(np.ones((2, 40)))
        source.discard_pending = lambda: events.append("flush")
        original = source.get_window
        source.get_window = lambda seconds: (events.append("capture"), original(seconds))[1]
        with tempfile.TemporaryDirectory() as temp:
            runner = CalibrationRunner(source, "P01", "session", 1, labels=("LEFT",),
                                       output_root=temp, cue_callback=events.append)
            save = runner._save
            runner._save = lambda *args: (events.append("save"), save(*args))[1]
            with patch("src.acquisition.calibration.time", wraps=time) as clock:
                clock.sleep.side_effect = lambda seconds: events.append("wait")
                runner.run()
            self.assertEqual(events, ["REST", "wait", "flush", "LEFT", "capture", "wait", "REST", "wait", "save"])
            self.assertFalse(source.started)

    def test_calibration_rate_is_checked_after_start(self):
        source = FakeSource(np.ones((2, 40)), rate=0)
        source.start = lambda: (setattr(source, "started", True), setattr(source, "sampling_rate", 10))
        with tempfile.TemporaryDirectory() as temp:
            runner = CalibrationRunner(source, "P01", "session", 1, labels=("LEFT",), output_root=temp, cue_callback=lambda _: None)
            runner.run(False)
            self.assertEqual(runner.sampling_rate, 10)
            with self.assertRaises(FileExistsError): runner.run(False)

    def test_calibration_failure_preserves_state_and_no_invalid_npz(self):
        source = FakeSource(np.ones((2, 3)))
        with tempfile.TemporaryDirectory() as temp:
            runner = CalibrationRunner(source, "P01", "session", 1, output_root=temp, cue_callback=lambda _: None)
            with self.assertRaisesRegex(ValueError, "Incomplete"):
                runner.run(False)
            folder = Path(temp) / "P01/session"
            self.assertEqual(json.loads((folder / "session.json").read_text())["status"], "failed")
            self.assertFalse(list(folder.glob("*.npz")))
            self.assertFalse(source.started)

    def test_raw_dataset_simulation_four_seconds_and_provenance(self):
        source = RawDatasetStreamer("data")
        with tempfile.TemporaryDirectory() as temp:
            paths = CalibrationRunner(source, "SIM", "review", 1, output_root=temp,
                                      simulation=True, cue_callback=lambda _: None).run(False)
            for path in paths:
                with np.load(path) as trial:
                    self.assertEqual(trial["eeg"].shape, (6, 640))
                record = json.loads(path.with_suffix(".json").read_text())
                self.assertTrue(record["simulation"])
                self.assertIn("T1" if record["label"] == "LEFT" else "T2", record["source"])
                self.assertEqual(record["samples_kind"], "raw_dataset_replay")

    def test_lsl_ambiguous_selection_rejected(self):
        with patch("src.acquisition.beast_stream.discover_streams", return_value=[Mock(), Mock()]):
            with self.assertRaisesRegex(RuntimeError, "Multiple"):
                BeastStreamer().start()

    def test_lsl_stopped_and_stale_windows_rejected(self):
        source = BeastStreamer()
        with self.assertRaisesRegex(RuntimeError, "stopped"):
            source.get_window(3)
        source._thread = Mock(); source._thread.is_alive.return_value = True
        source._stop.clear(); source.sampling_rate = 10
        source._last_received = time.monotonic() - 3
        source._buffer.extend((i / 10, np.ones(6)) for i in range(30))
        with self.assertRaises(TimeoutError): source.get_window(3)

    def test_lsl_nonfinite_chunk_rejected(self):
        source = BeastStreamer(sample_timeout=0.01)
        source.channel_names = tuple(f"CH{i}" for i in range(6))
        source._last_received = time.monotonic()
        inlet = Mock(); inlet.pull_chunk.return_value = ([[np.nan] * 6], [1.0])
        source._pull_loop(inlet)
        self.assertIsInstance(source._error, ValueError)

    def test_lsl_silent_publisher_times_out(self):
        source = BeastStreamer(sample_timeout=0.01)
        source._last_received = time.monotonic() - 1
        inlet = Mock(); inlet.pull_chunk.return_value = ([], [])
        source._pull_loop(inlet)
        self.assertIsInstance(source._error, TimeoutError)

    def test_lsl_timestamp_gaps_rejected(self):
        source = BeastStreamer(); source.sampling_rate = 10
        source._buffer.extend([(0.0, np.ones(6)), (1.0, np.ones(6))])
        with self.assertRaisesRegex(ValueError, "Missing"):
            source._consume(2)
