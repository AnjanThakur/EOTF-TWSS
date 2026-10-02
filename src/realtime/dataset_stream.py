"""Replay complete PhysioNet trials; this is offline replay, not live EEG."""

from pathlib import Path
import math
import time

from src.models.train_csp_lda import load_subject
from src.realtime.trial import Trial
from src.acquisition.base_stream import EEGSource


class DatasetStreamer(EEGSource):
    """Offline source exposing existing preprocessed trials through EEGSource."""
    def __init__(self, data_dir: str | Path, interval: float = 0.0):
        if interval < 0 or not math.isfinite(interval):
            raise ValueError("Replay interval must be finite and nonnegative.")
        self.data_dir, self.interval = Path(data_dir), interval
        self.sampling_rate = 160.0
        self.channel_names = ("FC3", "FC4", "C3", "C4", "CP3", "CP4")
        self._trials = None
        self._started = False

    def start(self) -> None:
        X, y, groups = load_subject(self.data_dir)
        self._trials = iter((Trial(data=d, actual_label=int(label), source=f"{run} trial {i}")
                             for i, (d, label, run) in enumerate(zip(X, y, groups), 1)))
        self._started = True

    def stop(self) -> None:
        self._started = False
        self._trials = None

    def get_samples(self):
        if not self._started:
            raise RuntimeError("DatasetStreamer is not started.")
        try:
            trial = next(self._trials)
        except StopIteration:
            raise StopIteration("DatasetStreamer replay is complete.") from None
        if self.interval:
            time.sleep(self.interval)
        self._last_trial = trial
        return trial.data

    def get_window(self, seconds: float):
        data = self.get_samples()
        return _window(data, seconds, self.sampling_rate)


def _window(data, seconds, sampling_rate):
    if seconds <= 0 or not math.isfinite(seconds):
        raise ValueError("Window duration must be finite and positive.")
    required = int(round(seconds * sampling_rate))
    if data.ndim != 2 or data.shape[1] < required:
        raise ValueError(f"Incomplete trial: need {required} samples, got {data.shape[-1]}.")
    return data[:, :required]


def dataset_stream(data_dir: str | Path, interval: float = 0.0):
    """Yield S001 R04/R08/R12 epochs in run/event order using shared preprocessing.

    interval=3 approximates arrival of one complete epoch every three seconds;
    interval=0 replays immediately for testing. No model fitting occurs here.
    """
    source = DatasetStreamer(data_dir, interval)
    source.start()
    while True:
        try:
            data = source.get_samples()
            yield Trial(data=data, actual_label=source._last_trial.actual_label,
                        source=source._last_trial.source)
        except StopIteration:
            source.stop()
            return


class RawDatasetStreamer(EEGSource):
    """Calibration storage simulation using raw cue-matched EDF windows.

    This is not a live participant recording. Unlike DatasetStreamer inference
    replay, it does not band-pass or epoch at 0.5 s and does not relabel trials.
    """
    def __init__(self, data_dir, subject="S001"):
        self.data_dir, self.subject = Path(data_dir), subject
        self.sampling_rate = 0.0
        self.channel_names = ()
        self.channel_units = ()
        self._windows = None
        self._label = "LEFT"
        self.source = ""
        self.samples_kind = "raw_dataset_replay"

    def start(self):
        from src.models.train_csp_lda import RUNS, find_run, select_channels
        from src.preprocessing.preprocess import load_eeg
        self._windows = {"LEFT": [], "RIGHT": [], "REST": []}
        self._positions = {name: 0 for name in self._windows}
        for run in RUNS:
            raw = select_channels(load_eeg(find_run(self.data_dir, run, self.subject)))
            rate = float(raw.info["sfreq"])
            if self.sampling_rate and self.sampling_rate != rate:
                raise ValueError("Dataset sampling rates differ between runs.")
            self.sampling_rate, self.channel_names = rate, tuple(raw.ch_names)
            self.channel_units = ("V",) * len(self.channel_names)
            samples = raw.get_data()
            for onset, duration, annotation in zip(raw.annotations.onset, raw.annotations.duration,
                                                   raw.annotations.description):
                label = {"T0": "REST", "T1": "LEFT", "T2": "RIGHT"}.get(annotation)
                if label:
                    begin = int(round(onset * rate))
                    end = min(samples.shape[1], begin + int(round(duration * rate)))
                    self._windows[label].append((samples[:, begin:end], f"{self.subject}{run} {annotation} onset={onset}"))

    def set_trial_label(self, label):
        self._label = label

    def get_samples(self):
        if self._windows is None:
            raise RuntimeError("RawDatasetStreamer is not started.")
        index = self._positions[self._label]
        if index >= len(self._windows[self._label]):
            raise StopIteration(f"No more raw {self._label} dataset trials.")
        data, self.source = self._windows[self._label][index]
        self._positions[self._label] += 1
        return data.copy()

    def stop(self):
        self._windows = None
