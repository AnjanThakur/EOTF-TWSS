# Phase 3 artifact status — 2026-10-02 review

The CSV/JSON/PNG files in this directory arrived in upstream commit `407ab37`.
Their SRM source dataset, `data/srm/ds003775`, is absent in this workspace.
They have **not** been reproduced or certified by this review. The real-SRM
integration test therefore skips. They describe exploratory features, not
LEFT/RIGHT command evaluation or free-thought decoding.

The review fixed feature finite-value checks, small-amplitude relative power,
constant-channel cross-correlation, SRM metadata validation, dataset-specific
feature metadata exports and standardized exploratory PCA. Existing generated
Phase 3 artifacts predate these fixes and must be regenerated when data arrives.

PhysioNet features use already filtered 8–30 Hz imagery epochs; SRM features
use unfiltered resting windows. Their delta/theta/gamma figures are not a
controlled comparison of datasets or evidence of command intent. A future
comparison needs matched preprocessing, units, channel selections and timing.
