"""Bounded, timestamped LSL acquisition; values retain the publisher's units."""
from collections import deque
import threading
import time
import numpy as np
from src.acquisition.base_stream import BaseEEGStream


def _pylsl():
    try:
        import pylsl
        return pylsl
    except (ImportError, RuntimeError) as exc:
        raise RuntimeError("pylsl/liblsl is required for LSL acquisition.") from exc


def discover_streams(name=None, stream_type=None, timeout=1.0, source_id=None):
    if not np.isfinite(timeout) or timeout <= 0:
        raise ValueError("Discovery timeout must be finite and positive.")
    return [s for s in _pylsl().resolve_streams(wait_time=timeout)
            if (name is None or s.name() == name)
            and (stream_type is None or s.type() == stream_type)
            and (source_id is None or s.source_id() == source_id)]


class BeastStreamer(BaseEEGStream):
    """FIFO raw samples, shape (channels, samples), in native LSL units.

    Consumers must verify units/scaling before preprocessing or inference. No
    ADC-to-volts conversion, channel relabeling, or resampling happens here.
    get_samples consumes pending data; get_window waits for a contiguous window.
    """
    def __init__(self, stream_name=None, stream_type=None, expected_channels=6,
                 resolve_timeout=2.0, pull_timeout=0.25, max_buffer_seconds=30,
                 sample_timeout=2.0, source_id=None):
        if expected_channels is not None and (expected_channels < 1 or int(expected_channels) != expected_channels):
            raise ValueError("expected_channels must be a positive integer or None.")
        for value in (resolve_timeout, pull_timeout, max_buffer_seconds, sample_timeout):
            if not np.isfinite(value) or value <= 0:
                raise ValueError("Timeouts and buffer duration must be finite and positive.")
        self.stream_name, self.stream_type, self.source_id = stream_name, stream_type, source_id
        self.expected_channels = expected_channels
        self.resolve_timeout, self.pull_timeout = float(resolve_timeout), float(pull_timeout)
        self.max_buffer_seconds, self.sample_timeout = float(max_buffer_seconds), float(sample_timeout)
        self.sampling_rate = 0.0
        self.channel_names, self.channel_units = (), ()
        self._inlet = self._thread = None
        self._stop = threading.Event()
        self._condition = threading.Condition()
        self._buffer = deque()
        self._error = None
        self.last_timestamps = np.array([])
        self._accept_after = float("-inf")

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self.stop()
        streams = discover_streams(self.stream_name, self.stream_type, self.resolve_timeout, self.source_id)
        if not streams:
            raise RuntimeError("No matching LSL stream found (hardware not connected or stream unavailable).")
        if len(streams) != 1:
            raise RuntimeError("Multiple matching LSL streams; select a unique name/type/source ID.")
        pylsl = _pylsl()
        inlet = pylsl.StreamInlet(streams[0], max_buflen=int(np.ceil(self.max_buffer_seconds)),
                                 recover=False, processing_flags=pylsl.proc_clocksync)
        try:
            inlet.open_stream(timeout=self.resolve_timeout)
            info = inlet.info(timeout=self.resolve_timeout)
            rate, count = float(info.nominal_srate()), int(info.channel_count())
            if not np.isfinite(rate) or rate <= 0:
                raise ValueError("LSL stream sampling rate must be finite and positive.")
            if count < 1 or (self.expected_channels is not None and count != self.expected_channels):
                raise ValueError(f"Wrong channel count: expected {self.expected_channels}, got {count}.")
            self.sampling_rate = rate
            self.channel_names, self.channel_units = self._metadata(info, count)
        except Exception:
            inlet.close_stream()
            raise
        self._inlet = inlet
        self._stop.clear()
        self._error = None
        self._accept_after = float("-inf")
        self._last_received = time.monotonic()
        self._thread = threading.Thread(target=self._pull_loop, args=(inlet,), name="beast-lsl", daemon=True)
        self._thread.start()

    @staticmethod
    def _metadata(info, count):
        node = info.desc().child("channels").child("channel")
        names, units = [], []
        for i in range(count):
            names.append(node.child_value("label") or node.child_value("name") or f"CH{i + 1}")
            units.append(node.child_value("unit") or "unknown")
            node = node.next_sibling()
        return tuple(names), tuple(units)

    def _pull_loop(self, inlet):
        try:
            while not self._stop.is_set():
                chunk, timestamps = inlet.pull_chunk(timeout=self.pull_timeout, max_samples=256)
                if not len(chunk):
                    if time.monotonic() - self._last_received > self.sample_timeout:
                        raise TimeoutError("LSL stream timeout/disconnection: samples stopped arriving.")
                    continue
                array, stamps = np.asarray(chunk, dtype=float), np.asarray(timestamps, dtype=float)
                if (array.ndim != 2 or array.shape[1] != len(self.channel_names)
                        or len(stamps) != len(array) or not np.isfinite(array).all()
                        or not np.isfinite(stamps).all()):
                    raise ValueError("LSL samples/timestamps are non-finite or have wrong channel count.")
                self._last_received = time.monotonic()
                with self._condition:
                    self._buffer.extend((stamp, row) for stamp, row in zip(stamps, array)
                                        if stamp >= self._accept_after)
                    capacity = max(1, int(self.sampling_rate * self.max_buffer_seconds))
                    while len(self._buffer) > capacity:
                        self._buffer.popleft()
                    self._condition.notify_all()
        except Exception as exc:
            with self._condition:
                self._error = exc
                self._condition.notify_all()

    def stop(self):
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=self.pull_timeout + 1)
            if self._thread.is_alive():
                raise RuntimeError("LSL reader did not stop; do not reconnect until it finishes.")
        if self._inlet is not None:
            self._inlet.close_stream()
        self._thread = self._inlet = None
        with self._condition:
            self._buffer.clear()
            self.last_timestamps = np.array([])
            self._condition.notify_all()

    def _check_running(self):
        if self._error is not None:
            raise self._error
        if not self._thread or not self._thread.is_alive() or self._stop.is_set():
            raise RuntimeError("LSL stream is stopped or disconnected.")
        if time.monotonic() - self._last_received > self.sample_timeout:
            raise TimeoutError("LSL stream timeout/disconnection: samples stopped arriving.")

    def discard_pending(self):
        """Start a new cue window; reject older timestamps still in the inlet."""
        with self._condition:
            self._check_running()
            self._accept_after = _pylsl().local_clock()
            self._buffer.clear()
            self.last_timestamps = np.array([])

    def _consume(self, count):
        entries = [self._buffer.popleft() for _ in range(count)]
        stamps = np.array([entry[0] for entry in entries])
        if len(stamps) > 1 and (np.any(np.diff(stamps) <= 0)
                               or np.any(np.diff(stamps) > 2.5 / self.sampling_rate)):
            raise ValueError("Missing samples: timestamp gap or out-of-order LSL window.")
        self.last_timestamps = stamps
        return np.asarray([entry[1] for entry in entries]).T

    def get_samples(self):
        with self._condition:
            self._check_running()
            if not self._buffer:
                raise TimeoutError("LSL stream timeout: no samples received.")
            return self._consume(len(self._buffer))

    def get_window(self, seconds):
        if not np.isfinite(seconds) or seconds <= 0:
            raise ValueError("Window duration must be finite and positive.")
        if seconds > self.max_buffer_seconds:
            raise ValueError("Requested window exceeds buffer capacity.")
        with self._condition:
            self._check_running()
            required = int(round(seconds * self.sampling_rate))
            if required < 1:
                raise ValueError("Window duration is shorter than one sample.")
            deadline = time.monotonic() + seconds + self.sample_timeout
            while len(self._buffer) < required:
                self._check_running()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"Incomplete window: need {required}, got {len(self._buffer)} samples.")
                self._condition.wait(timeout=min(self.pull_timeout, remaining))
            return self._consume(required)


BeastStream = BeastStreamer
