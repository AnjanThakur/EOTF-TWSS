"""Fit on calibration only. Evaluate later gestures without refitting."""
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

from .config import Profile
from .detection import replay_filtered, DETECTOR_VERSION


@dataclass
class Window:
    label: str
    start: float
    end: float
    timestamps: list = field(default_factory=list)
    filtered: list = field(default_factory=list)
    gestures: list = field(default_factory=list)

    def arrays(self):
        return np.asarray(self.timestamps), np.asarray(self.filtered)


def calibrate(windows, rate, channels, source_key, session_id):
    rest = [w for w in windows if w.label == "NORMAL"]
    singles = [w for w in windows if w.label == "SINGLE"]
    if len(rest) != 1 or len(singles) < 6:
        raise ValueError("Finish the normal-blinking step and all eight single-blink steps.")
    rest_t, rest_x = rest[0].arrays()
    if len(rest_t) < rate * 15 or np.max(np.diff(rest_t)) > 0.1:
        raise ValueError("Not enough continuous normal-blinking data. Repeat calibration.")
    for w in singles:
        t, x = w.arrays()
        if len(t) < rate * 2.5 or np.max(np.diff(t)) > 0.1 or x.ndim != 2:
            raise ValueError("A blink step has missing data. Repeat calibration.")
    candidates = []
    for channel in channels:
        absolute = np.abs(rest_x[:, channel])
        noise = max(float(np.percentile(absolute, 85)), np.finfo(float).eps)
        for polarity in (1, -1):
            peaks = np.asarray([np.max(w.arrays()[1][:, channel] * polarity) for w in singles])
            blink_level = float(np.percentile(peaks, 25))
            if blink_level < noise * 3:
                continue
            for fraction in (0.32, 0.42, 0.52, 0.62):
                threshold = max(noise * 2.8, blink_level * fraction)
                profile = Profile(channel, threshold, rate, source_key, noise, blink_level, polarity=polarity)
                counts = [len(replay_filtered(*_channel_window(w, channel), profile)[0]) for w in singles]
                normal_blinks, normal_groups = replay_filtered(rest_t, rest_x[:, channel], profile)
                correct = counts.count(1)
                unwanted_groups = sum(g.command in ("NEXT", "SELECT") for g in normal_groups)
                # Natural isolated blinks are allowed; baseline rapid noise is not.
                cost = sum(abs(c - 1) for c in counts) + unwanted_groups * 3
                candidates.append((correct, -cost, blink_level / noise, profile, counts, len(normal_blinks)))
    if not candidates:
        raise ValueError("Blinks are too close to background noise. Check forehead pad contact, keep your jaw still, then repeat.")
    best = max(candidates, key=lambda item: item[:3])
    correct, _, _, profile, counts, normal_count = best
    if correct < 6:
        raise ValueError(f"Only {correct}/{len(singles)} single blinks were clear. Recheck the pads and repeat with comfortable, distinct blinks.")
    profile.calibration = dict(session_id=session_id, single_trials=len(singles),
                               correctly_counted=correct, blink_counts=counts,
                               normal_blinks=normal_count,
                               created_at_utc=datetime.now(timezone.utc).isoformat(),
                               method="causal 0.5-12 Hz; personal amplitude + duration; calibration data only")
    return profile


def _channel_window(window, channel):
    t, x = window.arrays()
    return t, x[:, channel]


def evaluate(windows, profile, session_id, *, quick=False):
    trials = [w for w in windows if w.label in ("NEXT", "SELECT")]
    normals = [w for w in windows if w.label == "NORMAL"]
    if not trials or not normals:
        raise ValueError("The fresh-data check is incomplete.")
    for w in trials + normals:
        t, x = w.arrays()
        if (len(t) < profile.sample_rate * (w.end - w.start) * 0.90 or len(t) < 2
                or np.max(np.diff(t)) > 0.1 or np.any(np.diff(t) <= 0)
                or x.ndim != 2 or not np.isfinite(x).all()):
            raise ValueError("The fresh check has missing or invalid signal data. Repeat it after reconnecting.")
    rows, confusion = [], {label: {v: 0 for v in ("NEXT", "SELECT", "MISS", "EXTRA")} for label in ("NEXT", "SELECT")}
    correct = extras = 0
    for i, w in enumerate(trials, 1):
        commands = [g.command for g in w.gestures if g.command in ("NEXT", "SELECT")]
        prediction = commands[0] if len(commands) == 1 else ("MISS" if not commands else "EXTRA")
        is_correct = prediction == w.label
        correct += is_correct
        extras += max(0, len(commands) - 1)
        confusion[w.label][prediction] += 1
        rows.append(dict(trial=i, expected=w.label, observed=commands, correct=is_correct,
                         start=w.start, end=w.end))
    normal_seconds = sum(w.end - w.start for w in normals)
    accidental = sum(g.command in ("NEXT", "SELECT") for w in normals for g in w.gestures)
    outside = sum(g.command in ("NEXT", "SELECT") for w in windows
                  if w.label not in ("NEXT", "SELECT", "NORMAL") for g in w.gestures)
    counts = {label: sum(w.label == label for w in trials) for label in ("NEXT", "SELECT")}
    # A short personal readiness check, not a clinical/product accuracy claim.
    passed = (not quick and len(trials) >= 8 and normal_seconds >= 15 and correct / len(trials) >= 0.8
              and all(counts[k] >= 4 and confusion[k][k] / counts[k] >= 2 / 3 for k in counts)
              and accidental == 0 and extras == 0 and outside == 0)
    return dict(session_id=session_id, profile_id=profile.profile_id, passed=passed,
                detector_version=DETECTOR_VERSION,
                readiness_criteria=dict(minimum_trials=8, minimum_trials_per_gesture=4,
                                        minimum_normal_seconds=15, minimum_accuracy=0.8,
                                        minimum_accuracy_per_gesture=2 / 3,
                                        maximum_accidental_extra_or_waiting_commands=0),
                check_type="quick" if quick else "validation",
                source="fresh guided recording; profile frozen before this check",
                total_trials=len(trials), correct_trials=correct,
                trial_accuracy=correct / len(trials), extra_commands=extras,
                normal_seconds=normal_seconds, accidental_commands=accidental,
                commands_during_waiting=outside,
                accidental_commands_per_minute=60 * accidental / normal_seconds if normal_seconds else None,
                confusion=confusion, trials=rows,
                limitation=("Quick practice feedback only; too few trials and too little ordinary activity to enable blink control."
                            if quick else "Small personal readiness check. Repeat on a different session and longer ordinary activity before judging reliability."))
