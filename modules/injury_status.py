"""The ONE injury-status table.

Injury vocabulary used to be decided in more than ten places, each added when
one surface got a wrong label, and they disagreed: "Questionable" cost 0.25
weeks in the trade grader, a 0.85 play multiplier in projections, and was
"startable" in the roster logic; ``rankings.injury_level`` substring-matched
"ir" and "out" inside free text; ``player_value_trend`` kept a private set.

Every consumer now derives from the rows below. A row answers, for one Sleeper
designation:

* ``category``  healthy / minor / moderate / major (the severity bucket the
  valuation discounts and the UI severity use);
* ``ruled_out`` confirmed unavailable (a flat "Out", IR, PUP, NFI, suspended)
  as opposed to merely uncertain ("Doubtful");
* ``p_play``    probability the player plays his NEXT game;
* ``weeks_out`` expected weeks missed when no richer evidence exists (None =
  not a recovery window, e.g. a bare "Inactive" roster status);
* ``tone``      the UI colour family (see ``modules.injury_tone``).

The two availability numbers are the same fact stated twice, so for a
single-game designation ``weeks_out = 1 - p_play`` (Questionable: 0.85 plays,
0.15 weeks). Multi-week statuses carry documented defaults. None of the
play-probability priors can be backtested (Sleeper publishes no point-in-time
injury history); they are flagged ``calibrated=False``.

No import from rankings / trade code: this is the base layer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable

CATEGORY_RANK = {"healthy": 0, "minor": 1, "moderate": 2, "major": 3}

# --- category-level valuation factors ----------------------------------------
# What the market/valuation does with a severity bucket. These are valuation
# choices (not availability facts), kept here so the bucket and its factors
# cannot drift apart.
DYNASTY_VALUE_MULTIPLIER = {"major": 0.68, "moderate": 0.80, "minor": 0.95}
CURRENT_SEASON_MULTIPLIER = {"major": 0.42, "moderate": 0.72, "minor": 0.93}
RISK_SCORE = {"major": 2.0, "moderate": 1.0, "minor": 1.0}

# A game-time designation at or below this play probability reads as "likely out".
LIKELY_OUT_P_PLAY = 0.25

# An NFL reserve list keeps a player out at least four games.
RESERVE_MIN_GAMES_OUT = 4


@dataclass(frozen=True)
class StatusRow:
    key: str
    label: str
    category: str
    kind: str  # reserve | season_ending | suspended | inactive | out | game_time
    ruled_out: bool
    p_play: float
    weeks_out: float | None
    tone: str = "neutral"
    # Whole-word phrases matched anywhere in either field ("ir" is a token,
    # never a substring of another word).
    terms: tuple[str, ...] = ()
    # Whole-field exact spellings (abbreviations, roster statuses).
    aliases: tuple[str, ...] = ()
    # Exact normalized strings that get ``tone`` in the UI tone map.
    tone_keys: tuple[str, ...] = ()
    calibrated: bool = True
    designation: bool = True  # a real Sleeper designation worth showing


_QUESTIONABLE_P = 0.85
_DOUBTFUL_P = 0.15
_PROBABLE_P = 0.95

ROWS: tuple[StatusRow, ...] = (
    # Ordered most to least severe: the first row that matches wins.
    StatusRow(
        "season_ending", "Season-ending injury", "major", "season_ending", True, 0.0, 4.0,
        terms=("season-ending", "season ending", "out for season", "out for the season", "torn acl", "torn achilles"),
    ),
    StatusRow(
        "ir", "Injured Reserve", "major", "reserve", True, 0.0, 4.0, tone="danger",
        terms=("injured reserve", "ir", "reserve"),
        tone_keys=("ir", "injured reserve"),
    ),
    StatusRow(
        "pup", "Physically Unable to Perform", "major", "reserve", True, 0.0, 4.0, tone="danger",
        terms=("pup", "physically unable to perform"),
        tone_keys=("pup",),
    ),
    StatusRow(
        "nfi", "Non-Football Injury", "major", "reserve", True, 0.0, 4.0, tone="danger",
        terms=("nfi", "non-football injury", "non football injury"),
        tone_keys=("nfi", "non-football injury"),
    ),
    StatusRow(
        "suspended", "Suspended", "major", "suspended", True, 0.0, 3.0, tone="danger",
        aliases=("sus", "suspended", "suspension", "susp"),
        tone_keys=("sus", "susp", "suspended"),
    ),
    StatusRow(
        "inactive", "Inactive", "major", "inactive", True, 0.0, None, tone="danger",
        aliases=("inactive",), tone_keys=("inactive",),
    ),
    StatusRow(
        "practice_squad", "Practice Squad", "major", "inactive", True, 0.0, None,
        aliases=("practice squad",),
    ),
    StatusRow(
        "out", "Out", "moderate", "out", True, 0.0, 2.0, tone="danger",
        terms=("out",), aliases=("o",), tone_keys=("out", "o"),
    ),
    StatusRow(
        "dnr", "Did Not Report", "moderate", "out", True, 0.0, 2.0,
        terms=("dnr", "did not report"),
    ),
    StatusRow(
        "cov", "COVID-19 list", "moderate", "out", True, 0.0, 2.0, tone="danger",
        terms=("cov", "covid", "covid-19", "covid 19"), tone_keys=("covid", "covid-19"),
    ),
    StatusRow(
        "doubtful", "Doubtful", "moderate", "game_time", False, _DOUBTFUL_P, round(1 - _DOUBTFUL_P, 2),
        tone="danger", terms=("doubtful",), aliases=("d",), tone_keys=("doubtful", "d"), calibrated=False,
    ),
    StatusRow(
        "questionable", "Questionable", "minor", "game_time", False, _QUESTIONABLE_P, round(1 - _QUESTIONABLE_P, 2),
        tone="warning", terms=("questionable",), aliases=("q",), tone_keys=("questionable", "q"), calibrated=False,
    ),
    StatusRow(
        "day_to_day", "Day-to-day", "minor", "game_time", False, _QUESTIONABLE_P, round(1 - _QUESTIONABLE_P, 2),
        tone="warning", terms=("day-to-day", "day to day"), aliases=("dtd",),
        tone_keys=("day-to-day", "day to day", "dtd"), calibrated=False,
    ),
    StatusRow(
        "limited", "Limited", "minor", "game_time", False, _QUESTIONABLE_P, round(1 - _QUESTIONABLE_P, 2),
        terms=("limited",), calibrated=False,
    ),
    StatusRow(
        "probable", "Probable", "minor", "game_time", False, _PROBABLE_P, round(1 - _PROBABLE_P, 2),
        tone="warning", terms=("probable",), aliases=("p",), tone_keys=("probable", "p"), calibrated=False,
    ),
    StatusRow(
        "na", "Not Active", "healthy", "not_active", False, 1.0, 0.0,
        aliases=("na", "n/a"),
    ),
    StatusRow(
        "healthy", "Healthy", "healthy", "healthy", False, 1.0, 0.0, tone="success",
        aliases=("active", "healthy"), tone_keys=("active", "healthy"), designation=False,
    ),
)

ROWS_BY_KEY: dict[str, StatusRow] = {row.key: row for row in ROWS}

# Not in the table: Sleeper tags we do not know. Treated like a game-time
# designation (the conservative minor bucket), never as healthy.
UNKNOWN_DESIGNATION = StatusRow(
    "unknown", "", "minor", "game_time", False, _QUESTIONABLE_P, round(1 - _QUESTIONABLE_P, 2),
    calibrated=False, designation=False,
)

_HEALTHY_MARKERS = frozenset({"", "none", "nan", "null", "healthy", "active", "na", "n/a"})
_TOKEN = re.compile(r"[a-z0-9]+")
_TERM_TOKENS: dict[str, tuple[str, ...]] = {}


def _norm(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    return "" if text in {"nan", "none", "null"} else " ".join(text.split())


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(_TOKEN.findall(text))


def _contains_phrase(tokens: tuple[str, ...], phrase: tuple[str, ...]) -> bool:
    n = len(phrase)
    if n == 0 or n > len(tokens):
        return False
    return any(tokens[i : i + n] == phrase for i in range(len(tokens) - n + 1))


_ROW_PHRASES = {row.key: tuple(_tokens(t) for t in row.terms) for row in ROWS}


@dataclass(frozen=True)
class InjuryClass:
    row: StatusRow
    known: bool
    source: str  # "injury_status" | "status" | ""

    @property
    def category(self) -> str:
        return self.row.category

    @property
    def kind(self) -> str:
        return self.row.kind

    @property
    def ruled_out(self) -> bool:
        return self.row.ruled_out

    @property
    def suspended(self) -> bool:
        return self.row.kind == "suspended"

    @property
    def p_play(self) -> float:
        return self.row.p_play

    @property
    def weeks_out(self) -> float | None:
        return self.row.weeks_out


def _match(row: StatusRow, field: str, tokens: tuple[str, ...]) -> bool:
    if field in row.aliases:
        return True
    return any(_contains_phrase(tokens, phrase) for phrase in _ROW_PHRASES[row.key])


@lru_cache(maxsize=8192)
def _classify_cached(status: str, injury: str) -> InjuryClass:
    fields = (("injury_status", injury, _tokens(injury)), ("status", status, _tokens(status)))
    for row in ROWS:
        if row.category == "healthy":
            continue
        for source, field, tokens in fields:
            if field and _match(row, field, tokens):
                return InjuryClass(row, True, source)
    if injury and injury not in _HEALTHY_MARKERS:
        # A Sleeper injury tag we have no row for: never silently healthy.
        return InjuryClass(UNKNOWN_DESIGNATION, False, "injury_status")
    return InjuryClass(ROWS_BY_KEY["healthy"], True, "")


def classify(status: Any = "", injury_status: Any = "") -> InjuryClass:
    """Classify a (roster ``status``, Sleeper ``injury_status``) pair."""

    return _classify_cached(_norm(status), _norm(injury_status))


_DESIGNATION_LOOKUP: dict[str, StatusRow] = {}
for _r in ROWS:
    for _k in (_r.key, *_r.aliases, *(" ".join(t.lower().split()) for t in _r.terms)):
        _DESIGNATION_LOOKUP.setdefault(_k, _r)


def designation(value: Any = "") -> StatusRow | None:
    """The row for ONE raw designation string (whole-field match), else None.

    ``classify`` is for the (status, injury_status) pair; this is for a lone
    label such as an availability badge."""

    return _DESIGNATION_LOOKUP.get(_norm(value))


def category(status: Any = "", injury_status: Any = "") -> str:
    return classify(status, injury_status).category


def is_ruled_out(status: Any = "", injury_status: Any = "") -> bool:
    return classify(status, injury_status).ruled_out


def is_suspended(status: Any = "", injury_status: Any = "") -> bool:
    return classify(status, injury_status).suspended


def is_unavailable(status: Any = "", injury_status: Any = "") -> bool:
    """Confirmed out, or so unlikely to play that the next game is a write-off
    (Doubtful)."""

    cls = classify(status, injury_status)
    return cls.ruled_out or cls.p_play <= LIKELY_OUT_P_PLAY


def terms_for_kinds(kinds: Iterable[str]) -> frozenset[str]:
    """Every whole-field spelling (key, aliases, terms; lowercase) of rows of these kinds."""

    wanted = set(kinds)
    return frozenset(
        spelling for spelling, row in _DESIGNATION_LOOKUP.items() if row.kind in wanted and spelling
    )


def default_weeks_by_key() -> dict[str, float]:
    """Row key -> default expected weeks out, for every row with a recovery window."""

    return {row.key: row.weeks_out for row in ROWS if row.weeks_out and row.designation}


def tone(status: Any) -> str:
    """UI tone for ONE whole status string (exact match, never a substring)."""

    return TONE_BY_STATUS.get(" ".join(str(status if status is not None else "").strip().lower().replace("_", " ").split()), "neutral")


TONE_BY_STATUS: dict[str, str] = {}
for _row in ROWS:
    for _key in _row.tone_keys:
        TONE_BY_STATUS[_key] = _row.tone


def tone_keys() -> Iterable[str]:
    return TONE_BY_STATUS.keys()


# --- free-text injury notes ----------------------------------------------------
# The ONE reader for what an injury note / body-part string says about severity.
# It used to be a substring scan ("torn", "acl") that priced "MRI rules out a
# torn ACL" as season-ending. Matching is on whole tokens, per clause, with
# negation ("no", "rules out", "negative for", "avoided", ...), hedging
# ("possible", "suspected", "fears", ...) and an explicit "miss N weeks" read.


@dataclass(frozen=True)
class InjuryNoteRead:
    """What the notes say. season_ending and possibly_season_ending are exclusive."""

    season_ending: bool = False  # stated, unhedged, un-negated
    possibly_season_ending: bool = False  # a severe term that is hedged, or a bare tear/rupture
    surgery: bool = False
    weeks_low: float | None = None  # explicit "miss N-M weeks"
    weeks_high: float | None = None
    negated: tuple[str, ...] = ()  # severe terms the note explicitly rules out

    @property
    def weeks_mid(self) -> float | None:
        if self.weeks_low is None or self.weeks_high is None:
            return None
        return (self.weeks_low + self.weeks_high) / 2.0


_SEVERE_TERMS = frozenset({"acl", "achilles"})
_SEASON_PHRASES = (
    ("season", "ending"),
    ("out", "for", "the", "season"),
    ("out", "for", "season"),
    ("out", "for", "the", "year"),
    ("out", "for", "year"),
    ("rest", "of", "the", "season"),
    ("rest", "of", "season"),
    ("done", "for", "the", "season"),
    ("done", "for", "the", "year"),
)
_TEAR_TERMS = frozenset({"torn", "tore", "tear", "tears", "rupture", "ruptured", "ruptures"})
_MILD_MODIFIERS = frozenset({"partial", "partially", "minor", "slight", "mild", "small", "grade"})
# token -> None (negates alone) or the token that must follow it ("free agent" never negates).
_NEGATORS: dict[str, str | None] = {
    "no": None, "not": None, "without": None, "never": None, "neither": None, "nor": None,
    "avoid": None, "avoided": None, "avoids": None, "avoiding": None, "denies": None, "denied": None,
    "isnt": None, "wasnt": None, "doesnt": None, "didnt": None, "dont": None, "unlikely": None,
    "lacks": None, "excludes": None, "excluded": None,
    "negative": "for", "free": "of", "cleared": "of", "clear": "of",
    "rules": "out", "rule": "out", "ruled": "out", "ruling": "out",
}
_POST_NEGATORS = (("ruled", "out"), ("intact",), ("ok",), ("fine",))
_HEDGES = frozenset({
    "possible", "possibly", "potential", "potentially", "suspected", "suspect", "fear", "fears",
    "feared", "fearing", "concern", "concerns", "concerned", "worried", "worry", "may", "might",
    "could", "evaluate", "evaluated", "evaluation", "awaiting", "pending", "unconfirmed",
    "undergo", "undergoing", "undergoes", "tbd", "if", "whether", "likely", "appears", "apparent",
})
_CONFIRMS = frozenset({"confirmed", "confirms", "confirm", "diagnosed", "diagnosis", "revealed", "reveals", "showed", "shows"})
_CLAUSE_SPLIT = re.compile(r"[.;:!?,\n()]|\s[-–—]\s|\sbut\s|\showever\s|\sthough\s|\swhile\s")
_WEEKS = re.compile(r"(\d+(?:\.\d+)?)\s*(?:(?:-|–|to)\s*(\d+(?:\.\d+)?))?\s*(?:\+\s*)?weeks?\b")
_APOSTROPHE = re.compile(r"['’]")


def _clause_tokens(clause: str) -> tuple[str, ...]:
    return tuple(_TOKEN.findall(_APOSTROPHE.sub("", clause)))


def _negated(tokens: tuple[str, ...], start: int, end: int) -> bool:
    """Is the term at tokens[start:end] negated by a nearby cue in its clause?"""

    for i in range(max(0, start - 5), start):
        if tokens[i] not in _NEGATORS:
            continue
        need = _NEGATORS[tokens[i]]
        # A pair cue must be complete before the term: "ruled out for the season"
        # is not negation because "out" belongs to the term's own phrase.
        if need is None or (i + 1 < start and tokens[i + 1] == need):
            return True
    tail = tokens[end : end + 4]
    return any(_contains_phrase(tail, phrase) for phrase in _POST_NEGATORS)


def read_injury_notes(*texts: Any) -> InjuryNoteRead:
    """Severity evidence in free text (body part, notes, ...); never raises."""

    season_ending = possible = surgery = False
    negated: list[str] = []
    low = high = None
    for raw in texts:
        text = _norm(raw)
        if not text:
            continue
        for match in _WEEKS.finditer(text):
            a = float(match.group(1))
            b = float(match.group(2)) if match.group(2) else a
            lo, hi = (a, b) if a <= b else (b, a)
            low = lo if low is None else min(low, lo)
            high = hi if high is None else max(high, hi)
        for clause in _CLAUSE_SPLIT.split(text):
            tokens = _clause_tokens(clause)
            if not tokens:
                continue
            hedged = any(t in _HEDGES for t in tokens) and not any(t in _CONFIRMS for t in tokens)
            hits: list[tuple[str, int, int, bool]] = []  # (term, start, end, strong)
            for i, tok in enumerate(tokens):
                if tok in _SEVERE_TERMS:
                    hits.append((tok, i, i + 1, True))
                elif tok in _TEAR_TERMS:
                    around = tokens[max(0, i - 2) : i + 3]
                    mild = any(t in _MILD_MODIFIERS for t in tokens[max(0, i - 2) : i + 1])
                    # "torn ACL" is judged by the ACL token; a bare tear is only a weak signal.
                    if not mild and not any(t in _SEVERE_TERMS for t in around):
                        hits.append((tok, i, i + 1, False))
            for phrase in _SEASON_PHRASES:
                n = len(phrase)
                for i in range(len(tokens) - n + 1):
                    if tokens[i : i + n] == phrase:
                        hits.append((" ".join(phrase), i, i + n, True))
            for term, start, end, strong in hits:
                if _negated(tokens, start, end):
                    negated.append(term)
                elif strong and not hedged:
                    season_ending = True
                else:
                    possible = True
            for word in ("surgery", "surgical"):
                if word in tokens:
                    i = tokens.index(word)
                    if not _negated(tokens, i, i + 1):
                        surgery = True
    if season_ending:
        possible = False
    return InjuryNoteRead(season_ending, possible, surgery, low, high, tuple(dict.fromkeys(negated)))
