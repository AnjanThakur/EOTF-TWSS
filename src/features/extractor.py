"""Unified hardware-independent EEG Feature Extractor."""

from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import numpy as np
import pandas as pd

from .temporal import extract_temporal_features, TEMPORAL_FEATURE_NAMES
from .spectral import extract_spectral_features, SPECTRAL_FEATURE_NAMES, SPECTRAL_BANDS
from .spatial import extract_spatial_features, SPATIAL_FEATURE_NAMES, compute_covariance_matrix


@dataclass
class FeatureVector:
    """Container for extracted features and associated metadata."""

    features: np.ndarray  # Shape: (trials, total_features)
    feature_names: List[str]
    metadata: pd.DataFrame


class EEGFeatureExtractor:
    """Unified EEG feature extractor combining Temporal, Spectral, and Spatial representations.

    Parameters
    ----------
    include_temporal : bool, default=True
        Whether to extract temporal features.
    include_spectral : bool, default=True
        Whether to extract spectral band-power features.
    include_spatial : bool, default=True
        Whether to extract per-channel spatial features.
    include_covariance_matrix : bool, default=True
        Whether to extract upper-triangle channel covariance elements.
    """

    def __init__(
        self,
        include_temporal: bool = True,
        include_spectral: bool = True,
        include_spatial: bool = True,
        include_covariance_matrix: bool = True,
    ):
        self.include_temporal = include_temporal
        self.include_spectral = include_spectral
        self.include_spatial = include_spatial
        self.include_covariance_matrix = include_covariance_matrix

    def transform(
        self,
        X: np.ndarray,
        sampling_rate: float,
        channel_names: Optional[List[str]] = None,
    ) -> FeatureVector:
        """Transform EEG array into a unified feature matrix with complete metadata.

        Parameters
        ----------
        X : np.ndarray
            EEG array of shape (trials, channels, samples) or (channels, samples).
        sampling_rate : float
            Sampling rate in Hz.
        channel_names : List[str], optional
            Names of EEG channels. If None, channels are named Ch1, Ch2, ...

        Returns
        -------
        FeatureVector
            Dataclass containing feature matrix, feature names, and metadata DataFrame.
        """
        if not isinstance(X, np.ndarray):
            X = np.asarray(X, dtype=np.float64)

        squeeze_output = False
        if X.ndim == 2:
            X = np.expand_dims(X, axis=0)
            squeeze_output = True
        elif X.ndim != 3:
            raise ValueError(f"Expected 2D or 3D input array, got shape {X.shape}")

        n_trials, n_channels, n_samples = X.shape

        if channel_names is None:
            channel_names = [f"Ch{i+1}" for i in range(n_channels)]
        elif len(channel_names) != n_channels:
            raise ValueError(
                f"Length of channel_names ({len(channel_names)}) does not match n_channels ({n_channels})"
            )

        feature_blocks: List[np.ndarray] = []
        metadata_records: List[Dict[str, str]] = []

        # 1. Temporal features
        if self.include_temporal:
            temp_feat = extract_temporal_features(X)  # (trials, channels, 5)
            for ch_idx, ch_name in enumerate(channel_names):
                for f_idx, f_name in enumerate(TEMPORAL_FEATURE_NAMES):
                    feature_blocks.append(temp_feat[:, ch_idx, f_idx : f_idx + 1])
                    metadata_records.append(
                        {
                            "feature_name": f"{ch_name}_{f_name}",
                            "feature_type": "temporal",
                            "channel": ch_name,
                            "frequency_band": "N/A",
                        }
                    )

        # 2. Spectral features
        if self.include_spectral:
            spec_feat = extract_spectral_features(X, sampling_rate=sampling_rate)  # (trials, channels, 10)
            band_keys = list(SPECTRAL_BANDS.keys())
            for ch_idx, ch_name in enumerate(channel_names):
                for f_idx, f_name in enumerate(SPECTRAL_FEATURE_NAMES):
                    feature_blocks.append(spec_feat[:, ch_idx, f_idx : f_idx + 1])
                    band_name = band_keys[f_idx % len(band_keys)]
                    metadata_records.append(
                        {
                            "feature_name": f"{ch_name}_{f_name}",
                            "feature_type": "spectral",
                            "channel": ch_name,
                            "frequency_band": band_name,
                        }
                    )

        # 3. Spatial features
        if self.include_spatial:
            spat_feat = extract_spatial_features(X)  # (trials, channels, 2)
            for ch_idx, ch_name in enumerate(channel_names):
                for f_idx, f_name in enumerate(SPATIAL_FEATURE_NAMES):
                    feature_blocks.append(spat_feat[:, ch_idx, f_idx : f_idx + 1])
                    metadata_records.append(
                        {
                            "feature_name": f"{ch_name}_{f_name}",
                            "feature_type": "spatial",
                            "channel": ch_name,
                            "frequency_band": "N/A",
                        }
                    )

        # 4. Channel Covariance Matrix (Upper Triangle)
        if self.include_covariance_matrix:
            cov_matrices = compute_covariance_matrix(X)  # (trials, channels, channels)
            triu_i, triu_j = np.triu_indices(n_channels)
            for i, j in zip(triu_i, triu_j):
                cov_val = cov_matrices[:, i, j : j + 1]
                feature_blocks.append(cov_val)
                ch_pair = f"{channel_names[i]}-{channel_names[j]}"
                metadata_records.append(
                    {
                        "feature_name": f"cov_{ch_pair}",
                        "feature_type": "covariance",
                        "channel": ch_pair,
                        "frequency_band": "N/A",
                    }
                )

        if not feature_blocks:
            raise ValueError("No feature types selected for extraction.")

        feature_matrix = np.hstack(feature_blocks)  # Shape: (trials, total_features)

        if squeeze_output:
            feature_matrix = feature_matrix[0:1]

        metadata_df = pd.DataFrame(metadata_records)
        feature_names = metadata_df["feature_name"].tolist()

        return FeatureVector(
            features=feature_matrix,
            feature_names=feature_names,
            metadata=metadata_df,
        )
