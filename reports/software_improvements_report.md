# TWSS software improvements report

Work date: 2026-10-02. Repository: `D:/EOTF-TWSS`. This report covers the fourteen software tasks in the supplied request. It separates newly completed work from the prior MVP, existing local review fixes, exploratory evidence and unverified hardware/user outcomes.

## 1. Work completed

All requested software stages were implemented and executed: Streamlit navigation and separate held-out replay; frozen-score analysis; predefined six-channel and fixed-band experiments; CSP interpretation; held-out confidence/rejection; common CSV/JSON/Markdown reporting; technical and literature documents; complete unsigned SRM download and current-code Phase-3 reproduction; deterministic Phase-2 comparison; final test/dependency/freeze/leakage/staging checks.

The deployed model, frozen config, preprocessing file and Phase-1 results were not replaced. No CNN/LSTM/deep-learning implementation, REST classifier or hardware-dependent functionality was added. New experimental leaders were not deployed. The standard dashboard still uses the saved S001 pipeline; the held-out page trains a separate in-memory pipeline on exactly two runs.

## 2. Files added/changed

| Purpose | New files | Changed existing files in this task |
|---|---|---|
| Shared research evaluation | `src/models/research_evaluation.py` | `src/models/train_csp_lda.py` optional six-channel selector; `src/models/fbcsp.py` optional channels with unchanged defaults |
| Reporting/provenance | `src/reporting/__init__.py`, `src/reporting/experiments.py` | None in frozen reports |
| Experiments | `scripts/run_research_experiments.py` | `scripts/generate_phase2_plots.py`: seeded jitter, configurable destinations, Agg backend |
| Held-out UI | None | `src/realtime/heldout_demo.py`, `ui/app.py` |
| SRM reproduction | `scripts/reproduce_phase3.py` | `scripts/run_phase3_analysis.py`: configurable output/data root; `.gitignore`: temporary download root |
| Final checks | `scripts/validate_software_improvements.py`, `tests/test_research.py` | `tests/test_ui.py`: navigation and held-out replay checks |
| Documentation | `docs/TWSS_TECHNICAL_OVERVIEW.md`, `docs/LITERATURE_REVIEW.md`, this report | `README.md` updated commands/status |
| Artifacts | New analysis/experiment/reproduction/validation folders listed below | Current Phase-3 outputs promoted only after successful reproduction; originals preserved |

The workspace already contained uncommitted corrections from the previous review, including acquisition, feature and dataset modules, and a model restored to the original freeze version. Those changes were preserved; they are not new hardware work in this task. Git also already had twelve temporary-file removals staged. No commit or push was performed in this task. Requirements were already pinned to the installed versions and needed no upgrade or replacement.

## 3. Experiments performed

All classification experiments use S001–S010, R04/R08/R12, six channels, 0.5–3.5-second imagery epochs, `baseline=None`, CSP four components, LDA and within-subject leave-one-run-out evaluation. Each fold trains on thirty trials and tests fifteen. All ten subjects were available; no subject was skipped.

Channel comparison: six predefined montages × ten subjects × three runs = 180 fitted folds and 2700 out-of-fold trial predictions. Band comparison: four bands × ten subjects × three runs = 120 folds and 1800 out-of-fold predictions. Confidence uses the 450 out-of-fold predictions of the band experiment's unchanged 8–30 Hz baseline only. Phase 2 reproduced four models × ten subjects × three folds = 120 folds.

The two single-band baseline loaders return exactly equal arrays/labels/run groups in the real-data S001 regression test. New baseline fold scores match all stored Phase-1 fold values within 1e-14. Classification scores are ungated LEFT/RIGHT metrics; communication rejection is analyzed separately. No random trial split or CSP fitting on test epochs is used.

Each experiment exports source/protocol/configuration, subjects, runs, channels or exact candidates, filtering, epochs, estimator settings, LEFT-positive F1, confusion order, seed, threshold where relevant, UTC timestamp and installed software versions. `src/reporting/experiments.py` writes CSV/JSON/Markdown and prevents experiments targeting frozen Phase 1 or historical Phase 2.

## 4. Channel-selection results

