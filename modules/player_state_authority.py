"""Canonical ownership boundaries for current, rostered, and available players."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pandas as pd

from modules.player_eligibility import (
    FREE_AGENT_TEAM_MARKERS,
    filter_current_fantasy_players,
    player_eligibility,
)


_NFL_ACTIONABLE_STATUSES = frozenset(
    {
        "active",
        "questionable",
        "probable",
        "doubtful",
        "suspended",
    }
)
# These represent genuine multi-week-to-season-ending unavailability. A
# player whose Sleeper roster ``status`` field literally reads one of these
# (as opposed to a short-term weekly ``injury_status`` tag like
# "Questionable") is not "safe to rank as an NFL add" no matter how the
# `active` flag reads — Sleeper's `active` boolean is not a reliable proxy
# for availability on its own (confirmed live: a real 2025 rookie QB placed
# on injured reserve for a season-ending injury still carried `active: True`
# from Sleeper while `status` correctly read "Inactive"). Previously "out",
# "injured reserve", "ir", "pup", and "nfi" were incorrectly listed as
# ACTIONABLE here, which meant any player whose `status` field literally read
# one of those values (currently ~80+ real skill-position players at any
# given time) was treated as a safe waiver-add candidate purely because the
# `active` flag happened to still read True.
# Public (not underscore-prefixed) because modules/rankings.py's
# injury_level()/is_injury_status() reuse this exact set as their single
# source of truth for which literal Sleeper `status` values represent
# genuine unavailability — see the comment there. Keeping one definition
# avoids the "multiple sources of truth" bug class this whole module
# exists to prevent.
NFL_NON_ACTIONABLE_STATUSES = frozenset(
    {
        "inactive",
        "retired",
        "historical",
        "historical only",
        "deceased",
        "practice squad",
        "out",
        "injured reserve",
        "ir",
        "pup",
        "nfi",
        "physically unable to perform",
        "non-football injury",
        # Sleeper's real raw feed sends "Non Football Injury" (a space, not
        # a hyphen) — confirmed against data/sleeper_players.json. The
        # hyphenated form above never actually matches real data; kept
        # alongside it defensively in case a different feed source ever
        # does send the hyphenated spelling.
        "non football injury",
    }
)
_NFL_NON_ACTIONABLE_STATUSES = NFL_NON_ACTIONABLE_STATUSES  # internal alias, kept for this module's own readability

# Suspension is scheduled, known-duration unavailability, not an injury —
# a different kind of fact than anything in NFL_NON_ACTIONABLE_STATUSES
# above, which is why it gets its own set keyed on its own field rather than
# being folded into that one. Confirmed against data/sleeper_players.json
# (2026-10-19 valuation-system audit): Sleeper encodes it only via a literal
# "Sus" `injury_status` tag (currently ~8 real rostered players, e.g.
# C.J. Gardner-Johnson — the exact roster drifts week to week, so this is a
# vocabulary check, never a hardcoded player list). For every one of those
# players the roster-level `status` field independently read "Active" or
# "Inactive" — Sleeper has never been observed to send a literal status of
# "Suspended", even though _NFL_ACTIONABLE_STATUSES above already lists it
# defensively. is_suspended() below checks both fields so this stays correct
# if that ever changes.
SUSPENDED_INJURY_STATUS_TERMS = frozenset({"sus", "suspended", "suspension"})


def is_suspended(status: object, injury_status: object = "") -> bool:
    """True when Sleeper's real suspension signal is present.

    Single source of truth for "this player is suspended" so rankings.py's
    injury-severity vocabulary, waiver_actionability() below, and any UI
    surface that needs to say "Suspended" instead of a generic injury word
    never drift apart on what counts.
    """

    return (
        _text(injury_status).casefold() in SUSPENDED_INJURY_STATUS_TERMS
        or _text(status).casefold() in SUSPENDED_INJURY_STATUS_TERMS
    )


def _text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _optional_bool(value: object) -> bool | None:
    text = _text(value).casefold()
    if text in {"true", "1", "yes", "active"}:
        return True
    if text in {"false", "0", "no", "inactive"}:
        return False
    return value if isinstance(value, bool) else None


def waiver_actionability(player: Mapping[str, object] | pd.Series) -> dict[str, object]:
    """Return whether a fantasy free agent is safe to rank as an NFL add.

    Current-player identity, fantasy ownership, and add actionability are
    deliberately separate contracts.  Sleeper's structured ``team`` and
    ``status`` fields own current NFL attachment; market value and historical
    role labels never substitute for them.
    """

    current = player_eligibility(player)
    if not current["eligible"]:
        return {"actionable": False, "reason": "not_current_fantasy_player"}

    team = _text(player.get("team")).upper()
    if not team or team in FREE_AGENT_TEAM_MARKERS:
        return {"actionable": False, "reason": "no_current_nfl_team"}

    status = _text(player.get("status")).casefold()
    if status in _NFL_NON_ACTIONABLE_STATUSES:
        return {"actionable": False, "reason": "non_actionable_nfl_status"}
    # Suspension never shows up in the literal `status` field (see
    # SUSPENDED_INJURY_STATUS_TERMS above — Sleeper encodes it only via the
    # weekly `injury_status` tag "Sus"), so without this check a suspended
    # free agent's `status` reads plain "Active" and sails through as a safe
    # waiver add for the length of the suspension.
    if is_suspended(status, player.get("injury_status")):
        return {"actionable": False, "reason": "suspended"}
    if _optional_bool(player.get("active")) is False:
        return {"actionable": False, "reason": "explicitly_inactive"}
    if status not in _NFL_ACTIONABLE_STATUSES and _optional_bool(player.get("active")) is not True:
        return {"actionable": False, "reason": "unverified_nfl_status"}

    return {"actionable": True, "reason": "current_nfl_roster"}


def filter_waiver_actionable_players(players: pd.DataFrame) -> pd.DataFrame:
    """Keep only players eligible for current actionable add recommendations."""

    if players is None or players.empty:
        return players.copy() if players is not None else pd.DataFrame()
    decisions = players.apply(waiver_actionability, axis=1)
    actionable = decisions.map(lambda item: bool(item["actionable"]))
    result = players.loc[actionable].copy()
    result["waiver_actionable"] = True
    result["waiver_actionability_reason"] = decisions.loc[actionable].map(
        lambda item: str(item["reason"])
    )
    return result


def current_player_pool(
    players: pd.DataFrame,
    *,
    surface: str,
) -> pd.DataFrame:
    """A: identities allowed in current actionable product surfaces."""

    return filter_current_fantasy_players(players, surface=surface)


def rostered_player_ids(
    roster_player_map: Mapping[str, Sequence[object]] | None,
) -> set[str]:
    """B: league ownership only; never infer it from NFL team/status fields."""

    return {
        str(player_id).strip()
        for player_ids in (roster_player_map or {}).values()
        for player_id in (player_ids or ())
        if str(player_id or "").strip()
    }


def transaction_available_player_pool(
    players: pd.DataFrame,
    roster_player_map: Mapping[str, Sequence[object]] | None,
    *,
    surface: str = "waiver_free_agents",
) -> pd.DataFrame:
    """C: canonically current players not owned by any loaded fantasy roster."""

    current = current_player_pool(players, surface=surface)
    if current.empty:
        return current
    owned = rostered_player_ids(roster_player_map)
    player_ids = current.get(
        "player_id",
        pd.Series("", index=current.index, dtype="object"),
    ).fillna("").astype(str)
    return current.loc[~player_ids.isin(owned)].copy()


def waiver_actionable_player_pool(
    players: pd.DataFrame,
    roster_player_map: Mapping[str, Sequence[object]] | None,
    *,
    surface: str = "waiver_free_agents",
) -> pd.DataFrame:
    """Current, league-unowned players that can be ranked as NFL add actions."""

    available = transaction_available_player_pool(
        players,
        roster_player_map,
        surface=surface,
    )
    return filter_waiver_actionable_players(available)
