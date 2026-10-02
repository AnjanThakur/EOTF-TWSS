"""Filter Bank Common Spatial Pattern (FBCSP) implementation for multi-band EEG decoding."""

from pathlib import Path
from functools import partial
import mne
import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.feature_selection import SelectKBest, mutual_info_classif
from mne.decoding import CSP

from src.preprocessing.preprocess import load_eeg, extract_events
from src.models.train_csp_lda import CHANNELS, find_run, select_channels

DEFAULT_SUBBANDS = ((8.0, 12.0), (12.0, 16.0), (16.0, 20.0), (20.0, 24.0), (24.0, 30.0))


def load_subject_fbcsp(
    data_dir: str | Path,
    subject: str = "S001",
    runs: tuple[str, ...] = ("R04", "R08", "R12"),
    sub_bands: tuple[tuple[float, float], ...] = DEFAULT_SUBBANDS,
    channels: tuple[str, ...] = CHANNELS,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load continuous EEG, filter into sub-bands, epoch each band independently,

    and return sub-band trial array with shape (trials, n_bands, channels, samples),
    labels, and run groups.
    """
    data_dir = Path(data_dir)
    all_trials_by_band = []  # List of (n_bands, n_trials, n_channels, n_samples)
    all_labels = []
    all_groups = []

    for run in runs:
        edf_path = find_run(data_dir, run, subject)
        raw = select_channels(load_eeg(edf_path), channels)
        events, _ = extract_events(raw)

        band_epochs_data = []
        run_labels = None

        for l_freq, h_freq in sub_bands:
            filtered = raw.copy().filter(l_freq, h_freq, verbose=False)
            epochs = mne.Epochs(
                filtered,
                events,
                event_id={"left_hand": 1, "right_hand": 2},
                tmin=0.5,
                tmax=3.5,
                baseline=None,
                preload=True,
                proj=False,
                verbose=False,
            )
            X_band = epochs.get_data()  # (n_trials, n_channels, n_samples)
            if run_labels is None:
                run_labels = epochs.events[:, 2].copy()
            band_epochs_data.append(X_band)

        # Stack bands along axis 1 -> shape: (n_trials, n_bands, n_channels, n_samples)
        run_X = np.stack(band_epochs_data, axis=1)
        all_trials_by_band.append(run_X)
        all_labels.append(run_labels)
        all_groups.append(np.full(len(run_labels), run))

    X = np.concatenate(all_trials_by_band, axis=0)
    y = np.concatenate(all_labels, axis=0)
    groups = np.concatenate(all_groups, axis=0)
    return X, y, groups


class FBCSPPipeline(ClassifierMixin, BaseEstimator):
    """Filter Bank CSP Classifier with Mutual Information Feature Selection and LDA.

    Input X shape: (n_trials, n_bands, n_channels, n_samples)
    """

    def __init__(
        self,
        n_components_per_band: int = 2,
        n_features_to_select: int = 6,
        random_state: int | None = 0,
    ):
        self.n_components_per_band = n_components_per_band
        self.n_features_to_select = n_features_to_select
        self.random_state = random_state

        self.csps_ = []
        self.selector_ = None
        self.classifier_ = None
        self.classes_ = None

    def _extract_features(self, X: np.ndarray, fit: bool = False) -> np.ndarray:
        n_trials, n_bands, n_channels, n_samples = X.shape
        band_features = []

        for b in range(n_bands):
            X_b = X[:, b, :, :]
            if fit:
                csp = CSP(n_components=self.n_components_per_band)
                with mne.use_log_level("WARNING"):
                    feat_b = csp.fit_transform(X_b, self._y_fit)
                self.csps_.append(csp)
            else:
                csp = self.csps_[b]
                with mne.use_log_level("WARNING"):
                    feat_b = csp.transform(X_b)
            band_features.append(feat_b)

        return np.hstack(band_features)

    def fit(self, X: np.ndarray, y: np.ndarray):
        if X.ndim != 4:
            raise ValueError(f"Expected X with shape (trials, bands, channels, samples), got {X.shape}")
        self.classes_ = np.unique(y)
        self._y_fit = y
        self.csps_ = []

        # 1. Fit CSP per sub-band and extract log-variance features
        all_features = self._extract_features(X, fit=True)

        # 2. Fit Mutual Information Feature Selection on training features
        total_features = all_features.shape[1]
        k = min(self.n_features_to_select, total_features)
        self.selector_ = SelectKBest(
            score_func=partial(mutual_info_classif, random_state=self.random_state), k=k
        )
        selected_features = self.selector_.fit_transform(all_features, y)

        # 3. Fit LDA classifier on selected training features
        self.classifier_ = LinearDiscriminantAnalysis()
        self.classifier_.fit(selected_features, y)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        features = self._extract_features(X, fit=False)
        selected = self.selector_.transform(features)
        return self.classifier_.predict(selected)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        features = self._extract_features(X, fit=False)
        selected = self.selector_.transform(features)
        return self.classifier_.predict_proba(selected)