Small candidate set rationale: bilateral C3/C4 and neighboring frontal/posterior sensorimotor pairs; central-wide and central-midline variants. Candidates were predefined rather than exhaustively selected from 64 channels. Ranking averages all ten subject means. No candidate was selected using S001 alone.

| Montage | Exact ordered channels | Accuracy mean | Fold SD | Balanced accuracy | LEFT F1 | MCC |
|---|---|---:|---:|---:|---:|---:|
| posterior_nearby | CP1, CP2, CP3, CP4, C3, C4 | 68.22% | 14.93 pp | 0.679762 | 0.686802 | 0.391651 |
| anterior_midline | FC3, FC4, C3, C4, Cz, FCz | 67.56% | 16.12 pp | 0.677381 | 0.688497 | 0.379993 |
| frozen baseline | FC3, FC4, C3, C4, CP3, CP4 | 64.67% | 18.71 pp | 0.649107 | 0.637880 | 0.318166 |
| posterior_midline | CP3, CP4, C3, C4, Cz, CPz | 63.11% | 19.86 pp | 0.626786 | 0.609876 | 0.266913 |
| frontal_nearby | FC1, FC2, FC3, FC4, C3, C4 | 61.78% | 16.69 pp | 0.623214 | 0.588810 | 0.267762 |
| central_wide | C1, C2, C3, C4, C5, C6 | 60.89% | 17.75 pp | 0.612202 | 0.593083 | 0.230035 |

The exploratory leader improves mean accuracy by 3.56 percentage points over the frozen baseline on these folds. Its subject-mean SD is 12.96 pp; fold SD is 14.93 pp. This is not independent confirmation or a statistical superiority claim. All metrics/SDs, summed subject confusion counts, fold scores and trial predictions are exported in `results/channel_selection/`.

## 5. Frequency-band results

The fixed comparison reuses the FBCSP loader with one band and the ordinary existing CSP+LDA classifier. The frozen six channels remain fixed throughout; the montage leader was not combined with the band leader.

| Band | Accuracy mean | Fold SD | Balanced accuracy | LEFT F1 | MCC |
|---|---:|---:|---:|---:|---:|
| 12–30 Hz | 69.33% | 17.65 pp | 0.691667 | 0.684523 | 0.423127 |
| 8–12 Hz | 67.33% | 20.89 pp | 0.675595 | 0.662528 | 0.357614 |
| 8–20 Hz | 66.22% | 20.41 pp | 0.667262 | 0.643517 | 0.343451 |
| frozen 8–30 Hz baseline | 64.67% | 18.71 pp | 0.649107 | 0.637880 | 0.318166 |

12–30 Hz leads this exploratory fixed set by 4.67 pp over baseline. Its subject-mean SD is 15.06 pp. Per-subject/fold scores, exact configurations and predictions are in `results/frequency_analysis/`. Phase-1 and Phase-2 settings/results remain unchanged.

## 6. CSP interpretation findings

S001, high-performing S007 and low-performing S008 were selected from frozen scores. For each, CSP was fit on R08+R12 and R04 supplied the fifteen held-out feature vectors. Three figure types per subject show sensor patterns, projection filters and class feature distributions; numerical weights/features are also exported.

Filters are projection weights; patterns describe component contributions in sensor space; classifier features are four log mean-square powers. These are distinct objects. Pattern signs are arbitrary; colors do not denote classes. Sparse six-sensor interpolation is illustrative, not source localization. A shared symmetric range within each subject's pattern figure aids component comparison.

Mean held-out first-feature values (LEFT/RIGHT): S001 −0.6980/−1.0131; S007 −1.4878/−0.9258; S008 −1.0763/−1.0677. S008's means nearly coincide in that component, whereas S007 has a larger contrast. Means do not summarize overlap or validate an anatomical explanation. The report explicitly avoids tuning components or asserting that residual artifacts cannot drive discrimination. See `results/csp_analysis/csp_analysis.md`.

## 7. Confidence/rejection findings

Only held-out baseline predictions were used; every trial exports train/test run provenance. UNKNOWN means rejection rather than a learned REST label. Raw classifier predictions remain accessible, while the gated decision controls command mapping and speech.

