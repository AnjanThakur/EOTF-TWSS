"""Dataset adapters for hardware-independent EEG processing."""

from .srm import load_srm_dataset, SRMDatasetResult
from .physionet import load_physionet_adapter, PhysioNetAdapterResult

__all__ = [
    "load_srm_dataset",
    "SRMDatasetResult",
    "load_physionet_adapter",
    "PhysioNetAdapterResult",
]
