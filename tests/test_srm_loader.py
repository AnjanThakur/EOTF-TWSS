"""Unit tests for SRM dataset adapter and loader."""

import unittest
from pathlib import Path

from src.datasets.srm import load_srm_dataset, SRMDatasetResult
from src.datasets.physionet import load_physionet_adapter, PhysioNetAdapterResult


class SRMDatasetAdapterTests(unittest.TestCase):
    """Test suite for SRM dataset loading and chunking adapter."""

    def test_srm_loader_non_existent_directory(self):
        with self.assertRaises(FileNotFoundError):
            load_srm_dataset(dataset_dir="non_existent_directory_12345")

    def test_srm_loader_real_dataset_subset(self):
        srm_dir = Path("data/srm/ds003775")
        if not srm_dir.is_dir():
            self.skipTest("Local SRM dataset directory not found.")

        result = load_srm_dataset(
            dataset_dir=srm_dir,
            max_subjects=1,
            window_duration=2.0,
        )

        self.assertIsInstance(result, SRMDatasetResult)
        self.assertEqual(result.X.ndim, 3)  # (windows, channels, samples)
        self.assertEqual(result.X.shape[1], 64)  # 64 channels
        self.assertEqual(result.sampling_rate, 1024.0)  # 1024 Hz
        self.assertGreater(result.n_subjects, 0)
        self.assertGreater(result.n_recordings, 0)

    def test_physionet_adapter(self):
        physionet_dir = Path("data")
        result = load_physionet_adapter(data_dir=physionet_dir, subject_id="S001")

        self.assertIsInstance(result, PhysioNetAdapterResult)
        self.assertEqual(result.X.ndim, 3)  # (trials, 6, 481)
        self.assertEqual(result.X.shape[1], 6)
        self.assertEqual(result.sampling_rate, 160.0)
        self.assertEqual(result.channel_names, ["FC3", "FC4", "C3", "C4", "CP3", "CP4"])


if __name__ == "__main__":
    unittest.main()