| Threshold | Accepted / 450 | Rejected | Correct accepted | Incorrect accepted | Coverage | Accepted accuracy | Incorrect accepted / all attempts |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0.50 | 450 | 0 | 291 | 159 | 100.00% | 64.67% | 35.33% |
| 0.70, unchanged default | 319 | 131 | 227 | 92 | 70.89% | 71.16% | 20.44% |
| 0.80 | 252 | 198 | 193 | 59 | 56.00% | 76.59% | 13.11% |
| 0.90 | 187 | 263 | 156 | 31 | 41.56% | 83.42% | 6.89% |
| 0.95 | 146 | 304 | 127 | 19 | 32.44% | 86.99% | 4.22% |

All ten thresholds 0.50–0.95 at 0.05 increments are in `threshold_metrics.csv`. Rejection rate equals one minus coverage. Conditional false-command rate uses accepted attempts as denominator; at 0.70 it is 28.84%, and at 0.95 it is 13.01%. Increasing threshold reduced wrong accepted commands here at the cost of more rejected attempts; monotonic accepted accuracy is not guaranteed generally. No threshold is chosen as optimal, and LDA probabilities are not independently calibrated. A future cost model and untouched confirmation data are needed. No standard-demo training-data accuracy enters this analysis.

## 8. Phase-2 comparison

| Model | Historical mean accuracy | Current mean accuracy | Current fold SD |
|---|---:|---:|---:|
| CSP+LDA | 64.67% | 64.67% | 18.71 pp |
| FBCSP+LDA | 68.00% | 68.00% | 13.94 pp |
| Riemannian MDM | 66.22% | 66.22% | 16.23 pp |
| Tangent-space LDA | 59.11% | 59.11% | 16.40 pp |

All sixteen aggregate means for accuracy, balanced accuracy, F1 and MCC match historical values within 1e-12; in this run their recorded differences are exactly zero. No missing subjects/models. The existing seeded mutual-information selection is retained; plot jitter now uses `np.random.default_rng(0)`. Tests generate plots twice and require identical PNG hashes. Agg avoids a Tk/Streamlit cross-thread cleanup error.

Clean CSV/JSON/Markdown and four plots are in `results/phase2_reproduction/`. Historical `results/phase2/` files were not rewritten by this task. FBCSP has the highest reproduced mean of these four methods; that comparison is exploratory and does not replace the saved MVP model.

## 9. SRM download/status

AWS CLI v2.36.49 was available. Before downloading, approximately 182.38 GB was free. The initial sandboxed AWS call failed with `Failed to connect to proxy URL: "http://127.0.0.1:9"`. Approved unsigned public access succeeded; no AWS credentials were supplied or stored.

Executed:

```powershell
aws s3 sync --no-sign-request s3://openneuro.org/ds003775 ds003775-download/ --no-progress
```

Exit code: 0. Downloaded 634 objects, exactly 4,815,901,107 bytes (4.82 decimal GB). The completed temporary folder was moved using native PowerShell after checking that both resolved paths stayed inside the workspace, and refusing an existing destination. Correct loader root: `D:/EOTF-TWSS/data/srm/ds003775/`. Both permanent and temporary raw-data paths are ignored by Git.

All 153 EDF headers in 111 subject directories were inspected. There are 152 readable EDFs covering 110 subjects; readable EEG metadata is uniformly 64 channels and 1024 Hz. One file errors in the source date field:

```text
data/srm/ds003775/sub-041/ses-t1/eeg/sub-041_ses-t1_task-resteyesc_eeg.edf
ValueError: second must be in 0..59, not 60
```

The source EDF was not edited or fabricated. Header-readable files imply 18,240 possible nonoverlapping two-second windows, but only the defined five-subject subset had samples/features processed. Header validation across the full download is not full EEG signal-quality assessment. The real SRM loader test passes without skip.

## 10. Phase-3 reproducibility status

Current code was run in `results/phase3_reproduction/`. Both datasets completed, exported finite feature CSVs, produced per-dataset metadata of matching feature length and generated all eight figures before replacing stale current outputs. Historical outputs are retained under `results/phase3_historical/`.

