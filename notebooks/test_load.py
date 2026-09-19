"""Run from the project root: python notebooks/test_load.py --no-show."""

import argparse
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".cache/matplotlib"))
sys.path.insert(0, str(PROJECT_ROOT))

from src.preprocessing.preprocess import EVENT_ID, extract_events, load_eeg, prepare_data


def default_edf() -> Path:
    """Support both the requested folder and the existing dataset layout."""
    candidates = [
        PROJECT_ROOT / "data/physionet/S001R04.edf",
        PROJECT_ROOT / "data/physionet/S001/S001R04.edf",
        PROJECT_ROOT / "data/S001/S001R04.edf",
    ]
    return next((path for path in candidates if path.is_file()), candidates[0])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("edf", nargs="?", type=Path, default=default_edf())
    parser.add_argument("--no-show", action="store_true", help="Save the raw plot without opening a window.")
    args = parser.parse_args()

    import matplotlib
    if args.no_show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import mne
    import numpy as np

    try:
        raw = load_eeg(args.edf)
        events, mapping = extract_events(raw)
        print(f"Sampling frequency: {raw.info['sfreq']} Hz")
        print(f"Channel names: {raw.ch_names}")
        print(f"Annotations: {raw.annotations}")
        print(f"Annotation/event mapping: {mapping}")
        print(f"Extracted events: {len(events)}")
        print(f"Class labels: {EVENT_ID} (T0 ignored)")

        output_dir = PROJECT_ROOT / "notebooks/outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        plot_path = output_dir / f"{args.edf.stem}_raw.png"
        with mne.viz.use_browser_backend("matplotlib"):
            figure = raw.plot(
                duration=10, n_channels=16, scalings="auto", show=False, verbose=False
            )
        figure.savefig(plot_path, dpi=150)
        print(f"Raw EEG plot: {plot_path.relative_to(PROJECT_ROOT).as_posix()}")

        epochs, X, y = prepare_data(raw)
        print("Epochs summary:")
        print(epochs)
        print(f"X.shape: {X.shape}")
        print(f"y.shape: {y.shape}")
        labels, counts = np.unique(y, return_counts=True)
        class_counts = {int(label): int(count) for label, count in zip(labels, counts)}
        print(f"Class counts: {class_counts}")
        for name, code in EVENT_ID.items():
            print(f"{name} (label {code}): {int(np.sum(y == code))}")
        if args.no_show:
            plt.close(figure)
        else:
            plt.show(block=True)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
