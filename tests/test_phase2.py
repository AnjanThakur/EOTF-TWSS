"""Unit and integration tests for Phase 2 FBCSP and Riemannian decoding pipelines."""

from pathlib import Path
import unittest
import numpy as np
import yaml

from src.models.fbcsp import FBCSPPipeline
from src.models.riemannian import (
    build_riemannian_mdm_pipeline,
    build_riemannian_tangent_space_pipeline,
)


class Phase2Tests(unittest.TestCase):
    def setUp(self):
        # Create synthetic trial data: (n_trials, n_bands, n_channels, n_samples)
        np.random.seed(42)
        self.n_trials = 20
        self.n_bands = 5
        self.n_channels = 6
        self.n_samples = 481

        self.X_fbcsp = np.random.randn(self.n_trials, self.n_bands, self.n_channels, self.n_samples)
        self.y = np.array([1, 2] * (self.n_trials // 2))

        # Synthetic epoch data for Riemannian: (n_trials, n_channels, n_samples)
        self.X_riemann = np.random.randn(self.n_trials, self.n_channels, self.n_samples)

    def test_config_validity(self):
        config_path = Path(__file__).resolve().parents[1] / "configs/phase2_config.yaml"
        self.assertTrue(config_path.is_file(), "phase2_config.yaml must exist.")
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        self.assertEqual(len(config["subjects"]), 10)
        self.assertEqual(len(config["runs"]), 3)
        self.assertEqual(len(config["sub_bands"]), 5)
        self.assertEqual(len(config["models"]), 4)

    def test_fbcsp_pipeline_fit_predict(self):
        fbcsp = FBCSPPipeline(n_components_per_band=2, n_features_to_select=4)
        fbcsp.fit(self.X_fbcsp, self.y)
        preds = fbcsp.predict(self.X_fbcsp)
        probas = fbcsp.predict_proba(self.X_fbcsp)

        self.assertEqual(preds.shape, (self.n_trials,))
        self.assertTrue(set(preds).issubset({1, 2}))
        self.assertEqual(probas.shape, (self.n_trials, 2))
        self.assertTrue(np.allclose(probas.sum(axis=1), 1.0))

    def test_fbcsp_fold_isolation(self):
        train_idx = np.arange(0, 14)
        test_idx = np.arange(14, 20)

        fbcsp = FBCSPPipeline(n_components_per_band=2, n_features_to_select=4)
        fbcsp.fit(self.X_fbcsp[train_idx], self.y[train_idx])

        test_preds = fbcsp.predict(self.X_fbcsp[test_idx])
        self.assertEqual(len(test_preds), len(test_idx))

    def test_riemannian_mdm_pipeline(self):
        pipeline = build_riemannian_mdm_pipeline()
        pipeline.fit(self.X_riemann, self.y)
        preds = pipeline.predict(self.X_riemann)
        probas = pipeline.predict_proba(self.X_riemann)

        self.assertEqual(preds.shape, (self.n_trials,))
        self.assertTrue(set(preds).issubset({1, 2}))
        self.assertEqual(probas.shape, (self.n_trials, 2))

    def test_riemannian_tangent_space_pipeline(self):
        pipeline = build_riemannian_tangent_space_pipeline()
        pipeline.fit(self.X_riemann, self.y)
        preds = pipeline.predict(self.X_riemann)
        probas = pipeline.predict_proba(self.X_riemann)

        self.assertEqual(preds.shape, (self.n_trials,))
        self.assertTrue(set(preds).issubset({1, 2}))
        self.assertEqual(probas.shape, (self.n_trials, 2))


if __name__ == "__main__":
    unittest.main()
