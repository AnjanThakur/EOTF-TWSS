"""Communication actions are separate from the signal detector."""
from .config import WORDS, PHRASES


class MenuController:
    def __init__(self):
        self.index = 0
        self.armed = False
        self.last_selection = -float("inf")

    def pause(self):
        self.armed = False

    def accept(self, gesture):
        if not self.armed:
            return None
        if gesture.command == "NEXT":
            self.index = (self.index + 1) % len(WORDS)
            return dict(action="next", word=WORDS[self.index], timestamp=gesture.timestamp)
        if gesture.command == "SELECT" and gesture.timestamp - self.last_selection >= 2:
            self.last_selection = gesture.timestamp
            return dict(action="speak", word=WORDS[self.index], phrase=PHRASES[self.index], timestamp=gesture.timestamp)
        return None
