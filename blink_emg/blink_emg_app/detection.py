"""Causal streaming filtering, blink pulses and delayed gesture grouping.

Thresholds are in filtered native stream units, not microvolts. There is no
conversion to a brain signal or a pre-trained EEG classifier.
"""
from dataclasses import dataclass
import math

import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi

from .config import Profile

DETECTOR_VERSION = "sample_duration_v3"


@dataclass(frozen=True)
class Blink:
    timestamp: float
    amplitude: float
    width: float


@dataclass(frozen=True)
class Gesture:
    start: float
    timestamp: float
    count: int
    command: str  # SINGLE, NEXT, SELECT or REJECT


class SignalFilter:
    def __init__(self, rate, channels):
        if not math.isfinite(rate) or not 80 <= rate <= 2000:
            raise ValueError("Use a regular stream between 80 and 2000 Hz.")
        self.rate, self.channels = rate, channels
        self.sos = butter(2, [0.5, 12], fs=rate, btype="bandpass", output="sos")
        self.zi = None

    def reset(self):
        self.zi = None

    def process(self, values):
        values = np.asarray(values, dtype=float)
        if values.ndim != 2 or values.shape[1] != self.channels or not np.isfinite(values).all():
            raise ValueError("Non-finite samples or unexpected channel count.")
        if not len(values):
            return values.copy()
        if self.zi is None:
            self.zi = sosfilt_zi(self.sos)[:, :, None] * values[0][None, None, :]
        filtered, self.zi = sosfilt(self.sos, values, axis=0, zi=self.zi)
        return filtered


class PulseDetector:
    """Measure pulse timing in samples on the regular stream, not burst labels.

    The engine resets this detector across gaps. Original peak timestamps stay
    attached to events for cue attribution and grouping; raw data is unchanged.
    """
    def __init__(self, profile):
        self.p = profile
        self.reset()

    def reset(self):
        self.start = None
        self.peak_time = 0.0
        self.peak = 0.0
        self.sample_index = -1
        self.start_sample = self.peak_sample = self.last_above_sample = 0
        self.quiet_since_sample = None
        self.blocked_until_sample = -math.inf
        self.rejected = 0

    @property
    def active_seconds(self):
        return 0.0 if self.start is None else (self.sample_index - self.start_sample) / self.p.sample_rate

    def push(self, timestamp, value):
        self.sample_index += 1
        # A blink's high-pass filtered return swing has the opposite polarity.
        # Counting absolute amplitude can merge or double-count biphasic blinks.
        amplitude = max(0.0, self.p.polarity * float(value))
        if self.start is None:
            if self.sample_index >= self.blocked_until_sample and amplitude >= self.p.threshold:
                self.start = self.peak_time = timestamp
                self.start_sample = self.peak_sample = self.last_above_sample = self.sample_index
                self.peak = amplitude
                self.quiet_since_sample = None
            return None
        if amplitude > self.peak:
            self.peak, self.peak_time = amplitude, timestamp
            self.peak_sample = self.sample_index
        if amplitude >= self.p.threshold * self.p.release_ratio:
            self.last_above_sample = self.sample_index
            self.quiet_since_sample = None
            return None
        if self.quiet_since_sample is None:
            self.quiet_since_sample = self.sample_index
        if (self.sample_index - self.quiet_since_sample) / self.p.sample_rate < self.p.settle_seconds:
            return None
        width = (self.last_above_sample - self.start_sample) / self.p.sample_rate
        blink = Blink(self.peak_time, self.peak, width)
        self.start = None
        self.quiet_since_sample = None
        # Settling already waits for a quiet return below the release level.
        # Adding another full refractory interval *after* that wait discards
        # distinct rapid blinks (and can start counting only their short tails).
        # Anchor minimum spacing to the previous peak; keep settling, polarity
        # and duration checks intact to reject ringing and long excursions.
        self.blocked_until_sample = self.peak_sample + math.ceil(self.p.refractory * self.p.sample_rate)
        if self.p.min_width <= width <= self.p.max_width:
            return blink
        self.rejected += 1
        return None


