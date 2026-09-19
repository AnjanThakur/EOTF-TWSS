"""Synthetic LSL publisher for tests only; never used by production acquisition."""
import time
import numpy as np
import pylsl


class MockLSLPublisher:
    def __init__(self, name="TWSS Mock EEG", stream_type="EEG", channels=6, rate=100):
        self.channels, self.rate = channels, rate
        info = pylsl.StreamInfo(name, stream_type, channels, rate, pylsl.cf_float32, "twss-mock-source")
        desc = info.desc().append_child("channels")
        for i in range(channels): desc.append_child("channel").append_child_value("label", f"CH{i+1}")
        self.outlet = pylsl.StreamOutlet(info)

    def publish(self, seconds=3):
        count = int(seconds * self.rate)
        for i in range(count):
            t = i / self.rate
            self.outlet.push_sample([float(np.sin(2 * np.pi * (8 + c) * t)) for c in range(self.channels)])
            time.sleep(1 / self.rate)
