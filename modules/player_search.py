"""Name search over the FULL league-valued player pool.

Why this exists: every client search box (Players, Compare, Trade Analyzer,
GM orb, Veto) used to filter a `/rankings?limit=300` window client-side, so any
player the app valued below rank ~300 (e.g. a rookie backup QB like Carson Beck
at ~650) could not be found anywhere even though he is in the pool, has a rank
and a detail page. Low-value / blocked players must rank lower, never vanish.

This is a pure function over the already-ranked frame so the endpoint, tests and
the coverage audit share one matcher.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from modules import player_identity

MAX_QUERY_LENGTH = 80


def _tokens(value: Any) -> list[str]:
    return player_identity.normalize_player_name(value).split()


def _match_tier(query_tokens: list[str], name_tokens: list[str], extra: set[str]) -> int | None:
    """0 exact, 1 name starts with query, 2 every query token prefixes a name
    token (any order, so "beck carson" works), 3 substring of the joined name;
    None when it does not match. Team/position tokens may satisfy a token."""

    if not query_tokens:
        return None
    joined_query = " ".join(query_tokens)
    joined_name = " ".join(name_tokens)
    if joined_name == joined_query:
        return 0
    if joined_name.startswith(joined_query):
        return 1
    remaining = list(name_tokens)
    extras = set(extra)
    ok = True
    for qt in query_tokens:
        hit = next((t for t in remaining if t.startswith(qt)), None)
        if hit is not None:
            remaining.remove(hit)
        elif qt in extras:
            extras.discard(qt)
        else:
            ok = False
            break
    if ok:
        return 2
    if joined_query in joined_name:
        return 3
    return None


def search_ranked_players(
    ranked: pd.DataFrame,
    query: str,
    *,
    score_field: str,
    position: str = "",
    limit: int = 25,
) -> pd.DataFrame:
    """Rows of `ranked` matching `query`, best match first then highest value.

    No value/rank/depth cutoff is applied on purpose: the pool is already the
    eligibility-filtered set of real current players."""

    if ranked is None or ranked.empty:
        return pd.DataFrame()
    query_tokens = _tokens(str(query or "")[:MAX_QUERY_LENGTH])
    if not query_tokens:
        return ranked.iloc[0:0]
    wanted_position = str(position or "").strip().upper()
    frame = ranked
    if wanted_position and "position" in frame.columns:
        frame = frame[frame["position"].astype(str).str.upper() == wanted_position]
    scores = pd.to_numeric(frame[score_field], errors="coerce").fillna(0) if score_field in frame.columns else pd.Series(0.0, index=frame.index)
    tiers: list[int | None] = []
    for name, team, pos in zip(
        frame["name"] if "name" in frame.columns else [""] * len(frame),
        frame["team"] if "team" in frame.columns else [""] * len(frame),
        frame["position"] if "position" in frame.columns else [""] * len(frame),
    ):
        extra = {str(team or "").casefold(), str(pos or "").casefold()} - {""}
        tiers.append(_match_tier(query_tokens, _tokens(name), extra))
    out = frame.assign(_search_tier=tiers, _search_score=scores.values)
    out = out[out["_search_tier"].notna()]
    out = out.sort_values(["_search_tier", "_search_score"], ascending=[True, False], kind="stable")
    return out.head(max(1, int(limit))).drop(columns=["_search_tier", "_search_score"])
