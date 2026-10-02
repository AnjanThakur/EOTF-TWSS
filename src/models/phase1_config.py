"""Validate frozen settings instead of silently ignoring edited config values."""
from pathlib import Path
import yaml
from src.models.train_csp_lda import CHANNELS, RUNS


def validate_runs(runs):
    if len(runs) != 3 or len(set(runs)) != 3 or set(runs) != set(RUNS):
        raise ValueError("Expected the three distinct runs R04, R08, R12.")


def validate_preprocessing(config, phase=1):
    fixed = {"channels": list(CHANNELS), "epoch": [0.5, 3.5],
             "label_mapping": {"T1": 1, "T2": 2, "LEFT": 1, "RIGHT": 2}}
    if phase == 1:
        fixed.update({"filter": [8, 30], "csp_components": 4, "classifier": "LDA"})
    for key, expected in fixed.items():
        if config.get(key) != expected:
            raise ValueError(f"{key} differs from the frozen preprocessing/model settings: {expected}")


def load_phase1_config(path):
    config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    validate_preprocessing(config)
    validate_runs(config["runs"])
    if not config.get("subjects") or len(set(config["subjects"])) != len(config["subjects"]):
        raise ValueError("subjects must be nonempty and unique.")
    return config
