"""Dataset adapter for PhysioNet Motor Movement/Imagery dataset (R04/R08/R12)."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union
import numpy as np
import mne

from src.preprocessing.preprocess import load_eeg, prepare_data
from src.models.train_csp_lda import find_run, select_channels

PHYSIONET_CHANNELS = ("FC3", "FC4", "C3", "C4", "CP3", "CP4")


@dataclass
class PhysioNetAdapterResult:
    """Standardized representation of PhysioNet imagery trials."""

    X: np.ndarray  # Shape: (trials, 6, 481)
    y: np.ndarray  # Shape: (trials,)
    sampling_rate: float
    channel_names: List[str]
    subject_id: str
    recording_runs: List[str]


def select_physionet_channels(raw: mne.io.BaseRaw) -> mne.io.BaseRaw:
    """Select standard 6 channels (FC3, FC4, C3, C4, CP3, CP4) matching casing and trailing periods."""
    return select_channels(raw)


def load_physionet_adapter(
    data_dir: Union[str, Path] = "data",
    subject_id: str = "S001",
    runs: Optional[List[str]] = None,
    channel_selection: bool = True,
) -> PhysioNetAdapterResult:
    """Load PhysioNet motor imagery trials using existing protected preprocessing.

    Parameters
    ----------
    data_dir : str or Path
        Root directory containing subject data.
    subject_id : str, default="S001"
        Subject identifier string.
    runs : List[str], optional
        List of run strings e.g. ["R04", "R08", "R12"].
    channel_selection : bool, default=True
        Whether to restrict channels to the standard 6 channels.

    Returns
    -------
    PhysioNetAdapterResult
        Container with standardized preprocessed EEG trials and metadata.

    Raises
    ------
    FileNotFoundError
        If subject directory or run files are missing.
    """
    if runs is None:
        runs = ["R04", "R08", "R12"]

    data_path = Path(data_dir)

    X_list = []
    y_list = []
    loaded_runs = []

    for run_name in runs:
        edf_file = find_run(data_path, run_name, subject_id)

        raw = load_eeg(edf_file)
        if channel_selection:
            raw = select_physionet_channels(raw)

        epochs, X_run, y_run = prepare_data(raw)
        if X_list and (epochs.info["sfreq"] != sampling_rate or epochs.ch_names != channel_names):
            raise ValueError("PhysioNet runs must have matching sampling rates and channel order.")
        sampling_rate, channel_names = epochs.info["sfreq"], epochs.ch_names

        X_list.append(X_run)
        y_list.append(y_run)
        loaded_runs.append(run_name)

    if not X_list:
        raise FileNotFoundError(f"No valid PhysioNet runs found for {subject_id} in {data_path}")

    X_all = np.concatenate(X_list, axis=0)
    y_all = np.concatenate(y_list, axis=0)


    return PhysioNetAdapterResult(
        X=X_all,
        y=y_all,
        sampling_rate=float(sampling_rate),
        channel_names=channel_names,
        subject_id=subject_id,
        recording_runs=loaded_runs,
    )
