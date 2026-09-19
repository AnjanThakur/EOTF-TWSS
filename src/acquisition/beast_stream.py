"""Real-time LSL acquisition for NPG Lite Beast-compatible streams."""
from collections import deque
import threading
import time
import numpy as np
from src.acquisition.base_stream import BaseEEGStream


def _pylsl():
    try:
        import pylsl
        return pylsl
    except ImportError as exc:
        raise RuntimeError("pylsl is required for LSL acquisition; install it with pip install pylsl") from exc


def discover_streams(name=None, stream_type=None, timeout=1.0):
    if timeout <= 0: raise ValueError("Discovery timeout must be positive.")
    pylsl = _pylsl()
    return [s for s in pylsl.resolve_streams(wait_time=timeout)
            if (name is None or s.name() == name) and (stream_type is None or s.type() == stream_type)]


class BeastStreamer(BaseEEGStream):
    """Buffered LSL source. Stream selection is configured, never hardcoded."""
    def __init__(self, stream_name=None, stream_type=None, expected_channels=6,
                 resolve_timeout=2.0, pull_timeout=0.25, max_buffer_seconds=30):
        if expected_channels is not None and expected_channels < 1: raise ValueError("expected_channels must be positive or None.")
        self.stream_name, self.stream_type, self.expected_channels = stream_name, stream_type, expected_channels
        self.resolve_timeout, self.pull_timeout, self.max_buffer_seconds = float(resolve_timeout), float(pull_timeout), float(max_buffer_seconds)
        self.sampling_rate = 0.0; self.channel_names = (); self._inlet = None; self._thread = None
        self._stop = threading.Event(); self._lock = threading.Lock(); self._buffer = deque(); self._error = None

    def start(self):
        if self._thread and self._thread.is_alive(): return
        streams = discover_streams(self.stream_name, self.stream_type, self.resolve_timeout)
        if not streams: raise RuntimeError("No matching LSL stream found (hardware not connected or stream unavailable).")
        if len(streams) > 1 and self.stream_name is None and self.stream_type is None: raise RuntimeError("Multiple LSL streams found; configure stream_name or stream_type.")
        pylsl = _pylsl(); self._inlet = pylsl.StreamInlet(streams[0], max_buflen=int(self.max_buffer_seconds))
        self._inlet.open_stream(timeout=self.resolve_timeout)
        info = self._inlet.info(); self.sampling_rate = float(info.nominal_srate()); count = int(info.channel_count())
        if self.sampling_rate <= 0 or not np.isfinite(self.sampling_rate): raise ValueError("LSL stream sampling rate must be finite and positive.")
        if self.expected_channels is not None and count != self.expected_channels:
            self.stop(); raise ValueError(f"Wrong channel count: expected {self.expected_channels}, got {count}.")
        self.channel_names = tuple(self._labels(info, count)); self._stop.clear(); self._error = None
        self._thread = threading.Thread(target=self._pull_loop, name="beast-lsl", daemon=True); self._thread.start()

    @staticmethod
    def _labels(info, count):
        node = info.desc().child("channels").child("channel"); labels = []
        for i in range(count):
            if i: node = node.next_sibling()
            labels.append(node.child_value("label") or node.child_value("name") or f"CH{i + 1}")
        return labels

    def _pull_loop(self):
        while not self._stop.is_set():
            try:
                chunk, _ = self._inlet.pull_chunk(timeout=self.pull_timeout, max_samples=256)
                if chunk:
                    array = np.asarray(chunk, dtype=float)
                    if array.ndim != 2 or array.shape[1] != len(self.channel_names) or not np.isfinite(array).all():
                        self._error = ValueError("LSL samples are non-finite or have wrong channel count."); self._stop.set(); break
                    with self._lock:
                        self._buffer.extend(array.tolist())
                        while len(self._buffer) > int(self.sampling_rate * self.max_buffer_seconds): self._buffer.popleft()
            except Exception as exc:
                self._error = RuntimeError(f"LSL stream disconnected: {exc}"); self._stop.set(); break

    def stop(self):
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread(): self._thread.join(timeout=2)
        self._thread = None; self._inlet = None

    def get_samples(self):
        if self._error: raise self._error
        if not self._thread or not self._thread.is_alive(): raise RuntimeError("LSL stream is stopped or disconnected.")
        with self._lock:
            if not self._buffer: raise TimeoutError("LSL stream timeout: no samples received.")
            data = np.asarray(self._buffer, dtype=float).T; self._buffer.clear()
        return data

    def get_window(self, seconds):
        if seconds <= 0 or not np.isfinite(seconds): raise ValueError("Window duration must be finite and positive.")
        required = int(round(seconds * self.sampling_rate)); deadline = time.monotonic() + max(10.0, self.pull_timeout * 4)
        while time.monotonic() < deadline:
            if self._error: raise self._error
            with self._lock:
                if len(self._buffer) >= required:
                    return np.asarray([self._buffer.popleft() for _ in range(required)], dtype=float).T
            time.sleep(0.01)
        raise TimeoutError(f"Incomplete window: need {required} samples before timeout.")
