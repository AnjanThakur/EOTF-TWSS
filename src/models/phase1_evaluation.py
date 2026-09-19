"""Frozen multi-subject Phase 1 leave-one-run-out evaluation."""
import csv, json
from pathlib import Path
import numpy as np
import yaml
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, matthews_corrcoef, confusion_matrix
import mne
from src.models.train_csp_lda import load_subject, build_pipeline, PROJECT_ROOT


def evaluate_subject(data_dir, subject, runs=("R04", "R08", "R12")):
    X, y, groups = load_subject(data_dir, subject, runs)
    results = []
    for held_out in runs:
        test = groups == held_out; train = ~test
        if np.any(np.isin(groups[train], groups[test])): raise AssertionError("Train/test run overlap")
        model = build_pipeline()
        with mne.use_log_level("WARNING"): model.fit(X[train], y[train])
        pred = model.predict(X[test]); cm = confusion_matrix(y[test], pred, labels=[1, 2])
        results.append({"subject": subject, "test_run": held_out, "train_runs": "+".join(r for r in runs if r != held_out),
                        "train_trials": int(train.sum()), "test_trials": int(test.sum()),
                        "accuracy": float(accuracy_score(y[test], pred)),
                        "balanced_accuracy": float(balanced_accuracy_score(y[test], pred)),
                        "f1": float(f1_score(y[test], pred, average="binary", pos_label=1)),
                        "mcc": float(matthews_corrcoef(y[test], pred)),
                        "cm_11": int(cm[0, 0]), "cm_12": int(cm[0, 1]), "cm_21": int(cm[1, 0]), "cm_22": int(cm[1, 1])})
    return results


def run_evaluation(data_dir=PROJECT_ROOT / "data", config_path=PROJECT_ROOT / "configs/phase1_config.yaml", output_dir=PROJECT_ROOT / "results/phase1"):
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")); rows, skipped = [], []
    for subject in config["subjects"]:
        try: rows.extend(evaluate_subject(data_dir, subject, tuple(config["runs"])))
        except FileNotFoundError as exc: skipped.append({"subject": subject, "reason": str(exc)})
    if not rows: raise RuntimeError("No subjects could be evaluated.")
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with (output_dir / "fold_metrics.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    metrics = {name: [r[name] for r in rows] for name in ("accuracy", "balanced_accuracy", "f1", "mcc")}
    summary = {name: {"mean": float(np.mean(vals)), "std": float(np.std(vals, ddof=1))} for name, vals in metrics.items()}
    payload = {"config": config, "folds": rows, "skipped": skipped, "summary": summary}
    (output_dir / "results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    lines = ["# TWSS Phase 1 multi-subject evaluation", "", "Frozen CSP+LDA settings from `configs/phase1_config.yaml`.", "", f"Evaluated folds: {len(rows)}; skipped subjects: {len(skipped)}", "", "## Overall fold metrics", "", "| Metric | Mean | Std |", "|---|---:|---:|"]
    lines += [f"| {name} | {v['mean']:.4f} | {v['std']:.4f} |" for name, v in summary.items()]
    lines += ["", "## Per-subject fold means", "", "| Subject | Accuracy | Balanced accuracy | F1 | MCC |", "|---|---:|---:|---:|---:|"]
    for subject in config["subjects"]:
        subject_rows = [r for r in rows if r["subject"] == subject]
        if subject_rows:
            lines.append("| " + subject + " | " + " | ".join(f"{np.mean([r[k] for r in subject_rows]):.4f}" for k in ("accuracy", "balanced_accuracy", "f1", "mcc")) + " |")
    if skipped: lines += ["", "## Skipped", ""] + [f"- {x['subject']}: {x['reason']}" for x in skipped]
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = run_evaluation(); print(json.dumps(result["summary"], indent=2)); print(f"Skipped: {result['skipped']}")
