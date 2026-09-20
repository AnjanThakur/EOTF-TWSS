"""Phase 2 Multi-Subject Evaluation Benchmark comparing Baseline CSP+LDA, FBCSP+LDA,

Riemannian MDM, and Riemannian Tangent Space + LDA under Leave-One-Run-Out CV.
"""

import csv
import json
from pathlib import Path
import mne
import numpy as np
import yaml
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    precision_score,
    recall_score,
)

from src.models.fbcsp import FBCSPPipeline, load_subject_fbcsp
from src.models.riemannian import (
    build_riemannian_mdm_pipeline,
    build_riemannian_tangent_space_pipeline,
)
from src.models.train_csp_lda import PROJECT_ROOT, build_pipeline, load_subject


def evaluate_subject_model(
    data_dir: Path,
    subject: str,
    model_id: str,
    runs: tuple[str, ...] = ("R04", "R08", "R12"),
    sub_bands: tuple[tuple[float, float], ...] = (
        (8.0, 12.0),
        (12.0, 16.0),
        (16.0, 20.0),
        (20.0, 24.0),
        (24.0, 30.0),
    ),
) -> list[dict]:
    """Evaluate one model on one subject under Leave-One-Run-Out Cross-Validation."""
    if model_id == "fbcsp_lda":
        X, y, groups = load_subject_fbcsp(data_dir, subject, runs, sub_bands)
    else:
        X, y, groups = load_subject(data_dir, subject, runs)

    results = []
    for held_out in runs:
        test = groups == held_out
        train = ~test
        if np.any(np.isin(groups[train], groups[test])):
            raise AssertionError("Train/test run overlap detected.")

        if model_id == "baseline_csp_lda":
            model = build_pipeline()
        elif model_id == "fbcsp_lda":
            model = FBCSPPipeline(n_components_per_band=2, n_features_to_select=6)
        elif model_id == "riemannian_mdm":
            model = build_riemannian_mdm_pipeline()
        elif model_id == "riemannian_tangent_space_lda":
            model = build_riemannian_tangent_space_pipeline()
        else:
            raise ValueError(f"Unknown model_id: {model_id}")

        with mne.use_log_level("WARNING"):
            model.fit(X[train], y[train])
        pred = model.predict(X[test])

        cm = confusion_matrix(y[test], pred, labels=[1, 2])
        acc = float(accuracy_score(y[test], pred))
        b_acc = float(balanced_accuracy_score(y[test], pred))
        prec = float(precision_score(y[test], pred, pos_label=1, zero_division=0))
        rec = float(recall_score(y[test], pred, pos_label=1, zero_division=0))
        f1 = float(f1_score(y[test], pred, pos_label=1, zero_division=0))
        mcc = float(matthews_corrcoef(y[test], pred))

        results.append({
            "model_id": model_id,
            "subject": subject,
            "test_run": held_out,
            "train_runs": "+".join(r for r in runs if r != held_out),
            "train_trials": int(train.sum()),
            "test_trials": int(test.sum()),
            "accuracy": acc,
            "balanced_accuracy": b_acc,
            "precision": prec,
            "recall": rec,
            "f1": f1,
            "mcc": mcc,
            "cm_11": int(cm[0, 0]),
            "cm_12": int(cm[0, 1]),
            "cm_21": int(cm[1, 0]),
            "cm_22": int(cm[1, 1]),
        })
    return results


