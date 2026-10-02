# TWSS Phase 2 Benchmark Evaluation Report

Controlled evaluation comparing Baseline CSP+LDA, Filter Bank CSP (FBCSP), Riemannian MDM, and Riemannian Tangent Space + LDA under Leave-One-Run-Out Cross-Validation.
Summary standard deviations are across 30 held-out folds, not ten subject means. F1 uses LEFT=1 as the positive class. Model comparisons are exploratory; choosing a winner on these folds does not validate deployment on new users.

## Overall Model Performance Comparison

| Model ID | Model Name | Mean Acc | Std Acc | Median Acc | Mean Bal Acc | Mean F1 | Mean MCC |
|---|---|---:|---:|---:|---:|---:|---:|
| `baseline_csp_lda` | CSP + LDA (Phase 1 Baseline) | 0.6467 | 0.1871 | 0.6000 | 0.6491 | 0.6379 | 0.3182 |
| `fbcsp_lda` | Filter Bank CSP (FBCSP) + LDA | 0.6800 | 0.1394 | 0.6667 | 0.6804 | 0.6421 | 0.4045 |
| `riemannian_mdm` | Riemannian MDM | 0.6622 | 0.1623 | 0.6000 | 0.6643 | 0.6525 | 0.3657 |
| `riemannian_tangent_space_lda` | Riemannian Tangent Space + LDA | 0.5911 | 0.1640 | 0.5333 | 0.5899 | 0.5813 | 0.1847 |

## Per-Subject Mean Accuracy Breakdown

| Subject | Baseline CSP+LDA | FBCSP + LDA | Riemannian MDM | Tangent Space + LDA | Best Method |
|---|---:|---:|---:|---:|---|
| **S001** | 68.89% | 68.89% | 75.56% | 60.00% | **riemannian_mdm** (75.56%) |
| **S002** | 88.89% | 88.89% | 88.89% | 82.22% | **baseline_csp_lda** (88.89%) |
| **S003** | 53.33% | 55.56% | 62.22% | 53.33% | **riemannian_mdm** (62.22%) |
| **S004** | 73.33% | 75.56% | 77.78% | 51.11% | **riemannian_mdm** (77.78%) |
| **S005** | 53.33% | 60.00% | 53.33% | 57.78% | **fbcsp_lda** (60.00%) |
| **S006** | 53.33% | 55.56% | 55.56% | 48.89% | **fbcsp_lda** (55.56%) |
| **S007** | 95.56% | 91.11% | 80.00% | 84.44% | **baseline_csp_lda** (95.56%) |
| **S008** | 40.00% | 62.22% | 46.67% | 48.89% | **fbcsp_lda** (62.22%) |
| **S009** | 46.67% | 55.56% | 57.78% | 46.67% | **riemannian_mdm** (57.78%) |
| **S010** | 73.33% | 66.67% | 64.44% | 57.78% | **baseline_csp_lda** (73.33%) |
