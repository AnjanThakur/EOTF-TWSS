"""Versioned, validated personal detection profiles."""
from dataclasses import asdict, dataclass, field
import json
import math
import os
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[1]
DATA_HOME = Path(os.environ.get("BLINK_EMG_HOME", str(ROOT if (ROOT / "pyproject.toml").exists()
                                                        else Path.home() / "blink_emg"))).expanduser().resolve()
WORDS = ("Water", "Food", "Help", "Yes", "No", "Pain")
PHRASES = ("I need water.", "I would like food.", "Please help me.", "Yes.", "No.", "I am in pain.")


@dataclass
class Profile:
    channel: int
    threshold: float
    sample_rate: float
    source_key: str
    noise_level: float
    blink_level: float
    polarity: int = 1
    group_gap: float = 0.80
    release_ratio: float = 0.45
    min_width: float = 0.035
    max_width: float = 0.65
    settle_seconds: float = 0.08
    refractory: float = 0.18
    version: int = 1
    profile_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    calibration: dict = field(default_factory=dict)
    validation: dict = field(default_factory=dict)

    def __post_init__(self):
        if (self.version != 1 or type(self.channel) is not int or not 0 <= self.channel < 6
                or type(self.polarity) is not int or self.polarity not in (-1, 1)):
            raise ValueError("Unsupported profile version or channel.")
        numeric = (self.threshold, self.sample_rate, self.noise_level, self.blink_level,
                   self.group_gap, self.release_ratio, self.min_width, self.max_width,
                   self.settle_seconds, self.refractory)
        if not all(math.isfinite(x) and x > 0 for x in numeric):
            raise ValueError("Profile numbers must be positive and finite.")
        if not (80 <= self.sample_rate <= 2000 and 0.4 <= self.group_gap <= 1.5
                and 0.1 <= self.release_ratio <= 0.8
                and self.min_width < self.max_width <= 1.2
                and 0.02 <= self.settle_seconds <= 0.2
                and 0.1 <= self.refractory <= 0.5):
            raise ValueError("Profile timing or sampling rate is outside supported limits.")
        if not self.source_key or not self.profile_id:
            raise ValueError("Profile must identify its source and calibration.")

    def to_dict(self):
        return asdict(self)

    def save(self, path):
        atomic_json(path, self.to_dict())

    @classmethod
    def load(cls, path):
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, allow_nan=False)
            handle.flush()
            import os
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
