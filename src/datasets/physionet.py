"""Dataset adapter for PhysioNet Motor Movement/Imagery dataset (R04/R08/R12)."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union
import numpy as np
import mne

from src.preprocessing.preprocess import load_eeg, prepare_data

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
    selected = []
    for channel in PHYSIONET_CHANNELS:
        matches = [
            name
            for name in raw.ch_names
            if name.strip().rstrip(".").upper() == channel
        ]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one {channel} channel; found {matches}.")
        selected.append(matches[0])
    result = raw.copy().pick(selected)
    result.rename_channels(dict(zip(selected, PHYSIONET_CHANNELS)))
    return result


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
    subj_dir = data_path / subject_id
    if not subj_dir.is_dir():
        subj_dir = data_path / "physionet" / subject_id
    if not subj_dir.is_dir():
        raise FileNotFoundError(f"PhysioNet subject directory not found for {subject_id} in {data_path}")

    X_list = []
    y_list = []
    loaded_runs = []

    for run_name in runs:
        edf_file = subj_dir / f"{subject_id}{run_name}.edf"
        if not edf_file.is_file():
            continue

        raw = load_eeg(edf_file)
        if channel_selection:
            raw = select_physionet_channels(raw)

        _, X_run, y_run = prepare_data(raw)

        X_list.append(X_run)
        y_list.append(y_run)
        loaded_runs.append(run_name)

    if not X_list:
        raise FileNotFoundError(f"No valid PhysioNet runs found for {subject_id} in {subj_dir}")

    X_all = np.concatenate(X_list, axis=0)
    y_all = np.concatenate(y_list, axis=0)

    channel_names = list(PHYSIONET_CHANNELS) if channel_selection else [f"Ch{i+1}" for i in range(X_all.shape[1])]

    return PhysioNetAdapterResult(
        X=X_all,
        y=y_all,
        sampling_rate=160.0,
        channel_names=channel_names,
        subject_id=subject_id,
        recording_runs=loaded_runs,
    )
