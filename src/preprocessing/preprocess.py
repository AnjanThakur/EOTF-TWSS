"""First-stage preprocessing for PhysioNet left/right motor imagery."""

from pathlib import Path
import re

import mne
import numpy as np

EVENT_ID = {"left_hand": 1, "right_hand": 2}
ANNOTATION_ID = {"T0": 0, "T1": 1, "T2": 2}


def load_eeg(edf_path: str | Path) -> mne.io.BaseRaw:
    """Load an R04/R08/R12 EDF into memory, retaining only EEG channels."""
    path = Path(edf_path)
    if not path.is_file():
        raise FileNotFoundError(f"EDF file not found: {path.as_posix()}")
    if not re.fullmatch(r"S\d{3}R(04|08|12)\.edf", path.name, re.IGNORECASE):
        raise ValueError("Expected a PhysioNet SxxxR04/R08/R12.edf left/right imagery file.")
    raw = mne.io.read_raw_edf(path, preload=True, verbose=False)
    if not len(mne.pick_types(raw.info, eeg=True, exclude=[])):
        raise ValueError(f"No EEG channels found in {path.name}.")
    return raw.pick("eeg")


def extract_events(raw: mne.io.BaseRaw) -> tuple[np.ndarray, dict[str, int]]:
    """Extract annotations with explicit IDs; T0 is excluded during epoching."""
    events, mapping = mne.events_from_annotations(
        raw, event_id=ANNOTATION_ID, verbose=False
    )
    if not {"T1", "T2"}.issubset(mapping):
        raise ValueError("Both T1 and T2 annotations are required for left/right imagery.")
    return events, mapping


def create_epochs(raw: mne.io.BaseRaw, events: np.ndarray) -> mne.Epochs:
    """Filter continuous EEG to 8-30 Hz and epoch 0.5-3.5 s after cues."""
    filtered = raw.copy().pick("eeg").filter(8.0, 30.0, verbose=False)
    epochs = mne.Epochs(
        filtered,
        events,
        event_id=EVENT_ID,
        tmin=0.5,
        tmax=3.5,
        baseline=None,
        preload=True,
        proj=False,
        verbose=False,
    )
    if not all(np.any(epochs.events[:, 2] == code) for code in EVENT_ID.values()):
        raise ValueError("No usable epochs remain for one or both imagery classes.")
    return epochs


def prepare_data(raw: mne.io.BaseRaw) -> tuple[mne.Epochs, np.ndarray, np.ndarray]:
    """Return epochs, EEG in volts (trials, channels, samples), and labels 1/2."""
    events, _ = extract_events(raw)
    epochs = create_epochs(raw, events)
    X = epochs.get_data()
    # Use retained events so labels stay aligned if MNE drops boundary/bad epochs.
    y = epochs.events[:, 2].copy()
    return epochs, X, y
