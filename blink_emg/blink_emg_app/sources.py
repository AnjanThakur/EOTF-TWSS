"""Bounded asynchronous LSL capture and a clearly marked synthetic practice source."""
from dataclasses import dataclass
import queue
import threading
import time

import numpy as np


@dataclass
class Chunk:
    values: np.ndarray
    timestamps: np.ndarray
    source_timestamps: np.ndarray | None = None


class TimestampGuard:
    """Repair at most 1 ms of timestamp overlap without reordering samples.

    Chords stamps a Bluetooth batch in a tight loop. An LSL clock correction
    can therefore make adjacent times go backwards by a few microseconds.
    Keep the original clock-corrected times for recording; this is deliberately
    not full dejittering or reconstruction at the nominal sample rate.
    """
    max_adjustment = 0.001

    def __init__(self, rate):
        self.gap_threshold = max(0.1, 5 / rate)
        self.last = self.last_source = None

    def process(self, timestamps):
        source = np.asarray(timestamps, dtype=float)
        if source.ndim != 1 or not len(source) or not np.isfinite(source).all():
            raise ValueError("Invalid LSL sample timestamps.")
        result = source.copy()
        previous, previous_source = self.last, self.last_source
        for i, original in enumerate(source):
            corrected = float(original)
            if previous is not None:
                # Preserve a real gap even if its preceding time was adjusted.
                gap = original - previous_source
                if gap > self.gap_threshold:
                    corrected = max(corrected, previous + gap)
                if corrected <= previous:
                    corrected = float(np.nextafter(previous, np.inf))
                if corrected - original > self.max_adjustment:
                    raise ValueError("LSL clock moved backwards by more than 1 ms. Reconnect to start fresh.")
            result[i] = corrected
            previous, previous_source = corrected, float(original)
        self.last, self.last_source = previous, previous_source
        return result


def describe_stream(info):
    return dict(name=info.name(), source_id=info.source_id(), uid=info.uid(),
                channels=info.channel_count(), sample_rate=float(info.nominal_srate()),
                type=info.type(), simulated=False,
                source_key=f"LSL:{info.name()}:{info.source_id()}:{info.channel_count()}:{float(info.nominal_srate()):g}")


def discover():
    import pylsl
    infos = pylsl.resolve_streams(wait_time=1.5)
    return [i for i in infos if 1 <= i.channel_count() <= 6
            and 80 <= i.nominal_srate() <= 2000 and i.channel_format() in (1, 2, 4, 5, 6, 7)]


class Source:
    def __init__(self):
        self.messages = queue.Queue(maxsize=40)
        self.stop_event = threading.Event()
        self.thread = None
        self.error = None

    def send(self, kind, value):
        try:
            self.messages.put_nowait((kind, value))
        except queue.Full:
            self.error = "Processing fell behind. Reconnect to start with fresh signals."
            self.stop_event.set()

    def start(self):
        self.thread = threading.Thread(target=self.run, daemon=True, name="blink-signal-source")
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=0.4)


class LSLSource(Source):
    def __init__(self, info):
        super().__init__()
        self.info = info

    @staticmethod
    def clock():
        import pylsl
        return pylsl.local_clock()

    def run(self):
        import pylsl
        inlet = None
        try:
            inlet = pylsl.StreamInlet(self.info, max_buflen=2, recover=False,
                                     processing_flags=pylsl.proc_clocksync)
            inlet.open_stream(timeout=3)
            full_info = inlet.info(timeout=2)
            metadata = describe_stream(full_info)
            metadata["stream_xml"] = full_info.as_xml()
            metadata["timestamp_policy"] = dict(
                name="bounded_monotonic_v1", max_adjustment_seconds=TimestampGuard.max_adjustment,
                source="LSL proc_clocksync timestamps before the app's monotonic repair",
                note="Sample values and order are unchanged; real gaps are retained. Not full dejittering.")
            timing = TimestampGuard(metadata["sample_rate"])
            self.send("ready", metadata)
            last = time.monotonic()
            while not self.stop_event.is_set():
                values, timestamps = inlet.pull_chunk(timeout=0.05, max_samples=256)
                if values:
                    last = time.monotonic()
                    original_times = np.asarray(timestamps, dtype=float)
                    self.send("chunk", Chunk(np.asarray(values, dtype=float),
                                             timing.process(original_times), original_times))
                elif time.monotonic() - last > 2:
                    raise RuntimeError("No signals for two seconds. Check Bluetooth and the board battery, then reconnect.")
        except Exception as exc:
            self.error = f"NPG connection failed: {exc}"
        finally:
            if inlet:
                inlet.close_stream()


def simulated_values(times, blink_times=(), *, seed=4, channels=6):
    """Deterministic native ADC-like pulses; never counted as hardware evidence."""
    times = np.asarray(times)
    # Continuous deterministic noise makes results independent of chunk sizes.
    signal = 1.4 * np.sin(times * 19.1 + seed) + np.sin(times * 43.3 + seed * 0.7)
    for onset in blink_times:
        signal += 160 * np.exp(-0.5 * ((times - onset) / 0.060) ** 2)
    result = np.empty((len(times), channels))
    for ch in range(channels):
        result[:, ch] = 2000 + signal * (1 if ch == 0 else 0.8 if ch == 1 else 0.01) + 0.3 * np.sin(times * (31 + ch))
    return result


class DemoSource(Source):
    rate = 500.0
    clock = staticmethod(time.monotonic)

    def __init__(self):
        super().__init__()
        self.origin = self.clock()
        self.blinks = []
        self.lock = threading.Lock()

    def inject(self, count, delay=0.25):
        with self.lock:
            start = self.clock() - self.origin + delay
            self.blinks.extend(start + n * 0.48 for n in range(count))

    def run(self):
        self.send("ready", dict(name="Practice signals", channels=6, sample_rate=self.rate,
                                 source_id="simulated-v1", simulated=True, source_key="DEMO:v1:6:500"))
        index = 0
        while not self.stop_event.is_set():
            due = int((self.clock() - self.origin) * self.rate)
            if due > index:
                end = min(due, index + 100)
                times = np.arange(index, end) / self.rate
                with self.lock:
                    self.blinks = [t for t in self.blinks if t > times[0] - 1]
                    values = simulated_values(times, tuple(self.blinks))
                self.send("chunk", Chunk(values, times + self.origin))
                index = end
            self.stop_event.wait(0.02)
