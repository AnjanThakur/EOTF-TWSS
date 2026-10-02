import csv
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np

from src.acquisition.base_stream import EEGSource
from src.acquisition.beast_stream import BeastStreamer
from src.acquisition.calibration import CalibrationRunner
from src.realtime.dataset_stream import DatasetStreamer


class FakeSource(EEGSource):
    def __init__(self, samples, rate=10, names=("C1", "C2")):
        self.samples, self.sampling_rate, self.channel_names = samples, rate, names
        self.started = False
    def start(self): self.started = True
    def stop(self): self.started = False
    def get_samples(self):
        if not self.started: raise RuntimeError("not started")
        return self.samples


class AcquisitionTests(unittest.TestCase):
    def test_calibration_balanced_and_metadata(self):
        source = FakeSource(np.ones((2, 40)), 10)
        with tempfile.TemporaryDirectory() as temp:
            paths = CalibrationRunner(source, "S01", "sess_1", 2, output_root=temp, seed=3).run(sleep=False)
            self.assertEqual(len(paths), 4)
            records = [json.loads(p.with_suffix(".json").read_text()) for p in paths]
            self.assertEqual([r["label"] for r in records].count("LEFT"), 2)
            self.assertEqual([r["label"] for r in records].count("RIGHT"), 2)
            self.assertEqual(np.load(paths[0])["eeg"].shape, (2, 40))
            with (Path(temp) / "S01" / "sess_1" / "manifest.csv").open() as f:
                self.assertEqual(len(list(csv.DictReader(f))), 4)

    def test_validation(self):
        with self.assertRaises(ValueError): CalibrationRunner(FakeSource(np.ones((2,20))), "bad id!", "s")
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError): CalibrationRunner(FakeSource(np.ones((3,20))), "s", "wrong", 1, output_root=temp).run(False)
            with self.assertRaises(ValueError): CalibrationRunner(FakeSource(np.ones((2,5))), "s", "short", 1, rest_duration=1, imagery_duration=2, output_root=temp).run(False)

    def test_beast_is_explicit(self):
        beast = BeastStreamer(stream_name="TWSS intentionally absent test stream")
        with self.assertRaisesRegex(RuntimeError, "No matching LSL stream|hardware not connected/implemented"): beast.start()
        with self.assertRaisesRegex(RuntimeError, "stopped|hardware not connected/implemented"): beast.get_samples()

    def test_dataset_source_interface(self):
        source = DatasetStreamer("data")
        self.assertEqual(source.channel_names, ("FC3", "FC4", "C3", "C4", "CP3", "CP4"))
        source.start(); samples = source.get_samples(); source.stop()
        self.assertEqual(samples.shape[0], 6)
