# NPG recording EDA

Independent analysis of six existing CSV exports. This folder does not modify
the parent EEG model, blink app, or original Downloads files.

## Open the results

- `reports/eda_report.html`: main report, 28 figures, findings and downloads.
- `reports/outputs/npg_eda/quality_summary.xlsx`: Excel summary and channel statistics.
- `reports/quality_summary.csv`: counts, continuity checks and review flags.
- `reports/cleaning_log.csv`: exactly which operations were performed.
- `data/raw/`: byte-identical source snapshots and SHA-256 manifest.
- `data/cleaned/`: all source rows/values with source-row references and flags.
- `eda.ipynb`: analysis notebook; calculations are implemented in `analyze.py`.

## What the data means

The user reports these channel positions in order: C3, C4, F3, F4, P3, P4.
Physical position and channel order are not independently verified.

YES and NO were recorded while answering questions and speaking aloud. They
are not isolated imagined-speech recordings. The mixed file has no within-file
word labels or onset times. Left/right clenching body part is unconfirmed.

The user's Chords Web v2.7.0a screenshot confirms **Brain mode and the 50 Hz
notch selected on all six channels**. The 50 Hz choice is a mains-interference
filter, not the sampling rate. [Manufacturer documentation](https://docs.upsidedownlabs.tech/software/chords/chords-web/index.html)
describes Brain as a 45 Hz low-pass. This is the documented setting, not a
measurement of the effective filter response in these recordings.

The inspected [public recording code](https://github.com/upsidedownlabs/Chords-Web/blob/a0a77f7df5dcb88d8b21df3e70ead3761fffa309/src/components/Connection.tsx#L1188-L1211)
processes samples through filters before storing them for export. That revision
is version **2.7.1a**, whereas the screenshot shows **2.7.0a**. It corroborates
that the CSVs are likely already processed but does not prove the exact capture
build or its effective cutoff. Scaling and voltage conversion remain unverified.
All evidence and source links are in `recordings.json` under `filter_settings`.

The folder `data/raw` means untouched source exports, **not verified raw ADC
or unfiltered physiological EEG**. No filters were repeated or undone. Spectra
describe the exported signal and may reflect attenuation and residual components
from prior processing; a low-pass filter is not a brick-wall frequency cutoff.

The filter screenshot resolves the previously mentioned 50 Hz as a notch
selection. Approximate two-minute recordings and around 60,000 rows
suggest a nominal 500 Hz stream. **500 Hz remains provisional**. Sample-index
and cycles-per-sample plots do not require this assumption. Estimated seconds
and the secondary Hz axis do. No absolute sample timestamps exist in the files.

## Cleaning policy

1. Preserve and hash source snapshots. Refuse to overwrite snapshots if a source changes.
2. Parse numeric cells and flag invalid/nonfinite values. Preserve the originals.
3. Treat 255-to-0 counter transitions as normal wraps; mark all other unexpected steps.
4. Split window/PSD calculations at breaks or invalid rows. Never interpolate across them.
5. Flag amplitude deviations above 8 scaled median absolute deviations within each file/channel.
   These are review flags, not verified artifacts; do not delete or clip them.
6. Apply no new signal filter, rereferencing, normalization, resampling or voltage conversion.
7. Keep every row, original order and all finite numeric measurements unchanged.

Annotated files are not automatically clean physiological EEG or model-ready
word trials. Counters cannot establish elapsed clock time, a packet-loss count,
or absence of losses of complete counter cycles. Duplicate values are not
automatically corrupt measurements.

## Reproduce with ordinary Python

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe analyze.py
```

Sources default to the user's Downloads folder. Use `--source-dir` to select a
different folder containing the same six filenames. Preserved snapshots work
when Downloads originals are unavailable. `recordings.json` documents the
configuration. If the sample rate is verified later, change the rate **and its
status/evidence** there, then regenerate; never silently claim the assumption
was verified. Full reruns replace derived outputs but preserve source snapshots.

The optional `.analysis_deps` folder contains task-local plotting libraries
used by this machine's bundled analysis runtime and is ignored by Git.
To open the notebook interactively, install JupyterLab in your own environment
or use an existing notebook editor. The HTML report needs no Python installation.

The Excel summary is exported with the artifact-tool builder
`build_workbook.mjs`; it needs the desktop's bundled Node runtime and
`@oai/artifact-tool`. The HTML report and CSV/PNG outputs do not require Node.

## Validate

```powershell
.\.venv\Scripts\python.exe verify_analysis.py
```

Checks cover source hashes, numeric preservation, row accounting, counter
segmentation, analytic Welch scaling, plot dimensions and report links. No
classification model or accuracy metric is produced by this EDA.
