"""Spatial feature extraction for hardware-independent EEG processing."""

import numpy as np

SPATIAL_FEATURE_NAMES = ("spatial_variance", "mean_cross_correlation")


def compute_covariance_matrix(X: np.ndarray) -> np.ndarray:
    """Compute per-trial channel covariance matrix.

    Parameters
    ----------
    X : np.ndarray
        EEG data array of shape (trials, channels, samples) or (channels, samples).

    Returns
    -------
    np.ndarray
        Covariance matrix of shape (trials, channels, channels) or (channels, channels).
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

    if not np.isfinite(X).all():
        raise ValueError("Input EEG array contains non-finite values.")

    n_trials, n_channels, n_samples = X.shape
    if n_samples < 2:
        raise ValueError(f"At least 2 time samples required for covariance calculation, got {n_samples}")

    # Center continuous signals per channel per trial
    X_centered = X - np.mean(X, axis=2, keepdims=True)

    # Batch matrix multiplication: (trials, channels, samples) @ (trials, samples, channels)
    cov = np.matmul(X_centered, X_centered.transpose(0, 2, 1)) / (n_samples - 1)

    if squeeze_output:
        return cov[0]
    return cov


def compute_correlation_matrix(X: np.ndarray) -> np.ndarray:
    """Compute per-trial channel correlation matrix.

    Parameters
    ----------
    X : np.ndarray
        EEG data array of shape (trials, channels, samples) or (channels, samples).

    Returns
    -------
    np.ndarray
        Correlation matrix of shape (trials, channels, channels) or (channels, channels).
    """
    cov = compute_covariance_matrix(X)
    squeeze_output = cov.ndim == 2
    if squeeze_output:
        cov = np.expand_dims(cov, axis=0)

    # Extract diagonal std devs
    std_diag = np.sqrt(np.diagonal(cov, axis1=1, axis2=2))
    std_diag = np.where(std_diag > 0, std_diag, 1.0)

    # Outer product per trial: (trials, channels, channels)
    std_outer = np.matmul(
        np.expand_dims(std_diag, axis=2), np.expand_dims(std_diag, axis=1)
    )

    corr = cov / std_outer
    np.clip(corr, -1.0, 1.0, out=corr)

    if squeeze_output:
        return corr[0]
    return corr


def extract_spatial_features(X: np.ndarray) -> np.ndarray:
    """Extract spatial features per channel for generic EEG data.

    Parameters
    ----------
    X : np.ndarray
        EEG data array of shape (trials, channels, samples) or (channels, samples).

    Returns
    -------
    np.ndarray
        Spatial features of shape (trials, channels, 2) containing:
        - channel self-variance
        - mean cross-correlation with all other channels.
    """
    cov = compute_covariance_matrix(X)
    corr = compute_correlation_matrix(X)

    squeeze_output = False
    if cov.ndim == 2:
        cov = np.expand_dims(cov, axis=0)
        corr = np.expand_dims(corr, axis=0)
        squeeze_output = True

    n_trials, n_channels, _ = cov.shape

    # 1. Spatial self-variance (diagonal of covariance)
    spatial_variance = np.diagonal(cov, axis1=1, axis2=2)

    # 2. Mean cross-correlation with other channels
    if n_channels > 1:
        # Sum of rows minus diagonal (self-corr = 1.0)
        mean_cross_corr = (np.sum(corr, axis=2) - np.diagonal(corr, axis1=1, axis2=2)) / (n_channels - 1)
    else:
        mean_cross_corr = np.zeros((n_trials, 1), dtype=np.float64)

    features = np.stack([spatial_variance, mean_cross_corr], axis=-1)

    if squeeze_output:
        return features[0]
    return features
