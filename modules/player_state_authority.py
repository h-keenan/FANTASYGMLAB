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
        "out",
        "injured reserve",
        "ir",
        "pup",
        "nfi",
        "physically unable to perform",
        "non-football injury",
        "suspended",
    }
)
_NFL_NON_ACTIONABLE_STATUSES = frozenset(
    {
        "inactive",
        "retired",
        "historical",
        "historical only",
        "deceased",
        "practice squad",
    }
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
