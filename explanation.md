# TWSS: what the project does and how its parts fit

Updated after the 2026-10-02 repository review. Detailed changes and exact
verification output are in [the review report](docs/REVIEW_2026-10-02.md).

## Scope

TWSS is a motor-imagery command prototype. Given recorded EEG for a cued
left/right hand imagery trial, it predicts LEFT/RIGHT and maps an accepted
prediction to YES/NO, a sentence and optional speech. These are assigned
commands; the model does not read an intended yes/no answer directly, decode
arbitrary thoughts, or reconstruct a person's words.

The current UI is an offline dataset replay demonstration. The physical NPG
Lite Beast kit has arrived; its participant recordings and real-device
classification performance have not been validated in this review.

## Frozen Phase 1 pipeline

1. MNE reads PhysioNet EEGMMIDB EDF files. Runs R04/R08/R12 contain the chosen
   left/right hand motor imagery task. T1 maps to LEFT=1, T2 to RIGHT=2; T0 is
   ignored by this two-class classifier.
2. The shared channel selector normalizes case/trailing periods and selects
   FC3, FC4, C3, C4, CP3, CP4 in that order.
3. Shared preprocessing filters EEG 8–30 Hz with MNE's existing default FIR
   implementation, then epochs 0.5–3.5 seconds after cues, baseline=None.
   At 160 Hz the inclusive endpoints produce 481 samples per channel.
4. CSP(n_components=4) learns spatial features; LDA predicts LEFT/RIGHT.
   CSP fitting occurs inside each training fold, preventing test-trial fitting.
5. The saved pipeline contains CSP and LDA, not raw acquisition, channel
   selection or filtering. It expects appropriately preprocessed trials in
   volts and the established channel order.

`configs/phase1_config.yaml` freezes the experiment. Config validation rejects
changes that would otherwise be silently ignored by the fixed pipeline.
The existing classifier artifact `models/csp_lda_s001.joblib` is trained on
all three S001 runs and is for inference demonstrations. It must not be used
to claim held-out accuracy on those same trials.

## Evaluation and confidence

Leave-one-run-out trains two runs and tests the third, independently for each
subject. S001 remains 68.89% mean fold accuracy. Across S001–S010 the 30-fold
mean is 64.67%, with fold sample standard deviation 18.71 percentage points.
These results concern unseen runs of the same subjects; they do not establish
cross-subject transfer or clinical/device performance. Confusion matrices and
other metrics are exported under `results/phase1/`.

`src/realtime/heldout_demo.py` fits only the two non-held-out runs and replays
the third. Its raw prediction can still be LEFT/RIGHT while its mapped command
is UNKNOWN because the predicted class probability is below the gate.

The default gate is 0.70. Accepted LEFT → YES → `Yes.`; accepted RIGHT → NO →
`No.`. Rejected or unavailable probabilities → UNKNOWN → no word, sentence
or audio. Probabilities are not calibrated guarantees of correctness.

## Inference, speech and UI

`DatasetStreamer` supplies preprocessed trial replay. `Trial` defines the
inference input. The common controller uses the saved model, applies the
confidence gate and invokes existing TWSS mappings. Streamlit displays the
latest six-channel trial, prediction, confidence, word and sentence. One Start
Command processes one trial; debug mode reveals the dataset's actual label.
Speech is optional and uses the existing pyttsx3 wrapper. Its Windows COM
initialization/cleanup has regression coverage; physical audio playback was
not exercised in this review.

```powershell
.venv/Scripts/python.exe -m streamlit run ui/app.py
.venv/Scripts/python.exe -m src.realtime.demo --no-audio
.venv/Scripts/python.exe -m src.realtime.heldout_demo
```

The ordinary saved-model demo replays training data without accuracy claims.
Use the held-out demo for a leakage-free example.

## Useful incoming research additions

Phase 2 benchmarks retain run isolation and compare baseline CSP+LDA,
filter-bank CSP+LDA, Riemannian MDM and tangent-space LDA. FBCSP uses five
bands over 8–30 Hz, two CSP components per band and six selected features.
The selector's configured random seed now controls mutual-information scoring.
The reproduced mean accuracies are 64.67%, 68.00%, 66.22% and 59.11%, respectively.
These comparisons do not replace the deployed Phase 1 model or prove that the
best average method will work best for a new participant.

Phase 3 contains dataset adapters and temporal, spectral, spatial and covariance
features with channel metadata. They are useful for quality checks and future
research, but are not connected to the classifier/UI. Feature dimensions can
vary by channel count; this alone does not make a trained classifier portable.
SRM ds003775 is resting-state EEG, not labeled LEFT/RIGHT command training.
Its local source data is missing and the inherited generated results remain
unreproduced. See [artifact status](results/phase3/REPRODUCIBILITY_STATUS.md).

## Acquisition and calibration

`BaseEEGStream` supplies start/stop/get_samples/get_window. LSL BeastStreamer
discovers streams, supports name/type/source-ID selection, validates channel
count/rate/finite values, buffers timestamped samples, and rejects stale,
incomplete or gapped windows. It retains **native publisher units**. MNE expects
volts, so firmware/ADC/amplifier scaling must be confirmed before preprocessing.

Calibration uses REST → imagery → REST cues, balanced randomized trials, raw
samples, cue timestamps and session protection. NPZ/JSON/CSV record subject,
session, label, rate, channels, units, simulation status and provenance. Raw own
recordings are ignored by Git. The separate RawDatasetStreamer supports four
seconds of raw cue-matched PhysioNet data for storage simulation; it does not
relabel arbitrary preprocessed three-second trials as fresh calibration data.

## What remains for the received kit

Start with the [USB-first guide](docs/USB_KIT_GUIDE.md): compatible Serial
firmware → Chords LSL Connector → stream discovery → three-second acquisition
check. Confirm actual electrode positions, physical channel order, reference,
sampling rate and units. Collect a small raw session and inspect it.

A separate live adapter still needs to convert verified native units, provide
adequate filtering context and create model-shaped trials through shared
preprocessing. Then evaluate new participant sessions and connect that adapter
to the controller. The frozen offline FIR pipeline is not already a validated
causal real-time filter. No new model, REST classifier, deep learning, UI source
selector or free-thought decoder was added in this review.
