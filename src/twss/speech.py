"""Lazy pyttsx3 speech, with a silent mode that never initializes audio."""

import sys
import threading


class Speaker:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._engine = None
        self._com = None
        self._owner_thread = None

    def speak(self, sentence: str | None) -> None:
        if not self.enabled or not sentence:
            return
        try:
            if self._owner_thread is not None and self._owner_thread != threading.get_ident():
                raise RuntimeError("Speaker must be used and closed on its creating thread.")
            if self._engine is None:
                if sys.platform == "win32" and self._com is None:
                    import pythoncom
                    pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
                    self._com = pythoncom
                self._owner_thread = threading.get_ident()
                import pyttsx3
                self._engine = pyttsx3.init()
            self._engine.say(sentence)
            self._engine.runAndWait()
        except Exception as exc:
            raise RuntimeError(f"Speech failed: {exc}. Use --no-audio for silent testing.") from exc

    def close(self) -> None:
        if self._owner_thread is not None and self._owner_thread != threading.get_ident():
            raise RuntimeError("Speaker must be closed on its creating thread.")
        try:
            if self._engine is not None:
                self._engine.stop()
        finally:
            # Release engine references before balancing this thread's COM initialization.
            self._engine = None
            if self._com is not None:
                self._com.CoUninitialize()
                self._com = None
            self._owner_thread = None
