# TWSS project status — 2026-10-02

The implemented MVP classifies **left/right hand motor imagery** from recorded
EEG and maps the classes to YES/NO sentences and optional speech. It does not
decode arbitrary thoughts or validate performance on the newly received kit.

| Area | Verified status |
|---|---|
| Phase 1 CSP4 + LDA | Frozen pipeline; S001 68.89%, S001–S010 fold mean 64.67% |
| Confidence-gated inference/TWSS/Streamlit | Offline replay; UNKNOWN generates no command/audio |
| Leakage-free demo | Train two runs, replay only the third |
| Phase 2 comparisons | Reproduced 120 folds: FBCSP 68.00%, MDM 66.22%, tangent LDA 59.11%; not deployed |
| Phase 3 features/SRM | Feature code reviewed/tested; real SRM absent; stored analysis artifacts unreproduced |
| LSL acquisition | Synthetic six-channel discovery/connection/window checks pass; physical Beast untested |
| Calibration storage | Raw cue-matched simulation and cue-aligned LSL capture; NPZ/JSON/CSV; unique sessions |
| Tests | 60 tests in 19.151s, OK (skipped=1: real SRM data missing) |

The incoming model file was restored to the exact frozen Phase 1 bytes.
Preprocessing, deployed classifier parameters, UI architecture, mappings and
TTS architecture remain unchanged. The 70% gate is a probability threshold,
not a demonstrated correctness guarantee.

See [the completed review](docs/REVIEW_2026-10-02.md) for findings, fixes and
exact results, [project explanation](explanation.md) for the pipeline, and
[USB kit guide](docs/USB_KIT_GUIDE.md) for the next hardware session.

Next: establish USB → Chords LSL Connector → BeastStreamer; verify units,
rate and physical order; collect and inspect raw calibration data; then build
a tested live preprocessing adapter and evaluate new sessions before UI use.
