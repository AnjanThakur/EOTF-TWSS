import unittest
from pathlib import Path
import numpy as np
from src.models.phase1_evaluation import evaluate_subject
from src.realtime.heldout_demo import heldout_trials
from src.models.train_csp_lda import load_subject
import yaml


class Phase1Tests(unittest.TestCase):
    def test_config(self):
        config = yaml.safe_load(Path("configs/phase1_config.yaml").read_text())
        self.assertEqual(config["csp_components"], 4); self.assertEqual(config["runs"], ["R04", "R08", "R12"])
        self.assertEqual(config["channels"], ["FC3", "FC4", "C3", "C4", "CP3", "CP4"])

    def test_metrics_and_no_overlap(self):
        rows = evaluate_subject("data", "S001")
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertEqual(row["train_trials"], 30); self.assertEqual(row["test_trials"], 15)
            self.assertGreaterEqual(row["accuracy"], 0); self.assertLessEqual(row["accuracy"], 1)
            self.assertEqual(row["train_runs"].count(row["test_run"]), 0)

    def test_heldout_demo_has_gate_fields(self):
        rows = list(heldout_trials("data", "S001", "R04", threshold=0.99))
        self.assertEqual(len(rows), 15)
        self.assertTrue(all(row["held_out"] == "R04" and "R04" not in row["train_runs"] for row in rows))
        self.assertTrue(all(row["actual"] in ("LEFT", "RIGHT") and row["prediction"] in ("LEFT", "RIGHT") for row in rows))
        self.assertTrue(any(row["word"] is None for row in rows))
