"""Canonical ownership boundaries for current, rostered, and available players."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pandas as pd

from modules.player_eligibility import filter_current_fantasy_players


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
