# Project Progress & Status Report · EOTF-TWSS

**Project Name:** End-to-End Offline Thought-to-Word-to-Speech System (EOTF-TWSS)  
**Corpus:** `AnjanThakur/EOTF-TWSS`  
**Last Updated:** September 20, 2026  

---

## Executive Summary

The **EOTF-TWSS** project is an end-to-end BCI pipeline that decodes motor imagery EEG signals into discrete command words (`YES` / `NO`) and converts them into spoken sentences (`"Yes."` / `"No."`) with confidence gating. All core pipeline stages—data ingestion, band-pass filtering, CSP+LDA classification, probability thresholding, speech synthesis, real-time simulation, web UI, Phase 2 feature engineering benchmarks (FBCSP and Riemannian geometry), and automated test suites—are implemented, fully integrated, and verified on local environments.

---

## Detailed Milestone Progress

### 1. Project Infrastructure & Environment Setup
- [x] **Python Environment:** Created and configured virtual environment `.venv` under Python 3.14.
- [x] **Dependency Management:** Configured and installed all required packages via `requirements.txt` (`mne`, `scikit-learn`, `pyriemann`, `numpy`, `scipy`, `pandas`, `matplotlib`, `joblib`, `pyttsx3`, `streamlit`, `pylsl`, `PyYAML`).
- [x] **Dataset Ingestion:** Downloaded PhysioNet Motor Movement/Imagery Dataset (`eegmmidb`) runs `R04`, `R08`, `R12` (Left/Right hand motor imagery) for all 10 Subjects (`S001` through `S010`) into structured paths (`data/` & `data/physionet/`).

---

### 2. First-Stage EEG Preprocessing Pipeline (`src/preprocessing/preprocess.py`)
- [x] **EDF Ingestion & Channel Selection:** Retains EEG channels, standardizing on 6 key sensor locations: `FC3`, `FC4`, `C3`, `C4`, `CP3`, `CP4`.
- [x] **Filtering:** Applies 5th-order zero-phase 8.0 – 30.0 Hz band-pass filter (mu/beta rhythm range).
- [x] **Cue-Locked Epoching:** Epochs 3.0 seconds post-stimulus (0.5s to 3.5s) at 160 Hz (481 samples per trial) with `baseline=None`.
- [x] **Label Mapping:** Maps `T1` cue to Class `1` (`LEFT`) and `T2` cue to Class `2` (`RIGHT`), ignoring rest state (`T0`).

---

### 3. Machine Learning Model & CSP+LDA Pipeline (`src/models/train_csp_lda.py`)
- [x] **Pipeline Architecture:** Combined Common Spatial Patterns (CSP with $n\_components=4$) + Linear Discriminant Analysis (LDA).
- [x] **Leave-One-Run-Out Cross-Validation (S001):** Evaluated generalization across runs without data leakage:
  - **Train R08+R12 $\rightarrow$ Test R04:** Accuracy = **73.33%** (11 / 15 trials correct)
  - **Train R04+R12 $\rightarrow$ Test R08:** Accuracy = **60.00%** (9 / 15 trials correct)
  - **Train R04+R08 $\rightarrow$ Test R12:** Accuracy = **73.33%** (11 / 15 trials correct)
  - **Mean S001 CV Accuracy:** **68.89%**
- [x] **Final Model Artifact:** Trained on all 45 trials of S001 and serialized to `models/csp_lda_s001.joblib` with reload verification checks.

---

### 4. Phase 2 Advanced Feature Engineering & Riemannian Benchmarks (`src/models/fbcsp.py`, `src/models/riemannian.py`, `src/models/phase2_evaluation.py`)
- [x] **Filter Bank CSP (FBCSP):** Evaluates 5 frequency sub-bands (`8-12`, `12-16`, `16-20`, `20-24`, `24-30` Hz) with Mutual Information feature selection and LDA classifier.
- [x] **Riemannian Geometry Classifiers:** Implemented affine-invariant Minimum Distance to Mean (MDM) on SPD covariance matrices and Riemannian Tangent Space + LDA.
- [x] **10-Subject Comparative Evaluation Benchmark:**

