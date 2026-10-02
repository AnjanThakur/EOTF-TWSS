"""Train S001 CSP+LDA: python -m src.models.train_csp_lda."""

import argparse
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".cache/matplotlib"))

import joblib
import mne
from mne.decoding import CSP
import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.pipeline import Pipeline

from src.preprocessing.preprocess import load_eeg, prepare_data

RUNS = ("R04", "R08", "R12")
CHANNELS = ("FC3", "FC4", "C3", "C4", "CP3", "CP4")
LABELS = [1, 2]


def select_channels(raw: mne.io.BaseRaw, channels=CHANNELS) -> mne.io.BaseRaw:
    """Match case/trailing periods, reject missing or ambiguous channel names."""
    channels = tuple(str(c).strip().rstrip('.').upper() for c in channels)
    if len(channels) != 6 or len(set(channels)) != 6:
        raise ValueError('Expected six distinct channel names.')
    selected = []
    for channel in channels:
        matches = [name for name in raw.ch_names
                   if name.strip().rstrip(".").upper() == channel]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one {channel} channel; found {matches}.")
        selected.append(matches[0])
    result = raw.copy().pick(selected)
    result.rename_channels(dict(zip(selected, channels)))
    return result


def find_run(data_dir: Path, run: str, subject: str = "S001") -> Path:
    """Accept a data root, physionet directory, or subject directory."""
    name = f"{subject}{run}.edf"
    candidates = [
        data_dir / "physionet/MNE-eegbci-data/files/eegmmidb/1.0.0" / subject / name,
        data_dir / "physionet" / subject / name,
        data_dir / "physionet" / name,
        data_dir / subject / name,
        data_dir / name,
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(f"Cannot find {name} under {data_dir.as_posix()}.")


def load_subject(data_dir: str | Path, subject: str = "S001", runs=RUNS) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Preprocess each run independently and return trials, labels, run groups."""
    trials, labels, groups = [], [], []
    reference_times = None
    reference_sfreq = None
    for run in runs:
        raw = select_channels(load_eeg(find_run(Path(data_dir), run, subject)))
        epochs, X, y = prepare_data(raw)
        if reference_times is None:
            reference_times = epochs.times.copy()
            reference_sfreq = epochs.info["sfreq"]
        elif (epochs.info["sfreq"] != reference_sfreq
              or not np.array_equal(epochs.times, reference_times)):
            raise ValueError(f"{run} has a different sampling frequency or epoch time grid.")
        if not np.isfinite(X).all():
            raise ValueError(f"{run} contains non-finite EEG samples.")
        trials.append(X)
        labels.append(y)
        groups.append(np.full(len(y), run))
    return np.concatenate(trials), np.concatenate(labels), np.concatenate(groups)


def build_pipeline() -> Pipeline:
    """Fresh estimators ensure CSP and LDA are fitted only on training trials."""
    return Pipeline([
        ("csp", CSP(n_components=4)),
        ("lda", LinearDiscriminantAnalysis()),
    ])


def evaluate_runs(X: np.ndarray, y: np.ndarray, groups: np.ndarray) -> list[dict]:
    """Leave one complete run out; never fit CSP on held-out trials."""
    results = []
    for run in RUNS:
        test = groups == run
        train = ~test
        if not test.any() or not train.any():
            raise ValueError(f"Missing training or test trials for {run}.")
        model = build_pipeline()
        with mne.use_log_level("WARNING"):
            model.fit(X[train], y[train])
        predictions = model.predict(X[test])
        result = {
            "test_run": run,
            "train_trials": int(train.sum()),
            "test_trials": int(test.sum()),
            "accuracy": float(accuracy_score(y[test], predictions)),
            "confusion_matrix": confusion_matrix(y[test], predictions, labels=LABELS),
        }
        results.append(result)
        print(f"\nTrain {'+'.join(r for r in RUNS if r != run)}; test {run}")
        print(f"Train trials: {result['train_trials']}; test trials: {result['test_trials']}")
        print(f"Accuracy: {result['accuracy']:.6f} ({result['accuracy']:.2%})")
        print("Confusion matrix (rows=true, columns=predicted; order: LEFT=1, RIGHT=2):")
        print(result["confusion_matrix"])
    print(f"\nMean accuracy: {np.mean([r['accuracy'] for r in results]):.6f} "
          f"({np.mean([r['accuracy'] for r in results]):.2%})")
    return results


def train(data_dir: str | Path, model_path: str | Path) -> tuple[Pipeline, list[dict]]:
    """Evaluate held-out runs, then save a separate model fitted on all trials."""
    X, y, groups = load_subject(data_dir)
    print(f"Channel order: {list(CHANNELS)}")
    print(f"Total X.shape: {X.shape}")
    print(f"Total y.shape: {y.shape}")
    print(f"Class counts (1=LEFT, 2=RIGHT): { {label: int((y == label).sum()) for label in LABELS} }")
    results = evaluate_runs(X, y, groups)
    final_model = build_pipeline()
    with mne.use_log_level("WARNING"):
        final_model.fit(X, y)
    model_path = Path(model_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(final_model, model_path)
    # Check that the serialized pipeline reproduces the fitted model's predictions.
    restored = joblib.load(model_path)
    if not np.array_equal(final_model.predict(X), restored.predict(X)):
        raise RuntimeError("Saved model predictions differ after reloading.")
    print(f"Final model trained on {len(y)} trials.")
    print(f"Saved model: {model_path.as_posix()}")
    print("Model reload verification: passed")
    return final_model, results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    parser.add_argument("--model-path", type=Path,
                        default=PROJECT_ROOT / "models/csp_lda_s001.joblib")
    args = parser.parse_args()
    try:
        train(args.data_dir, args.model_path)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
