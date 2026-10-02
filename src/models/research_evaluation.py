"""Shared run splits and metrics for separate exploratory experiments."""
import mne
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score, matthews_corrcoef
from src.models.phase1_config import validate_runs
from src.models.train_csp_lda import RUNS, build_pipeline


def run_split(groups, held_out, runs=RUNS):
    validate_runs(runs)
    groups = np.asarray(groups)
    if groups.ndim != 1 or held_out not in runs or set(groups) != set(runs):
        raise ValueError('All three configured runs are required for a held-out split.')
    test = groups == held_out
    train = ~test
    if not train.any() or not test.any() or set(groups[train]) & set(groups[test]):
        raise ValueError('Empty or overlapping train/test runs.')
    return train, test


def classification_metrics(actual, predicted):
    cm = confusion_matrix(actual, predicted, labels=[1, 2])
    return {'accuracy': float(accuracy_score(actual, predicted)),
            'balanced_accuracy': float(balanced_accuracy_score(actual, predicted)),
            'f1': float(f1_score(actual, predicted, pos_label=1, zero_division=0)),
            'mcc': float(matthews_corrcoef(actual, predicted)),
            **{f'cm_{i+1}{j+1}': int(cm[i, j]) for i in range(2) for j in range(2)}}


def evaluate_epochs(X, y, groups, subject, variant, runs=RUNS):
    """Fit a fresh existing pipeline per split; return folds and out-of-fold trials."""
    X, y, groups = np.asarray(X), np.asarray(y), np.asarray(groups)
    if X.ndim != 3 or len(X) != len(y) or len(y) != len(groups) or not np.isfinite(X).all():
        raise ValueError('Invalid EEG epochs/labels/run groups.')
    folds, trials = [], []
    for held_out in runs:
        train, test = run_split(groups, held_out, runs)
        model = build_pipeline()
        with mne.use_log_level('WARNING'):
            model.fit(X[train], y[train])
            prediction = model.predict(X[test])
            probability = model.predict_proba(X[test])
        metadata = {'variant': variant, 'subject': subject, 'test_run': held_out,
                    'train_runs': '+'.join(r for r in runs if r != held_out)}
        folds.append({**metadata, 'train_trials': int(train.sum()), 'test_trials': int(test.sum()),
                      **classification_metrics(y[test], prediction)})
        for number, (actual, pred, proba) in enumerate(zip(y[test], prediction, probability), 1):
            confidence = float(proba[np.flatnonzero(model.classes_ == pred)[0]])
            trials.append({**metadata, 'trial': number, 'actual': int(actual), 'prediction': int(pred),
                           'confidence': confidence, 'correct': bool(actual == pred),
                           'prob_left': float(proba[np.flatnonzero(model.classes_ == 1)[0]]),
                           'prob_right': float(proba[np.flatnonzero(model.classes_ == 2)[0]])})
    return folds, trials


def threshold_metrics(predictions, thresholds):
    """False-command rate uses all attempts; conditional error uses accepted attempts."""
    frame = pd.DataFrame(predictions)
    if frame.empty or not {'test_run', 'train_runs', 'confidence', 'actual', 'prediction'} <= set(frame.columns):
        raise ValueError('Held-out predictions with split provenance are required.')
    for row in frame.itertuples():
        if row.test_run in row.train_runs.split('+'):
            raise ValueError('Threshold analysis cannot use training-run predictions.')
    confidence = frame.confidence.to_numpy(float)
    if not np.isfinite(confidence).all() or ((confidence < 0) | (confidence > 1)).any():
        raise ValueError('Invalid prediction probabilities.')
    correct = frame.actual.to_numpy() == frame.prediction.to_numpy()
    rows = []
    for threshold in thresholds:
        if not np.isfinite(threshold) or not 0 <= threshold <= 1:
            raise ValueError('Threshold must be between zero and one.')
        accepted = confidence >= threshold
        count = int(accepted.sum()); total = len(frame)
        good = int((accepted & correct).sum()); bad = count - good
        rows.append({'threshold': float(threshold), 'total_predictions': total,
                     'accepted_predictions': count, 'rejected_predictions': total-count,
                     'acceptance_rate': count/total, 'rejection_rate': (total-count)/total,
                     'correct_accepted': good, 'incorrect_accepted': bad,
                     'accepted_command_accuracy': good/count if count else None,
                     'false_command_rate': bad/total,
                     'conditional_false_command_rate': bad/count if count else None})
    return pd.DataFrame(rows)
