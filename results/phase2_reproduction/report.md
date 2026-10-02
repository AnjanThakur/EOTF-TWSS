# Phase-2 deterministic reproduction

Historical Phase-2 outputs retained. FBCSP mutual-information selection and plotting jitter use seed zero.

## Protocol

```json
{
  "experiment": "Phase-2 deterministic reproduction",
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
  "sub_bands": [
    [
      8,
      12
    ],
    [
      12,
      16
    ],
    [
      16,
      20
    ],
    [
      20,
      24
    ],
    [
      24,
      30
    ]
  ],
  "csp_components_per_band": 2,
  "n_features_to_select": 6,
  "epoch": [
    0.5,
    3.5
  ],
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
  "models": [
    {
      "id": "baseline_csp_lda",
      "name": "CSP + LDA (Phase 1 Baseline)"
    },
    {
      "id": "fbcsp_lda",
      "name": "Filter Bank CSP (FBCSP) + LDA"
    },
    {
      "id": "riemannian_mdm",
      "name": "Riemannian MDM"
    },
    {
      "id": "riemannian_tangent_space_lda",
      "name": "Riemannian Tangent Space + LDA"
    }
  ],
  "dataset": "PhysioNet EEGMMIDB 1.0.0",
  "evaluation": "Within-subject leave-one-run-out",
  "historical_source": "results/phase2/results.json",
  "plot_seed": 0,
  "baseline": null,
  "f1_positive_label": "LEFT=1"
}
```

Timestamp (UTC): 2026-10-02T12:54:10.086669+00:00

## Results

### comparison

Rows: 16. Complete table: `comparison.csv`.

| model | metric | historical_mean | current_mean | difference | current_fold_std | matches_at_1e_12 |
| --- | --- | --- | --- | --- | --- | --- |
| baseline_csp_lda | accuracy | 0.6466666666666668 | 0.6466666666666668 | 0.0 | 0.18705214713316293 | True |
| baseline_csp_lda | balanced_accuracy | 0.6491071428571428 | 0.6491071428571428 | 0.0 | 0.18702511408090083 | True |
| baseline_csp_lda | f1 | 0.637880383639234 | 0.637880383639234 | 0.0 | 0.23520714449227348 | True |
| baseline_csp_lda | mcc | 0.31816618110625966 | 0.31816618110625966 | 0.0 | 0.38594012700931385 | True |
| fbcsp_lda | accuracy | 0.6800000000000003 | 0.6800000000000003 | 0.0 | 0.139402116883392 | True |
| fbcsp_lda | balanced_accuracy | 0.6803571428571428 | 0.6803571428571428 | 0.0 | 0.13842811008173975 | True |
| fbcsp_lda | f1 | 0.6421099263130493 | 0.6421099263130493 | 0.0 | 0.22687557374100845 | True |
| fbcsp_lda | mcc | 0.40453513462658974 | 0.40453513462658974 | 0.0 | 0.2713392944261044 | True |
| riemannian_mdm | accuracy | 0.6622222222222225 | 0.6622222222222225 | 0.0 | 0.1622951602154981 | True |
| riemannian_mdm | balanced_accuracy | 0.6642857142857143 | 0.6642857142857143 | 0.0 | 0.15912597747239351 | True |
| riemannian_mdm | f1 | 0.6525189061024974 | 0.6525189061024974 | 0.0 | 0.21580330599316025 | True |
| riemannian_mdm | mcc | 0.36567711789801977 | 0.36567711789801977 | 0.0 | 0.3246663108432913 | True |
| riemannian_tangent_space_lda | accuracy | 0.5911111111111111 | 0.5911111111111111 | 0.0 | 0.16398610662890084 | True |
| riemannian_tangent_space_lda | balanced_accuracy | 0.5898809523809523 | 0.5898809523809523 | 0.0 | 0.16662524409013657 | True |
| riemannian_tangent_space_lda | f1 | 0.5813238516492657 | 0.5813238516492657 | 0.0 | 0.2317297801524652 | True |
| riemannian_tangent_space_lda | mcc | 0.18470927390796102 | 0.18470927390796102 | 0.0 | 0.35428846532082553 | True |

### current_folds

Rows: 120. Complete table: `current_folds.csv`.

## Details

```json
{
  "skipped": []
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
