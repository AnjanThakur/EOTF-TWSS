"""Cue-locked calibration with raw samples, provenance and session protection."""
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


def _valid_id(value, name):
    reserved = {"CON", "PRN", "AUX", "NUL"} | {f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10)}
    if not isinstance(value, str) or not ID_RE.fullmatch(value) or value.upper() in reserved:
        raise ValueError(f"Invalid {name}: use 1-64 letters, numbers, '_' or '-'; avoid reserved device names.")
    return value


class CalibrationRunner:
    def __init__(self, source, subject_id, session_id, trials_per_class=5,
                 sampling_rate=None, channel_names=(), rest_duration=2.0,
                 imagery_duration=4.0, output_root="data/own", seed=None,
                 simulation=False, labels=("LEFT", "RIGHT"), cue_callback=print):
        self.subject_id = _valid_id(subject_id, "subject ID")
        self.session_id = _valid_id(session_id, "session ID")
        if trials_per_class < 1 or int(trials_per_class) != trials_per_class:
            raise ValueError("trials_per_class must be a positive integer.")
        self.trials_per_class = int(trials_per_class)
        self.sampling_rate = sampling_rate
        if sampling_rate is not None and (not np.isfinite(sampling_rate) or sampling_rate <= 0):
            raise ValueError("sampling_rate must be finite and positive.")
        self.channel_names = tuple(channel_names)
        self.rest_duration, self.imagery_duration = float(rest_duration), float(imagery_duration)
        if not np.isfinite([self.rest_duration, self.imagery_duration]).all() or min(self.rest_duration, self.imagery_duration) <= 0:
            raise ValueError("rest_duration and imagery_duration must be finite and positive.")
        self.source, self.output_root = source, Path(output_root)
        self.seed, self.rng = seed, np.random.default_rng(seed)
        self.simulation, self.cue_callback = simulation, cue_callback
        self.labels = tuple(labels)
        if not self.labels or len(set(self.labels)) != len(self.labels) or any(label not in VALID_LABELS for label in self.labels):
            raise ValueError(f"labels must be distinct and drawn from {VALID_LABELS}.")

    def _check_metadata(self):
        rate = float(self.source.sampling_rate)
        if not np.isfinite(rate) or rate <= 0:
            raise ValueError("Source sampling_rate must be finite and positive.")
        if self.sampling_rate is not None and self.sampling_rate != rate:
            raise ValueError(f"Configured sampling rate {self.sampling_rate} differs from source rate {rate}.")
        self.sampling_rate = rate
        self.channel_names = self.channel_names or tuple(self.source.channel_names)
        if not self.channel_names or len(set(self.channel_names)) != len(self.channel_names):
            raise ValueError("Channel names must be nonempty and unique.")
        if len(self.channel_names) != len(self.source.channel_names):
            raise ValueError("Wrong channel count in configured channel names.")

    def _capture(self, seconds):
        data = np.asarray(self.source.get_window(seconds), dtype=float)
        required = int(round(seconds * self.sampling_rate))
        if required < 1:
            raise ValueError("Trial is shorter than one sample.")
        if data.ndim != 2 or data.shape[0] != len(self.channel_names):
            raise ValueError(f"Wrong channel count: expected {len(self.channel_names)}, got shape {data.shape}.")
        if data.shape[1] != required:
            raise ValueError(f"Incomplete trial: expected {required} samples, got {data.shape[1]}.")
        if not np.isfinite(data).all():
            raise ValueError("Missing samples: EEG contains non-finite values.")
        return data

    def _save(self, folder, trial_id, label, samples, cue_timestamp, timestamps):
        stem = f"trial_{trial_id:04d}_{label.lower()}"
        metadata = {"subject_id": self.subject_id, "session_id": self.session_id,
                    "trial_id": trial_id, "label": label, "timestamp": cue_timestamp,
                    "saved_at": datetime.now(timezone.utc).isoformat(),
                    "sampling_rate": self.sampling_rate, "channel_names": list(self.channel_names),
                    "channel_units": list(getattr(self.source, "channel_units", ("unknown",) * len(self.channel_names))),
                    "shape": list(samples.shape), "samples_file": f"{stem}.npz",
                    "simulation": self.simulation, "source": getattr(self.source, "source", type(self.source).__name__),
                    "samples_kind": getattr(self.source, "samples_kind", "raw_lsl_native_units"),
                    "rest_duration": self.rest_duration, "imagery_duration": self.imagery_duration,
                    "seed": self.seed}
        # Both NPZ and JSON carry essential labels/metadata; load NPZ without pickle.
        np.savez_compressed(folder / f"{stem}.npz", eeg=samples, timestamps=timestamps,
                            subject_id=self.subject_id, session_id=self.session_id,
                            trial_id=trial_id, label=label, timestamp=cue_timestamp,
                            sampling_rate=self.sampling_rate, channel_names=self.channel_names,
                            metadata_json=json.dumps(metadata))
        (folder / f"{stem}.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        manifest = folder / "manifest.csv"
        exists = manifest.exists()
        with manifest.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(metadata))
            if not exists:
                writer.writeheader()
            writer.writerow(metadata)
        return folder / f"{stem}.npz"

    def run(self, sleep=True):
        labels = [label for label in self.labels for _ in range(self.trials_per_class)]
        self.rng.shuffle(labels)
        folder = self.output_root / self.subject_id / self.session_id
        # Refuse session reuse: never overwrite trials or append duplicate trial IDs.
        folder.mkdir(parents=True, exist_ok=False)
        state = {"subject_id": self.subject_id, "session_id": self.session_id,
                 "simulation": self.simulation, "labels": labels, "seed": self.seed,
                 "status": "recording", "saved_trials": 0}
        def write_state():
            (folder / "session.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
        write_state()
        saved = []
        try:
            self.source.start()
            self._check_metadata()
            for trial_id, label in enumerate(labels, 1):
                self.cue_callback("REST")
                if sleep:
                    time.sleep(self.rest_duration)
                if hasattr(self.source, "discard_pending"):
                    self.source.discard_pending()
                if hasattr(self.source, "set_trial_label"):
                    self.source.set_trial_label(label)
                cue_timestamp = datetime.now(timezone.utc).isoformat()
                self.cue_callback(label)
                begin = time.monotonic()
                samples = self._capture(self.imagery_duration)
                stamps = np.asarray(getattr(self.source, "last_timestamps", []), dtype=float).copy()
                if sleep:
                    time.sleep(max(0, self.imagery_duration - (time.monotonic() - begin)))
                self.cue_callback("REST")
                if sleep:
                    time.sleep(self.rest_duration)
                saved.append(self._save(folder, trial_id, label, samples, cue_timestamp, stamps))
                state["saved_trials"] = len(saved)
                write_state()
            state["status"] = "complete"
        except Exception as exc:
            state.update(status="failed", error=str(exc))
            raise
        finally:
            write_state()
            self.source.stop()
        return saved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--trials-per-class", type=int, default=5)
    parser.add_argument("--sampling-rate", type=float, default=None, help="Optional expected rate; never overrides LSL metadata.")
    parser.add_argument("--channel-names", nargs="+", help="Names in confirmed physical channel order.")
    parser.add_argument("--rest-duration", type=float, default=2)
    parser.add_argument("--imagery-duration", type=float, default=4)
    parser.add_argument("--output-root", type=Path, default=Path("data/own"))
    parser.add_argument("--simulation", action="store_true")
    parser.add_argument("--stream-name")
    parser.add_argument("--stream-type")
    parser.add_argument("--source-id")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    if args.simulation:
        from src.realtime.dataset_stream import RawDatasetStreamer
        source = RawDatasetStreamer("data")
    else:
        from src.acquisition.beast_stream import BeastStreamer
        source = BeastStreamer(stream_name=args.stream_name, stream_type=args.stream_type,
                               source_id=args.source_id)
    try:
        paths = CalibrationRunner(source, args.subject_id, args.session_id, args.trials_per_class,
                                  args.sampling_rate, args.channel_names or (), args.rest_duration,
                                  args.imagery_duration, args.output_root, args.seed,
                                  args.simulation).run(sleep=not args.simulation)
        print(f"Saved {len(paths)} trials to {args.output_root / args.subject_id / args.session_id}")
    except (OSError, ValueError, RuntimeError, StopIteration) as exc:
        print(f"Error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
