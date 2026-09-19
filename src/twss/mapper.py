"""Map accepted imagery decisions to words."""


def to_word(decision: str) -> str | None:
    return {"LEFT": "YES", "RIGHT": "NO"}.get(decision)
