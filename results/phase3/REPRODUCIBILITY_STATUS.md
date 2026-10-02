# Phase-3 reproducibility status

Reproduced successfully with current code on 2026-10-02.

Unsigned S3 sync completed with exit code 0. Source: `s3://openneuro.org/ds003775`. Root: `data/srm/ds003775/`.
Downloaded 634 objects, 4815901107 bytes; 153 EDF headers inspected across 111 subject directories. Valid headers: 152 across 110 subjects.
Header validation: EEG channel counts [64]; sampling rates [1024.0] Hz. Failed headers: [{'file': 'D:\\EOTF-TWSS\\data\\srm\\ds003775\\sub-041\\ses-t1\\eeg\\sub-041_ses-t1_task-resteyesc_eeg.edf', 'error': 'second must be in 0..59, not 60'}].
Header readability is not a signal-quality assessment. Finite samples were validated for the processed subset, not every downloaded recording.

SRM processed subset: 5 subjects, 8 recordings, 960 nonoverlapping 2-second windows, 64 channels, 1024.0 Hz, 3168 features/window.
PhysioNet: 45 S001 imagery trials, 6 channels, 160.0 Hz, 123 features/trial.
No failed/excluded files in the selected subset. Additional downloaded subjects were intentionally outside the existing five-subject analysis limit; no short recording was silently discarded by a file-size threshold.

Both datasets were regenerated in `results/phase3_reproduction/`, verified for finite CSV values, matching per-dataset metadata lengths, and eight plots, then copied here. Previous artifacts are preserved under `results/phase3_historical/`.
Per-dataset metadata: `srm/feature_metadata.json` and `physionet/feature_metadata.json`. The root legacy metadata file describes SRM only; use the per-dataset files for comparisons.
PCA uses standardized features under current code. EEG rates, channel counts, tasks and window definitions differ, so PCA/feature plots do not establish dataset equivalence or transfer performance.

Inventory: `download_inventory.json`, `edf_inventory.csv`. Processing summary: `dataset_summary.json`. Environment and code fingerprint: `reproduction_provenance.json`. The real SRM loader test now executes rather than skips.
