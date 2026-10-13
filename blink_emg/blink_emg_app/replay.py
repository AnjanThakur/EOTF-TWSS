"""Re-run a completed fresh-data check using its frozen profile and raw CSV."""
import csv
import json
from pathlib import Path

import numpy as np

from .calibration import Window, evaluate
from .config import Profile
from .detection import BlinkEngine


def replay_validation(folder):
    folder = Path(folder)
    metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    events = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    # Find the last *completed* test. A later aborted test is not a result.
    candidates, start_index = [], None
    for i, event in enumerate(events):
        if event["kind"] == "protocol_start" and event.get("protocol") in ("validation", "quick"):
            start_index = i
        elif start_index is not None and event["kind"] in ("protocol_cancelled", "protocol_failed"):
            start_index = None
        elif start_index is not None and event["kind"] == "protocol_complete" and event.get("protocol") == events[start_index]["protocol"]:
            candidates.append((start_index, i))
            start_index = None
    if not candidates:
        raise ValueError("No completed fresh-blink test in this recording. Inspection is still available.")
    begin, end = candidates[-1]
    kind = events[begin]["protocol"]
    profile = Profile(**events[begin]["profile"])
    invalidated = [e for e in events[begin:end] if e["kind"] == "cue_invalidated"]
    cues = []
    for event in events[begin:end]:
        if event["kind"] == "cue" and event.get("protocol") == kind:
            cues.append(event)
        elif event["kind"] == "cue_invalidated" and cues:
            # Earlier live versions logged the cue a few microseconds after
            # its actual window start. The active instruction index identifies
            # that attempt exactly, including repeated retries of one index.
            if cues[-1].get("index") == event.get("index"):
                cues.pop()
    windows = [Window(e["label"], e["timestamp"], e["timestamp"] + e["seconds"]) for e in cues]
    if not windows:
        raise ValueError("Missing test cue markers.")
    engine = BlinkEngine(metadata["sample_rate"], len(metadata["channels"]), profile)
    next_cue = 0
    gaps = 0
    buffer = []
    skipped = [(e["first_sample_timestamp"], e["last_sample_timestamp"])
               for e in events if e["kind"] == "delayed_chunk" and "first_sample_timestamp" in e]

    def consume(rows):
        if not rows:
            return
        matrix = np.asarray(rows, dtype=float)
        omit = np.zeros(len(matrix), dtype=bool)
        for first, last in skipped:
            omit |= (matrix[:, 0] >= first) & (matrix[:, 0] <= last)
        cuts = np.r_[0, np.flatnonzero(np.diff(omit)) + 1, len(matrix)]
        for begin, end in zip(cuts[:-1], cuts[1:]):
            if omit[begin]:
                engine.reset()
            else:
                consume_fresh(matrix[begin:end])

    def consume_fresh(matrix):
        nonlocal next_cue, gaps
        matrix = matrix[matrix[:, 0] < windows[-1].end]
        if not len(matrix):
            return
        stamps, values = matrix[:, 0], matrix[:, 1:]
        # Split at cue boundaries exactly as live detection resets grouping at
        # each instruction. Keep the causal filter continuous across cues.
        cursor = 0
        while cursor < len(stamps):
            if next_cue < len(windows) and stamps[cursor] >= windows[next_cue].start:
                engine.cancel()
                next_cue += 1
                continue
            boundary = (int(np.searchsorted(stamps, windows[next_cue].start, side="left"))
                        if next_cue < len(windows) else len(stamps))
            boundary = max(cursor + 1, min(boundary, len(stamps)))
            previous = engine.last_timestamp
            filtered, _, gestures, lost = engine.process(values[cursor:boundary], stamps[cursor:boundary])
            section_times = stamps[cursor:boundary]
            if lost:
                intervals = np.diff(np.r_[previous, section_times]) if previous is not None else np.diff(section_times)
                positions = np.flatnonzero(intervals > max(.1, 5 / metadata["sample_rate"]))
                if previous is None:
                    positions += 1
                gaps += sum(any(w.start <= section_times[i] < w.end for w in windows) for i in positions)
            for w in windows:
                mask = (section_times >= w.start) & (section_times < w.end)
                if mask.any():
                    w.timestamps.extend(section_times[mask].tolist())
                    w.filtered.extend(filtered[mask].tolist())
                w.gestures.extend(g for g in gestures if w.start <= g.start and g.timestamp <= w.end)
            cursor = boundary

    with (folder / "samples.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        expected = ["timestamp"] + [f"ch{i + 1}" for i in range(len(metadata["channels"]))]
        if header != expected:
            raise ValueError("Raw sample header does not match the session.")
        for row in reader:
            if len(row) != len(expected):
                raise ValueError("Incomplete sample row. Preserve the original before attempting repair.")
            buffer.append([float(v) for v in row])
            if len(buffer) == 512:
                consume(buffer)
                buffer = []
        consume(buffer)
    if gaps:
        raise ValueError("A signal gap interrupted the fresh-data test; no replay accuracy produced.")
    report = evaluate(windows, profile, metadata["session_id"], quick=kind == "quick")
    report.update(simulated=metadata["simulated"], replay=True,
                  repeated_steps=len(invalidated),
                  recorded_detector_version=events[begin].get("detector_version", "release_refractory_v1"),
                  replay_note="Raw CSV replay using the frozen profile and current detector version; an older recording is development evidence, not a new independent test. Software cue times; physical screen latency is not measured.")
    return report
