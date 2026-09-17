"""League-wide team ranking assembly (Power Rank, Franchise Rank, Draft
Capital Rank) — ported from app.py so it can be called from services/ without
importing app.py (modules/ never imports app.py, per dashboard_engine.py's
docstring).

Ported verbatim from app.py's safe_pick_value/build_draft_capital_summary/
build_league_display_frame/add_league_detail_ranks (the "Rankings" page's
real computation chain, confirmed pure pandas with no Streamlit dependency
anywhere in it). build_league_rankings_frame is new — it's the composition
glue app.py's cached_league_shell_context does inline, extracted into one
function so a caller only needs a league_id and a valued players frame.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from modules import trade_ideas
from modules.league_value_settings import _safe_float, _safe_positive_int
from modules.team_eval import build_league_summary, team_strategy_label


def safe_pick_value(pick: dict) -> int:
    value = _safe_positive_int(pick.get("score"), 0)
    if value > 0:
        return value
    base_score = _safe_positive_int(pick.get("base_score"), 0)
    if base_score > 0:
        future_discount = max(0.1, _safe_float(pick.get("future_discount"), 1.0))
        team_modifier = max(0.5, _safe_float(pick.get("team_modifier"), 1.0))
        format_multiplier = max(0.3, _safe_float(pick.get("format_multiplier"), 1.0))
        class_strength_multiplier = max(0.5, _safe_float(pick.get("class_strength_multiplier"), 1.0))
        prospect_strength_multiplier = max(0.5, _safe_float(pick.get("prospect_strength_multiplier"), 1.0))
        return int(
            round(
                base_score
                * future_discount
                * team_modifier
                * format_multiplier
                * class_strength_multiplier
                * prospect_strength_multiplier
            )
        )
    round_num = _safe_positive_int(pick.get("round"), 4)
    default_values = {1: 6500, 2: 3200, 3: 1400, 4: 650}
    return default_values.get(round_num, max(150, 650 - ((round_num - 4) * 150)))


def build_draft_capital_summary(
    df_summary: pd.DataFrame,
    draft_picks: list[dict],
) -> pd.DataFrame:
    if df_summary.empty:
        return pd.DataFrame()

    capital_rows = df_summary[
        [column for column in ["roster_id", "team_name", "owner_name", "avatar_url", "mode"] if column in df_summary.columns]
    ].copy()
    capital_rows["roster_id_key"] = pd.to_numeric(capital_rows["roster_id"], errors="coerce").astype("Int64")

    totals: dict[int, int] = {}
    pick_counts: dict[int, int] = {}
    first_rounders: dict[int, int] = {}
    second_rounders: dict[int, int] = {}
    third_rounders: dict[int, int] = {}
    yearly_values: dict[tuple[int, int], int] = {}
    seasons: set[int] = set()
    for pick in draft_picks or []:
        owner_id = pd.to_numeric(pd.Series([pick.get("owner_roster_id")]), errors="coerce").iloc[0]
        if pd.isna(owner_id):
            continue
        owner_key = int(owner_id)
        pick_value = safe_pick_value(pick)
        totals[owner_key] = totals.get(owner_key, 0) + pick_value
        pick_counts[owner_key] = pick_counts.get(owner_key, 0) + 1
        round_num = int(pick.get("round") or 0)
        if round_num == 1:
            first_rounders[owner_key] = first_rounders.get(owner_key, 0) + 1
        elif round_num == 2:
            second_rounders[owner_key] = second_rounders.get(owner_key, 0) + 1
        elif round_num == 3:
            third_rounders[owner_key] = third_rounders.get(owner_key, 0) + 1
        season = _safe_positive_int(pick.get("season"), 0)
        if season:
            seasons.add(season)
            yearly_values[(owner_key, season)] = yearly_values.get((owner_key, season), 0) + pick_value

    capital_rows["draft_capital"] = capital_rows["roster_id_key"].map(totals).fillna(0).astype(int)
    capital_rows["pick_count"] = capital_rows["roster_id_key"].map(pick_counts).fillna(0).astype(int)
    capital_rows["first_rounders"] = capital_rows["roster_id_key"].map(first_rounders).fillna(0).astype(int)
    capital_rows["second_rounders"] = capital_rows["roster_id_key"].map(second_rounders).fillna(0).astype(int)
    capital_rows["third_rounders"] = capital_rows["roster_id_key"].map(third_rounders).fillna(0).astype(int)
    for season in sorted(seasons):
        column = f"pick_value_{season}"
        capital_rows[column] = (
            capital_rows["roster_id_key"]
            .map(lambda roster_id: yearly_values.get((int(roster_id), season), 0) if pd.notna(roster_id) else 0)
            .fillna(0)
            .astype(int)
        )
    capital_rows["draft_capital_rank"] = (
        capital_rows["draft_capital"].rank(method="dense", ascending=False).astype(int)
    )
    return capital_rows.sort_values(["draft_capital_rank", "draft_capital", "team_name"], ascending=[True, False, True]).reset_index(drop=True)


def build_league_display_frame(
    df_summary: pd.DataFrame,
    draft_capital_summary: pd.DataFrame,
    include_picks: bool,
) -> pd.DataFrame:
    df_display = df_summary.copy()
    if draft_capital_summary is not None and not draft_capital_summary.empty:
        draft_cols_to_merge = [
            "roster_id",
            "draft_capital",
            "pick_count",
            "first_rounders",
            "second_rounders",
            "third_rounders",
            "draft_capital_rank",
        ]
        draft_cols_to_merge.extend(
            [column for column in draft_capital_summary.columns if column.startswith("pick_value_")]
        )
        draft_cols = draft_capital_summary[draft_cols_to_merge].copy()
        df_display = df_display.merge(draft_cols, on="roster_id", how="left")
    for column in ["draft_capital", "pick_count", "first_rounders", "second_rounders", "third_rounders", "draft_capital_rank"]:
        if column not in df_display.columns:
            df_display[column] = 0
    for column in [column for column in df_display.columns if column.startswith("pick_value_")]:
        df_display[column] = pd.to_numeric(df_display[column], errors="coerce").fillna(0).astype(int)
    df_display["draft_capital"] = pd.to_numeric(df_display["draft_capital"], errors="coerce").fillna(0).astype(int)
    df_display["power_score"] = pd.to_numeric(df_display["total_score"], errors="coerce").fillna(0)
    df_display["power_rank"] = df_display["power_score"].rank(method="dense", ascending=False).astype(int)
    raw_roster_score = pd.to_numeric(df_display.get("raw_roster_score"), errors="coerce").fillna(df_display["power_score"])
    df_display["franchise_score"] = raw_roster_score + df_display["draft_capital"]
    df_display["franchise_rank"] = df_display["franchise_score"].rank(method="dense", ascending=False).astype(int)
    if include_picks:
        df_display["overall_score"] = df_display["franchise_score"]
        df_display["overall_rank"] = df_display["franchise_rank"]
    else:
        df_display["overall_score"] = df_display["power_score"]
        df_display["overall_rank"] = df_display["power_rank"]
    df_display["rank_points"] = len(df_display) - df_display["power_rank"] + 1
    if "strategy_label" in df_display.columns:
        df_display["strategy_display"] = df_display["strategy_label"].fillna("").astype(str)
    else:
        df_display["strategy_display"] = df_display["mode"].apply(lambda value: team_strategy_label(value))
    return df_display.sort_values(["power_rank", "power_score", "team_name"], ascending=[True, False, True]).reset_index(drop=True)


def add_league_detail_ranks(df_display: pd.DataFrame) -> pd.DataFrame:
    if df_display.empty:
        return df_display
    ranked = df_display.copy()
    ranked["roster_value_rank"] = (
        pd.to_numeric(ranked["raw_roster_score"], errors="coerce")
        .fillna(0)
        .rank(method="dense", ascending=False)
        .astype(int)
    )
    ranked["current_roster_rank"] = (
        pd.to_numeric(ranked.get("current_roster_score"), errors="coerce")
        .fillna(pd.to_numeric(ranked["starter_score"], errors="coerce").fillna(0) + pd.to_numeric(ranked["bench_score"], errors="coerce").fillna(0))
        .rank(method="dense", ascending=False)
        .astype(int)
    )
    ranked["starter_rank"] = (
        pd.to_numeric(ranked["starter_score"], errors="coerce")
        .fillna(0)
        .rank(method="dense", ascending=False)
        .astype(int)
    )
    ranked["bench_rank"] = (
        pd.to_numeric(ranked["bench_score"], errors="coerce")
        .fillna(0)
        .rank(method="dense", ascending=False)
        .astype(int)
    )
    ranked["age_rank"] = (
        pd.to_numeric(ranked["avg_age"], errors="coerce")
        .fillna(999)
        .rank(method="dense", ascending=True)
        .astype(int)
    )
    return ranked


def build_league_rankings_frame(
    df_players: pd.DataFrame,
    league_id: str,
    *,
    score_field: str = "dynasty_score",
    current_score_field: str = "value_score",
    league_settings: dict[str, Any] | None = None,
    adapter=None,
) -> pd.DataFrame:
    """One row per roster with power_rank, franchise_rank, draft_capital_rank,
    starter_rank, bench_rank, age_rank, avg_age — the full "Rankings" page
    computation, minus the archetype/strategy-refine layer (not needed for
    these columns; see the investigation this was built from).

    draft_status is intentionally omitted from the list_draft_pick_assets
    call — that parameter only affects whether current-year rookie picks
    count as active trade capital, and omitting it (None) falls back to
    future_picks_are_trade_capital(league_settings), the same effective
    default the "Rankings" page's real production traffic already uses.
    """

    df_summary = build_league_summary(
        df_players,
        league_id,
        score_field=score_field,
        current_score_field=current_score_field,
        lineup_settings=league_settings,
        adapter=adapter,
    )
    if df_summary.empty:
        return df_summary

    draft_picks = trade_ideas.list_draft_pick_assets(
        league_id, df_summary, league_settings=league_settings, adapter=adapter
    )
    draft_capital_summary = build_draft_capital_summary(df_summary, draft_picks)
    df_display = build_league_display_frame(df_summary, draft_capital_summary, include_picks=True)
    return add_league_detail_ranks(df_display)
