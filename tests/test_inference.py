"""Contract and confidence-gate checks; run with unittest discovery."""

import contextlib
import io
import unittest
from unittest.mock import Mock, patch

import numpy as np
from src.realtime.demo import run_demo
from src.realtime.inference import predict_trial
from src.realtime.trial import Trial
from src.twss.speech import Speaker


class InferenceTests(unittest.TestCase):
    def setUp(self):
        self.trial = Trial(np.zeros((6, 481)), actual_label=2)
        self.model = Mock()
        self.model.classes_ = np.array([2, 1])
        self.model.predict.return_value = np.array([1])
        self.model.predict_proba.return_value = np.array([[0.2, 0.8]])

    def test_probability_uses_class_order_and_threshold_boundary(self):
        result = predict_trial(self.model, self.trial, threshold=0.8)
        self.assertEqual((result.predicted_class, result.predicted_label), (1, "LEFT"))
        self.assertEqual(result.confidence, 0.8)
        self.assertEqual(result.actual_label, 2)
        self.assertEqual(result.decision, "LEFT")
        self.assertEqual(self.model.predict.call_args.args[0].shape, (1, 6, 481))

    def test_unknown_never_speaks(self):
        speaker = Mock()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            run_demo([self.trial], self.model, speaker, threshold=0.9)
        speaker.speak.assert_not_called()
        self.assertIn("Decision: UNKNOWN", output.getvalue())
        self.assertIn("Sentence: (none)", output.getvalue())

    def test_both_command_sentences(self):
        for label, sentence in [(1, "Yes."), (2, "No.")]:
            self.model.predict.return_value = np.array([label])
            self.model.predict_proba.return_value = np.array([[0.8, 0.2] if label == 2 else [0.2, 0.8]])
            speaker = Mock()
            with contextlib.redirect_stdout(io.StringIO()):
                run_demo([self.trial], self.model, speaker, threshold=0.7)
            speaker.speak.assert_called_once_with(sentence)

    def test_no_probability_is_unknown(self):
        model = Mock(spec=["predict"])
        model.predict.return_value = np.array([1])
        result = predict_trial(model, self.trial, threshold=0)
        self.assertIsNone(result.confidence)
        self.assertEqual(result.decision, "UNKNOWN")

    def test_invalid_input_and_threshold(self):
        for threshold in [-0.1, 1.1, float("nan")]:
            with self.assertRaises(ValueError):
                predict_trial(self.model, self.trial, threshold)
        with self.assertRaises(ValueError):
            predict_trial(self.model, Trial(np.zeros((6, 480))))

    def test_audio_disabled_and_enabled_engine_calls(self):
        with patch("pyttsx3.init") as initialize:
            Speaker(enabled=False).speak("Yes.")
            initialize.assert_not_called()
            speaker = Speaker()
            speaker.speak(None)
            initialize.assert_not_called()
            speaker.speak("Yes.")
            speaker.speak("No.")
            initialize.assert_called_once()
            self.assertEqual(initialize.return_value.runAndWait.call_count, 2)
            speaker.close()
            initialize.return_value.stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