| Dataset processed | Subjects | Recordings/trials | Windows | Channels | Sampling rate | Samples/window | Features/window |
|---|---:|---:|---:|---:|---:|---:|---:|
| SRM defined subset | 5 | 8 recordings | 960 | 64 | 1024 Hz | 2048 | 3168 |
| PhysioNet S001 | 1 | 45 trials | 45 | 6 | 160 Hz | 481 | 123 |

SRM selected subjects are the first five sorted subject IDs (001–005). No selected files failed or were excluded. The sub-041 header problem is outside this subset. Other downloaded subjects remain intentionally unprocessed by the existing five-subject analysis limit. Current features comprise temporal, spectral and spatial descriptors; PCA is standardized before projection. These plots are representation exploration, not classification or demonstrated transfer learning.

`results/phase3/REPRODUCIBILITY_STATUS.md` records the full inventory, processing limits and differences. Use `srm/feature_metadata.json` and `physionet/feature_metadata.json`; the legacy root metadata describes SRM alone. Provenance stores processing parameters, timestamp, versions and a code fingerprint. Regeneration can be rerun while preserving the original historical archive.

## 11. Tests

Final full suite: **73 tests in 22.494s; 73 passed, 0 failures, 0 errors, 0 skipped.** Exit code 0; unittest reports `OK`. The real SRM test executed. `pip check` exited 0 with exact output `No broken requirements found.`

Targeted stages passed after fixes: 33 shared evaluation/Phase-1/Phase-2/review tests; 13 UI/research/SRM tests after download; 32 research/features/SRM/UI tests after headless plotting. Final commands are `python -m unittest discover -v` and `python -m pip check` through the project virtual environment. Exact unmodified subprocess stdout/stderr and exit-code metadata are saved under `results/software_improvements/`.

Intermediate issues were found and corrected, rather than omitted from the record:

| Issue encountered | Correction / outcome |
|---|---|
| Invalid held-out settings reached a missing-file lookup before validation | Validate configured runs/held-out choice before loading; 33 targeted tests pass |
| Windows shell text pipeline substituted an em dash with `?`, breaking the exact dashboard warning assertion | UTF-8 source patched directly; exact disclaimer and other UI text restored |
| Inventory JSON attempted to serialize NumPy int64 | Inventory explicitly uses native integer/float values; complete inspection/reproduction succeeds |
| Tk plot cleanup triggered `RuntimeError: main thread is not in main loop`, followed by `AppTest script run timed out after 30(s)` | Phase-2 plotting uses Agg; 32 targeted tests pass |
| Changing held-out `prediction` to UNKNOWN broke the existing raw-prediction contract | Preserve raw `prediction`, add gated `decision`; CLI displays gated value; explicit rejection test added |
| Browser visual inspection | Browser tool returned `No browser is available`; graphical screenshot review of the UI remains unverified. AppTest navigation and HTTP health are verified |

Nonfatal final logs include liblsl informational messages and Streamlit `missing ScriptRunContext` warnings from AppTest. The CSP figure script also emitted MNE's `FutureWarning: Montage name 'standard_1020' is deprecated and will be removed in MNE 1.14. Use 'colin27_1020' instead.` It completed successfully on pinned MNE 1.13.2; this concerns figure montage naming, not frozen preprocessing or model behavior. Actual speech is mocked/silent in automated tests; no hardware data was faked. A local headless Streamlit process on port 8503 returned HTTP health body `ok`; the documented normal launch target remains unchanged.

The CLI held-out demo exited 0, and smoke replay across all three held-out choices returned 45 labeled trials. Exact R04 CLI output is in `results/software_improvements/heldout_demo.stdout.log`; all three runs, raw predictions, gated decisions, probabilities, words/sentences and training-run identifiers are in `results/software_improvements/heldout_demo/trials.csv`. For example, an actual LEFT trial at 54.07% confidence prints UNKNOWN and no sentence at the unchanged 0.70 threshold.

## 12. Phase-1 freeze verification

All six before/after frozen artifact hashes unchanged: **True**. Saved model SHA256: `3ddbf91d3abfc281248545d4db191eb2139cee28dd35aa25e56fdfb18f6d043b`.

