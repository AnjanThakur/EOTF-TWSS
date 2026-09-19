"""Source-independent orchestration for one command at a time."""

from collections.abc import Iterable
from dataclasses import dataclass

from src.realtime.inference import predict_trial
from src.realtime.trial import Prediction, Trial
from src.twss.mapper import to_word
from src.twss.sentence import to_sentence


@dataclass(frozen=True)
class CommandResult:
    trial: Trial
    prediction: Prediction
    word: str | None
    sentence: str | None


class CommandController:
    """Accept any iterable of preprocessed Trial objects, including future hardware."""

    def __init__(self, trials: Iterable[Trial], model):
        self.trials = iter(trials)
        self.model = model
        self.latest = None
        self.processed = 0
        self.exhausted = False

    def process_next(self, threshold: float = 0.7) -> CommandResult:
        # Clear the previous command before acquisition so errors cannot leave it speakable.
        self.latest = None
        try:
            trial = next(self.trials)
        except StopIteration:
            self.exhausted = True
            raise
        self.latest = self._process(trial, threshold)
        self.processed += 1
        return self.latest

    def _process(self, trial: Trial, threshold: float) -> CommandResult:
        prediction = predict_trial(self.model, trial, threshold)
        word = to_word(prediction.decision)
        return CommandResult(trial, prediction, word, to_sentence(word))

    def refresh_threshold(self, threshold: float) -> None:
        """Recheck the displayed trial without consuming another trial."""
        if self.latest is not None:
            trial = self.latest.trial
            self.latest = None
            self.latest = self._process(trial, threshold)

    def speak_latest(self, speaker) -> bool:
        if self.latest is None or self.latest.sentence is None:
            return False
        speaker.speak(self.latest.sentence)
        return True
