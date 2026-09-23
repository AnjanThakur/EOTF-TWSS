import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
import os
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.signal import welch
from sklearn.decomposition import PCA

from src.datasets.srm import load_srm_dataset
from src.datasets.physionet import load_physionet_adapter
from src.features import EEGFeatureExtractor


def ensure_dirs(base_dir: Path) -> dict:
    """Create directory structure for Phase 3 results."""
    dirs = {
        "root": base_dir,
        "physionet": base_dir / "physionet",
        "srm": base_dir / "srm",
        "plots": base_dir / "plots",
        "plots_psd": base_dir / "plots" / "psd",
        "plots_band_power": base_dir / "plots" / "band_power",
        "plots_distributions": base_dir / "plots" / "distributions",
        "plots_pca": base_dir / "plots" / "pca",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return dirs


def plot_psd(X: np.ndarray, sfreq: float, dataset_name: str, output_path: Path):
    """Generate and save Welch PSD plot averaged across trials and channels."""
    fig, ax = plt.subplots(figsize=(8, 5))
    n_samples = X.shape[2]
    nperseg = min(n_samples, int(sfreq * 2.0))
    freqs, psd = welch(X, fs=sfreq, nperseg=nperseg, axis=-1)

    # Average over trials and channels
    psd_mean = np.mean(psd, axis=(0, 1))
    psd_std = np.std(psd, axis=(0, 1))

    ax.plot(freqs, psd_mean, label="Mean PSD", color="#1f77b4", linewidth=2)
    ax.fill_between(freqs, psd_mean - psd_std, psd_mean + psd_std, color="#1f77b4", alpha=0.2, label="±1 SD")

    ax.set_xlim(0, min(sfreq / 2.0, 50.0))
    ax.set_yscale("log")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Power Spectral Density (V²/Hz)")
    ax.set_title(f"EEG Power Spectral Density ({dataset_name})")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper right")
    plt.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_band_power(metadata_df: pd.DataFrame, feature_matrix: np.ndarray, dataset_name: str, output_path: Path):
    """Generate and save band power bar plot across Delta, Theta, Alpha, Beta, Gamma."""
    fig, ax = plt.subplots(figsize=(8, 5))
    bands = ["delta", "theta", "alpha", "beta", "gamma"]

    means = []
    stds = []

    for b in bands:
        rel_feat_mask = (metadata_df["feature_type"] == "spectral") & (metadata_df["frequency_band"] == b) & (metadata_df["feature_name"].str.contains("rel"))
        if rel_feat_mask.any():
            feat_idx = metadata_df.index[rel_feat_mask]
            vals = feature_matrix[:, feat_idx]
            means.append(np.mean(vals))
            stds.append(np.std(vals))
        else:
            means.append(0.0)
            stds.append(0.0)

    colors = ["#2ca02c", "#ff7f0e", "#1f77b4", "#d62728", "#9467bd"]
    ax.bar(bands, means, yerr=stds, capsize=5, color=colors, alpha=0.85, edgecolor="black")
    ax.set_xlabel("Frequency Band")
    ax.set_ylabel("Mean Relative Power")
    ax.set_title(f"Relative Band-Power Distribution ({dataset_name})")
    ax.grid(True, linestyle="--", alpha=0.4, axis="y")
    plt.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_feature_distributions(feature_df: pd.DataFrame, dataset_name: str, output_path: Path):
    """Generate histogram distribution plots for selected representative features."""
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    cols = [c for c in feature_df.columns if "rms" in c or "std" in c or "spatial_variance" in c][:3]

    colors = ["#1f77b4", "#ff7f0e", "#2ca02c"]
    for idx, col in enumerate(cols):
        ax = axes[idx]
        ax.hist(feature_df[col], bins=15, color=colors[idx % len(colors)], alpha=0.7, edgecolor="black")
        ax.set_title(col, fontsize=10)
        ax.set_xlabel("Value")
        ax.set_ylabel("Count")
        ax.grid(True, linestyle="--", alpha=0.4)

    plt.suptitle(f"Selected Feature Distributions ({dataset_name})", fontsize=12)
    plt.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_pca(features: np.ndarray, labels: np.ndarray, dataset_name: str, output_path: Path):
    """Generate 2D PCA scatter plot of high-dimensional EEG feature space."""
    fig, ax = plt.subplots(figsize=(7, 6))
    pca = PCA(n_components=2)
    embedding = pca.fit_transform(features)

    var_exp = pca.explained_variance_ratio_

    if labels is not None and len(np.unique(labels)) > 1:
        unique_labels = np.unique(labels)
        colors = ["#1f77b4", "#d62728"]
        label_names = {1: "LEFT", 2: "RIGHT"}
        for lbl in unique_labels:
            mask = labels == lbl
            ax.scatter(
                embedding[mask, 0],
                embedding[mask, 1],
                label=label_names.get(lbl, f"Class {lbl}"),
                color=colors[(lbl - 1) % len(colors)],
                alpha=0.8,
                edgecolors="w",
                s=60,
            )
        ax.legend(title="Imagery Class")
    else:
        ax.scatter(
            embedding[:, 0],
            embedding[:, 1],
            color="#2ca02c",
            alpha=0.7,
            edgecolors="w",
            s=50,
            label="SRM Windows",
        )
        ax.legend(loc="upper right")

    ax.set_xlabel(f"PCA Component 1 ({var_exp[0]:.1%} variance)")
    ax.set_ylabel(f"PCA Component 2 ({var_exp[1]:.1%} variance)")
    ax.set_title(f"EEG Feature Space — 2D PCA Projection ({dataset_name})\n(Exploratory representation; not command intent)")
    ax.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def run_phase3_analysis():
    """Execute complete Phase 3 representation pipeline on SRM and PhysioNet datasets."""
    project_root = Path(__file__).resolve().parents[1]
    base_dir = project_root / "results" / "phase3"
    dirs = ensure_dirs(base_dir)

    print("=== Phase 3: Hardware-Independent EEG Representation Analysis ===")
    extractor = EEGFeatureExtractor()

    # 1. Process SRM Resting-State Dataset
    print("\n[1/2] Loading SRM Dataset (ds003775)...")
    srm_res = load_srm_dataset(
        dataset_dir=project_root / "data" / "srm" / "ds003775",
        max_subjects=5,
        window_duration=2.0,
    )
    print(f"  Loaded SRM: {srm_res.X.shape[0]} windows, {srm_res.X.shape[1]} channels, {srm_res.X.shape[2]} samples @ {srm_res.sampling_rate} Hz")

    srm_fv = extractor.transform(srm_res.X, sampling_rate=srm_res.sampling_rate, channel_names=srm_res.channel_names)
    print(f"  Extracted SRM features shape: {srm_fv.features.shape}")

    srm_df = pd.DataFrame(srm_fv.features, columns=srm_fv.feature_names)
    srm_df.to_csv(dirs["srm"] / "features.csv", index=False)

    srm_summary = {
        "dataset": "SRM Resting-State EEG (ds003775)",
        "subjects_processed": srm_res.n_subjects,
        "recordings_processed": srm_res.n_recordings,
        "total_windows": int(srm_res.X.shape[0]),
        "channels": len(srm_res.channel_names),
        "sampling_frequency_hz": srm_res.sampling_rate,
        "window_duration_sec": srm_res.window_duration_sec,
        "total_features": int(srm_fv.features.shape[1]),
    }
    with open(dirs["srm"] / "summary.json", "w") as f:
        json.dump(srm_summary, f, indent=2)

    # 2. Process PhysioNet Left/Right Motor Imagery Dataset
    print("\n[2/2] Loading PhysioNet Dataset (S001)...")
    pn_res = load_physionet_adapter(data_dir=project_root / "data", subject_id="S001")
    print(f"  Loaded PhysioNet S001: {pn_res.X.shape[0]} trials, {pn_res.X.shape[1]} channels, {pn_res.X.shape[2]} samples @ {pn_res.sampling_rate} Hz")

    pn_fv = extractor.transform(pn_res.X, sampling_rate=pn_res.sampling_rate, channel_names=pn_res.channel_names)
    print(f"  Extracted PhysioNet features shape: {pn_fv.features.shape}")

    pn_df = pd.DataFrame(pn_fv.features, columns=pn_fv.feature_names)
    pn_df["label"] = pn_res.y
    pn_df.to_csv(dirs["physionet"] / "features.csv", index=False)

    pn_summary = {
        "dataset": "PhysioNet Motor Movement/Imagery (S001 R04/R08/R12)",
        "subject_id": pn_res.subject_id,
        "total_trials": int(pn_res.X.shape[0]),
        "channels": len(pn_res.channel_names),
        "channel_names": pn_res.channel_names,
        "sampling_frequency_hz": pn_res.sampling_rate,
        "epoch_duration_sec": 3.0,
        "total_features": int(pn_fv.features.shape[1]),
    }
    with open(dirs["physionet"] / "summary.json", "w") as f:
        json.dump(pn_summary, f, indent=2)

    # 3. Save Feature Metadata
    srm_fv.metadata.to_json(dirs["root"] / "feature_metadata.json", orient="records", indent=2)

    # 4. Save Overall Dataset Summary
    dataset_summary = {
        "phase": "Phase 3 — Hardware-Independent EEG Representation",
        "srm": srm_summary,
        "physionet": pn_summary,
        "feature_counts": {
            "srm_total_features": int(srm_fv.features.shape[1]),
            "physionet_total_features": int(pn_fv.features.shape[1]),
            "temporal_per_channel": 5,
            "spectral_per_channel": 10,
            "spatial_per_channel": 2,
        },
    }
    with open(dirs["root"] / "dataset_summary.json", "w") as f:
        json.dump(dataset_summary, f, indent=2)

    # 5. Generate Visualizations
    print("\nGenerating Phase 3 Visualizations...")
    plot_psd(srm_res.X, srm_res.sampling_rate, "SRM EEG (ds003775)", dirs["plots_psd"] / "srm_psd.png")
    plot_psd(pn_res.X, pn_res.sampling_rate, "PhysioNet S001", dirs["plots_psd"] / "physionet_psd.png")

    plot_band_power(srm_fv.metadata, srm_fv.features, "SRM EEG", dirs["plots_band_power"] / "srm_band_power.png")
    plot_band_power(pn_fv.metadata, pn_fv.features, "PhysioNet S001", dirs["plots_band_power"] / "physionet_band_power.png")

    plot_feature_distributions(srm_df, "SRM EEG", dirs["plots_distributions"] / "srm_feature_distributions.png")
    plot_feature_distributions(pn_df, "PhysioNet S001", dirs["plots_distributions"] / "physionet_feature_distributions.png")

    plot_pca(srm_fv.features, None, "SRM EEG", dirs["plots_pca"] / "srm_pca.png")
    plot_pca(pn_fv.features, pn_res.y, "PhysioNet S001", dirs["plots_pca"] / "physionet_pca.png")

    print(f"\nPhase 3 analysis completed successfully! All artifacts saved to:\n  {dirs['root'].as_posix()}")


if __name__ == "__main__":
    run_phase3_analysis()