| Frozen artifact | Before/after SHA256 | Unchanged |
|---|---|---|
| `models/csp_lda_s001.joblib` | `3ddbf91d3abfc281248545d4db191eb2139cee28dd35aa25e56fdfb18f6d043b` | True |
| `configs/phase1_config.yaml` | `bd7972dfcf3cfdb7d581c41c88a20a3c4d7f4a10d3416867fcf5975e33febc1f` | True |
| `src/preprocessing/preprocess.py` | `c61452ed30d06d99e6438e0c7d0492d53a19dfd8d80e771eeac0d3f07807b439` | True |
| `results/phase1/results.json` | `147c0311aeb0edd9d99727deca9a302b6311fd59eb95d106ca3148255a937167` | True |
| `results/phase1/fold_metrics.csv` | `2fa2969e38172282664673ce2018cb2cf36a2a0a44f1c60173080992e1a43d8a` | True |
| `results/phase1/summary.md` | `b1224f66bfd59b33c966ba42d028e55731d77984a0b6202428047f2d4fcc2c16` | True |

Train/test overlap errors: []. Staged new/modified files: []. Staged files above 10 MB: []. Sensitive staged filenames: []. SRM ignored by Git: True.

The before/after SHA256 comparison covers the saved model, YAML config, preprocessing Python file and three frozen result files. A second comparison checks against original freeze commit `7a19eddf045cd7ffc4deb6c8416a922f3d3bf805`; result text may differ only in checkout CRLF/LF bytes, while normalization must equal the original. Model/config/preprocessing are compared directly as well. Existing local model restoration happened in the previous review; this task never retrained or rewrote that artifact.

Shared selector/experiment helpers extend optional inputs while preserving six-channel, band and epoch defaults. Standard dashboard inference/mapping/speech behavior remains covered by regression tests. Full experiment train/test run provenance was checked for overlap. No experiment report writes into Phase 1 or historical Phase 2.

## 13. Any unresolved issues

One SRM source EDF has an invalid seconds field and remains unreadable with current MNE; its exact path/error is exported. Correcting that source metadata or accepting an exclusion requires a separately documented research decision. It does not block the processed subset or real SRM loader test.

Exploratory winners and threshold trends lack independent confirmation, uncertainty analysis for superiority and user communication validation. No useful-on-hardware or patient outcome is established. The sparse CSP maps cannot establish brain sources or absence of artifacts. Auditory TTS output and browser screenshot layout review are not verified here. The Riemannian full-paper host was access-blocked during literature review, so unverified protocol details are explicitly marked instead of invented.

Repository-wide pre-existing uncommitted edits remain reviewable; this task does not commit or push them. No new raw dataset or credential file was staged/committed. The detailed staging check is limited to the current index, not a forensic credential scan of every historical commit.

## 14. Recommended next software step

Predefine an independent confirmation experiment before adopting the montage, band or confidence leaders. Use additional untouched subjects or later sessions, preserve the selected protocol in a new config, and state the cost of wrong commands versus rejection. If calibrating probabilities, fit calibration only within training folds and reserve the final confirmation set for evaluation. Report coverage, accepted accuracy, false commands per attempt and per accepted command together.

Keep frozen Phase 1 as the reference. Evaluate montage and band candidates separately before proposing any combined setting. Actual kit acquisition/units/channel order, signal-quality assessment and a raw-live trial adapter belong to the next hardware-integration task; none is claimed implemented by this software work.

## Reproduce and locate the artifacts

```powershell
.venv/Scripts/python.exe -m scripts.run_research_experiments
.venv/Scripts/python.exe -m scripts.reproduce_phase3
.venv/Scripts/python.exe -m scripts.validate_software_improvements
.venv/Scripts/python.exe -m streamlit run ui/app.py
```

