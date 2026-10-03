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

import time
from datetime import datetime
from typing import Any

import pandas as pd

from modules import league_value_settings, player_eligibility, rankings, redis_cache, sleeper, trade_ideas
from modules.league_value_settings import _safe_float, _safe_positive_int
from modules.rank_tie_metadata import add_rank_tie_metadata
from modules.team_eval import build_league_summary, normalize_team_strategy, team_strategy_label

__all__ = ["add_rank_tie_metadata"]  # re-exported: see modules/rank_tie_metadata.py's
# docstring for why this lives in its own module (team_eval.py needs it too,
# and team_eval.py is imported *by* this module, so it couldn't import it
# back from here without a cycle) — kept importable from here as well since
# every existing caller (app.py, this module's own rank-producing functions)
# already does `from modules.league_rankings import add_rank_tie_metadata`.


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
    capital_rows = add_rank_tie_metadata(capital_rows, ["draft_capital_rank"])
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
            "draft_capital_rank_tied",
            "draft_capital_rank_tie_count",
        ]
        draft_cols_to_merge.extend(
            [column for column in draft_capital_summary.columns if column.startswith("pick_value_")]
        )
        # Defensive against a caller-supplied draft_capital_summary that
        # predates add_rank_tie_metadata (e.g. a hand-built test fixture) —
        # only merge columns that actually exist rather than KeyError.
        draft_cols_to_merge = [
            column for column in draft_cols_to_merge if column in draft_capital_summary.columns
        ]
        draft_cols = draft_capital_summary[draft_cols_to_merge].copy()
        df_display = df_display.merge(draft_cols, on="roster_id", how="left")
    for column in ["draft_capital", "pick_count", "first_rounders", "second_rounders", "third_rounders", "draft_capital_rank"]:
        if column not in df_display.columns:
            df_display[column] = 0
    if "draft_capital_rank_tied" not in df_display.columns:
        df_display["draft_capital_rank_tied"] = False
    else:
        df_display["draft_capital_rank_tied"] = df_display["draft_capital_rank_tied"].fillna(False).astype(bool)
    if "draft_capital_rank_tie_count" not in df_display.columns:
        df_display["draft_capital_rank_tie_count"] = 1
    else:
        df_display["draft_capital_rank_tie_count"] = pd.to_numeric(
            df_display["draft_capital_rank_tie_count"], errors="coerce"
        ).fillna(1).astype(int)
    for column in [column for column in df_display.columns if column.startswith("pick_value_")]:
        df_display[column] = pd.to_numeric(df_display[column], errors="coerce").fillna(0).astype(int)
    df_display["draft_capital"] = pd.to_numeric(df_display["draft_capital"], errors="coerce").fillna(0).astype(int)
    df_display["power_score"] = pd.to_numeric(df_display["total_score"], errors="coerce").fillna(0)
    df_display["power_rank"] = df_display["power_score"].rank(method="dense", ascending=False).astype(int)
    raw_roster_score = pd.to_numeric(df_display.get("raw_roster_score"), errors="coerce").fillna(df_display["power_score"])
    df_display["franchise_score"] = raw_roster_score + df_display["draft_capital"]
    df_display["franchise_rank"] = df_display["franchise_score"].rank(method="dense", ascending=False).astype(int)
    df_display = add_rank_tie_metadata(df_display, ["power_rank", "franchise_rank"])
    if include_picks:
        df_display["overall_score"] = df_display["franchise_score"]
        df_display["overall_rank"] = df_display["franchise_rank"]
        df_display["overall_rank_tied"] = df_display["franchise_rank_tied"]
        df_display["overall_rank_tie_count"] = df_display["franchise_rank_tie_count"]
    else:
        df_display["overall_score"] = df_display["power_score"]
        df_display["overall_rank"] = df_display["power_rank"]
        df_display["overall_rank_tied"] = df_display["power_rank_tied"]
        df_display["overall_rank_tie_count"] = df_display["power_rank_tie_count"]
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
    ranked = add_rank_tie_metadata(
        ranked,
        ["roster_value_rank", "current_roster_rank", "starter_rank", "bench_rank", "age_rank"],
    )
    return ranked