| Subject | Baseline CSP+LDA | Filter Bank CSP (FBCSP) | Riemannian MDM | Tangent Space + LDA | Best Method |
|---|---:|---:|---:|---:|---|
| **S001** | 68.89% | 68.89% | **75.56%** | 60.00% | **Riemannian MDM** (75.56%) |
| **S002** | **88.89%** | **88.89%** | **88.89%** | 82.22% | **Baseline / FBCSP / MDM** (88.89%) |
| **S003** | 53.33% | 55.56% | **62.22%** | 53.33% | **Riemannian MDM** (62.22%) |
| **S004** | 73.33% | 75.56% | **77.78%** | 51.11% | **Riemannian MDM** (77.78%) |
| **S005** | 53.33% | **60.00%** | 53.33% | 57.78% | **FBCSP + LDA** (60.00%) |
| **S006** | 53.33% | **55.56%** | **55.56%** | 48.89% | **FBCSP / MDM** (55.56%) |
| **S007** | **95.56%** | 91.11% | 80.00% | 84.44% | **Baseline CSP+LDA** (95.56%) |
| **S008** | 40.00% | **62.22%** | 46.67% | 48.89% | **FBCSP + LDA** (62.22%) |
| **S009** | 46.67% | 55.56% | **57.78%** | 46.67% | **Riemannian MDM** (57.78%) |
| **S010** | **73.33%** | 66.67% | 64.44% | 57.78% | **Baseline CSP+LDA** (73.33%) |
| **Overall Mean** | **64.67%** | **68.00%** | **66.22%** | **59.11%** | **FBCSP Highest Mean** |
| **Std Dev** | 18.71% | **13.94%** | 16.23% | 16.40% | **FBCSP Most Stable** |
| **Mean MCC** | 0.3182 | **0.4045** | 0.3657 | 0.1847 | **FBCSP Highest MCC** |

- [x] **Scientific Visualization Generation (`scripts/generate_phase2_plots.py`):**
  - `per_subject_accuracy_comparison.png`
  - `per_subject_mcc_comparison.png`
  - `accuracy_distribution_boxplot.png`
  - `per_subject_improvement_over_baseline.png`

---

### 5. Real-Time Inference Engine & TWSS Speech Integration (`src/realtime/`, `src/twss/`)
- [x] **Single-Trial Inference (`inference.py`):** Accepts preprocessed 6-channel $\times$ 481 sample trials, evaluates class probability, and enforces a confidence threshold (default 70%).
- [x] **TWSS Mapping (`mapper.py` & `sentence.py`):**
  - Accepted `LEFT` $\rightarrow$ Word `"YES"` $\rightarrow$ Sentence `"Yes."`
  - Accepted `RIGHT` $\rightarrow$ Word `"NO"` $\rightarrow$ Sentence `"No."`
  - Below threshold / low confidence $\rightarrow$ Decision `"UNKNOWN"`, suppressing sentence and audio generation.
- [x] **Speech Synthesis (`speech.py`):** Thread-safe COM initialization for `pyttsx3` text-to-speech with graceful audio fallback (`--no-audio`).
- [x] **LSL Acquisition Interface (`src/acquisition/beast_stream.py`):** Multi-threaded Lab Streaming Layer (LSL) buffer for NPG Lite / Beast real-time stream integration.

---

### 6. Interactive Web Application MVP (`ui/app.py`)
- [x] **Streamlit Dashboard:**
  - Interactive trial stepper (`Start Command` button).
  - Confidence threshold slider (0.0 to 1.0) with real-time recalculation.
  - Sentence display and triggerable text-to-speech button.
  - Multi-channel EEG window visualization ($\mu\text{V}$ over 3.0s time domain).
  - Debug mode showing actual ground truth labels and source identifiers.
- [x] **Application Verification:** Tested and running locally via `.venv/Scripts/python.exe -m streamlit run ui/app.py`.

---

### 7. Comprehensive Automated Test Suite (`tests/`)
- [x] **Test Coverage (24 / 24 Tests Passing):**
  - `test_acquisition.py`: Tests calibration recording, dataset streaming, and validation checks.
  - `test_inference.py`: Verifies probability extraction, threshold boundary enforcement, UNKNOWN suppression, and speech engine safety.
  - `test_lsl.py`: Tests LSL stream discovery, connection, windowing, and timeout handling.
  - `test_phase1.py`: Tests configuration parsing, cross-validation metrics, and held-out trial formatting.
  - `test_phase2.py`: Tests FBCSP feature extraction, fold isolation (no data leakage), Riemannian MDM and Tangent Space pipelines, and config validation.
  - `test_speech.py`: Verifies COM initialization lifecycle and exception handling.
  - `test_ui.py`: Full AppTest integration testing for Streamlit user flows, button states, metric updates, threshold adjustments, and error states.

### 8. Phase 3 — Hardware-Independent EEG Representation Pipeline (`src/features/`, `src/datasets/`)
- [x] **Hardware & Dataset Abstraction Layer:** Constructed a dataset-agnostic EEG representation pipeline operating on arbitrary sampling rates, channel counts, and window durations.
- [x] **Generic Feature Extractors (`src/features/`):**
  - **Temporal (`temporal.py`):** Mean, variance, std, RMS, peak-to-peak amplitude.
  - **Spectral (`spectral.py`):** Welch PSD band power (Delta 1-4Hz, Theta 4-8Hz, Alpha 8-13Hz, Beta 13-30Hz, Gamma 30-45Hz) with absolute and relative power.
  - **Spatial (`spatial.py`):** Channel covariance matrices, correlation matrices, spatial channel variance, and cross-channel correlation.
  - **Unified Extractor (`extractor.py`):** `EEGFeatureExtractor` with structured feature metadata (`feature_name`, `feature_type`, `channel`, `frequency_band`).