class GestureGrouper:
    """Wait after the last blink so a triple never first emits a double."""
    def __init__(self, gap=0.8):
        self.gap = gap
        self.pending = []

    def reset(self):
        self.pending.clear()

    def add(self, blink):
        events = []
        if self.pending and blink.timestamp - self.pending[-1].timestamp > self.gap:
            events.extend(self.flush(blink.timestamp, force=True))
        self.pending.append(blink)
        return events

    def flush(self, now, *, force=False):
        if not self.pending or (not force and now - self.pending[-1].timestamp <= self.gap):
            return []
        count = len(self.pending)
        command = {1: "SINGLE", 2: "NEXT", 3: "SELECT"}.get(count, "REJECT")
        result = Gesture(self.pending[0].timestamp, now, count, command)
        self.pending.clear()
        return [result]


class BlinkEngine:
    """Accept strictly ordered sample times; do not flush against wall time."""
    def __init__(self, rate, channels, profile=None):
        self.rate = rate
        self.filter = SignalFilter(rate, channels)
        self.profile = None
        self.pulse = self.grouper = None
        self.last_timestamp = None
        self.warm_until = math.inf
        if profile:
            self.set_profile(profile)

    def set_profile(self, profile):
        if profile.channel >= self.filter.channels or abs(profile.sample_rate - self.rate) > 0.01:
            raise ValueError("Calibration does not match the stream channels or rate.")
        self.profile = profile
        self.pulse = PulseDetector(profile)
        self.grouper = GestureGrouper(profile.group_gap)

    def cancel(self):
        if self.pulse:
            self.pulse.reset()
            self.grouper.reset()

    def reset(self):
        self.filter.reset()
        self.cancel()
        self.last_timestamp = None
        self.warm_until = math.inf

    def process(self, values, timestamps):
        timestamps = np.asarray(timestamps, dtype=float)
        values = np.asarray(values, dtype=float)
        if (values.ndim != 2 or timestamps.shape != (len(values),) or not len(values)
                or not np.isfinite(timestamps).all() or np.any(np.diff(timestamps) <= 0)):
            raise ValueError("Invalid or non-increasing sample timestamps.")
        if self.last_timestamp is not None and timestamps[0] <= self.last_timestamp:
            raise ValueError("Stream timestamps moved backwards. Reconnect the device.")
        intervals = np.diff(np.r_[self.last_timestamp, timestamps]) if self.last_timestamp is not None else np.diff(timestamps)
        # Reset rather than join signals across missing samples. Caller pauses any
        # protocol and communication on gaps > 100 ms (returned explicitly).
        gap_indices = np.flatnonzero(intervals > max(0.1, 5 / self.rate))
        if self.last_timestamp is None:
            gap_indices = gap_indices + 1
        boundaries = [0] + [int(i) for i in gap_indices if i > 0] + [len(values)]
        filtered_parts, blinks, gestures = [], [], []
        gaps = len(gap_indices)
        for begin, end in zip(boundaries, boundaries[1:]):
            if begin > 0 or (begin == 0 and len(gap_indices) and gap_indices[0] == 0):
                self.filter.reset()
                self.cancel()
                self.warm_until = timestamps[begin] + 2.0
            if math.isinf(self.warm_until):
                self.warm_until = timestamps[begin] + 2.0
            block = self.filter.process(values[begin:end])
            filtered_parts.append(block)
            if self.profile:
                for t, row in zip(timestamps[begin:end], block):
                    if t < self.warm_until:
                        continue
                    blink = self.pulse.push(float(t), row[self.profile.channel])
                    if blink:
                        blinks.append(blink)
                        gestures.extend(self.grouper.add(blink))
                    # While a pulse is active it might be the third blink. Do not
                    # commit the previous double until this pulse is resolved.
                    if self.pulse.start is None:
                        gestures.extend(self.grouper.flush(float(t)))
        self.last_timestamp = float(timestamps[-1])
        return np.concatenate(filtered_parts), blinks, gestures, gaps


def replay_filtered(timestamps, filtered, profile):
    """Replay calibration windows through the very same pulse/group logic."""
    pulse, grouper = PulseDetector(profile), GestureGrouper(profile.group_gap)
    blinks, gestures = [], []
    for t, x in zip(timestamps, filtered):
        b = pulse.push(float(t), x)
        if b:
            blinks.append(b)
            gestures.extend(grouper.add(b))
        if pulse.start is None:
            gestures.extend(grouper.flush(float(t)))
    return blinks, gestures