| Main report | Exact path |
|---|---|
| Frozen subject/run analysis | `D:/EOTF-TWSS/results/analysis/analysis_summary.md` |
| Channel comparison | `D:/EOTF-TWSS/results/channel_selection/report.md` |
| Band comparison | `D:/EOTF-TWSS/results/frequency_analysis/report.md` |
| CSP interpretation | `D:/EOTF-TWSS/results/csp_analysis/csp_analysis.md` |
| Confidence/rejection | `D:/EOTF-TWSS/results/confidence_analysis/summary.md` |
| Phase-2 reproduction | `D:/EOTF-TWSS/results/phase2_reproduction/summary.md` |
| Phase-3 reproducibility | `D:/EOTF-TWSS/results/phase3/REPRODUCIBILITY_STATUS.md` |
| Technical overview, nineteen sections | `D:/EOTF-TWSS/docs/TWSS_TECHNICAL_OVERVIEW.md` |
| Sourced literature review | `D:/EOTF-TWSS/docs/LITERATURE_REVIEW.md` |
| Final exact tests/dependency/freeze evidence | `D:/EOTF-TWSS/results/software_improvements/validation.json` |
| This detailed report | `D:/EOTF-TWSS/reports/software_improvements_report.md` |

## Complete report/data-table path index

CSV/JSON/Markdown/log outputs, including preserved historical and staged reproduction reports. Figure paths are described inside their reports. A machine-readable index is `results/software_improvements/generated_report_manifest.json`.

