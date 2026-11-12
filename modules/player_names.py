"""One player-name normalizer.

Six modules each carried their own ``normalize_*name`` with different rules
(accents, apostrophes, suffixes, spacing). This is the single implementation;
the old entry points delegate here.

``normalize_player_name`` returns space-separated tokens. ``player_name_key``
is the same thing with the spaces removed (the market-join key). Both are
accent-, case-, punctuation- and generational-suffix-insensitive.

``loose_name_key`` additionally folds common given-name nicknames
(Kenny/Kenneth). It is only ever a last-resort fallback for joins and callers
must log when it is the reason two records matched.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

GENERATIONAL_SUFFIXES = frozenset({"jr", "sr", "ii", "iii", "iv", "v"})
# Apostrophes and periods join the letters around them ("De'Von" == "DeVon",
# "A.J." == "AJ"); hyphens and whitespace separate tokens.
_JOINING_PUNCTUATION = re.compile(r"[\'‘’ʼ`.]")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Given-name nicknames -> canonical form. Deliberately small and unambiguous.
NICKNAMES = {
    "kenny": "kenneth", "ken": "kenneth",
    "mike": "michael", "mikey": "michael",
    "matt": "matthew", "mattie": "matthew",
    "chris": "christopher", "topher": "christopher",
    "nick": "nicholas", "nicky": "nicholas",
    "will": "william", "willie": "william", "bill": "william", "billy": "william",
    "bob": "robert", "bobby": "robert", "rob": "robert", "robbie": "robert",
    "jim": "james", "jimmy": "james", "jamie": "james",
    "joe": "joseph", "joey": "joseph",
    "tom": "thomas", "tommy": "thomas",
    "dave": "david", "davey": "david",
    "dan": "daniel", "danny": "daniel",
    "tony": "anthony",
    "rick": "richard", "ricky": "richard", "rich": "richard", "dick": "richard",
    "greg": "gregory", "jeff": "jeffrey", "steve": "steven", "stevie": "steven",
    "zach": "zachary", "zack": "zachary", "zac": "zachary",
    "alex": "alexander", "andy": "andrew", "drew": "andrew",
    "ben": "benjamin", "benny": "benjamin", "sam": "samuel", "sammy": "samuel",
    "tim": "timothy", "timmy": "timothy", "ed": "edward", "eddie": "edward", "ted": "edward",
    "charlie": "charles", "chuck": "charles", "pat": "patrick", "pete": "peter",
    "josh": "joshua", "jon": "jonathan", "johnny": "john", "jack": "john",
    "cam": "cameron", "jake": "jacob", "luke": "lucas",
    "tj": "tj", "aj": "aj",
}


def normalize_player_name(name: Any) -> str:
    """Canonical spaced name: ``"Kenneth Walker III"`` -> ``"kenneth walker"``."""

    if name is None:
        return ""
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold().strip()
    text = _JOINING_PUNCTUATION.sub("", text)
    tokens = _NON_ALNUM.sub(" ", text).split()
    # A lone token that looks like a suffix ("V", "Jr") is a name, not a suffix.
    while len(tokens) > 1 and tokens[-1] in GENERATIONAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def player_name_key(name: Any) -> str:
    """Space-free join key (``"ajbrown"``)."""

    return normalize_player_name(name).replace(" ", "")


def loose_name_key(name: Any) -> str:
    """``player_name_key`` with the first token folded through ``NICKNAMES``."""

    tokens = normalize_player_name(name).split()
    if len(tokens) > 1:
        tokens[0] = NICKNAMES.get(tokens[0], tokens[0])
    return "".join(tokens)
