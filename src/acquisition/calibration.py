"""Balanced motor-imagery calibration and durable trial storage."""

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
import numpy as np

VALID_LABELS = ("REST", "LEFT", "RIGHT")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def _valid_id(value: str, name: str) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise ValueError(f"Invalid {name}: use 1-64 letters, numbers, '_' or '-'.")
    return value


class CalibrationRunner:
    def __init__(self, source, subject_id: str, session_id: str, trials_per_class: int = 5,
                 sampling_rate: float | None = None, channel_names=(), rest_duration: float = 2.0,
                 imagery_duration: float = 4.0, output_root: str | Path = "data/own",
                 seed: int | None = None, simulation: bool = False, labels=("LEFT", "RIGHT")):
        self.subject_id = _valid_id(subject_id, "subject ID")
        self.session_id = _valid_id(session_id, "session ID")
        if trials_per_class < 1 or int(trials_per_class) != trials_per_class:
            raise ValueError("trials_per_class must be a positive integer.")
        self.trials_per_class = int(trials_per_class)
        self.sampling_rate = float(sampling_rate or source.sampling_rate)
        self.channel_names = tuple(channel_names or getattr(source, "channel_names", ()))
        if not self.channel_names:
            raise ValueError("At least one channel name is required.")
        if self.sampling_rate <= 0 or not np.isfinite(self.sampling_rate):
            raise ValueError("sampling_rate must be finite and positive.")
        self.rest_duration, self.imagery_duration = float(rest_duration), float(imagery_duration)
        if self.rest_duration <= 0 or self.imagery_duration <= 0:
            raise ValueError("rest_duration and imagery_duration must be positive.")
        self.source, self.output_root, self.rng = source, Path(output_root), np.random.default_rng(seed)
        self.simulation = simulation
        self.labels = tuple(labels)
        if not self.labels or any(label not in VALID_LABELS for label in self.labels):
            raise ValueError(f"labels must be drawn from {VALID_LABELS}.")

    def _capture(self, seconds: float) -> np.ndarray:
        data = self.source.get_window(seconds)
        data = np.asarray(data, dtype=float)
        required = int(round(seconds * self.sampling_rate))
        if data.ndim != 2 or data.shape[0] != len(self.channel_names):
            raise ValueError(f"Wrong channel count: expected {len(self.channel_names)}, got {data.shape[0] if data.ndim else 0}.")
        if data.shape[1] < required:
            raise ValueError(f"Incomplete trial: expected {required} samples, got {data.shape[1]}.")
        if not np.isfinite(data).all():
            raise ValueError("Missing samples: EEG contains non-finite values.")
        return data[:, :required]

    def _save(self, trial_id: int, label: str, samples: np.ndarray) -> Path:
        folder = self.output_root / self.subject_id / self.session_id
        folder.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat()
        stem = f"trial_{trial_id:04d}_{label.lower()}"
        np.savez_compressed(folder / f"{stem}.npz", eeg=samples)
        metadata = {"subject_id": self.subject_id, "session_id": self.session_id,
                    "trial_id": trial_id, "label": label, "timestamp": timestamp,
                    "sampling_rate": self.sampling_rate, "channel_names": list(self.channel_names),
                    "shape": list(samples.shape), "samples_file": f"{stem}.npz"}
        (folder / f"{stem}.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        manifest = folder / "manifest.csv"
        fields = list(metadata.keys())
        exists = manifest.exists()
        with manifest.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            if not exists: writer.writeheader()
            row = metadata.copy(); row["channel_names"] = "|".join(self.channel_names); row["shape"] = "x".join(map(str, samples.shape))
            writer.writerow(row)
        return folder / f"{stem}.npz"

    def run(self, sleep: bool = True) -> list[Path]:
        labels = [label for label in self.labels for _ in range(self.trials_per_class)]
        self.rng.shuffle(labels)
        saved = []
        self.source.start()
        try:
            for trial_id, label in enumerate(labels, 1):
                if sleep: time.sleep(self.rest_duration)
                # Cue is represented in metadata; a live UI can render it here.
                if sleep: time.sleep(self.imagery_duration)
                saved.append(self._save(trial_id, label, self._capture(self.imagery_duration)))
        finally:
            self.source.stop()
        return saved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject-id", required=True); parser.add_argument("--session-id", required=True)
    parser.add_argument("--trials-per-class", type=int, default=5); parser.add_argument("--sampling-rate", type=float, default=160)
    parser.add_argument("--rest-duration", type=float, default=2); parser.add_argument("--imagery-duration", type=float, default=4)
    parser.add_argument("--output-root", type=Path, default=Path("data/own")); parser.add_argument("--simulation", action="store_true")
    args = parser.parse_args()
    if not args.simulation:
        print("Use a live source integration for hardware calibration; --simulation is required for DatasetStreamer.")
        return 1
    from src.realtime.dataset_stream import DatasetStreamer
    source = DatasetStreamer(Path("data"))
    try:
        paths = CalibrationRunner(source, args.subject_id, args.session_id, args.trials_per_class,
                                  args.sampling_rate, source.channel_names, args.rest_duration,
                                  args.imagery_duration, args.output_root, simulation=True).run(sleep=False)
        print(f"Saved {len(paths)} trials to {args.output_root / args.subject_id / args.session_id}")
    except (OSError, ValueError, RuntimeError, StopIteration) as exc:
        print(f"Error: {exc}"); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
