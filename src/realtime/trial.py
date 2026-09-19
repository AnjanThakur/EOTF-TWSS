"""Acquisition boundary shared by dataset and future hardware sources."""

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class Trial:
    """One preprocessed epoch in volts, ordered FC3/FC4/C3/C4/CP3/CP4.

    Data shape is (6, 481): 0.5-3.5 s inclusive at 160 Hz, filtered 8-30 Hz,
    baseline=None. Future sources must use the shared preprocessing upstream.
    Actual label is optional for sources without ground truth.
    """

    data: np.ndarray
    actual_label: int | None = None
    source: str = ""


@dataclass(frozen=True)
class Prediction:
    predicted_class: int
    predicted_label: str
    confidence: float | None
    actual_label: int | None
    decision: str  # LEFT/RIGHT when accepted; UNKNOWN otherwise.
