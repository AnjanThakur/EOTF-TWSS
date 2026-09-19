"""Run: python -m src.realtime.demo --no-audio."""

import argparse
from collections.abc import Iterable
from itertools import islice
import math
from pathlib import Path
import sys

from src.models.train_csp_lda import PROJECT_ROOT
import joblib
from src.realtime.dataset_stream import dataset_stream
from src.realtime.inference import LABEL_NAMES, predict_trial
from src.realtime.trial import Trial
from src.twss.mapper import to_word
from src.twss.sentence import to_sentence
from src.twss.speech import Speaker


def run_demo(trials: Iterable[Trial], model, speaker: Speaker, threshold: float) -> None:
    """Any source yielding Trial objects can replace dataset_stream."""
    for index, trial in enumerate(trials, start=1):
        result = predict_trial(model, trial, threshold)
        word = to_word(result.decision)
        sentence = to_sentence(word)
        confidence = "unavailable" if result.confidence is None else f"{result.confidence:.2%}"
        print(f"\nTrial {index} ({trial.source})")
        print(f"Actual: {LABEL_NAMES.get(result.actual_label, 'UNKNOWN')}")
        print(f"Predicted: {result.predicted_label}")
        print(f"Confidence: {confidence}")
        print(f"Decision: {result.decision}")
        print(f"Word: {word if word else 'UNKNOWN'}")
        print(f"Sentence: {sentence if sentence else '(none)'}")
        if sentence is not None:
            speaker.speak(sentence)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    parser.add_argument("--model-path", type=Path, default=PROJECT_ROOT / "models/csp_lda_s001.joblib")
    parser.add_argument("--threshold", type=float, default=0.7)
    parser.add_argument("--limit", type=int, default=6, help="Number of trials (default: 6; full dataset: 45).")
    parser.add_argument("--interval", type=float, default=0, help="Seconds to wait per trial; use 3 for paced replay.")
    parser.add_argument("--no-audio", action="store_true")
    args = parser.parse_args()
    speaker = Speaker(enabled=not args.no_audio)
    try:
        if not math.isfinite(args.threshold) or not 0 <= args.threshold <= 1:
            raise ValueError("Confidence threshold must be between 0 and 1.")
        if args.limit < 1:
            raise ValueError("Trial limit must be positive.")
        if not math.isfinite(args.interval) or args.interval < 0:
            raise ValueError("Replay interval must be finite and nonnegative.")
        if not args.model_path.is_file():
            raise FileNotFoundError(f"Model file not found: {args.model_path.as_posix()}")
        model = joblib.load(args.model_path)
        print("DEMO ONLY: S001 R04/R08/R12 were used to train this final model.")
        print("These predictions are not an accuracy evaluation; see models/training_report.txt for leave-one-run-out results.")
        print(f"Confidence threshold: {args.threshold:.2%}; audio: {'disabled' if args.no_audio else 'enabled'}")
        print("Confidence is model probability, not validated command reliability.")
        trials = islice(dataset_stream(args.data_dir, args.interval), args.limit)
        run_demo(trials, model, speaker, args.threshold)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        speaker.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
