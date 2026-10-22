"""contains_phrase got a substring pre-check, a compiled-pattern cache and a
remembered lowercase haystack; results must equal the original implementation."""

import random
import re

from modules import news_signal


def _reference(text, phrase):
    phrase = str(phrase or "").lower().strip()
    if not phrase:
        return False
    haystack = str(text or "").lower()
    if " " in phrase or "-" in phrase:
        return phrase in haystack
    return re.search(rf"\b{re.escape(phrase)}\b", haystack) is not None


WORDS = ["Jefferson", "jeff", "Chase", "chase's", "A.J.", "Brown", "NE", "ne", "new england", "kelce", "x-ray", "49ers", "Mc'Caffrey", ""]


def test_matches_reference_on_random_texts_and_phrases():
    rng = random.Random(7)
    for _ in range(3000):
        text = " ".join(rng.choice(WORDS + ["the", "a", "ruled out", "Jefferson,", "(chase)", "NEw"]) for _ in range(rng.randrange(0, 14)))
        phrase = rng.choice(WORDS + ["ruled out", " Chase ", "BROWN", "ne.", "[x]", "a.j."])
        assert news_signal.contains_phrase(text, phrase) == _reference(text, phrase), (text, phrase)


def test_non_string_and_repeated_haystack_inputs():
    for text in (None, 12, ["x"], b"bytes"):
        for phrase in ("x", "12", None, ""):
            assert news_signal.contains_phrase(text, phrase) == _reference(text, phrase)
    big = "Justin Jefferson was ruled OUT. " * 50
    assert news_signal.contains_phrase(big, "jefferson") is True
    assert news_signal.contains_phrase(big, "chase") is False
    changed = big + " Chase"
    assert news_signal.contains_phrase(changed, "chase") is True
    assert news_signal.contains_phrase(big, "chase") is False
