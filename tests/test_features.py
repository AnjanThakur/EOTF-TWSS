"""Unit tests for Phase 3 hardware-independent feature extraction components."""

import unittest
import numpy as np

from src.features.temporal import extract_temporal_features, TEMPORAL_FEATURE_NAMES
from src.features.spectral import extract_spectral_features, SPECTRAL_BANDS, SPECTRAL_FEATURE_NAMES
from src.features.spatial import extract_spatial_features, compute_covariance_matrix, compute_correlation_matrix
from src.features.extractor import EEGFeatureExtractor, FeatureVector


class FeatureExtractionTests(unittest.TestCase):
    """Test suite for generic temporal, spectral, and spatial EEG feature extractors."""

    def setUp(self):
        np.random.seed(42)
        # Synthetic EEG: 4 trials, 6 channels, 480 samples @ 160 Hz (3 seconds)
        self.trials = 4
        self.channels = 6
        self.samples = 480
        self.sfreq = 160.0
        self.channel_names = ["FC3", "FC4", "C3", "C4", "CP3", "CP4"]
        self.X_synthetic = np.random.randn(self.trials, self.channels, self.samples)

    # --- Temporal Feature Tests ---

    def test_temporal_shape_3d(self):
        res = extract_temporal_features(self.X_synthetic)
        self.assertEqual(res.shape, (self.trials, self.channels, 5))

    def test_temporal_shape_2d(self):
        X_2d = self.X_synthetic[0]
        res = extract_temporal_features(X_2d)
        self.assertEqual(res.shape, (self.channels, 5))

    def test_temporal_constant_signal(self):
        val = 3.5
        X_const = np.full((1, 2, 100), val)
        res = extract_temporal_features(X_const)
        # Features: [mean, variance, std, rms, peak_to_peak]
        np.testing.assert_allclose(res[0, :, 0], val, rtol=1e-5)  # mean
        np.testing.assert_allclose(res[0, :, 1], 0.0, atol=1e-5)  # variance
        np.testing.assert_allclose(res[0, :, 2], 0.0, atol=1e-5)  # std
        np.testing.assert_allclose(res[0, :, 3], val, rtol=1e-5)  # rms
        np.testing.assert_allclose(res[0, :, 4], 0.0, atol=1e-5)  # ptp

    def test_temporal_nan_handling(self):
        X_nan = self.X_synthetic.copy()
        X_nan[0, 0, 10] = np.nan
        with self.assertRaises(ValueError):
            extract_temporal_features(X_nan)

    def test_temporal_empty_array(self):
        with self.assertRaises(ValueError):
            extract_temporal_features(np.array([]))

    # --- Spectral Feature Tests ---

    def test_spectral_shape_and_features(self):
        res = extract_spectral_features(self.X_synthetic, sampling_rate=self.sfreq)
        self.assertEqual(res.shape, (self.trials, self.channels, 10))

    def test_spectral_sinusoid_dominant_band(self):
        # 10 Hz pure sine wave (Alpha band: 8-13 Hz)
        t = np.linspace(0, 2.0, int(self.sfreq * 2.0), endpoint=False)
        sin_10hz = np.sin(2 * np.pi * 10.0 * t)
        X_sine = np.tile(sin_10hz, (1, 2, 1))  # (1 trial, 2 channels, samples)

        res = extract_spectral_features(X_sine, sampling_rate=self.sfreq)
        # res has 5 abs powers followed by 5 rel powers
        # Rel power indices: 5=delta, 6=theta, 7=alpha, 8=beta, 9=gamma
        alpha_rel_ch0 = res[0, 0, 7]
        other_rels_ch0 = np.delete(res[0, 0, 5:10], 2)

        self.assertGreater(alpha_rel_ch0, 0.7)  # Alpha should dominate
        self.assertTrue(np.all(alpha_rel_ch0 > other_rels_ch0))

    def test_spectral_invalid_sampling_rate(self):
        with self.assertRaises(ValueError):
            extract_spectral_features(self.X_synthetic, sampling_rate=0.0)
        with self.assertRaises(ValueError):
            extract_spectral_features(self.X_synthetic, sampling_rate=-10.0)

    def test_spectral_invalid_band_range(self):
        custom_bands = {"invalid": (10.0, 5.0)}
        with self.assertRaises(ValueError):
            extract_spectral_features(self.X_synthetic, sampling_rate=100.0, bands=custom_bands)

    # --- Spatial Feature Tests ---

    def test_spatial_covariance_shape_and_symmetry(self):
        cov = compute_covariance_matrix(self.X_synthetic)
        self.assertEqual(cov.shape, (self.trials, self.channels, self.channels))
        for t in range(self.trials):
            np.testing.assert_allclose(cov[t], cov[t].T, rtol=1e-5)
            self.assertTrue(np.isfinite(cov[t]).all())

    def test_spatial_correlation_shape_and_bounds(self):
        corr = compute_correlation_matrix(self.X_synthetic)
        self.assertEqual(corr.shape, (self.trials, self.channels, self.channels))
        for t in range(self.trials):
            # Diagonal of correlation matrix should be 1.0
            np.testing.assert_allclose(np.diag(corr[t]), 1.0, rtol=1e-4)
            self.assertTrue(np.all(corr[t] >= -1.0 - 1e-5))
            self.assertTrue(np.all(corr[t] <= 1.0 + 1e-5))

    def test_spatial_features_extraction(self):
        res = extract_spatial_features(self.X_synthetic)
        self.assertEqual(res.shape, (self.trials, self.channels, 2))
        self.assertTrue(np.isfinite(res).all())

    # --- Unified EEGFeatureExtractor Tests ---

    def test_extractor_arbitrary_channel_counts(self):
        for n_ch in [2, 16, 64]:
            X = np.random.randn(2, n_ch, 200)
            ch_names = [f"Ch{i+1}" for i in range(n_ch)]
            extractor = EEGFeatureExtractor()
            fv = extractor.transform(X, sampling_rate=100.0, channel_names=ch_names)

            self.assertEqual(fv.features.shape[0], 2)
            self.assertEqual(len(fv.feature_names), fv.features.shape[1])
            self.assertEqual(len(fv.metadata), fv.features.shape[1])

    def test_extractor_metadata_alignment(self):
        extractor = EEGFeatureExtractor()
        fv = extractor.transform(self.X_synthetic, sampling_rate=self.sfreq, channel_names=self.channel_names)

        # Expected features per channel: 5 temporal + 10 spectral + 2 spatial = 17
        # Covariance upper triangle: 6 * 7 / 2 = 21
        expected_total = (6 * 17) + 21
        self.assertEqual(fv.features.shape, (self.trials, expected_total))
        self.assertEqual(len(fv.feature_names), expected_total)
        self.assertEqual(list(fv.metadata.columns), ["feature_name", "feature_type", "channel", "frequency_band"])

    def test_extractor_determinism(self):
        extractor = EEGFeatureExtractor()
        fv1 = extractor.transform(self.X_synthetic, sampling_rate=self.sfreq, channel_names=self.channel_names)
        fv2 = extractor.transform(self.X_synthetic, sampling_rate=self.sfreq, channel_names=self.channel_names)

        np.testing.assert_array_equal(fv1.features, fv2.features)


if __name__ == "__main__":
    unittest.main()
