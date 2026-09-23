"""Temporal feature extraction for hardware-independent EEG processing."""

import numpy as np

TEMPORAL_FEATURE_NAMES = ("mean", "variance", "std", "rms", "peak_to_peak")


def extract_temporal_features(X: np.ndarray) -> np.ndarray:
    """Extract temporal features for generic EEG trial data.

    Parameters
    ----------
    X : np.ndarray
        EEG data array of shape (trials, channels, samples) or (channels, samples).

    Returns
    -------
    np.ndarray
        Extracted features of shape (trials, channels, n_temporal_features)
        where n_temporal_features = 5 (mean, variance, std, rms, peak_to_peak).

    Raises
    ------
    ValueError
        If input array is empty, not 2D/3D, or contains NaNs.
    """
    if not isinstance(X, np.ndarray):
        X = np.asarray(X, dtype=np.float64)

    if X.size == 0:
        raise ValueError("Input EEG array is empty.")

    squeeze_output = False
    if X.ndim == 2:
        X = np.expand_dims(X, axis=0)
        squeeze_output = True
    elif X.ndim != 3:
        raise ValueError(f"Expected 2D or 3D input array, got shape {X.shape}")

    if np.isnan(X).any():
        raise ValueError("Input EEG array contains NaN values.")

    if X.shape[2] == 0:
        raise ValueError("Number of time samples per trial must be > 0.")

    mean_val = np.mean(X, axis=2)
    var_val = np.var(X, axis=2)
    std_val = np.std(X, axis=2)
    rms_val = np.sqrt(np.mean(X**2, axis=2))
    ptp_val = np.ptp(X, axis=2)

    features = np.stack([mean_val, var_val, std_val, rms_val, ptp_val], axis=-1)

    if squeeze_output:
        return features[0]
    return features
