"""Real, data-backed team signal badges for the web League boards.

Mirrors mobile's `TeamRanking.team_badges` field (see
`services/mobile_api_service.py`'s `get_league_team_rankings`, which computes
the identical badge set for the mobile API response — `TeamsScreen.tsx`
renders them as a wrapping badge row per team). Web's own Power Rankings /
Standings boards never surfaced this signal at all; this module ports the
same computation for the Streamlit rendering path.

Deliberately a hand-kept copy of that endpoint's inline badge block rather
than a shared import across `services/` and `modules/` (the service module
pulls in FastAPI/web-service wiring web rendering has no reason to import).
Both read from the exact same underlying modules — `manager_activity`,
`pick_flow`, `team_streaks` — so the thresholds and labels cannot drift
even though the code lives in two places; if one changes, the other should.
"""

from __future__ import annotations

import pandas as pd

from modules import manager_activity, pick_flow, team_streaks


def compute_team_signal_badges(
    rankings_frame: pd.DataFrame,
    league_id: str,
) -> dict[str, list[str]]:
    """roster_id (str) -> ordered list of real, data-backed badge labels.

    Best-effort per signal: a scan failure (e.g. an offseason league with no
    transaction history yet) just omits that one signal's badges rather than
    failing the whole board — same contract
    `services.mobile_api_service.get_league_team_rankings` uses.
    """

    if rankings_frame is None or rankings_frame.empty or not league_id:
        return {}
    if "roster_id" not in rankings_frame.columns:
        return {}

    try:
        activity_counts = manager_activity.manager_activity_counts_cached(league_id)
    except Exception:
        activity_counts = {}
    try:
        pick_flow_counts = pick_flow.league_pick_flow_counts_cached(league_id)
    except Exception:
        pick_flow_counts = {}
    try:
        current_streaks = team_streaks.league_current_streaks_cached(league_id)
    except Exception:
        current_streaks = {}

    def _activity_count_for(raw_roster_id: object) -> int:
        try:
            return int(activity_counts.get(int(raw_roster_id), 0))
        except (TypeError, ValueError):
            return 0

    tx_low, tx_high = manager_activity.activity_quartiles(
        _activity_count_for(raw_roster_id) for raw_roster_id in rankings_frame["roster_id"]
    )

    league_size = max(len(rankings_frame), 1)
    top_rank_cut = max(2, int(round(league_size * 0.33)))
    bottom_rank_cut = max(top_rank_cut + 1, int(round(league_size * 0.67)))

    zero_series = pd.Series(0, index=rankings_frame.index)
    top_heavy_ratios = (
        pd.to_numeric(rankings_frame.get("starter_score", zero_series), errors="coerce").fillna(0)
        / pd.to_numeric(rankings_frame.get("bench_score", zero_series), errors="coerce").fillna(0).clip(lower=1.0)
    )
    if len(top_heavy_ratios) > 1:
        top_heavy_cutoff: float | None = float(top_heavy_ratios.quantile(0.75))
    elif len(top_heavy_ratios) == 1:
        top_heavy_cutoff = float(top_heavy_ratios.iloc[0]) + 1.0
    else:
        top_heavy_cutoff = None

    badges_by_roster: dict[str, list[str]] = {}
    for idx, row in rankings_frame.iterrows():
        roster_id = str(row.get("roster_id"))
        try:
            roster_id_int: int | None = int(roster_id)
        except (TypeError, ValueError):
            roster_id_int = None

        activity_count = _activity_count_for(roster_id_int) if roster_id_int is not None else 0
        pick_flow_entry = pick_flow_counts.get(roster_id_int, {}) if roster_id_int is not None else {}
        firsts_acquired = int(pick_flow_entry.get("firsts_acquired") or 0)
        firsts_sent = int(pick_flow_entry.get("firsts_sent") or 0)
        streak_entry = current_streaks.get(roster_id_int, {}) if roster_id_int is not None else {}
        current_streak = int(streak_entry.get("current_streak") or 0)

        age_rank = row.get("age_rank")
        draft_rank = row.get("draft_capital_rank")
        try:
            age_rank_int: int | None = (
                int(age_rank) if age_rank is not None and not pd.isna(age_rank) else None
            )
        except (TypeError, ValueError):
            age_rank_int = None
        try:
            draft_rank_int: int | None = (
                int(draft_rank) if draft_rank is not None and not pd.isna(draft_rank) else None
            )
        except (TypeError, ValueError):
            draft_rank_int = None

        badges: list[str] = []
        activity_badge = manager_activity.classify_activity_level(
            transaction_count=activity_count, tx_high=tx_high, tx_low=tx_low
        )
        if activity_badge:
            badges.append(activity_badge)
        pick_flow_badge = pick_flow.classify_pick_flow(firsts_acquired, firsts_sent)
        if pick_flow_badge:
            badges.append(pick_flow_badge)
        if age_rank_int is not None and draft_rank_int is not None:
            if age_rank_int >= bottom_rank_cut and draft_rank_int >= bottom_rank_cut:
                badges.append("Veteran Collector")
            elif age_rank_int <= top_rank_cut and draft_rank_int <= top_rank_cut:
                badges.append("Youth Builder")
        streak_badge = team_streaks.classify_streak_badge(current_streak)
        if streak_badge:
            badges.append(streak_badge)
        if top_heavy_cutoff is not None and top_heavy_ratios.loc[idx] >= top_heavy_cutoff:
            badges.append("Top-Heavy Roster")

        if badges:
            badges_by_roster[roster_id] = badges

    return badges_by_roster


# Tone for the existing `.dg-ui-badge--*` family (modules/ui_primitive_styles.py)
# — same tone tokens every other badge in the app already uses, rather than
# a page-local color vocabulary. Mirrors TEAM_BADGE_VISUALS' tone split
# (mobile/src/screens/TeamsScreen.tsx): most badges are neutral play-style
# descriptors ("information"), the two with a real positive/negative read
# (an active streak, a roster-concentration risk) get success/caution.
_BADGE_TONE = {
    "Highly Active": "information",
    "Quiet Manager": "information",
    "Pick Hoarder": "premium",
    "Pick Seller": "information",
    "Veteran Collector": "premium",
    "Youth Builder": "success",
    "Hot Streak": "success",
    "Cold Streak": "caution",
    "Top-Heavy Roster": "caution",
}


def badge_tone(label: str) -> str:
    return _BADGE_TONE.get(label, "information")
