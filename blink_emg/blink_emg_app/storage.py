"""Stream to disk continuously; retain partial recordings after interruption."""
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import uuid

import numpy as np

from .config import DATA_HOME, atomic_json


class SessionWriter:
    def __init__(self, metadata, root=None):
        root = Path(root or DATA_HOME / "data")
        root.mkdir(parents=True, exist_ok=True)
        name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:8]
        self.folder = root / name
        self.folder.mkdir()
        self.metadata = dict(metadata, session_id=name, status="recording", sample_count=0,
                             started_utc=datetime.now(timezone.utc).isoformat(),
                             units="native stream values; voltage conversion not assumed",
                             modality="forehead eye-blink signal (EOG/ocular artifact), not imagined speech",
                             channels=["A0 / CH1", "A1 / CH2", "A2 / CH3", "A3 / CH4", "A4 / CH5", "A5 / CH6"][:metadata["channels"]])
        self.count = 0
        self.last_timestamp = None
        self.closed = False
        self.last_flush = time.monotonic()
        self.raw = (self.folder / "samples.csv").open("w", newline="", encoding="utf-8")
        self.events = (self.folder / "events.jsonl").open("w", encoding="utf-8")
        self.csv = csv.writer(self.raw)
        self.csv.writerow(["timestamp"] + [f"ch{i + 1}" for i in range(metadata["channels"])])
        self.source_times = self.source_csv = None
        if metadata.get("timestamp_policy"):
            self.metadata["source_timestamps_file"] = "source_timestamps.csv"
            self.source_times = (self.folder / "source_timestamps.csv").open("w", newline="", encoding="utf-8")
            self.source_csv = csv.writer(self.source_times)
            self.source_csv.writerow(["sample_index", "lsl_clock_corrected_timestamp"])
        atomic_json(self.folder / "metadata.json", self.metadata)
        self.event("session_start", None)

    @property
    def session_id(self):
        return self.folder.name

    def append(self, values, timestamps, source_timestamps=None):
        values, timestamps = np.asarray(values), np.asarray(timestamps)
        if (values.ndim != 2 or values.shape[1] != len(self.metadata["channels"])
                or timestamps.shape != (len(values),) or not len(values)
                or not np.isfinite(values).all() or not np.isfinite(timestamps).all()
                or np.any(np.diff(timestamps) <= 0)
                or self.last_timestamp is not None and timestamps[0] <= self.last_timestamp):
            raise ValueError("Invalid recording samples or timestamp order.")
        if self.source_csv is not None:
            original = np.asarray(source_timestamps, dtype=float)
            limit = self.metadata["timestamp_policy"]["max_adjustment_seconds"]
            if (original.shape != timestamps.shape or not np.isfinite(original).all()
                    or np.any(timestamps < original) or np.any(timestamps - original > limit)):
                raise ValueError("Missing or invalid original LSL timestamps.")
            self.source_csv.writerows(zip(range(self.count, self.count + len(values)), original.tolist()))
        self.csv.writerows(np.column_stack([timestamps, values]).tolist())
        self.count += len(values)
        self.last_timestamp = float(timestamps[-1])
        if time.monotonic() - self.last_flush >= 1:
            self.flush()

    def event(self, kind, timestamp, **detail):
        if self.closed:
            return
        self.events.write(json.dumps(dict(kind=kind, timestamp=timestamp, **detail), allow_nan=False) + "\n")
        self.events.flush()

    def artifact(self, name, value):
        if Path(name).name != name:
            raise ValueError("Use a local artifact filename.")
        atomic_json(self.folder / name, value)

    def flush(self):
        if self.closed:
            return
        self.raw.flush()
        self.events.flush()
        os.fsync(self.raw.fileno())
        os.fsync(self.events.fileno())
        if self.source_times is not None:
            self.source_times.flush()
            os.fsync(self.source_times.fileno())
        self.metadata.update(sample_count=self.count, last_timestamp=self.last_timestamp)
        atomic_json(self.folder / "metadata.json", self.metadata)
        self.last_flush = time.monotonic()

    def close(self, status="complete", error=None):
        if self.closed:
            return
        try:
            self.event("session_end", self.last_timestamp, status=status, error=error)
            self.metadata.update(status=status, error=error, ended_utc=datetime.now(timezone.utc).isoformat())
            self.flush()
        finally:
            try:
                self.raw.close()
            finally:
                self.events.close()
                if self.source_times is not None:
                    self.source_times.close()
                self.closed = True


def inspect_session(folder):
    folder = Path(folder)
    metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    count, first, last, gaps, invalid = 0, None, None, 0, 0
    largest_gap = 0.0
    rate = float(metadata["sample_rate"])
    with (folder / "samples.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        expected = ["timestamp"] + [f"ch{i + 1}" for i in range(len(metadata["channels"]))]
        if header != expected:
            raise ValueError("Sample header does not match recorded channels.")
        for row in reader:
            try:
                x = np.asarray(row, dtype=float)
                if len(x) != len(header) or not np.isfinite(x).all():
                    raise ValueError()
                timestamp = float(x[0])
                if last is not None:
                    gap = timestamp - last
                    if gap <= 0:
                        raise ValueError()
                    largest_gap = max(largest_gap, gap)
                    gaps += gap > max(0.1, 5 / rate)
                first = timestamp if first is None else first
                last = timestamp
                count += 1
            except ValueError:
                invalid += 1
    report = dict(session_id=metadata["session_id"], status=metadata["status"],
                  simulated=metadata["simulated"], sample_count=count,
                  checkpoint_sample_count=metadata["sample_count"],
                  duration_seconds=last - first if first is not None else 0,
                  gaps_over_100ms=gaps, largest_gap_seconds=largest_gap, invalid_rows=invalid,
                  incomplete=metadata["status"] != "complete",
                  note="A recording left at 'recording' was interrupted. Complete CSV rows can still be inspected.")
    validation_path = folder / "validation.json"
    if validation_path.exists():
        report["validation"] = json.loads(validation_path.read_text(encoding="utf-8"))
    return report
