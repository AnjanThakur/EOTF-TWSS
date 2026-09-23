"""Spectral feature extraction using Welch PSD for hardware-independent EEG processing."""

from typing import Dict, Tuple
import numpy as np
from scipy.signal import welch
from scipy.integrate import trapezoid

SPECTRAL_BANDS: Dict[str, Tuple[float, float]] = {
    "delta": (1.0, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 13.0),
    "beta": (13.0, 30.0),
    "gamma": (30.0, 45.0),
}

SPECTRAL_FEATURE_NAMES = (
    "delta_abs",
    "theta_abs",
    "alpha_abs",
    "beta_abs",
    "gamma_abs",
    "delta_rel",
    "theta_rel",
    "alpha_rel",
    "beta_rel",
    "gamma_rel",
)


def extract_spectral_features(
    X: np.ndarray, sampling_rate: float, bands: Dict[str, Tuple[float, float]] = None
) -> np.ndarray:
    """Calculate frequency-domain band power features using Welch PSD.

    Parameters
    ----------
    X : np.ndarray
        EEG data array of shape (trials, channels, samples) or (channels, samples).
    sampling_rate : float
        Sampling frequency of the EEG signal in Hz. Must be > 0.
    bands : Dict[str, Tuple[float, float]], optional
        Frequency band dictionary. Defaults to SPECTRAL_BANDS.

    Returns
    -------
    np.ndarray
        Extracted spectral features of shape (trials, channels, n_spectral_features)
        containing absolute power followed by relative power for each band.

    Raises
    ------
    ValueError
        If sampling_rate <= 0, input is invalid, or highest band exceeds Nyquist frequency.
    """
    if sampling_rate <= 0:
        raise ValueError(f"sampling_rate must be > 0, got {sampling_rate}")

    if bands is None:
        bands = SPECTRAL_BANDS

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

    n_trials, n_channels, n_samples = X.shape
    if n_samples < 4:
        raise ValueError(f"Insufficient samples per trial for spectral analysis: {n_samples}")

    nyquist = sampling_rate / 2.0
    for band_name, (f_min, f_max) in bands.items():
        if f_min >= f_max:
            raise ValueError(f"Invalid band range for {band_name}: ({f_min}, {f_max})")
        if f_min >= nyquist:
            raise ValueError(
                f"Band {band_name} min frequency ({f_min} Hz) reaches or exceeds Nyquist ({nyquist} Hz)"
            )

    # Compute Welch PSD along the last axis (time samples)
    nperseg = min(n_samples, int(sampling_rate * 2.0))
    if nperseg < 4:
        nperseg = n_samples

    freqs, psd = welch(X, fs=sampling_rate, nperseg=nperseg, axis=-1)

    abs_powers = []
    for band_name, (f_min, f_max) in bands.items():
        band_mask = (freqs >= f_min) & (freqs <= f_max)
        if not np.any(band_mask):
            band_power = np.zeros((n_trials, n_channels), dtype=np.float64)
        else:
            freq_step = freqs[1] - freqs[0] if len(freqs) > 1 else 1.0
            band_power = trapezoid(psd[..., band_mask], freqs[band_mask], axis=-1)
        abs_powers.append(band_power)

    # Total power across full spectrum (1 Hz to min(Nyquist, 45 Hz))
    total_mask = (freqs >= 1.0) & (freqs <= min(nyquist, 45.0))
    if np.any(total_mask):
        total_power = trapezoid(psd[..., total_mask], freqs[total_mask], axis=-1)
    else:
        total_power = trapezoid(psd, freqs, axis=-1)

    # Prevent division by zero
    total_power_safe = np.where(total_power > 1e-15, total_power, 1.0)

    rel_powers = []
    for abs_p in abs_powers:
        rel_p = np.where(total_power > 1e-15, abs_p / total_power_safe, 0.0)
        rel_powers.append(rel_p)

    all_features = abs_powers + rel_powers
    stacked = np.stack(all_features, axis=-1)

    if squeeze_output:
        return stacked[0]
    return stacked
