# Held-out demo smoke run

Three two-run models, each replaying only its fifteen held-out trials. No saved-model fitting or audio.

## Protocol

```json
{
  "subjects": [
    "S001"
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
  "experiment": "Held-out demo smoke run",
  "dataset": "PhysioNet EEGMMIDB 1.0.0",
  "source_root": "data/",
  "baseline": null,
  "evaluation": "Within-subject leave-one-run-out; CSP and LDA fit on two runs only",
  "f1_positive_label": "LEFT=1",
  "confusion_order": "rows actual, columns predicted; LEFT, RIGHT",
  "frozen_phase1_changed": false
}
```

Timestamp (UTC): 2026-10-02T13:17:07.829927+00:00

## Results

### trials

Rows: 45. Complete table: `trials.csv`.

| actual | prediction | decision | confidence | word | sentence | held_out | train_runs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RIGHT | RIGHT | RIGHT | 0.9798218323364917 | NO | No. | R04 | ('R08', 'R12') |
| LEFT | LEFT | UNKNOWN | 0.5407007915265261 | Not defined | Not defined | R04 | ('R08', 'R12') |
| LEFT | LEFT | UNKNOWN | 0.6698614065147424 | Not defined | Not defined | R04 | ('R08', 'R12') |
| RIGHT | RIGHT | RIGHT | 0.9529278949216909 | NO | No. | R04 | ('R08', 'R12') |
| RIGHT | RIGHT | RIGHT | 0.724206936101348 | NO | No. | R04 | ('R08', 'R12') |
| LEFT | LEFT | UNKNOWN | 0.5298153742632987 | Not defined | Not defined | R04 | ('R08', 'R12') |
| RIGHT | RIGHT | RIGHT | 0.7357985921959301 | NO | No. | R04 | ('R08', 'R12') |
| LEFT | RIGHT | UNKNOWN | 0.6116941392086945 | Not defined | Not defined | R04 | ('R08', 'R12') |
| RIGHT | RIGHT | UNKNOWN | 0.685039448332031 | Not defined | Not defined | R04 | ('R08', 'R12') |
| LEFT | RIGHT | RIGHT | 0.7026873343508743 | NO | No. | R04 | ('R08', 'R12') |
| LEFT | LEFT | LEFT | 0.7983297933477812 | YES | Yes. | R04 | ('R08', 'R12') |
| RIGHT | RIGHT | RIGHT | 0.9485013552883231 | NO | No. | R04 | ('R08', 'R12') |
| LEFT | RIGHT | UNKNOWN | 0.552421679890187 | Not defined | Not defined | R04 | ('R08', 'R12') |
| RIGHT | RIGHT | RIGHT | 0.9947002250879953 | NO | No. | R04 | ('R08', 'R12') |
| LEFT | RIGHT | UNKNOWN | 0.6391582274642422 | Not defined | Not defined | R04 | ('R08', 'R12') |
| LEFT | RIGHT | RIGHT | 0.8933545884660538 | NO | No. | R08 | ('R04', 'R12') |
| RIGHT | RIGHT | RIGHT | 0.9215882384660949 | NO | No. | R08 | ('R04', 'R12') |
| LEFT | RIGHT | RIGHT | 0.8467351372588496 | NO | No. | R08 | ('R04', 'R12') |
| RIGHT | LEFT | UNKNOWN | 0.6095390430193846 | Not defined | Not defined | R08 | ('R04', 'R12') |
| LEFT | LEFT | LEFT | 0.8711249013493 | YES | Yes. | R08 | ('R04', 'R12') |
| RIGHT | RIGHT | RIGHT | 0.7006108397615228 | NO | No. | R08 | ('R04', 'R12') |
| LEFT | LEFT | LEFT | 0.7301275528673785 | YES | Yes. | R08 | ('R04', 'R12') |
| RIGHT | RIGHT | RIGHT | 0.8586317041812516 | NO | No. | R08 | ('R04', 'R12') |
| RIGHT | RIGHT | RIGHT | 0.7143671355763396 | NO | No. | R08 | ('R04', 'R12') |
| LEFT | RIGHT | UNKNOWN | 0.5348201286720958 | Not defined | Not defined | R08 | ('R04', 'R12') |
| LEFT | RIGHT | RIGHT | 0.7965661457171154 | NO | No. | R08 | ('R04', 'R12') |
| RIGHT | RIGHT | RIGHT | 0.8892115763094199 | NO | No. | R08 | ('R04', 'R12') |
| RIGHT | RIGHT | RIGHT | 0.8393767833566236 | NO | No. | R08 | ('R04', 'R12') |
| LEFT | LEFT | UNKNOWN | 0.573052131971693 | Not defined | Not defined | R08 | ('R04', 'R12') |
| LEFT | RIGHT | UNKNOWN | 0.5692575906831892 | Not defined | Not defined | R08 | ('R04', 'R12') |
| RIGHT | LEFT | UNKNOWN | 0.5037690347094002 | Not defined | Not defined | R12 | ('R04', 'R08') |
| LEFT | LEFT | LEFT | 0.9685080988916098 | YES | Yes. | R12 | ('R04', 'R08') |
| RIGHT | LEFT | LEFT | 0.9713746747703768 | YES | Yes. | R12 | ('R04', 'R08') |
| LEFT | LEFT | LEFT | 0.951280521940606 | YES | Yes. | R12 | ('R04', 'R08') |
| LEFT | LEFT | UNKNOWN | 0.580010947356058 | Not defined | Not defined | R12 | ('R04', 'R08') |
| RIGHT | RIGHT | RIGHT | 0.9998734894837042 | NO | No. | R12 | ('R04', 'R08') |
| RIGHT | RIGHT | RIGHT | 0.8221260773428969 | NO | No. | R12 | ('R04', 'R08') |
| LEFT | LEFT | LEFT | 0.9679270867949135 | YES | Yes. | R12 | ('R04', 'R08') |
| LEFT | LEFT | LEFT | 0.9999982154318401 | YES | Yes. | R12 | ('R04', 'R08') |
| RIGHT | RIGHT | RIGHT | 0.999584635231364 | NO | No. | R12 | ('R04', 'R08') |
| RIGHT | LEFT | LEFT | 0.9651715286193354 | YES | Yes. | R12 | ('R04', 'R08') |
| LEFT | LEFT | LEFT | 0.9999469899519476 | YES | Yes. | R12 | ('R04', 'R08') |
| RIGHT | RIGHT | RIGHT | 0.9987647512946682 | NO | No. | R12 | ('R04', 'R08') |
| LEFT | LEFT | LEFT | 0.9224051019152691 | YES | Yes. | R12 | ('R04', 'R08') |
| RIGHT | LEFT | LEFT | 0.843049617126912 | YES | Yes. | R12 | ('R04', 'R08') |

## Details

```json
{}
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
