"""Phase 3 — Hardware-Independent EEG Feature Extraction Package."""

from .temporal import extract_temporal_features, TEMPORAL_FEATURE_NAMES
from .spectral import extract_spectral_features, SPECTRAL_BANDS, SPECTRAL_FEATURE_NAMES
from .spatial import extract_spatial_features, SPATIAL_FEATURE_NAMES
from .extractor import EEGFeatureExtractor, FeatureVector

__all__ = [
    "extract_temporal_features",
    "TEMPORAL_FEATURE_NAMES",
    "extract_spectral_features",
    "SPECTRAL_BANDS",
    "SPECTRAL_FEATURE_NAMES",
    "extract_spatial_features",
    "SPATIAL_FEATURE_NAMES",
    "EEGFeatureExtractor",
    "FeatureVector",
]
