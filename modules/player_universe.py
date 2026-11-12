"""Player universe, phase 1: ages from birth dates and an explicit lifecycle state.

Two ideas that used to be scattered ad hoc rules:

* **Age** is derived from ``birth_date`` on the clock date. Sleeper's ``age`` is
  frozen for non-active records (612 of 791 teamless pool rows were off by 1+
  years), and it was feeding the age curve and the stale free-agent rules for
  exactly the rows those rules are meant to police. Sleeper's value stays as the
  fallback when no birth date exists.
* **Lifecycle state** is one explicit, data-derived classification per player
  (``LIFECYCLE_STATES``) with named predicates per surface. Nothing is removed
  from the pool by this module; rows are classified, and surfaces/valuation ask a
  predicate instead of re-implementing "who counts".

The state is a pure function of the row, the clock date and the season, so it is
safe to memoize. Evidence (depth chart, current stats, a market print, fresh
news) is what separates a free agent from a name that merely survives in
Sleeper's dump.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Mapping

import pandas as pd

from modules import injury_status as injury_table
from modules import season_clock

# --- Lifecycle vocabulary ---------------------------------------------------
ACTIVE_ROSTERED = "active_rostered"
RESERVE = "reserve"  # IR / PUP / NFI: a team holds the rights
PRACTICE_SQUAD = "practice_squad"
FREE_AGENT = "free_agent"  # no team, with current evidence
INACTIVE = "inactive"  # Sleeper "Inactive" with evidence it still matters
RETIRED_OR_UNKNOWN = "retired_or_unknown"  # no current evidence of an NFL career

LIFECYCLE_STATES = (
    ACTIVE_ROSTERED,
    RESERVE,
    PRACTICE_SQUAD,
    FREE_AGENT,
    INACTIVE,
    RETIRED_OR_UNKNOWN,
)

# --- Shared constants (the eligibility gate re-exports these) -----------------
INELIGIBLE_STATUS_TERMS = frozenset(
    {"retired", "inactive", "not active", "historical", "historical only", "deceased", "invalid"}
)
RESERVE_STATUS_TERMS = frozenset(injury_table.terms_for_kinds(("reserve",)))
# Sleeper reports some rostered injured players as ``status: "Inactive"`` with an
# IR-type ``injury_status``; the injury designation is the reserve signal.
RESERVE_INJURY_STATUS_TERMS = RESERVE_STATUS_TERMS | {"out"}
FREE_AGENT_TEAM_MARKERS = frozenset({"", "FA", "FREE AGENT", "FREE_AGENT", "NONE", "N/A", "NA"})
NEWS_FRESHNESS_DAYS = 730
UNSIGNED_VETERAN_NEWS_FRESHNESS_DAYS = 180
VETERAN_MIN_EXPERIENCE = 10
VETERAN_MIN_AGE = 35
# Nobody at this age is an unsigned/undepth-charted fantasy asset. (Kickers and
# punters are exempt where a team holds them.)
RETIREMENT_AGE = 40

_DAY_SECONDS = 24 * 60 * 60


# --- tiny coercions ------------------------------------------------------------
def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = _text(value).casefold()
    if text in {"1", "1.0", "true", "yes", "y", "active"}:
        return True
    if text in {"0", "0.0", "false", "no", "n", "inactive"}:
        return False
    return None


def news_timestamp_seconds(value: Any) -> float | None:
    timestamp = _number(value)
    if timestamp is None or timestamp <= 0:
        return None
    return timestamp / 1000.0 if timestamp > 10_000_000_000 else timestamp


# --- Age ----------------------------------------------------------------------
def parse_birth_date(value: Any) -> date | None:
    text = _text(value)[:10]
    if len(text) != 10:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def age_on(birth_date: Any, as_of: date) -> int | None:
    """Completed years on ``as_of`` (matches how Sleeper reports age for active players)."""

    born = parse_birth_date(birth_date)
    if born is None or born > as_of:
        return None
    years = as_of.year - born.year - ((as_of.month, as_of.day) < (born.month, born.day))
    return years if 15 <= years <= 60 else None


def resolve_age(birth_date: Any, sleeper_age: Any, *, as_of: date | None = None) -> float | None:
    """Age from ``birth_date`` on the clock date, else Sleeper's age, else None."""

    computed = age_on(birth_date, as_of or datetime.now(timezone.utc).date())
    if computed is not None:
        return float(computed)
    fallback = _number(sleeper_age)
    return fallback


# --- Lifecycle ----------------------------------------------------------------
def has_team(row: Mapping[str, Any]) -> bool:
    team = _text(row.get("team")).upper()
    return bool(team) and team not in FREE_AGENT_TEAM_MARKERS


