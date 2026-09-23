"""Dataset adapter for SRM Resting-State EEG Dataset (ds003775)."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union
import glob
import re

mne_import_error = None
try:
    import mne
except ImportError as err:
    mne_import_error = err

import numpy as np


@dataclass
class SRMDatasetResult:
    """Standardized representation of SRM dataset chunks."""

    X: np.ndarray  # Shape: (total_windows, n_channels, n_samples)
    sampling_rate: float
    channel_names: List[str]
    n_subjects: int
    n_recordings: int
    subject_ids: List[str]
    recording_paths: List[str]
    window_duration_sec: float


def load_srm_dataset(
    dataset_dir: Union[str, Path] = "data/srm/ds003775",
    max_subjects: Optional[int] = None,
    max_recordings: Optional[int] = None,
    window_duration: float = 2.0,
    overlap: float = 0.0,
    target_channels: Optional[List[str]] = None,
) -> SRMDatasetResult:
    """Load SRM resting-state EEG files and segment continuous data into standardized windows.

    Parameters
    ----------
    dataset_dir : str or Path
        Root path to SRM ds003775 directory.
    max_subjects : int, optional
        Maximum number of unique subjects to process.
    max_recordings : int, optional
        Maximum number of total recordings to load.
    window_duration : float, default=2.0
        Duration of window segments in seconds.
    overlap : float, default=0.0
        Fraction of overlap between consecutive windows (0.0 to 0.9).
    target_channels : List[str], optional
        List of specific channel names to select. If None, retains all EEG channels.

    Returns
    -------
    SRMDatasetResult
        Container with standardized EEG windows (trials, channels, samples) and metadata.

    Raises
    ------
    FileNotFoundError
        If dataset directory or no EDF files are found.
    ValueError
        If parameters are invalid.
    """
    if mne_import_error is not None:
        raise RuntimeError("MNE is required to load SRM dataset.") from mne_import_error

    path = Path(dataset_dir)
    if not path.is_dir():
        raise FileNotFoundError(f"SRM dataset directory not found: {path.as_posix()}")

    edf_pattern = str(path / "**" / "*.edf")
    all_edf_files = sorted(glob.glob(edf_pattern, recursive=True))

    if not all_edf_files:
        raise FileNotFoundError(f"No EDF files found in {path.as_posix()}")

    # Filter out empty or git-annex stub files (< 100KB)
    edf_files_valid = [f for f in all_edf_files if Path(f).is_file() and Path(f).stat().st_size > 100_000]

    if not edf_files_valid:
        raise FileNotFoundError(f"No valid EDF files (>100KB) found in {path.as_posix()}")

    # Group by subject
    subjects_map = {}
    for edf_path in edf_files_valid:
        match = re.search(r"sub-(\d+)", Path(edf_path).name)
        sub_id = match.group(1) if match else "unknown"
        if sub_id not in subjects_map:
            subjects_map[sub_id] = []
        subjects_map[sub_id].append(edf_path)

    selected_sub_ids = list(subjects_map.keys())
    if max_subjects is not None and max_subjects > 0:
        selected_sub_ids = selected_sub_ids[:max_subjects]

    files_to_load = []
    for sub_id in selected_sub_ids:
        files_to_load.extend(subjects_map[sub_id])
        if max_recordings is not None and len(files_to_load) >= max_recordings:
            files_to_load = files_to_load[:max_recordings]
            break

    if max_recordings is not None and len(files_to_load) > max_recordings:
        files_to_load = files_to_load[:max_recordings]

    windows_list = []
    sampling_rate = None
    channel_names = None
    processed_files = []
    processed_subjects = set()

    for edf_file in files_to_load:
        try:
            raw = mne.io.read_raw_edf(edf_file, preload=True, verbose=False)
        except Exception:
            continue
        raw.pick("eeg")

        if target_channels is not None:
            raw.pick([ch for ch in target_channels if ch in raw.ch_names])

        if sampling_rate is None:
            sampling_rate = float(raw.info["sfreq"])
            channel_names = list(raw.ch_names)

        data = raw.get_data()  # Shape: (channels, total_samples)
        sfreq = raw.info["sfreq"]
        n_samples_per_win = int(round(window_duration * sfreq))
        step_samples = int(round(n_samples_per_win * (1.0 - overlap)))

        if step_samples < 1:
            step_samples = n_samples_per_win

        total_samples = data.shape[1]
        start_idx = 0
        file_windows = []

        while start_idx + n_samples_per_win <= total_samples:
            win_data = data[:, start_idx : start_idx + n_samples_per_win]
            file_windows.append(win_data)
            start_idx += step_samples

        if file_windows:
            windows_list.append(np.stack(file_windows, axis=0))
            processed_files.append(edf_file)
            match = re.search(r"sub-(\d+)", Path(edf_file).name)
            if match:
                processed_subjects.add(match.group(1))

    if not windows_list:
        raise ValueError("No windows could be extracted from SRM recordings.")

    X = np.concatenate(windows_list, axis=0)  # Shape: (total_windows, channels, samples_per_win)

    return SRMDatasetResult(
        X=X,
        sampling_rate=sampling_rate,
        channel_names=channel_names,
        n_subjects=len(processed_subjects),
        n_recordings=len(processed_files),
        subject_ids=sorted(list(processed_subjects)),
        recording_paths=processed_files,
        window_duration_sec=window_duration,
    )
