"""Riemannian geometry EEG classification pipelines (MDM & Tangent Space + LDA)."""

from pyriemann.classification import MDM
from pyriemann.estimation import Covariances
from pyriemann.tangentspace import TangentSpace
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.pipeline import Pipeline


def build_riemannian_mdm_pipeline(estimator: str = "lwf") -> Pipeline:
    """Return a scikit-learn Pipeline for Riemannian Minimum Distance to Mean (MDM).

    Pipeline stages:
    1. Covariances estimation (Ledoit-Wolf shrinkage)
    2. MDM classification under affine-invariant Riemannian metric
    """
    return Pipeline([
        ("cov", Covariances(estimator=estimator)),
        ("mdm", MDM(metric="riemann")),
    ])


def build_riemannian_tangent_space_pipeline(estimator: str = "lwf") -> Pipeline:
    """Return a scikit-learn Pipeline for Riemannian Tangent Space + LDA.

    Pipeline stages:
    1. Covariances estimation (Ledoit-Wolf shrinkage)
    2. Tangent Space projection at Riemannian geometric mean
    3. Linear Discriminant Analysis classification
    """
    return Pipeline([
        ("cov", Covariances(estimator=estimator)),
        ("ts", TangentSpace(metric="riemann")),
        ("lda", LinearDiscriminantAnalysis()),
    ])