- [x] **Dataset Adapters (`src/datasets/`):**
  - **SRM Resting-State EEG (`srm.py`):** Ingests BIDS `ds003775` dataset (64 channels @ 1024 Hz), handles git-annex stubs gracefully, and segments continuous recordings into standardized 2.0s windows (120 windows extracted).
  - **PhysioNet Adapter (`physionet.py`):** Standardizes PhysioNet preprocessed output without touching existing `preprocess.py` pipeline.
- [x] **Scientific Representation Analysis (`scripts/run_phase3_analysis.py`):**
  - Processed SRM (64 channels, 1024 Hz, 3,168 features) and PhysioNet S001 (6 channels, 160 Hz, 123 features).
  - Generated dataset summaries, feature metadata JSON, and publication-quality plots under `results/phase3/plots/` (`psd/`, `band_power/`, `distributions/`, `pca/`).
- [x] **Expanded Test Suite:** Added `tests/test_features.py` and `tests/test_srm_loader.py` bringing total passing test suite to **42 / 42 tests passing**.

---

## Current Status Overview

| Component | Status | Verification Command / Artifact |
|---|:---:|---|
| **Python Venv & Dependencies** |  Completed | `.venv/` with all packages installed including `pyriemann` |
| **Data Ingestion (S001–S010)** |  Completed | [data/](file:///c:/Projects/Thought_to_Speech/EOTF-TWSS/data/) (`R04`, `R08`, `R12` for 10 subjects) |
| **SRM Dataset Ingestion** |  Completed | [data/srm/ds003775/](file:///c:/Projects/Thought_to_Speech/EOTF-TWSS/data/srm/ds003775/) (64 channels @ 1024 Hz resting state) |
| **Preprocessing Pipeline** |  Completed | [src/preprocessing/preprocess.py](file:///c:/Projects/Thought_to_Speech/EOTF-TWSS/src/preprocessing/preprocess.py) |
| **CSP + LDA Classifier** |  Completed | [models/csp_lda_s001.joblib](file:///c:/Projects/Thought_to_Speech/EOTF-TWSS/models/csp_lda_s001.joblib) (68.89% CV accuracy) |
| **Filter Bank CSP (FBCSP)** |  Completed | [src/models/fbcsp.py](file:///c:/Projects/Thought_to_Speech/EOTF-TWSS/src/models/fbcsp.py) (**68.00%** mean accuracy, **0.4045** MCC) |
| **Riemannian MDM & TS** |  Completed | [src/models/riemannian.py](file:///c:/Projects/Thought_to_Speech/EOTF-TWSS/src/models/riemannian.py) (MDM **66.22%** mean accuracy) |
| **Phase 2 Benchmark Suite** |  Completed | [results/phase2/summary.md](file:///c:/Projects/Thought_to_Speech/EOTF-TWSS/results/phase2/summary.md) |
| **Phase 3 Feature Representation** |  Completed | [src/features/](file:///c:/Projects/Thought_to_Speech/EOTF-TWSS/src/features/) & [src/datasets/](file:///c:/Projects/Thought_to_Speech/EOTF-TWSS/src/datasets/) |
| **Phase 3 Artifacts & Plots** |  Completed | [results/phase3/](file:///c:/Projects/Thought_to_Speech/EOTF-TWSS/results/phase3/) (Summary JSONs, CSVs, PSD, PCA plots) |
| **Realtime Inference Simulator** |  Completed | `.venv/Scripts/python.exe -m src.realtime.demo --no-audio` |
| **TWSS Speech Engine** |  Completed | [src/twss/speech.py](file:///c:/Projects/Thought_to_Speech/EOTF-TWSS/src/twss/speech.py) |
| **Streamlit Web UI** |  Completed | `.venv/Scripts/python.exe -m streamlit run ui/app.py` |
| **Automated Unit Tests** |  Completed | **42 / 42 tests passing** (`.venv/Scripts/python.exe -m unittest discover -s tests -v`) |

---

## Next Steps & Roadmap

1. **Phase 3 Model Selection & Deployment:**
   - Package Filter Bank CSP (FBCSP) as the production model artifact due to highest mean accuracy (**68.00%**), lowest subject variance (**13.94%**), and highest MCC (**0.4045**).
2. **Subject Adaptation & Calibration Protocol:**
   - Establish rapid 2-run subject calibration for new users before real-time inference.
3. **Live Hardware Integration:**
   - Connect physical Upside Down Labs NPG Lite / Beast EEG hardware via `BeastStreamer` LSL buffer.

