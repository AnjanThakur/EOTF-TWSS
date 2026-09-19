"""Leakage-free held-out-run replay using a model fit on the other two runs."""
import mne
import numpy as np
from src.models.train_csp_lda import load_subject, build_pipeline
from src.realtime.trial import Trial
from src.realtime.inference import predict_trial, LABEL_NAMES
from src.twss.mapper import to_word
from src.twss.sentence import to_sentence


def heldout_trials(data_dir, subject="S001", held_out="R04", runs=("R04", "R08", "R12"), threshold=0.70):
    X, y, groups = load_subject(data_dir, subject, runs)
    test = groups == held_out; train = ~test
    if not test.any() or np.any(np.isin(groups[train], groups[test])): raise ValueError("Invalid held-out run split.")
    model = build_pipeline()
    with mne.use_log_level("WARNING"): model.fit(X[train], y[train])
    for i in np.flatnonzero(test):
        trial = Trial(X[i], int(y[i]), f"{subject} {held_out} trial {i + 1}")
        result = predict_trial(model, trial, threshold)
        word = to_word(result.decision); sentence = to_sentence(word)
        yield {"actual": LABEL_NAMES[result.actual_label], "prediction": result.predicted_label,
               "confidence": result.confidence, "word": word, "sentence": sentence,
               "held_out": held_out, "train_runs": tuple(r for r in runs if r != held_out)}


if __name__ == "__main__":
    for row in heldout_trials("data", "S001", "R04"):
        print(f"Actual: {row['actual']} | Predicted: {row['prediction']} | Confidence: {row['confidence']:.2%} | Word: {row['word'] or 'UNKNOWN'} | Sentence: {row['sentence'] or '(none)'}")