- `D:/EOTF-TWSS/results/analysis/analysis_summary.md`
- `D:/EOTF-TWSS/results/analysis/configuration.json`
- `D:/EOTF-TWSS/results/analysis/confusion_summary.csv`
- `D:/EOTF-TWSS/results/analysis/fold_analysis.csv`
- `D:/EOTF-TWSS/results/analysis/report.json`
- `D:/EOTF-TWSS/results/analysis/report.md`
- `D:/EOTF-TWSS/results/analysis/subject_metrics.csv`
- `D:/EOTF-TWSS/results/channel_selection/configuration.json`
- `D:/EOTF-TWSS/results/channel_selection/fold_metrics.csv`
- `D:/EOTF-TWSS/results/channel_selection/heldout_predictions.csv`
- `D:/EOTF-TWSS/results/channel_selection/ranking.csv`
- `D:/EOTF-TWSS/results/channel_selection/report.json`
- `D:/EOTF-TWSS/results/channel_selection/report.md`
- `D:/EOTF-TWSS/results/channel_selection/subject_metrics.csv`
- `D:/EOTF-TWSS/results/confidence_analysis/configuration.json`
- `D:/EOTF-TWSS/results/confidence_analysis/heldout_predictions.csv`
- `D:/EOTF-TWSS/results/confidence_analysis/report.json`
- `D:/EOTF-TWSS/results/confidence_analysis/report.md`
- `D:/EOTF-TWSS/results/confidence_analysis/summary.md`
- `D:/EOTF-TWSS/results/confidence_analysis/threshold_metrics.csv`
- `D:/EOTF-TWSS/results/csp_analysis/configuration.json`
- `D:/EOTF-TWSS/results/csp_analysis/csp_analysis.md`
- `D:/EOTF-TWSS/results/csp_analysis/heldout_features.csv`
- `D:/EOTF-TWSS/results/csp_analysis/report.json`
- `D:/EOTF-TWSS/results/csp_analysis/report.md`
- `D:/EOTF-TWSS/results/csp_analysis/spatial_weights.csv`
- `D:/EOTF-TWSS/results/frequency_analysis/configuration.json`
- `D:/EOTF-TWSS/results/frequency_analysis/fold_metrics.csv`
- `D:/EOTF-TWSS/results/frequency_analysis/heldout_predictions.csv`
- `D:/EOTF-TWSS/results/frequency_analysis/ranking.csv`
- `D:/EOTF-TWSS/results/frequency_analysis/report.json`
- `D:/EOTF-TWSS/results/frequency_analysis/report.md`
- `D:/EOTF-TWSS/results/frequency_analysis/subject_metrics.csv`
- `D:/EOTF-TWSS/results/phase2_reproduction/comparison.csv`
- `D:/EOTF-TWSS/results/phase2_reproduction/configuration.json`
- `D:/EOTF-TWSS/results/phase2_reproduction/current_folds.csv`
- `D:/EOTF-TWSS/results/phase2_reproduction/fold_metrics.csv`
- `D:/EOTF-TWSS/results/phase2_reproduction/report.json`
- `D:/EOTF-TWSS/results/phase2_reproduction/report.md`
- `D:/EOTF-TWSS/results/phase2_reproduction/results.json`
- `D:/EOTF-TWSS/results/phase2_reproduction/summary.md`
- `D:/EOTF-TWSS/results/phase3/dataset_summary.json`
- `D:/EOTF-TWSS/results/phase3/download_inventory.json`
- `D:/EOTF-TWSS/results/phase3/edf_inventory.csv`
- `D:/EOTF-TWSS/results/phase3/feature_metadata.json`
- `D:/EOTF-TWSS/results/phase3/physionet/feature_metadata.json`
- `D:/EOTF-TWSS/results/phase3/physionet/features.csv`
- `D:/EOTF-TWSS/results/phase3/physionet/summary.json`
- `D:/EOTF-TWSS/results/phase3/REPRODUCIBILITY_STATUS.md`
- `D:/EOTF-TWSS/results/phase3/reproduction_provenance.json`
- `D:/EOTF-TWSS/results/phase3/srm/feature_metadata.json`
- `D:/EOTF-TWSS/results/phase3/srm/features.csv`
- `D:/EOTF-TWSS/results/phase3/srm/summary.json`
- `D:/EOTF-TWSS/results/phase3_historical/ARCHIVE.md`
- `D:/EOTF-TWSS/results/phase3_historical/dataset_summary.json`
- `D:/EOTF-TWSS/results/phase3_historical/feature_metadata.json`
- `D:/EOTF-TWSS/results/phase3_historical/physionet/features.csv`
- `D:/EOTF-TWSS/results/phase3_historical/physionet/summary.json`
- `D:/EOTF-TWSS/results/phase3_historical/REPRODUCIBILITY_STATUS.md`
- `D:/EOTF-TWSS/results/phase3_historical/srm/features.csv`
- `D:/EOTF-TWSS/results/phase3_historical/srm/summary.json`
- `D:/EOTF-TWSS/results/phase3_reproduction/dataset_summary.json`
- `D:/EOTF-TWSS/results/phase3_reproduction/download_inventory.json`
- `D:/EOTF-TWSS/results/phase3_reproduction/edf_inventory.csv`
- `D:/EOTF-TWSS/results/phase3_reproduction/feature_metadata.json`
- `D:/EOTF-TWSS/results/phase3_reproduction/physionet/feature_metadata.json`
- `D:/EOTF-TWSS/results/phase3_reproduction/physionet/features.csv`
- `D:/EOTF-TWSS/results/phase3_reproduction/physionet/summary.json`
- `D:/EOTF-TWSS/results/phase3_reproduction/srm/feature_metadata.json`
- `D:/EOTF-TWSS/results/phase3_reproduction/srm/features.csv`
- `D:/EOTF-TWSS/results/phase3_reproduction/srm/summary.json`
- `D:/EOTF-TWSS/results/software_improvements/freeze_after.json`
- `D:/EOTF-TWSS/results/software_improvements/freeze_before.json`
- `D:/EOTF-TWSS/results/software_improvements/intermediate_heldout_failure.log`
- `D:/EOTF-TWSS/results/software_improvements/pip_check.stderr.log`
- `D:/EOTF-TWSS/results/software_improvements/pip_check.stdout.log`
- `D:/EOTF-TWSS/results/software_improvements/unittest.stderr.log`
- `D:/EOTF-TWSS/results/software_improvements/unittest.stdout.log`
- `D:/EOTF-TWSS/results/software_improvements/validation.json`
- `D:/EOTF-TWSS/docs/TWSS_TECHNICAL_OVERVIEW.md`
- `D:/EOTF-TWSS/docs/LITERATURE_REVIEW.md`
- `D:/EOTF-TWSS/reports/software_improvements_report.md`

- `D:/EOTF-TWSS/results/software_improvements/generated_report_manifest.json`

- `D:/EOTF-TWSS/results/software_improvements/heldout_demo.stderr.log`

- `D:/EOTF-TWSS/results/software_improvements/heldout_demo.stdout.log`

- `D:/EOTF-TWSS/results/software_improvements/heldout_demo/configuration.json`

- `D:/EOTF-TWSS/results/software_improvements/heldout_demo/report.json`

- `D:/EOTF-TWSS/results/software_improvements/heldout_demo/report.md`

- `D:/EOTF-TWSS/results/software_improvements/heldout_demo/trials.csv`
