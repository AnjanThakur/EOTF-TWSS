"""Nonblocking, explicitly labelled recording instructions."""
from dataclasses import dataclass
import random


@dataclass(frozen=True)
class Step:
    label: str
    seconds: float
    title: str
    detail: str


def make_protocol(kind, seed=None, *, extended=False):
    if kind not in ("calibration", "validation", "quick"):
        raise ValueError("Unknown guided protocol.")
    quick = kind == "quick"
    short_validation = kind == "validation" and not extended
    if quick and extended:
        raise ValueError("Quick checks cannot use the extended protocol.")
    steps = [Step("PREPARE", 3 if quick or short_validation else 4, "Get comfortable", "Look ahead. Relax your jaw and shoulders.")]
    normal_seconds = 10 if quick or short_validation else 20 if kind == "calibration" else 60
    steps.append(Step("NORMAL", normal_seconds, "Relax and blink normally", "No deliberate double or triple blinks. Keep your jaw relaxed."))
    if kind == "validation":
        steps.append(Step("NORMAL", 5 if short_validation else 15, "Try ordinary face movements", "Look left and right, then say a short sentence. Do not make deliberate double or triple blinks."))
    repetitions = 3 if quick else 4 if short_validation else 20
    labels = ["SINGLE"] * 8 if kind == "calibration" else ["NEXT"] * repetitions + ["SELECT"] * repetitions
    if kind != "calibration":
        random.Random(seed).shuffle(labels)
    for label in labels:
        steps.append(Step("PREPARE", 1 if quick or short_validation else 2, "Get ready", "Wait for the next instruction. Relax your face."))
        count = {"SINGLE": "ONCE", "NEXT": "TWICE", "SELECT": "THREE TIMES"}[label]
        steps.append(Step(label, 4, f"Blink {count}", "Blink comfortably, about half a second apart. Then relax and wait."))
    steps.append(Step("FINISH", 2, "All done", "Relax while the last signals arrive."))
    return steps
