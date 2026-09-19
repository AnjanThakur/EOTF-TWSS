# TWSS BCI: first-stage EEG preprocessing

Install dependencies and run from the project root (PowerShell):

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe notebooks/test_load.py
```

Use `--no-show` to save the raw EEG plot without opening an interactive window.
Plots are saved in `notebooks/outputs/`. The browser initially shows 16 channels
over 10 seconds; interactive mode allows browsing the rest.

Place `S001R04.edf` in `data/physionet/` (optionally under `S001/`). The runner
also detects the existing `data/S001/S001R04.edf` layout without moving data.
An explicit path is interpreted relative to the current working directory:

```powershell
.venv/Scripts/python.exe notebooks/test_load.py data/S001/S001R08.edf --no-show
```

The loader accepts only R04/R08/R12 left/right motor-imagery runs. T1 maps to
left hand (label 1), T2 to right hand (label 2); T0/rest is ignored for epochs.
See the [PhysioNet dataset description](https://physionet.org/content/eegmmidb/1.0.0/).

`src/preprocessing/preprocess.py` exposes `load_eeg`, `extract_events`,
`create_epochs`, and `prepare_data`. It keeps EEG channels, applies an 8-30 Hz
band-pass to a copy of the continuous recording, and creates 0.5-3.5 second
epochs with `baseline=None`. No re-referencing or artifact correction is added.

```python
from src.preprocessing.preprocess import load_eeg, prepare_data

raw = load_eeg("data/S001/S001R04.edf")
epochs, X, y = prepare_data(raw)
```

`X` is in volts with axes `(epochs, channels, time_samples)`; `y` contains the
matching integer labels from retained epochs. MNE includes both time endpoints,
so a 3-second interval at 160 Hz contains 481 samples. Arrays are returned in
memory for later use.

## CSP + LDA baseline

```powershell
.venv/Scripts/python.exe -m src.models.train_csp_lda
```

The reusable training module loads S001 R04/R08/R12 using the preprocessing
module above. It selects exactly `FC3, FC4, C3, C4, CP3, CP4` in that order,
matching case and trailing periods and rejecting missing or ambiguous names.
Each run is filtered and epoched separately with the existing settings.

Evaluation holds out one entire run at a time. A fresh sklearn pipeline fits
MNE `CSP(n_components=4)` and `LinearDiscriminantAnalysis()` on the other two
runs. CSP is never fitted on held-out data. Confusion matrices use rows=true,
columns=predicted and class order `[1=LEFT, 2=RIGHT]`.

After evaluation, a separate pipeline is trained on all 45 trials and saved to
`models/csp_lda_s001.joblib`. The saved object is the sklearn pipeline itself:

```python
import joblib
model = joblib.load("models/csp_lda_s001.joblib")
predictions = model.predict(X)
```

Prediction input must already be preprocessed EEG in volts with shape
`(trials, 6, 481)`, at 160 Hz, in the exact channel order above, using the same
8-30 Hz filter and 0.5-3.5 second epochs with no baseline correction. Channel
selection and preprocessing are outside the saved CSP+LDA pipeline.
Use `--data-dir` and `--model-path` to override the default locations.
These scores evaluate held-out runs of S001, not generalization to new subjects.

## End-to-end inference simulator

```powershell
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m src.realtime.demo --no-audio
# All trials, optional pacing and confidence gate:
.venv/Scripts/python.exe -m src.realtime.demo --no-audio --limit 45 --threshold 0.7 --interval 3
# Speak accepted commands with pyttsx3:
.venv/Scripts/python.exe -m src.realtime.demo
```

The default demo replays six trials with no delay and a 70% confidence threshold.
S001 R04/R08/R12 are training data for the saved final model: these predictions
demonstrate inference only. No accuracy is computed. The separate held-out-run
evaluation remains in `models/training_report.txt`.

`dataset_stream.py` reuses `load_subject` and the existing preprocessing, yielding
one complete epoch at a time. Three seconds includes both endpoints (481 samples),
as during training. This is offline trial replay, not causal/live filtering.
`Trial` in `src/realtime/trial.py` defines the source boundary: preprocessed volts,
six channels in the established order, shape `(6, 481)`, optional actual label,
and a source identifier. A future hardware adapter can supply an iterable of
these trials to `run_demo` without changing inference or TWSS code, and reuse
the shared preprocessing upstream. Hardware timing/buffering is not implemented.

`predict_trial` returns the raw predicted class/name, the probability for that
class, actual label, and a gated decision. Below the threshold (or if probabilities
are unavailable), the decision is UNKNOWN; no command sentence or speech is
generated. Equality with the threshold is accepted. Probabilities are not a
validated reliability measure. LEFT maps to YES then "Yes."; RIGHT to NO then
"No.". `--no-audio` avoids importing/initializing the speech engine entirely.

## Streamlit MVP

Run `.venv/Scripts/python.exe -m streamlit run ui/app.py` from the project root.
Start Command consumes one trial. The sidebar threshold defaults to 0.70;
changing it rechecks the current trial without advancing the source. UNKNOWN
produces no word or sentence and disables Speak. Speech is off by default;
enable it and click Speak to play audio on the computer running Streamlit.
Actual labels appear only in Debug Mode. Reset replay restarts the source.

`src/realtime/controller.py` accepts an iterable of existing `Trial` objects.
The UI's `create_controller` connects the dataset source to the saved model;
a future BeastStreamer can replace the source without changing preprocessing,
inference, or TWSS mapping. State is separate for each browser session.
No model fitting is performed. These training-data demonstrations are not
accuracy evaluations.

Run tests: `.venv/Scripts/python.exe -m unittest discover -s tests -v`.
