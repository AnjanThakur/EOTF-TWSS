import queue
import sys
import threading
import types
import unittest
from unittest.mock import patch

from blink_emg_app.protocol import make_protocol
from blink_emg_app.speech import SpeechWorker


class ProtocolTests(unittest.TestCase):
    def test_calibration_and_two_fresh_test_sizes(self):
        calibration = make_protocol("calibration", seed=4)
        short = make_protocol("validation", seed=4)
        quick = make_protocol("quick", seed=4)
        long = make_protocol("validation", seed=4, extended=True)
        self.assertEqual(sum(s.seconds for s in calibration), 74)
        self.assertEqual(sum(s.seconds for s in quick), 45)
        self.assertEqual(sum(s.label == "NEXT" for s in quick), 3)
        self.assertEqual(sum(s.label == "SELECT" for s in quick), 3)
        self.assertEqual(sum(s.seconds for s in quick if s.label == "NORMAL"), 10)
        self.assertEqual(sum(s.label == "SINGLE" for s in calibration), 8)
        self.assertEqual(sum(s.seconds for s in short), 60)
        self.assertEqual(sum(s.label == "NEXT" for s in short), 4)
        self.assertEqual(sum(s.label == "SELECT" for s in short), 4)
        self.assertEqual(sum(s.seconds for s in short if s.label == "NORMAL"), 15)
        self.assertEqual(sum(s.label == "NEXT" for s in long), 20)
        self.assertEqual(sum(s.label == "SELECT" for s in long), 20)
        self.assertEqual(sum(s.seconds for s in long), 321)
        with self.assertRaises(ValueError):
            make_protocol("unknown")
        with self.assertRaises(ValueError):
            make_protocol("quick", extended=True)


class SpeechTests(unittest.TestCase):
    def test_worker_owns_engine_and_cancels_queued_phrases(self):
        entered = threading.Event()
        release = threading.Event()
        calls = []

        class Engine:
            def speak(self, text):
                calls.append((text, threading.get_ident()))
                entered.set()
                release.wait(timeout=2)
            def close(self):
                calls.append(("stop", threading.get_ident()))

        def create():
            calls.append(("create", threading.get_ident()))
            return Engine()

        com = types.SimpleNamespace(CoInitialize=lambda: None, CoUninitialize=lambda: None)
        with patch.dict(sys.modules, {"pythoncom": com}), patch("blink_emg_app.speech.create_speaker", side_effect=create):
            speaker = SpeechWorker()
            try:
                self.assertTrue(speaker.say("First phrase"))
                self.assertTrue(entered.wait(timeout=2))
                self.assertTrue(speaker.say("Should be cancelled"))
                self.assertFalse(speaker.say("Queue is full"))
                speaker.cancel_pending()
                release.set()
                self.assertEqual(speaker.results.get(timeout=2), ("speaking", "First phrase"))
                self.assertEqual(speaker.results.get(timeout=2), ("spoken", "First phrase"))
            finally:
                release.set()
                speaker.close()
                speaker.thread.join(timeout=2)
            self.assertFalse(speaker.thread.is_alive())
        self.assertNotIn("Should be cancelled", [text for text, _ in calls])
        self.assertTrue(all(thread != threading.get_ident() for _, thread in calls))

    def test_backend_failure_reports_error_and_does_not_retry_forever(self):
        def fail():
            raise RuntimeError("No voice installed")
        com = types.SimpleNamespace(CoInitialize=lambda: None, CoUninitialize=lambda: None)
        with patch.dict(sys.modules, {"pythoncom": com}), patch("blink_emg_app.speech.create_speaker", side_effect=fail):
            speaker = SpeechWorker()
            speaker.say("Test")
            kind, message = speaker.results.get(timeout=2)
            speaker.thread.join(timeout=2)
            self.assertEqual(kind, "error")
            self.assertIn("No voice installed", message)
            self.assertFalse(speaker.say("Another test"))

    def test_windows_speech_waits_for_each_native_utterance_on_its_com_thread(self):
        entered = threading.Event()
        release = threading.Event()
        calls = []

        class Voice:
            def Speak(self, phrase, flags):
                calls.append((phrase, flags, threading.get_ident()))
                entered.set()
                if not release.wait(timeout=2):
                    raise RuntimeError("Test did not release native speech")

        voice = Voice()
        client = types.SimpleNamespace(Dispatch=lambda name: voice)
        com = types.SimpleNamespace(CoInitialize=lambda: calls.append(("init", threading.get_ident())),
                                    CoUninitialize=lambda: calls.append(("uninit", threading.get_ident())))
        modules = {"pythoncom": com, "win32com": types.SimpleNamespace(client=client), "win32com.client": client}
        with patch.dict(sys.modules, modules), patch("blink_emg_app.speech.sys.platform", "win32"):
            speaker = SpeechWorker()
            try:
                for phrase in ("First sentence", "Second sentence", "Third sentence"):
                    entered.clear()
                    release.clear()
                    self.assertTrue(speaker.say(phrase))
                    self.assertEqual(speaker.results.get(timeout=2), ("speaking", phrase))
                    self.assertTrue(entered.wait(timeout=2))
                    self.assertTrue(speaker.results.empty(), "Completion must wait for native Speak to return")
                    release.set()
                    self.assertEqual(speaker.results.get(timeout=2), ("spoken", phrase))
            finally:
                release.set()
                speaker.close()
                speaker.thread.join(timeout=2)
        utterances = [call for call in calls if len(call) == 3]
        self.assertEqual([call[:2] for call in utterances], [("First sentence", 0), ("Second sentence", 0), ("Third sentence", 0)])
        self.assertEqual(voice.Volume, 100)
        self.assertEqual(voice.Rate, -1)
        self.assertEqual(calls[0][0], "init")
        self.assertEqual(calls[-1][0], "uninit")
        self.assertTrue(all(call[-1] != threading.get_ident() for call in calls))


if __name__ == "__main__":
    unittest.main()
