"""Leakage, rejection, reproducible exports, and frozen-artifact contracts."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from src.models.research_evaluation import run_split, classification_metrics, threshold_metrics
from src.models.train_csp_lda import select_channels
from src.reporting.experiments import export_experiment, freeze_hashes
from src.realtime.heldout_demo import create_heldout_replay
import mne


class ResearchTests(unittest.TestCase):
    def test_split_disjoint(self):
        groups = np.repeat(['R04', 'R08', 'R12'], 4)
        for run in ('R04', 'R08', 'R12'):
            train, test = run_split(groups, run)
            self.assertEqual((train.sum(), test.sum()), (8, 4))
            self.assertFalse(set(groups[train]) & set(groups[test]))
        with self.assertRaises(ValueError):
            run_split(['R04', 'R08'], 'R04')

    def test_metric_definitions(self):
        metrics = classification_metrics([1, 1, 2, 2], [1, 2, 2, 2])
        self.assertEqual(metrics['accuracy'], .75)
        self.assertEqual(metrics['balanced_accuracy'], .75)
        self.assertAlmostEqual(metrics['f1'], 2/3)
        self.assertEqual([metrics[k] for k in ('cm_11', 'cm_12', 'cm_21', 'cm_22')], [1, 1, 0, 2])

    def test_threshold_counts_and_boundary(self):
        rows = [{'test_run': 'R04', 'train_runs': 'R08+R12', 'actual': 1, 'prediction': pred, 'confidence': conf}
                for pred, conf in ((1, .7), (2, .8), (1, .6))]
        table = threshold_metrics(rows, [.7, .95])
        self.assertEqual(table.iloc[0].accepted_predictions, 2)
        self.assertEqual(table.iloc[0].correct_accepted, 1)
        self.assertAlmostEqual(table.iloc[0].false_command_rate, 1/3)
        self.assertTrue(pd.isna(table.iloc[1].accepted_command_accuracy))
        rows[0]['train_runs'] = 'R04+R08'
        with self.assertRaises(ValueError):
            threshold_metrics(rows, [.7])

    def test_montage_normalization(self):
        raw = mne.io.RawArray(np.zeros((6, 10)), mne.create_info(['fc3.', 'FC4.', 'c3.', 'C4.', 'cp3.', 'CP4.'], 160, 'eeg'), verbose=False)
        self.assertEqual(select_channels(raw).ch_names, ['FC3', 'FC4', 'C3', 'C4', 'CP3', 'CP4'])
        with self.assertRaises(ValueError):
            select_channels(raw, ['C3']*6)

    def test_export_preserves_frozen(self):
        before = freeze_hashes()
        with tempfile.TemporaryDirectory(dir='.cache') as temp:
            export_experiment(temp, {'experiment': 'test'}, {'metrics': [{'value': .75}]}, 'test')
            payload = json.loads((Path(temp)/'report.json').read_text())
            self.assertIn('software_versions', payload)
            self.assertTrue((Path(temp)/'report.md').exists())
        self.assertEqual(before, freeze_hashes())
        with self.assertRaises(ValueError):
            export_experiment('results/phase1', {'experiment': 'test'}, {}, '')

    def test_heldout_replay_only_test_run(self):
        groups = np.repeat(['R04', 'R08', 'R12'], 2)
        X = np.random.default_rng(0).normal(size=(6, 6, 481))
        y = np.tile([1, 2], 3)
        with patch('src.realtime.heldout_demo.load_subject', return_value=(X, y, groups)), \
             patch('src.realtime.heldout_demo.build_pipeline') as factory:
            model, trials = create_heldout_replay('data', held_out='R08')
            np.testing.assert_array_equal(model.fit.call_args.args[0], X[groups != 'R08'])
            self.assertEqual(len(list(trials)), 2)

    def test_heldout_demo_rejection_keeps_raw_prediction(self):
        from src.realtime.heldout_demo import heldout_trials
        rows = list(heldout_trials('data', threshold=1.0))
        self.assertTrue(any(row['decision'] == 'UNKNOWN' for row in rows))
        for row in rows:
            self.assertIn(row['prediction'], ['LEFT', 'RIGHT'])
            if row['decision'] == 'UNKNOWN':
                self.assertIsNone(row['word']); self.assertIsNone(row['sentence'])

    def test_freeze_snapshot(self):
        snapshot = Path('results/software_improvements/freeze_before.json')
        if snapshot.exists():
            self.assertEqual(json.loads(snapshot.read_text()), freeze_hashes())

    def test_research_baseline_matches_existing_loader(self):
        from src.models.fbcsp import load_subject_fbcsp
        from src.models.train_csp_lda import load_subject
        with mne.use_log_level('ERROR'):
            X, y, groups = load_subject('data', 'S001')
            bands, band_y, band_groups = load_subject_fbcsp('data', 'S001', sub_bands=((8., 30.),))
        np.testing.assert_array_equal(X, bands[:, 0])
        np.testing.assert_array_equal(y, band_y)
        np.testing.assert_array_equal(groups, band_groups)

    def test_generated_experiments_complete_and_disjoint(self):
        for directory, variants in [('channel_selection', 6), ('frequency_analysis', 4)]:
            path = Path('results')/directory
            rows = pd.read_csv(path/'fold_metrics.csv')
            predictions = pd.read_csv(path/'heldout_predictions.csv')
            self.assertEqual(len(rows), variants*30)
            self.assertEqual(len(predictions), variants*450)
            self.assertTrue(all(r.test_run not in r.train_runs.split('+') for r in rows.itertuples()))
            self.assertTrue(all(r.test_run not in r.train_runs.split('+') for r in predictions.itertuples()))
            self.assertTrue((rows.train_trials == 30).all())
            self.assertTrue((rows.test_trials == 15).all())
            report = json.loads((path/'report.json').read_text())
            self.assertEqual(report['configuration']['csp_components'], 4)
            self.assertEqual(len(report['configuration']['subjects']), 10)
            self.assertFalse(report['details']['skipped'])
        frozen = pd.read_csv('results/phase1/fold_metrics.csv')
        new = rows[rows.variant == '8-30']
        for metric in ['accuracy', 'balanced_accuracy', 'f1', 'mcc']:
            np.testing.assert_allclose(new[metric], frozen[metric], atol=1e-14, rtol=0)

    def test_threshold_export_recomputed_only_from_heldout(self):
        path = Path('results/confidence_analysis')
        expected = pd.read_csv(path/'threshold_metrics.csv')
        actual = threshold_metrics(pd.read_csv(path/'heldout_predictions.csv'), expected.threshold)
        np.testing.assert_allclose(expected.to_numpy(), actual.to_numpy(), atol=1e-14, rtol=0)

    def test_phase2_numeric_and_plot_reproduction(self):
        from scripts.generate_phase2_plots import generate_plots
        import hashlib
        source = Path('results/phase2_reproduction')
        rows = pd.read_csv(source/'comparison.csv')
        self.assertEqual(len(rows), 16)
        self.assertTrue(rows.matches_at_1e_12.all())
        with tempfile.TemporaryDirectory(dir='.cache') as temp:
            a, b = Path(temp)/'a', Path(temp)/'b'
            generate_plots(source, a, seed=0); generate_plots(source, b, seed=0)
            for image in a.glob('*.png'):
                self.assertEqual(hashlib.sha256(image.read_bytes()).digest(),
                                 hashlib.sha256((b/image.name).read_bytes()).digest())
