"""Generate high-resolution scientific visualization plots for Phase 2 benchmark results."""

import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results/phase2"
PLOTS_DIR = RESULTS_DIR / "plots"


def generate_plots():
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    results_json = RESULTS_DIR / "results.json"
    if not results_json.is_file():
        raise FileNotFoundError(f"Missing {results_json.as_posix()}")

    payload = json.loads(results_json.read_text(encoding="utf-8"))
    folds = payload["folds"]
    config = payload["config"]

    subjects = config["subjects"]
    models = config["models"]
    model_ids = [m["id"] for m in models]
    model_names = [m["name"] for m in models]

    # Collect per-subject mean accuracy & MCC
    sub_acc = {m_id: [] for m_id in model_ids}
    sub_mcc = {m_id: [] for m_id in model_ids}

    for s in subjects:
        for m_id in model_ids:
            s_rows = [r for r in folds if r["subject"] == s and r["model_id"] == m_id]
            if s_rows:
                sub_acc[m_id].append(float(np.mean([r["accuracy"] for r in s_rows])))
                sub_mcc[m_id].append(float(np.mean([r["mcc"] for r in s_rows])))
            else:
                sub_acc[m_id].append(np.nan)
                sub_mcc[m_id].append(np.nan)

    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    colors = ["#2b5c8f", "#d95f02", "#7570b3", "#1b9e77"]

    # --- PLOT 1: Per-subject Accuracy Comparison ---
    fig, ax = plt.subplots(figsize=(12, 6), dpi=300)
    x = np.arange(len(subjects))
    width = 0.2

    for i, (m_id, name) in enumerate(zip(model_ids, model_names)):
        ax.bar(x + (i - 1.5) * width, np.array(sub_acc[m_id]) * 100, width, label=name, color=colors[i])

    ax.axhline(50, color="gray", linestyle="--", alpha=0.7, label="Chance Level (50%)")
    ax.set_ylabel("LOOR Cross-Validation Accuracy (%)", fontsize=12)
    ax.set_xlabel("Subject", fontsize=12)
    ax.set_title("Phase 2: Per-Subject Classification Accuracy Comparison", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(subjects, fontsize=11)
    ax.set_ylim(30, 105)
    ax.legend(frameon=True, facecolor="white", edgecolor="none", loc="upper right")
    plt.tight_layout()
    fig.savefig(PLOTS_DIR / "per_subject_accuracy_comparison.png")
    plt.close(fig)

    # --- PLOT 2: Per-subject MCC Comparison ---
    fig, ax = plt.subplots(figsize=(12, 6), dpi=300)
    for i, (m_id, name) in enumerate(zip(model_ids, model_names)):
        ax.bar(x + (i - 1.5) * width, sub_mcc[m_id], width, label=name, color=colors[i])

    ax.axhline(0, color="black", linestyle="-", linewidth=0.8)
    ax.set_ylabel("Matthews Correlation Coefficient (MCC)", fontsize=12)
    ax.set_xlabel("Subject", fontsize=12)
    ax.set_title("Phase 2: Per-Subject Matthews Correlation Coefficient (MCC)", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(subjects, fontsize=11)
    ax.set_ylim(-0.3, 1.0)
    ax.legend(frameon=True, facecolor="white", edgecolor="none", loc="upper right")
    plt.tight_layout()
    fig.savefig(PLOTS_DIR / "per_subject_mcc_comparison.png")
    plt.close(fig)

    # --- PLOT 3: Distribution of Subject-Level Accuracy ---
    fig, ax = plt.subplots(figsize=(9, 6), dpi=300)
    acc_data = [np.array(sub_acc[m_id]) * 100 for m_id in model_ids]
    box = ax.boxplot(acc_data, tick_labels=[m["name"] for m in models], patch_artist=True)
    for patch, color in zip(box["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    # Scatter individual points
    for i, m_id in enumerate(model_ids):
        y_pts = np.array(sub_acc[m_id]) * 100
        x_pts = np.random.normal(i + 1, 0.04, size=len(y_pts))
        ax.scatter(x_pts, y_pts, color="black", alpha=0.7, zorder=3, s=25)

    ax.axhline(50, color="gray", linestyle="--", alpha=0.7, label="Chance (50%)")
    ax.set_ylabel("Accuracy (%)", fontsize=12)
    ax.set_title("Subject Accuracy Distribution Across Decoding Methods", fontsize=14, fontweight="bold")
    plt.xticks(rotation=15, ha="right", fontsize=10)
    plt.tight_layout()
    fig.savefig(PLOTS_DIR / "accuracy_distribution_boxplot.png")
    plt.close(fig)

    # --- PLOT 4: Subject-level Accuracy Change over Baseline ---
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=300)
    base_acc = np.array(sub_acc["baseline_csp_lda"]) * 100
    fbcsp_diff = np.array(sub_acc["fbcsp_lda"]) * 100 - base_acc
    mdm_diff = np.array(sub_acc["riemannian_mdm"]) * 100 - base_acc

    ax.bar(x - width / 2, fbcsp_diff, width, label="FBCSP - Baseline", color="#d95f02", alpha=0.85)
    ax.bar(x + width / 2, mdm_diff, width, label="Riemannian MDM - Baseline", color="#7570b3", alpha=0.85)
    ax.axhline(0, color="black", linestyle="-", linewidth=1)
    ax.set_ylabel("Accuracy Difference (% points)", fontsize=12)
    ax.set_xlabel("Subject", fontsize=12)
    ax.set_title("Per-Subject Accuracy Improvement over Phase 1 CSP+LDA Baseline", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(subjects, fontsize=11)
    ax.set_ylim(-20, 25)
    ax.legend(frameon=True, loc="upper right")
    plt.tight_layout()
    fig.savefig(PLOTS_DIR / "per_subject_improvement_over_baseline.png")
    plt.close(fig)

    print(f"Phase 2 plots successfully generated in {PLOTS_DIR.as_posix()}")


if __name__ == "__main__":
    generate_plots()