def build_league_summary_and_draft_capital(
    df_players: pd.DataFrame,
    league_id: str,
    *,
    score_field: str = "dynasty_score",
    current_score_field: str = "value_score",
    league_settings: dict[str, Any] | None = None,
    adapter=None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(df_summary, draft_capital_summary) — the shared first half of
    build_league_rankings_frame, split out so a caller that needs the raw
    draft_capital_summary too (e.g. build_draft_workspace_frame) doesn't
    have to recompute df_summary/draft_picks a second time.

    draft_status is intentionally omitted from the list_draft_pick_assets
    call — see build_league_rankings_frame's docstring.
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
        return df_summary, pd.DataFrame()

    draft_picks = trade_ideas.list_draft_pick_assets(
        league_id, df_summary, league_settings=league_settings, adapter=adapter
    )
    draft_capital_summary = build_draft_capital_summary(df_summary, draft_picks)
    return df_summary, draft_capital_summary


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
    """

    df_summary, draft_capital_summary = build_league_summary_and_draft_capital(
        df_players,
        league_id,
        score_field=score_field,
        current_score_field=current_score_field,
        league_settings=league_settings,
        adapter=adapter,
    )
    if df_summary.empty:
        return df_summary

    df_display = build_league_display_frame(df_summary, draft_capital_summary, include_picks=True)
    return add_league_detail_ranks(df_display)


# This is a full league-wide Power/Franchise/Draft Capital Rank pass — real
# work, and (like trade_hub_engine's generate_trade_idea_records_cached)
# redone from scratch on every call even though a given (league, lens)
# combo can't change faster than the underlying Sleeper roster data does.
# get_league_dashboard and get_league_team_rankings both ask this exact
# question for the same league within seconds of each other on a typical
# session (open Dashboard, tap into Team Rankings) with zero sharing before
# this cache existed. Same live-time-bucket idiom modules.sleeper and
# trade_hub_engine already use for their own caches.
LEAGUE_RANKINGS_FRAME_TTL_SECONDS = 30


def _league_rankings_frame_cache_bucket() -> int:
    return int(time.time() // LEAGUE_RANKINGS_FRAME_TTL_SECONDS)


# Redis-backed single-flight + cache (modules.redis_cache.redis_single_flight_cache),
# shared by both caches below (they key on the exact same
# (league_id, lens, players_db_path, bucket) shape) — same pattern, and
# same reason, as modules.playoff_simulator's and
# modules.trade_hub_engine's own caches: without a single-flight guard, N
# concurrent requests that all miss the same key before the first one
# finishes would each independently redo the full league-wide
# ranking/draft-capital pass instead of sharing one — directly
# contradicting these caches' own documented purpose (Dashboard and Team
# Rankings, or Draft Center and Draft Picks, sharing one entry instead of
# each recomputing it).
#
# This used to be a per-process threading.Lock + functools.lru_cache pair,
# which only protected ONE uvicorn worker: under docker-compose.yml's
# multiple mobile-api workers, each worker has its own process memory, so
# that old pair would let the same expensive pass run redundantly once per
# worker AND a cache hit in worker A would never help a request that
# happened to land on worker B. Redis fixes both: the distributed lock
# makes only one worker, cluster-wide, actually run a given pass, and the
# cached result lives in Redis, not in any one worker's memory.
_LEAGUE_RANKINGS_LOCK_TIMEOUT_SECONDS = 15.0


def _build_league_summary_and_draft_capital_cached(
    league_id: str,
    lens: str,
    players_db_path: str,
    _bucket: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    league = sleeper.get_league(league_id)
    if not league:
        return pd.DataFrame(), pd.DataFrame()
    settings = league_value_settings.detect_league_value_settings_from_payload(league)

    players_df = rankings.load_players(players_db_path)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(players_db_path)
    players_df = player_eligibility.filter_current_fantasy_players(
        players_df, surface="league_rankings_frame_cache"
    )
    if players_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    valued = league_value_settings.apply_valuation_lens(players_df, lens, settings)
    score_field = league_value_settings.valuation_score_field(lens)
    return build_league_summary_and_draft_capital(
        valued, league_id, score_field=score_field, league_settings=settings
    )


def build_league_summary_and_draft_capital_cached(
    *,
    league_id: str,
    lens: str,
    players_db_path: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cached front door for `build_league_summary_and_draft_capital` — same
    30s live-time-bucket idiom as `build_league_rankings_frame_cached`
    below, for the same reason: this is the same real per-roster
    Power/Franchise/Draft-Capital pass `build_league_rankings_frame` is
    built on top of. Draft Center and Draft Picks each called the uncached
    function directly, redoing this full-league pass from scratch on every
    request even though the two screens are commonly opened seconds apart
    in one session — the same class of problem
    `build_league_rankings_frame_cached` already exists to solve for
    Dashboard/Team Rankings. A separate cache entry from
    `_build_league_rankings_frame_cached` below (not a shared one) — kept
    that way deliberately so this addition can't change what Dashboard/Team
    Rankings compute or how their existing cache-sharing test observes
    `build_league_rankings_frame` being called. Returns copies so a caller
    mutating either frame never corrupts the cached entry.

    Single-flight + cache, now shared across every mobile-api worker via
    Redis: see modules.redis_cache.redis_single_flight_cache and this
    module's own comment above `_build_league_summary_and_draft_capital_cached`."""

    key = (league_id, lens, players_db_path, _league_rankings_frame_cache_bucket())
    cache_key = redis_cache.build_cache_key("league_summary_and_draft_capital", *key)
    df_summary, draft_capital_summary = redis_cache.redis_single_flight_cache(
        cache_key=cache_key,
        ttl_seconds=LEAGUE_RANKINGS_FRAME_TTL_SECONDS,
        compute=lambda: _build_league_summary_and_draft_capital_cached(*key),
        lock_timeout_seconds=_LEAGUE_RANKINGS_LOCK_TIMEOUT_SECONDS,
    )
    return df_summary.copy(), draft_capital_summary.copy()


def _build_league_rankings_frame_cached(
    league_id: str,
    lens: str,
    players_db_path: str,
    _bucket: int,
) -> pd.DataFrame:
    league = sleeper.get_league(league_id)
    if not league:
        return pd.DataFrame()
    settings = league_value_settings.detect_league_value_settings_from_payload(league)

    players_df = rankings.load_players(players_db_path)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(players_db_path)
    players_df = player_eligibility.filter_current_fantasy_players(
        players_df, surface="league_rankings_frame_cache"
    )
    if players_df.empty:
        return pd.DataFrame()

    valued = league_value_settings.apply_valuation_lens(players_df, lens, settings)
    score_field = league_value_settings.valuation_score_field(lens)
    return build_league_rankings_frame(valued, league_id, score_field=score_field, league_settings=settings)


def build_league_rankings_frame_cached(
    *,
    league_id: str,
    lens: str,
    players_db_path: str,
) -> pd.DataFrame:
    """Cached front door for `build_league_rankings_frame` — resolves its
    own players_df/settings from just (league_id, lens) rather than
    accepting them as arguments, so two different callers (the dashboard's
    power/franchise rank lookup, the team-rankings screen) asking about the
    same league/lens combo within the same 30s window hit one cache entry
    instead of each re-running the full league-wide ranking pass
    independently. Returns a copy so a caller mutating the frame (e.g.
    adding display-only columns) never corrupts the cached entry.

    Single-flight + cache, now shared across every mobile-api worker via
    Redis: see modules.redis_cache.redis_single_flight_cache and this
    module's own comment above `_build_league_summary_and_draft_capital_cached`."""

    key = (league_id, lens, players_db_path, _league_rankings_frame_cache_bucket())
    cache_key = redis_cache.build_cache_key("league_rankings_frame", *key)
    frame = redis_cache.redis_single_flight_cache(
        cache_key=cache_key,
        ttl_seconds=LEAGUE_RANKINGS_FRAME_TTL_SECONDS,
        compute=lambda: _build_league_rankings_frame_cached(*key),
        lock_timeout_seconds=_LEAGUE_RANKINGS_LOCK_TIMEOUT_SECONDS,
    )
    return frame.copy()


def draft_year_columns(df: pd.DataFrame) -> list[str]:
    """Ported verbatim from app.py — the sorted list of `pick_value_<year>`
    columns a draft-capital summary frame carries."""

    return sorted(
        [column for column in df.columns if str(column).startswith("pick_value_")],
        key=lambda column: int(str(column).replace("pick_value_", "") or 0),
    )


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    return str(value)


def build_draft_workspace_frame(
    draft_capital_summary: pd.DataFrame,
    df_intel: pd.DataFrame | None,
    *,
    draft_year: int | None = None,
) -> pd.DataFrame:
    """Ported verbatim from app.py (confirmed pure pandas, no Streamlit
    dependency anywhere in it) — feeds modules.draft_center_ui's
    build_draft_decision_cards/build_draft_partner_cards. `df_intel` is
    optional: every column it would otherwise supply (power_rank,
    franchise_rank, age_rank, avg_age, strategy_display, trading_style,
    roster_philosophy, asset_behavior, activity_level,
    manager_tendencies_summary, manager_trade_implication) already has a
    graceful fallback default below when absent."""

    if draft_capital_summary is None or draft_capital_summary.empty:
        return pd.DataFrame()

    current_draft_year = _safe_positive_int(draft_year, datetime.now().year) or datetime.now().year
    summary = draft_capital_summary.copy()
    for column in ["draft_capital", "pick_count", "first_rounders", "second_rounders", "third_rounders", "draft_capital_rank"]:
        if column not in summary.columns:
            summary[column] = 0
        summary[column] = pd.to_numeric(summary.get(column), errors="coerce").fillna(0)

    year_cols = draft_year_columns(summary)
    future_year_cols = [
        column
        for column in year_cols
        if _safe_positive_int(str(column).replace("pick_value_", ""), 0) > current_draft_year
    ]
    summary["future_draft_capital"] = (
        summary[future_year_cols].sum(axis=1)
        if future_year_cols
        else 0
    )
    summary["future_draft_capital_rank"] = (
        pd.to_numeric(summary["future_draft_capital"], errors="coerce")
        .fillna(0)
        .rank(method="dense", ascending=False)
        .astype(int)
    )
    summary = add_rank_tie_metadata(summary, ["future_draft_capital_rank"])

    if df_intel is not None and not df_intel.empty:
        intel_cols = [
            "roster_id",
            "team_name",
            "owner_name",
            "owner_username",
            "power_rank",
            "power_rank_tied",
            "power_rank_tie_count",
            "franchise_rank",
            "franchise_rank_tied",
            "franchise_rank_tie_count",
            "age_rank",
            "age_rank_tied",
            "age_rank_tie_count",
            "avg_age",
            "strategy_display",
            "trading_style",
            "roster_philosophy",
            "asset_behavior",
            "activity_level",
            "manager_tendencies_summary",
            "manager_trade_implication",
        ]
        available_cols = [column for column in intel_cols if column in df_intel.columns]
        intel_frame = df_intel[available_cols].copy()
        rename_map = {}
        for column in [column for column in available_cols if column != "roster_id" and column in summary.columns]:
            rename_map[column] = f"intel_{column}"
        if rename_map:
            intel_frame = intel_frame.rename(columns=rename_map)
        summary = summary.merge(intel_frame, on="roster_id", how="left")
        for base_column in ["team_name", "owner_name"]:
            intel_column = f"intel_{base_column}"
            if intel_column in summary.columns:
                summary[base_column] = summary[intel_column].where(
                    summary[intel_column].fillna("").astype(str).str.strip() != "",
                    summary.get(base_column),
                )

    numeric_defaults = {
        "draft_capital_rank": len(summary),
        "future_draft_capital_rank": len(summary),
        "power_rank": len(summary),
        "franchise_rank": len(summary),
        "age_rank": len(summary),
        "avg_age": 0.0,
        "future_draft_capital": 0.0,
    }
    for column, default in numeric_defaults.items():
        if column not in summary.columns:
            summary[column] = default
        summary[column] = pd.to_numeric(summary.get(column), errors="coerce").fillna(default)

    for rank_col in ["draft_capital_rank", "future_draft_capital_rank", "power_rank", "franchise_rank", "age_rank"]:
        tied_col = f"{rank_col}_tied"
        tie_count_col = f"{rank_col}_tie_count"
        if tied_col not in summary.columns:
            summary[tied_col] = False
        else:
            summary[tied_col] = summary[tied_col].fillna(False).astype(bool)
        if tie_count_col not in summary.columns:
            summary[tie_count_col] = 1
        else:
            summary[tie_count_col] = pd.to_numeric(summary[tie_count_col], errors="coerce").fillna(1).astype(int)

    if "strategy_display" not in summary.columns:
        summary["strategy_display"] = ""
    if "mode" not in summary.columns:
        summary["mode"] = ""
    summary["strategy_display"] = summary.apply(
        lambda row: _safe_text(row.get("strategy_display")) or team_strategy_label(row.get("mode")),
        axis=1,
    )

    for column, default in [
        ("trading_style", "Unknown"),
        ("roster_philosophy", "Balanced"),
        ("asset_behavior", "Balanced Asset Manager"),
        ("activity_level", "Average Activity"),
        ("manager_tendencies_summary", ""),
        ("manager_trade_implication", ""),
    ]:
        if column not in summary.columns:
            summary[column] = default
        summary[column] = summary[column].fillna(default).astype(str)

    summary["strategy_key"] = summary.apply(
        lambda row: normalize_team_strategy(row.get("strategy") or row.get("mode")),
        axis=1,
    )
    return summary.sort_values(["draft_capital_rank", "draft_capital", "team_name"], ascending=[True, False, True]).reset_index(drop=True)