def run_phase2_evaluation(
    data_dir: Path = PROJECT_ROOT / "data",
    config_path: Path = PROJECT_ROOT / "configs/phase2_config.yaml",
    output_dir: Path = PROJECT_ROOT / "results/phase2",
) -> dict:
    """Run Phase 2 evaluation across all configured models and subjects."""
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    sub_bands = tuple(tuple(b) for b in config["sub_bands"])
    runs = tuple(config["runs"])

    all_rows = []
    skipped = []

    for model_cfg in config["models"]:
        model_id = model_cfg["id"]
        print(f"\n--- Evaluating Model: {model_cfg['name']} ({model_id}) ---")
        for subject in config["subjects"]:
            try:
                subject_rows = evaluate_subject_model(
                    data_dir, subject, model_id, runs, sub_bands
                )
                all_rows.extend(subject_rows)
                subject_mean_acc = np.mean([r["accuracy"] for r in subject_rows])
                print(f"[{model_id}] {subject}: Mean LOOR Accuracy = {subject_mean_acc:.2%}")
            except FileNotFoundError as exc:
                if {"model_id": model_id, "subject": subject} not in skipped:
                    skipped.append({"model_id": model_id, "subject": subject, "reason": str(exc)})
                print(f"[{model_id}] {subject}: SKIPPED ({exc})")

    if not all_rows:
        raise RuntimeError("No models or subjects could be evaluated.")

    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Save fold_metrics.csv
    fields = list(all_rows[0].keys())
    with (output_dir / "fold_metrics.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(all_rows)

    # 2. Compute aggregate summary metrics per model
    model_summaries = {}
    metric_keys = ("accuracy", "balanced_accuracy", "precision", "recall", "f1", "mcc")

    for model_cfg in config["models"]:
        m_id = model_cfg["id"]
        m_rows = [r for r in all_rows if r["model_id"] == m_id]
        if not m_rows:
            continue
        m_summary = {}
        for k in metric_keys:
            vals = [r[k] for r in m_rows]
            m_summary[k] = {
                "mean": float(np.mean(vals)),
                "std": float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0,
                "median": float(np.median(vals)),
                "min": float(np.min(vals)),
                "max": float(np.max(vals)),
            }
        model_summaries[m_id] = m_summary

    payload = {
        "config": config,
        "folds": all_rows,
        "skipped": skipped,
        "model_summaries": model_summaries,
    }
    (output_dir / "results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # 3. Generate summary.md
    generate_markdown_summary(output_dir / "summary.md", config, all_rows, model_summaries, skipped)
    print(f"\nPhase 2 evaluation complete! Artifacts saved in {output_dir.as_posix()}")
    return payload


def generate_markdown_summary(
    summary_path: Path,
    config: dict,
    all_rows: list[dict],
    model_summaries: dict,
    skipped: list[dict],
) -> None:
    lines = [
        "# TWSS Phase 2 Benchmark Evaluation Report",
        "",
        "Controlled evaluation comparing Baseline CSP+LDA, Filter Bank CSP (FBCSP), Riemannian MDM, and Riemannian Tangent Space + LDA under Leave-One-Run-Out Cross-Validation.",
        "",
        "## Overall Model Performance Comparison",
        "",
        "| Model ID | Model Name | Mean Acc | Std Acc | Median Acc | Mean Bal Acc | Mean F1 | Mean MCC |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]

    for model_cfg in config["models"]:
        m_id = model_cfg["id"]
        m_name = model_cfg["name"]
        if m_id in model_summaries:
            s = model_summaries[m_id]
            lines.append(
                f"| `{m_id}` | {m_name} | {s['accuracy']['mean']:.4f} | {s['accuracy']['std']:.4f} | {s['accuracy']['median']:.4f} | {s['balanced_accuracy']['mean']:.4f} | {s['f1']['mean']:.4f} | {s['mcc']['mean']:.4f} |"
            )

    lines += [
        "",
        "## Per-Subject Mean Accuracy Breakdown",
        "",
        "| Subject | Baseline CSP+LDA | FBCSP + LDA | Riemannian MDM | Tangent Space + LDA | Best Method |",
        "|---|---:|---:|---:|---:|---|",
    ]

    for subject in config["subjects"]:
        row_str = f"| **{subject}** |"
        accs = {}
        for model_cfg in config["models"]:
            m_id = model_cfg["id"]
            sub_rows = [r for r in all_rows if r["subject"] == subject and r["model_id"] == m_id]
            if sub_rows:
                acc = float(np.mean([r["accuracy"] for r in sub_rows]))
                accs[m_id] = acc
                row_str += f" {acc:.2%} |"
            else:
                row_str += " N/A |"
        if accs:
            best_m = max(accs, key=accs.get)
            row_str += f" **{best_m}** ({accs[best_m]:.2%}) |"
        else:
            row_str += " N/A |"
        lines.append(row_str)

    if skipped:
        lines += [
            "",
            "## Skipped Runs / Subjects",
            "",
        ] + [f"- `{x['model_id']}` {x['subject']}: {x['reason']}" for x in skipped]

    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run_phase2_evaluation()
