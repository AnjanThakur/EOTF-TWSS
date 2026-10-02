# Held-out confidence and command rejection

Only out-of-fold probabilities from fixed baseline CSP+LDA. UNKNOWN is a rejection, not a learned REST state.

## Protocol

```json
{
  "subjects": [
    "S001",
    "S002",
    "S003",
    "S004",
    "S005",
    "S006",
    "S007",
    "S008",
    "S009",
    "S010"
  ],
  "runs": [
    "R04",
    "R08",
    "R12"
  ],
  "channels": [
    "FC3",
    "FC4",
    "C3",
    "C4",
    "CP3",
    "CP4"
  ],
  "filter": [
    8,
    30
  ],
  "epoch": [
    0.5,
    3.5
  ],
  "csp_components": 4,
  "classifier": "LDA",
  "confidence_threshold": 0.7,
  "random_seeds": [
    0
  ],
  "label_mapping": {
    "T1": 1,
    "T2": 2,
    "LEFT": 1,
    "RIGHT": 2
  },
  "experiment": "Held-out confidence and command rejection",
  "dataset": "PhysioNet EEGMMIDB 1.0.0",
  "source_root": "data/",
  "baseline": null,
  "evaluation": "Within-subject leave-one-run-out; CSP and LDA fit on two runs only",
  "f1_positive_label": "LEFT=1",
  "confusion_order": "rows actual, columns predicted; LEFT, RIGHT",
  "frozen_phase1_changed": false,
  "thresholds": [
    0.5,
    0.55,
    0.6,
    0.65,
    0.7,
    0.75,
    0.8,
    0.85,
    0.9,
    0.95
  ],
  "prediction_source": "results\\frequency_analysis\\heldout_predictions.csv"
}
```

Timestamp (UTC): 2026-10-02T12:53:57.678217+00:00

## Results

### threshold_metrics

Rows: 10. Complete table: `threshold_metrics.csv`.

| threshold | total_predictions | accepted_predictions | rejected_predictions | acceptance_rate | rejection_rate | correct_accepted | incorrect_accepted | accepted_command_accuracy | false_command_rate | conditional_false_command_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.5 | 450 | 450 | 0 | 1.0 | 0.0 | 291 | 159 | 0.6466666666666666 | 0.35333333333333333 | 0.35333333333333333 |
| 0.55 | 450 | 412 | 38 | 0.9155555555555556 | 0.08444444444444445 | 272 | 140 | 0.6601941747572816 | 0.3111111111111111 | 0.33980582524271846 |
| 0.6 | 450 | 380 | 70 | 0.8444444444444444 | 0.15555555555555556 | 259 | 121 | 0.6815789473684211 | 0.2688888888888889 | 0.31842105263157894 |
| 0.65 | 450 | 348 | 102 | 0.7733333333333333 | 0.22666666666666666 | 243 | 105 | 0.6982758620689655 | 0.23333333333333334 | 0.3017241379310345 |
| 0.7 | 450 | 319 | 131 | 0.7088888888888889 | 0.2911111111111111 | 227 | 92 | 0.7115987460815048 | 0.20444444444444446 | 0.2884012539184953 |
| 0.75 | 450 | 287 | 163 | 0.6377777777777778 | 0.3622222222222222 | 213 | 74 | 0.7421602787456446 | 0.16444444444444445 | 0.2578397212543554 |
| 0.8 | 450 | 252 | 198 | 0.56 | 0.44 | 193 | 59 | 0.7658730158730159 | 0.13111111111111112 | 0.23412698412698413 |
| 0.85 | 450 | 213 | 237 | 0.47333333333333333 | 0.5266666666666666 | 173 | 40 | 0.812206572769953 | 0.08888888888888889 | 0.18779342723004694 |
| 0.9 | 450 | 187 | 263 | 0.41555555555555557 | 0.5844444444444444 | 156 | 31 | 0.8342245989304813 | 0.06888888888888889 | 0.1657754010695187 |
| 0.95 | 450 | 146 | 304 | 0.3244444444444444 | 0.6755555555555556 | 127 | 19 | 0.8698630136986302 | 0.042222222222222223 | 0.13013698630136986 |

### heldout_predictions

Rows: 450. Complete table: `heldout_predictions.csv`.

## Details

```json
{
  "false_command_rate_denominator": "all held-out attempts",
  "conditional_false_command_rate_denominator": "accepted attempts",
  "probability_calibration": "LDA predict_proba; not independently calibrated",
  "selection_warning": "No threshold is optimized or deployed here. Choosing on these predictions needs independent confirmation."
}
```

## Software versions

```json
{
  "python": "3.14.7",
  "mne": "1.13.2",
  "numpy": "2.5.3",
  "scipy": "1.18.1",
  "matplotlib": "3.11.2",
  "scikit-learn": "1.9.1",
  "pandas": "3.0.6",
  "joblib": "1.6.0",
  "pyttsx3": "2.99",
  "streamlit": "1.64.0",
  "pylsl": "1.18.2",
  "PyYAML": "6.0.3",
  "pyriemann": "0.12"
}
```
