"""Windows COM lifetime regression checks without audible output."""
import unittest
from unittest.mock import Mock, patch
from src.twss.speech import Speaker


class SpeechTests(unittest.TestCase):
    def test_com_initialized_before_engine_and_balanced_once(self):
        com = Mock()
        calls = []
        com.CoInitializeEx.side_effect = lambda mode: calls.append("COM")
        with patch("src.twss.speech.sys.platform", "win32"), patch.dict("sys.modules", {"pythoncom": com}), patch("pyttsx3.init") as initialize:
            initialize.side_effect = lambda: (calls.append("engine") or Mock())
            speaker = Speaker()
            speaker.speak("Yes.")
            speaker.speak("No.")
            self.assertEqual(calls, ["COM", "engine"])
            speaker.close()
            speaker.close()
            com.CoUninitialize.assert_called_once()

    def test_failed_engine_initialization_can_be_cleaned_up(self):
        com = Mock()
        with patch("src.twss.speech.sys.platform", "win32"), patch.dict("sys.modules", {"pythoncom": com}), patch("pyttsx3.init", side_effect=RuntimeError("failure")):
            speaker = Speaker()
            with self.assertRaises(RuntimeError):
                speaker.speak("Yes.")
            speaker.close()
            com.CoUninitialize.assert_called_once()
