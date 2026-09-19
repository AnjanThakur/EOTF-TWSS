"""Generate a sentence only for a recognized command word."""


def to_sentence(word: str | None) -> str | None:
    return {"YES": "Yes.", "NO": "No."}.get(word)
