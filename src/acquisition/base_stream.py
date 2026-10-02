"""Common interface for offline and future live EEG sources."""

from abc import ABC, abstractmethod
import numpy as np


class EEGSource(ABC):
    """Channel-first EEG samples; each source must document its native units.

    MNE preprocessing expects volts. LSL publisher values need confirmed scaling
    before they can be passed to that preprocessing layer.
    """

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def get_samples(self) -> np.ndarray: ...

    def get_window(self, seconds: float) -> np.ndarray:
        samples = self.get_samples()
        if seconds <= 0 or not np.isfinite(seconds):
            raise ValueError("Window duration must be finite and positive.")
        required = int(round(seconds * self.sampling_rate))
        if samples.ndim != 2 or samples.shape[1] < required:
            raise ValueError(f"Incomplete trial: need {required} samples, got {samples.shape[-1]}.")
        return samples[:, :required]


BaseEEGStream = EEGSource