def evidence(row: Mapping[str, Any], *, now: datetime, season: int) -> dict[str, bool]:
    """Current-activity evidence independent of team assignment."""

    now_seconds = now.timestamp()
    years_exp = _number(row.get("years_exp"))
    age = _number(row.get("age"))
    veteran = (years_exp is not None and years_exp >= VETERAN_MIN_EXPERIENCE) or (
        age is not None and age >= VETERAN_MIN_AGE
    )
    teamed = has_team(row)
    news_ts = news_timestamp_seconds(row.get("news_updated"))
    # An unsigned veteran's news only counts while it is genuinely recent; old
    # provider rows that still say Active are how retirees linger.
    window_days = UNSIGNED_VETERAN_NEWS_FRESHNESS_DAYS if (veteran and not teamed) else NEWS_FRESHNESS_DAYS
    fresh_news = bool(news_ts and (now_seconds - news_ts) <= window_days * _DAY_SECONDS)
    seasons = [
        _number(row.get(column)) for column in ("stats_season", "latest_stats_season", "prior_season")
    ]
    stats_season = max((value for value in seasons if value is not None), default=None)
    return {
        "depth": bool(_text(row.get("depth_chart_position")) or (_number(row.get("depth_chart_order")) or 0) > 0),
        "stats": bool(stats_season and stats_season >= season - 1),
        "market": (_number(row.get("fantasycalc_value")) or 0) > 0,
        "news": fresh_news,
        "veteran": veteran,
    }


def has_current_evidence(ev: Mapping[str, bool], *, teamed: bool = True) -> bool:
    """Is there evidence he is a live NFL asset?

    Depth chart, current/last-season stats and a market print are real evidence.
    News is corroboration only while a club holds the player: Sleeper bumps
    ``news_updated`` on non-football record edits, so for an unsigned player a
    fresh timestamp alone is how retirees (Antonio Brown, Henry Ruggs) linger.
    """

    return bool(ev["depth"] or ev["stats"] or ev["market"] or (teamed and ev["news"]))


def lifecycle_state(
    row: Mapping[str, Any],
    *,
    now: datetime | None = None,
    season: int | None = None,
) -> str:
    """Classify one player. Pure: same row + clock => same state."""

    now = now or datetime.now(timezone.utc)
    season = season if season is not None else season_clock.current_season(now.astimezone(timezone.utc).date())
    status = _text(row.get("status")).casefold()
    injury = _text(row.get("injury_status")).casefold()
    ev = evidence(row, now=now, season=season)
    teamed = has_team(row)
    current = has_current_evidence(ev, teamed=teamed)
    age = _number(row.get("age"))
    position = _text(row.get("position")).upper()
    kicker = position in {"K", "P"}

    inactive_status = any(term in status for term in INELIGIBLE_STATUS_TERMS)
    reserve_designation = status in RESERVE_STATUS_TERMS or (
        inactive_status and injury in RESERVE_INJURY_STATUS_TERMS
    )
    if reserve_designation:
        return RESERVE
    if status == "practice squad":
        return PRACTICE_SQUAD
    if inactive_status:
        return INACTIVE if current else RETIRED_OR_UNKNOWN
    past_retirement_age = age is not None and age >= RETIREMENT_AGE and not kicker
    if teamed:
        if past_retirement_age and not ev["depth"]:
            return RETIRED_OR_UNKNOWN
        # A last-known club on a veteran with no depth, stats or news is not an asset.
        if ev["veteran"] and not current:
            return RETIRED_OR_UNKNOWN
        return ACTIVE_ROSTERED
    if past_retirement_age or not current:
        return RETIRED_OR_UNKNOWN
    return FREE_AGENT


def annotate_lifecycle(frame: pd.DataFrame, *, now: datetime | None = None) -> pd.Series:
    """Lifecycle state for every row of ``frame`` (index-aligned Series)."""

    if frame is None or frame.empty:
        return pd.Series(dtype="object", index=getattr(frame, "index", None))
    now = now or datetime.now(timezone.utc)
    season = season_clock.current_season(now.astimezone(timezone.utc).date())
    states = [lifecycle_state(row, now=now, season=season) for row in frame.to_dict("records")]
    return pd.Series(states, index=frame.index, dtype="object")


# --- Named predicates per surface -----------------------------------------------
# Each takes a lifecycle state (str or Series) so a surface states its rule once.
_HELD_BY_TEAM = frozenset({ACTIVE_ROSTERED, RESERVE, PRACTICE_SQUAD})
_VALUE_BEARING = _HELD_BY_TEAM | {FREE_AGENT}


def _isin(state: Any, members: frozenset[str]):
    if isinstance(state, pd.Series):
        return state.isin(members)
    return state in members


def is_team_held(state: Any):
    """A club holds his rights (roster, reserve or practice squad)."""

    return _isin(state, _HELD_BY_TEAM)


def is_rankable(state: Any):
    """May appear in rankings and be valued from popularity/role signals alone."""

    return _isin(state, _VALUE_BEARING)


def is_searchable(state: Any):
    """Resolvable by name search and comparison (everyone except unknown ghosts)."""

    return _isin(state, _VALUE_BEARING | {INACTIVE})


def is_waiver_actionable(state: Any):
    """A real pickup candidate: on an active roster slot or genuinely available."""

    return _isin(state, frozenset({ACTIVE_ROSTERED, FREE_AGENT}))


def is_tradeable_asset(state: Any):
    """May carry trade value. Unknown/retired names never do."""

    return _isin(state, _VALUE_BEARING | {INACTIVE})
