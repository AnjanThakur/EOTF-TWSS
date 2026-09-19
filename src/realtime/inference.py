"""Single-trial prediction independent of the acquisition source."""

import numpy as np
from src.realtime.trial import Prediction, Trial

LABEL_NAMES = {1: "LEFT", 2: "RIGHT"}


def predict_trial(model, trial: Trial, threshold: float = 0.7) -> Prediction:
    if not np.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Confidence threshold must be between 0 and 1.")
    data = np.asarray(trial.data, dtype=float)
    if data.shape != (6, 481) or not np.isfinite(data).all():
        raise ValueError("Expected finite EEG data with shape (6, 481).")
    X = data[np.newaxis, ...]
    predicted_class = int(model.predict(X)[0])
    if predicted_class not in LABEL_NAMES:
        raise ValueError(f"Unsupported model class: {predicted_class}.")
    confidence = None
    if callable(getattr(model, "predict_proba", None)):
        probabilities = np.asarray(model.predict_proba(X), dtype=float)
        classes = np.asarray(model.classes_)
        indices = np.flatnonzero(classes == predicted_class)
        if (probabilities.shape != (1, len(classes)) or len(indices) != 1
                or not np.isfinite(probabilities).all()
                or np.any(probabilities < 0) or np.any(probabilities > 1)
                or not np.isclose(probabilities.sum(), 1.0)):
            raise ValueError("Model returned invalid class probabilities.")
        confidence = float(probabilities[0, indices[0]])
    name = LABEL_NAMES[predicted_class]
    # Without a probability, confidence cannot satisfy the gate.
    decision = name if confidence is not None and confidence >= threshold else "UNKNOWN"
    return Prediction(predicted_class, name, confidence, trial.actual_label, decision)
