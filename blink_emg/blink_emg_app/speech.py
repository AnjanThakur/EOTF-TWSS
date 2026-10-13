"""One local worker owns native Windows speech or a pyttsx3 fallback."""
import queue
import sys
import threading


class WindowsSpeech:
    def __init__(self):
        import win32com.client
        self.voice = win32com.client.Dispatch("SAPI.SpVoice")
        self.voice.Rate = -1
        self.voice.Volume = 100

    def speak(self, phrase):
        # SVSFDefault (0) is synchronous: it returns after this utterance.
        # Only the speech worker blocks, never Tk or signal acquisition. This
        # avoids the reused pyttsx3 event loop's premature end notifications.
        self.voice.Speak(phrase, 0)

    def close(self):
        self.voice = None


class Pyttsx3Speech:
    def __init__(self):
        import pyttsx3
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", 155)
        self.engine.setProperty("volume", 1.0)

    def speak(self, phrase):
        self.engine.say(phrase)
        self.engine.runAndWait()

    def close(self):
        self.engine.stop()
        self.engine = None


def create_speaker():
    return WindowsSpeech() if sys.platform == "win32" else Pyttsx3Speech()


class SpeechWorker:
    def __init__(self):
        self.requests = queue.Queue(maxsize=1)
        self.results = queue.Queue()
        self.stop_event = threading.Event()
        self.generation = 0
        self.thread = None

    def say(self, phrase):
        if self.stop_event.is_set():
            return False
        if self.thread is None:
            self.thread = threading.Thread(target=self._run, daemon=True, name="blink-local-speech")
            self.thread.start()
        try:
            self.requests.put_nowait((self.generation, phrase))
            return True
        except queue.Full:
            return False

    def cancel_pending(self):
        self.generation += 1
        try:
            while True:
                self.requests.get_nowait()
        except queue.Empty:
            pass

    def close(self):
        self.cancel_pending()
        self.stop_event.set()

    def _run(self):
        engine = com = None
        try:
            if sys.platform == "win32":
                import pythoncom
                pythoncom.CoInitialize()
                com = pythoncom
            engine = create_speaker()
            while not self.stop_event.is_set():
                try:
                    generation, phrase = self.requests.get(timeout=0.15)
                except queue.Empty:
                    continue
                if generation != self.generation:
                    continue
                self.results.put(("speaking", phrase))
                engine.speak(phrase)
                self.results.put(("spoken", phrase))
        except Exception as exc:
            self.results.put(("error", f"Speech is unavailable: {exc}. Check Windows sound and installed voices."))
        finally:
            try:
                if engine:
                    engine.close()
            finally:
                engine = None
                if com:
                    com.CoUninitialize()
                self.stop_event.set()
