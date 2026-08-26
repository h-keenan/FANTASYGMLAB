import pandas as pd
from typing import List, Dict, Any, Mapping, Sequence
from datetime import datetime
from collections import defaultdict
from contextlib import contextmanager
from copy import deepcopy
from itertools import combinations
from types import MappingProxyType
from hashlib import sha256
import json
import time

from modules.platforms.sleeper import get_sleeper_adapter
from modules.league_format_context import (
    future_picks_are_trade_capital,
    pick_is_actionable_capital,
)
from modules.team_eval import (
    get_team_vs_league,
    normalize_team_strategy,
    suggest_optimal_lineup,
    team_strategy_label,
    team_strategy_mode,
)
from modules.roster_needs import true_roster_needs
from modules.rankings import injury_level, is_injury_status, summarize_team_injuries
from modules.performance import debug_enabled, record_timing
from modules import runtime_trace

BASE_PICK_VALUES = {
    1: 6500,
    2: 3200,
    3: 1400,
    4: 650,
}
PICK_TIER_BASE_VALUES = {
    1: {"early": 7600, "mid": 6500, "late": 5600},
    2: {"early": 3800, "mid": 3200, "late": 2700},
    3: {"early": 1750, "mid": 1400, "late": 1100},
    4: {"early": 850, "mid": 650, "late": 500},
}
PICK_TIER_MULTIPLIERS = {
    "early": 1.10,
    "mid": 1.0,
    "late": 0.90,
}
DEFAULT_PICK_LEAGUE_SETTINGS = {
    "league_format": "Dynasty",
    "qb_format": "1QB",
    "te_premium": False,
    "league_size": 12,
    "starter_count": 9,
    "flex_count": 2,
    "bench_count": 0,
    "taxi_count": 0,
    "ir_count": 0,
    "superflex_count": 0,
    "qb_count": 1,
    "rb_count": 2,
    "wr_count": 3,
    "te_count": 1,
}
DEFAULT_CLASS_STRENGTH_BY_YEAR: Dict[int, float] = {}
CORE_POSITIONS = ("QB", "RB", "WR", "TE")
POSITION_MINIMUMS = {"QB": 1, "RB": 3, "WR": 4, "TE": 1}
PRIMARY_REASON_TAGS = {
    "Need-Based",
    "Contender Move",
    "Rebuild Move",
    "Draft Capital Move",
    "Age Optimization",
    "Roster Consolidation",
    "Value Arbitrage",
    "Temporary Injury Need",
}
TIER_MARKET_RANK = {
    "developmental": 0,
    "depth": 1,
    "contributor": 2,
    "starter": 3,
    "core starter": 4,
    "star": 5,
    "elite": 6,
}
MARKET_REALISM_LIKELY_MIN = 82
MARKET_REALISM_PLAUSIBLE_MIN = 68
MARKET_REALISM_THIN_MIN = 55
TRADE_CONFIDENCE_HIGH_MIN = 78
TRADE_CONFIDENCE_MEDIUM_MIN = 60
TRADE_HEADLINE_REALISM_MIN = 76


def _safe_int(value, default=0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value, default=0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _roster_players_map(rosters: List[Dict[str, Any]]) -> Dict[int, List[str]]:
    return {
        _safe_int(roster.get("roster_id")): [
            str(player_id)
            for player_id in roster.get("players", []) or []
            if str(player_id or "").strip()
        ]
        for roster in rosters or []
        if _safe_int(roster.get("roster_id")) > 0
    }


def _ordinal_round(round_num: int) -> str:
    if round_num == 1:
        return "1st"
    if round_num == 2:
        return "2nd"
    if round_num == 3:
        return "3rd"
    return f"{round_num}th"


def _clamp_float(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, _safe_float(value, lower)))


def _pick_league_settings(league_settings: Dict[str, Any] | None = None) -> Dict[str, Any]:
    settings = dict(DEFAULT_PICK_LEAGUE_SETTINGS)
    settings.update(league_settings or {})
    settings["league_format"] = str(settings.get("league_format") or "Dynasty")
    settings["qb_format"] = str(settings.get("qb_format") or "1QB")
    settings["te_premium"] = bool(settings.get("te_premium"))
    settings["league_size"] = max(8, min(32, _safe_int(settings.get("league_size"), 12) or 12))
    for key, default in {
        "starter_count": 9,
        "flex_count": 2,
        "bench_count": 0,
        "taxi_count": 0,
        "ir_count": 0,
        "max_roster_size": 0,
        "superflex_count": 0,
        "qb_count": 1,
        "rb_count": 2,
        "wr_count": 3,
        "te_count": 1,
    }.items():
        settings[key] = max(0, _safe_int(settings.get(key), default))
    if not settings.get("taxi_count") and settings.get("taxi_slots"):
        settings["taxi_count"] = max(0, _safe_int(settings.get("taxi_slots"), 0))
    return settings


def _team_position_minimums(league_settings: Dict[str, Any] | None = None) -> Dict[str, int]:
    minimums = dict(POSITION_MINIMUMS)
    if not league_settings:
        return minimums
    settings = _pick_league_settings(league_settings)
    qb_minimum = max(1, settings.get("qb_count", 1))
    if settings.get("qb_format") == "2QB":
        qb_minimum = max(2, qb_minimum)
    elif settings.get("qb_format") == "Superflex" or settings.get("superflex_count", 0) > 0:
        qb_minimum = max(2, qb_minimum + 1)

    flex_bonus = 1 if settings.get("flex_count", 0) > 0 else 0
    minimums["QB"] = qb_minimum
    minimums["RB"] = max(2, settings.get("rb_count", 2) + flex_bonus)
    minimums["WR"] = max(3, settings.get("wr_count", 3) + flex_bonus)
    minimums["TE"] = max(1, settings.get("te_count", 1))
    return minimums


def _team_roster_size_context(
    df_team: pd.DataFrame | None,
    league_settings: Dict[str, Any] | None = None,
) -> Dict[str, int | bool]:
    settings = _pick_league_settings(league_settings)
    starter_count = int(settings.get("starter_count") or 0)
    bench_count = int(settings.get("bench_count") or 0)
    taxi_count = int(settings.get("taxi_count") or 0)
    ir_count = int(settings.get("ir_count") or 0)
    total_rostered = int(len(df_team)) if df_team is not None else 0
    active_limit = int(settings.get("max_roster_size") or 0) or starter_count + bench_count
    total_limit = active_limit + taxi_count + ir_count
    active_or_total_limit = active_limit or total_limit
    return {
        "rostered_player_count": total_rostered,
        "active_roster_limit": active_limit,
        "total_roster_limit": total_limit,
        "roster_at_limit": bool(active_or_total_limit > 0 and total_rostered >= active_or_total_limit),
        "roster_over_limit": bool(active_or_total_limit > 0 and total_rostered > active_or_total_limit),
    }


def _round_tier_base_value(round_num: int, tier_bucket: str) -> int:
    tier_bucket = tier_bucket if tier_bucket in {"early", "mid", "late"} else "mid"
    tier_values = PICK_TIER_BASE_VALUES.get(round_num)
    if tier_values:
        return int(tier_values.get(tier_bucket, tier_values.get("mid", 0)))
    base = BASE_PICK_VALUES.get(round_num, max(150, 650 - ((round_num - 4) * 150)))
    return int(round(base * PICK_TIER_MULTIPLIERS.get(tier_bucket, 1.0)))


def canonical_pick_identity_value(pick: Mapping[str, Any]) -> int | None:
    """Resolve an existing pick identity through the canonical pick-value table.

    Exact/current values supplied by the canonical asset owner win. Otherwise a
    declared early/mid/late projection is used, then the round-level midpoint.
    This is intentionally context-light for retrospective History grading.
    """

    for key in ("current_value", "value_score", "dynasty_score", "score", "base_score"):
        value = _safe_int(pick.get(key), 0)
        if value > 0:
            return value
    round_num = _safe_int(pick.get("round"), 0)
    if round_num <= 0:
        return None
    projected = str(
        pick.get("projected_range")
        or pick.get("projected_slot")
        or pick.get("slot_tier")
        or ""
    ).casefold()
    tier = next((label for label in ("early", "mid", "late") if label in projected), "mid")
    return _round_tier_base_value(round_num, tier)


def _normalize_bucket_probabilities(weights: Dict[str, float]) -> Dict[str, float]:
    buckets = ("early", "mid", "late")
    normalized = {bucket: max(0.0, _safe_float(weights.get(bucket), 0.0)) for bucket in buckets}
    total = sum(normalized.values())
    if total <= 0:
        return {bucket: 1 / 3 for bucket in buckets}
    return {bucket: normalized[bucket] / total for bucket in buckets}


def _pick_team_context(original_roster_id: int, df_summary: pd.DataFrame) -> Dict[str, float | str]:
    if df_summary.empty or "roster_id" not in df_summary.columns or "total_score" not in df_summary.columns:
        return {"tier_bucket": "mid", "team_modifier": 1.0, "slot_percentile": 0.5}

    roster_ids = pd.to_numeric(df_summary["roster_id"], errors="coerce")
    scores = pd.to_numeric(df_summary["total_score"], errors="coerce")
    valid = df_summary.copy()
    valid["_roster_id_key"] = roster_ids
    valid["_total_score_key"] = scores
    valid = valid.dropna(subset=["_roster_id_key", "_total_score_key"])
    if valid.empty:
        return {"tier_bucket": "mid", "team_modifier": 1.0, "slot_percentile": 0.5}

    team_row = valid[valid["_roster_id_key"] == original_roster_id]
    if team_row.empty:
        return {"tier_bucket": "mid", "team_modifier": 1.0, "slot_percentile": 0.5}

    ranked = valid[["_roster_id_key", "_total_score_key"]].copy()
    ranked["strength_rank"] = ranked["_total_score_key"].rank(method="average", ascending=False)
    team_rank = float(ranked.loc[ranked["_roster_id_key"] == original_roster_id, "strength_rank"].iloc[0])
    total_teams = max(1, int(len(ranked)))
    slot_percentile = (team_rank - 1) / max(total_teams - 1, 1)
    if slot_percentile >= 0.67:
        tier_bucket = "early"
    elif slot_percentile >= 0.34:
        tier_bucket = "mid"
    else:
        tier_bucket = "late"
    team_modifier = 0.96 + (slot_percentile * 0.08)
    return {
        "tier_bucket": tier_bucket,
        "team_modifier": float(team_modifier),
        "slot_percentile": float(slot_percentile),
    }


def _pick_range_projection(
    current_slot_percentile: float,
    years_out: int,
    round_num: int,
) -> Dict[str, Any]:
    current_slot = _clamp_float(current_slot_percentile, 0.0, 1.0)
    stability = max(0.42, 0.84 - (max(0, years_out) * 0.18))
    projected_slot = _clamp_float(0.5 + ((current_slot - 0.5) * stability), 0.0, 1.0)
    spread = min(0.34, 0.18 + (max(0, years_out) * 0.05))
    bucket_centers = {
        "late": 0.18,
        "mid": 0.50,
        "early": 0.82,
    }
    weights = {}
    for bucket, center in bucket_centers.items():
        distance = abs(projected_slot - center)
        weights[bucket] = max(0.0, 1.0 - (distance / max(spread, 0.01))) ** 2
    probabilities = _normalize_bucket_probabilities(weights)
    ordered = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)
    primary_bucket, primary_probability = ordered[0]
    secondary_bucket, secondary_probability = ordered[1]
    if primary_probability >= 0.58 or (primary_probability - secondary_probability) >= 0.18:
        projected_range = f"{primary_bucket.title()} {_ordinal_round(round_num)}"
    else:
        projected_range = f"{primary_bucket.title()}/{secondary_bucket.title()} {_ordinal_round(round_num)}"
    return {
        "projected_slot_percentile": float(projected_slot),
        "bucket_probabilities": probabilities,
        "primary_bucket": primary_bucket,
        "projected_range": projected_range,
        "projection_confidence": float(primary_probability),
    }


def _weighted_pick_base_value(round_num: int, bucket_probabilities: Dict[str, float]) -> float:
    probabilities = _normalize_bucket_probabilities(bucket_probabilities)
    return float(
        sum(
            _round_tier_base_value(round_num, bucket) * probability
            for bucket, probability in probabilities.items()
        )
    )


def _pick_format_multiplier(
    round_num: int,
    tier_bucket: str,
    league_settings: Dict[str, Any] | None = None,
) -> float:
    settings = _pick_league_settings(league_settings)
    multiplier = 1.0
    league_format = settings["league_format"]
    qb_format = settings["qb_format"]
    league_size = _safe_int(settings.get("league_size"), 12) or 12

    # Redraft/horizon discount is owned solely by app.draft_pick_score_multiplier.
    # Do not apply a second redraft haircut here (stacking bug across #252/#253).
    _ = league_format

    if qb_format == "Superflex":
        if round_num == 1:
            multiplier *= {"early": 1.14, "mid": 1.10, "late": 1.06}.get(tier_bucket, 1.08)
        elif round_num == 2:
            multiplier *= {"early": 1.09, "mid": 1.06, "late": 1.03}.get(tier_bucket, 1.05)
        elif round_num == 3:
            multiplier *= 1.02
    elif qb_format == "2QB":
        if round_num == 1:
            multiplier *= {"early": 1.18, "mid": 1.13, "late": 1.08}.get(tier_bucket, 1.10)
        elif round_num == 2:
            multiplier *= {"early": 1.12, "mid": 1.08, "late": 1.05}.get(tier_bucket, 1.07)
        elif round_num == 3:
            multiplier *= 1.03
    else:
        if round_num == 1:
            multiplier *= {"early": 0.97, "mid": 0.99, "late": 1.0}.get(tier_bucket, 1.0)
        elif round_num == 2:
            multiplier *= {"early": 0.98, "mid": 0.99, "late": 1.0}.get(tier_bucket, 1.0)

    if settings.get("te_premium"):
        if round_num <= 2:
            multiplier *= 1.03
        elif round_num == 3:
            multiplier *= 1.015

    size_delta = max(-4, min(8, league_size - 12))
    if round_num == 1:
        multiplier *= 1 + (size_delta * 0.012)
    elif round_num == 2:
        multiplier *= 1 + (size_delta * 0.009)
    elif round_num <= 4:
        multiplier *= 1 + (size_delta * 0.006)

    starter_count = settings.get("starter_count", 9)
    flex_count = settings.get("flex_count", 2)
    reserve_depth = settings.get("bench_count", 0) + settings.get("taxi_count", 0) + settings.get("ir_count", 0)
    lineup_delta = max(-4, min(8, (starter_count - 9) + (flex_count - 2)))
    reserve_delta = max(-6, min(10, reserve_depth - 8))
    if round_num <= 2:
        multiplier *= 1 + (lineup_delta * 0.014)
    elif round_num <= 4:
        multiplier *= 1 + (lineup_delta * 0.009)
    if round_num >= 2:
        multiplier *= 1 + (reserve_delta * 0.005)

    return float(multiplier)


def _weighted_pick_format_multiplier(
    round_num: int,
    bucket_probabilities: Dict[str, float],
    league_settings: Dict[str, Any] | None = None,
) -> float:
    probabilities = _normalize_bucket_probabilities(bucket_probabilities)
    return float(
        sum(
            _pick_format_multiplier(round_num, bucket, league_settings) * probability
            for bucket, probability in probabilities.items()
        )
    )


def _rookie_class_strength_multiplier(
    season: int,
    class_strength_by_year: Dict[int, float] | None = None,
) -> float:
    lookup = class_strength_by_year or DEFAULT_CLASS_STRENGTH_BY_YEAR
    value = lookup.get(int(season))
    try:
        parsed = float(value)
    except Exception:
        return 1.0
    return max(0.8, min(1.25, parsed))


def _prospect_rankings_multiplier(
    season: int,
    round_num: int,
    tier_bucket: str,
    prospect_rankings_by_year: Dict[int, Any] | None = None,
) -> float:
    if not prospect_rankings_by_year:
        return 1.0
    season_data = prospect_rankings_by_year.get(int(season))
    if not isinstance(season_data, dict):
        return 1.0
    raw_value = (
        season_data.get(f"{tier_bucket}_{round_num}")
        or season_data.get(str(round_num))
        or season_data.get(round_num)
        or season_data.get(tier_bucket)
        or season_data.get("default")
    )
    try:
        parsed = float(raw_value)
    except Exception:
        return 1.0
    return max(0.8, min(1.25, parsed))


def _pick_value_components(
    season: int,
    round_num: int,
    original_roster_id: int,
    df_summary: pd.DataFrame,
    league_settings: Dict[str, Any] | None = None,
    class_strength_by_year: Dict[int, float] | None = None,
    prospect_rankings_by_year: Dict[int, Any] | None = None,
    team_context: Mapping[str, float | str] | None = None,
) -> Dict[str, Any]:
    context = (
        team_context
        if team_context is not None
        else _pick_team_context(original_roster_id, df_summary)
    )
    current_year = datetime.now().year
    years_out = max(0, season - (current_year + 1))
    projection = _pick_range_projection(
        _safe_float(context.get("slot_percentile"), 0.5),
        years_out,
        round_num,
    )
    tier_bucket = str(projection.get("primary_bucket") or context.get("tier_bucket") or "mid")
    bucket_probabilities = projection.get("bucket_probabilities") or {"mid": 1.0}
    base = _weighted_pick_base_value(round_num, bucket_probabilities)
    future_discount = 0.88 ** years_out
    projected_slot_percentile = _safe_float(projection.get("projected_slot_percentile"), 0.5)
    team_modifier = 0.96 + (projected_slot_percentile * 0.08)
    format_multiplier = _weighted_pick_format_multiplier(round_num, bucket_probabilities, league_settings)
    class_strength_multiplier = _rookie_class_strength_multiplier(season, class_strength_by_year)
    prospect_strength_multiplier = _prospect_rankings_multiplier(
        season,
        round_num,
        tier_bucket,
        prospect_rankings_by_year,
    )
    score = int(
        round(
            base
            * future_discount
            * team_modifier
            * format_multiplier
            * class_strength_multiplier
            * prospect_strength_multiplier
        )
    )
    return {
        "score": score,
        "tier_bucket": tier_bucket,
        "pick_tier": f"{tier_bucket.title()} {_ordinal_round(round_num)}",
        "projected_pick_range": str(projection.get("projected_range") or f"{tier_bucket.title()} {_ordinal_round(round_num)}"),
        "base_score": int(round(base)),
        "future_discount": float(future_discount),
        "team_modifier": float(team_modifier),
        "format_multiplier": float(format_multiplier),
        "class_strength_multiplier": float(class_strength_multiplier),
        "prospect_strength_multiplier": float(prospect_strength_multiplier),
        "slot_percentile": float(_safe_float(context.get("slot_percentile"), 0.5)),
        "projected_slot_percentile": float(projected_slot_percentile),
        "early_probability": float(bucket_probabilities.get("early", 0.0)),
        "mid_probability": float(bucket_probabilities.get("mid", 0.0)),
        "late_probability": float(bucket_probabilities.get("late", 0.0)),
        "projection_confidence": float(projection.get("projection_confidence") or 0.0),
        "projection_source": "team_strength_model",
    }


def _pick_value(
    season: int,
    round_num: int,
    original_roster_id: int,
    df_summary: pd.DataFrame,
    league_settings: Dict[str, Any] | None = None,
    class_strength_by_year: Dict[int, float] | None = None,
    prospect_rankings_by_year: Dict[int, Any] | None = None,
) -> int:
    return int(
        _pick_value_components(
            season,
            round_num,
            original_roster_id,
            df_summary,
            league_settings=league_settings,
            class_strength_by_year=class_strength_by_year,
            prospect_rankings_by_year=prospect_rankings_by_year,
        )["score"]
    )


def _build_roster_pick_assets(
    league_id: str,
    rosters: List[Dict[str, Any]],
    df_summary: pd.DataFrame,
    league_settings: Dict[str, Any] | None = None,
    draft_status: Dict[str, Any] | None = None,
    class_strength_by_year: Dict[int, float] | None = None,
    prospect_rankings_by_year: Dict[int, Any] | None = None,
    adapter=None,
) -> Dict[int, List[Dict[str, Any]]]:
    platform_adapter = adapter or get_sleeper_adapter()
    league = platform_adapter.get_league(league_id)
    draft_rounds = _safe_int(league.get("settings", {}).get("draft_rounds"), 4) or 4
    draft_rounds = max(1, min(draft_rounds, 6))

    traded_picks = platform_adapter.get_traded_picks(league_id)
    league_year = _safe_int(league.get("season"), datetime.now().year) or datetime.now().year
    draft_context = draft_status if isinstance(draft_status, dict) else {}
    current_pick_year = _safe_int(draft_context.get("draft_year"), league_year) or league_year
    # Redraft defaults to post-draft (no invented current-year board) unless
    # draft_status explicitly says current-year picks are still active.
    default_current_year_active = future_picks_are_trade_capital(league_settings)
    if "current_year_picks_active" in draft_context:
        current_year_picks_active = bool(draft_context.get("current_year_picks_active"))
    else:
        current_year_picks_active = bool(default_current_year_active)
    if draft_context.get("draft_completed"):
        current_year_picks_active = False
    traded_seasons = {
        _safe_int(p.get("season"))
        for p in traded_picks
        if pick_is_actionable_capital(
            _safe_int(p.get("season")),
            current_pick_year=current_pick_year,
            current_year_picks_active=current_year_picks_active,
            settings=league_settings,
            as_of_year=datetime.now().year,
        )
    }
    seasons: set[int] = set(traded_seasons)
    if current_year_picks_active:
        seasons.add(current_pick_year)
    if future_picks_are_trade_capital(league_settings):
        start = current_pick_year if current_year_picks_active else current_pick_year + 1
        seasons.update({start, start + 1})
    seasons = sorted(year for year in seasons if year > 0)

    roster_ids = [
        _safe_int(r.get("roster_id"))
        for r in rosters
        if r.get("roster_id") is not None and _safe_int(r.get("roster_id")) > 0
    ]
    pick_team_contexts = {
        roster_id: MappingProxyType(_pick_team_context(roster_id, df_summary))
        for roster_id in dict.fromkeys(roster_ids)
    }
    owner_by_pick = {}
    for season in seasons:
        for round_num in range(1, draft_rounds + 1):
            for original_roster_id in roster_ids:
                owner_by_pick[(season, round_num, original_roster_id)] = original_roster_id

    for pick in traded_picks:
        season = _safe_int(pick.get("season"))
        round_num = _safe_int(pick.get("round"))
        original_roster_id = _safe_int(pick.get("roster_id"))
        owner_id = _safe_int(pick.get("owner_id"))
        key = (season, round_num, original_roster_id)
        if key in owner_by_pick and owner_id:
            owner_by_pick[key] = owner_id

    team_name_by_roster = {}
    for _, row in df_summary.iterrows():
        roster_id = _safe_int(row.get("roster_id"))
        if roster_id:
            team_name_by_roster[roster_id] = row.get("team_name", f"Team {roster_id}")
    assets_by_owner: Dict[int, List[Dict[str, Any]]] = {rid: [] for rid in roster_ids}
    for (season, round_num, original_roster_id), owner_id in owner_by_pick.items():
        if owner_id not in assets_by_owner:
            continue
        if not pick_is_actionable_capital(
            season,
            current_pick_year=current_pick_year,
            current_year_picks_active=current_year_picks_active,
            settings=league_settings,
            as_of_year=datetime.now().year,
        ):
            continue
        original_team = team_name_by_roster.get(original_roster_id, f"Team {original_roster_id}")
        owner_team = team_name_by_roster.get(owner_id, f"Team {owner_id}")
        label = f"{season} Round {round_num}"
        if owner_id != original_roster_id:
            label = f"{label} ({original_team})"
        value_details = _pick_value_components(
            season,
            round_num,
            original_roster_id,
            df_summary,
            league_settings=league_settings,
            class_strength_by_year=class_strength_by_year,
            prospect_rankings_by_year=prospect_rankings_by_year,
            team_context=pick_team_contexts[original_roster_id],
        )
        value = int(value_details["score"])
        assets_by_owner[owner_id].append(
            {
                "asset_type": "pick",
                "label": label,
                "score": value,
                "season": season,
                "round": round_num,
                "original_roster_id": original_roster_id,
                "owner_roster_id": owner_id,
                "original_team_name": original_team,
                "owner_team_name": owner_team,
                "pick_tier": value_details["pick_tier"],
                "projected_pick_range": value_details["projected_pick_range"],
                "tier_bucket": value_details["tier_bucket"],
                "base_score": value_details["base_score"],
                "future_discount": value_details["future_discount"],
                "team_modifier": value_details["team_modifier"],
                "format_multiplier": value_details["format_multiplier"],
                "class_strength_multiplier": value_details["class_strength_multiplier"],
                "prospect_strength_multiplier": value_details["prospect_strength_multiplier"],
                "slot_percentile": value_details["slot_percentile"],
                "projected_slot_percentile": value_details["projected_slot_percentile"],
                "early_probability": value_details["early_probability"],
                "mid_probability": value_details["mid_probability"],
                "late_probability": value_details["late_probability"],
                "projection_confidence": value_details["projection_confidence"],
                "projection_source": value_details["projection_source"],
                "is_current_year_pick": season == current_pick_year,
            }
        )

    for owner_id in assets_by_owner:
        assets_by_owner[owner_id].sort(key=lambda p: (p["season"], p["round"], -p["score"]))
    return assets_by_owner


def list_draft_pick_assets(
    league_id: str,
    df_summary: pd.DataFrame,
    league_settings: Dict[str, Any] | None = None,
    draft_status: Dict[str, Any] | None = None,
    class_strength_by_year: Dict[int, float] | None = None,
    prospect_rankings_by_year: Dict[int, Any] | None = None,
    adapter=None,
):
    platform_adapter = adapter or get_sleeper_adapter()
    rosters = platform_adapter.get_rosters(league_id)
    assets_by_owner = _build_roster_pick_assets(
        league_id,
        rosters,
        df_summary,
        league_settings=league_settings,
        draft_status=draft_status,
        class_strength_by_year=class_strength_by_year,
        prospect_rankings_by_year=prospect_rankings_by_year,
        adapter=platform_adapter,
    )
    picks = []
    for owner_id, assets in assets_by_owner.items():
        for asset in assets:
            if asset["asset_type"] == "pick":
                picks.append(asset)
    return sorted(picks, key=lambda p: (p["season"], p["round"], -p["score"]))


def _row_score(row, score_field: str = "value_score") -> int:
    value = row.get(score_field)
    if value is None:
        value = row.get("value_score", row.get("dynasty_score", 0))
    try:
        return int(float(value) or 0)
    except Exception:
        return 0


def _player_asset(
    row,
    role: str = "Flex",
    score_field: str = "value_score",
    *,
    protected: bool | None = None,
) -> Dict[str, Any]:
    asset = {
        "asset_type": "player",
        "label": str(row["name"]),
        "score": _row_score(row, score_field),
        "score_field": str(score_field),
        "source_score": row.get(score_field),
        "position": str(row.get("position") or ""),
        "team": str(row.get("team") or ""),
        "status": str(row.get("status") or ""),
        "injury_status": str(row.get("injury_status") or ""),
        "injury_level": str(
            row.get("injury_level")
            or injury_level(row.get("status"), row.get("injury_status"))
            or "healthy"
        ),
        "news_updated": row.get("news_updated"),
        "age": row.get("age"),
        "player_id": str(row.get("player_id") or ""),
        "player_tier": str(row.get("player_tier") or ""),
        "opportunity_label": str(row.get("opportunity_label") or ""),
        "opportunity_explanation": str(row.get("opportunity_explanation") or ""),
        "role": role,
    }
    asset["is_protected"] = (
        _is_core_or_protected_starter(asset)
        if protected is None
        else bool(protected)
    )
    return asset


def _pick_asset(pick: Dict[str, Any], score_multiplier: float = 1.0) -> Dict[str, Any]:
    base_score = _safe_int(pick.get("score"), 0)
    adjusted_score = max(0, int(round(base_score * float(score_multiplier or 1.0))))
    return {
        "asset_type": "pick",
        "label": pick["label"],
        "score": adjusted_score,
        "position": "PICK",
        "age": "",
        "player_id": None,
        "round": pick.get("round"),
        "season": pick.get("season"),
        "owner_roster_id": pick.get("owner_roster_id"),
        "original_roster_id": pick.get("original_roster_id"),
        "owner_team_name": pick.get("owner_team_name"),
        "original_team_name": pick.get("original_team_name"),
        "pick_tier": pick.get("pick_tier"),
        "projected_pick_range": pick.get("projected_pick_range"),
        "tier_bucket": pick.get("tier_bucket"),
        "base_score": pick.get("base_score"),
        "future_discount": pick.get("future_discount"),
        "team_modifier": pick.get("team_modifier"),
        "format_multiplier": pick.get("format_multiplier"),
        "class_strength_multiplier": pick.get("class_strength_multiplier"),
        "prospect_strength_multiplier": pick.get("prospect_strength_multiplier"),
        "slot_percentile": pick.get("slot_percentile"),
        "projected_slot_percentile": pick.get("projected_slot_percentile"),
        "early_probability": pick.get("early_probability"),
        "mid_probability": pick.get("mid_probability"),
        "late_probability": pick.get("late_probability"),
        "projection_confidence": pick.get("projection_confidence"),
        "projection_source": pick.get("projection_source"),
    }


def _score_assets(assets: List[Dict[str, Any]]) -> int:
    return int(sum(int(asset.get("score") or 0) for asset in assets))


def _asset_labels(assets: List[Dict[str, Any]]) -> str:
    return " + ".join(str(asset["label"]) for asset in assets)


def _first_player_asset(assets: List[Dict[str, Any]]):
    for asset in assets:
        if asset.get("asset_type") == "player":
            return asset
    return None


def _has_pick(assets: List[Dict[str, Any]]) -> bool:
    return any(asset.get("asset_type") == "pick" for asset in assets)


def _player_assets(assets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [asset for asset in assets if asset.get("asset_type") == "player"]


def _pick_assets(assets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [asset for asset in assets if asset.get("asset_type") == "pick"]


def _asset_positions(assets: List[Dict[str, Any]]) -> set[str]:
    return {
        str(asset.get("position") or "").upper()
        for asset in _player_assets(assets)
        if str(asset.get("position") or "").upper() in CORE_POSITIONS
    }


def _asset_avg_age(assets: List[Dict[str, Any]]) -> float | None:
    ages = []
    for asset in _player_assets(assets):
        try:
            age = float(asset.get("age") or 0)
        except Exception:
            age = 0
        if age > 0:
            ages.append(age)
    if not ages:
        return None
    return float(sum(ages) / len(ages))


def _asset_age(asset: Dict[str, Any]) -> float:
    try:
        return float(asset.get("age") or 0.0)
    except Exception:
        return 0.0


def _asset_tier_rank(asset: Dict[str, Any]) -> int:
    return int(TIER_MARKET_RANK.get(str(asset.get("player_tier") or "").strip().lower(), 0))


def _best_player_asset(assets: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    players = _player_assets(assets)
    if not players:
        return None
    return max(players, key=lambda asset: int(asset.get("score") or 0))


def _is_throw_in_asset(asset: Dict[str, Any]) -> bool:
    if asset.get("asset_type") != "player":
        return False
    score = int(asset.get("score") or 0)
    tier_rank = _asset_tier_rank(asset)
    age = _asset_age(asset)
    opportunity = str(asset.get("opportunity_label") or "").strip()
    if score <= 1800:
        return True
    if score <= 2600 and tier_rank <= 1:
        return True
    if score <= 3200 and tier_rank <= 2 and opportunity in {"Buried Depth", "Handcuff"}:
        return True
    if age >= 28 and score <= 3200 and tier_rank <= 2:
        return True
    return False


def _is_premium_market_asset(
    asset: Dict[str, Any],
    league_settings: Dict[str, Any] | None = None,
) -> bool:
    if asset.get("asset_type") != "player":
        return False
    settings = _pick_league_settings(league_settings)
    pos = str(asset.get("position") or "").upper()
    score = int(asset.get("score") or 0)
    age = _asset_age(asset)
    tier_rank = _asset_tier_rank(asset)
    qb_format = settings.get("qb_format")

    if pos == "QB":
        if qb_format in {"Superflex", "2QB"}:
            return score >= 5200 or tier_rank >= 3
        return score >= 7600 or tier_rank >= 5
    if pos == "RB":
        return age > 0 and age <= 26 and (score >= 4200 or tier_rank >= 3)
    if pos == "WR":
        return score >= 5400 or tier_rank >= 4
    if pos == "TE":
        if settings.get("te_premium"):
            return score >= 4200 or tier_rank >= 4
        return score >= 5200 or tier_rank >= 5
    return False


def _is_cornerstone_asset(
    asset: Dict[str, Any],
    league_settings: Dict[str, Any] | None = None,
) -> bool:
    if asset.get("asset_type") != "player":
        return False
    settings = _pick_league_settings(league_settings)
    pos = str(asset.get("position") or "").upper()
    score = int(asset.get("score") or 0)
    age = _asset_age(asset)
    tier_rank = _asset_tier_rank(asset)
    opportunity = str(asset.get("opportunity_label") or "").strip()
    qb_format = settings.get("qb_format")

    if score >= 9800:
        return True
    if tier_rank >= 5 and 0 < age <= 26:
        return True
    if pos == "QB" and qb_format in {"Superflex", "2QB"} and tier_rank >= 4 and 0 < age <= 28 and score >= 7600:
        return True
    if pos == "RB" and tier_rank >= 4 and 0 < age <= 24 and score >= 7600 and opportunity == "Elite Opportunity":
        return True
    return False


def _fit_grade_label(fit_context: Dict[str, Any] | None) -> str:
    context = fit_context or {}
    total = int(context.get("score") or 0)
    partner = int(context.get("partner_score") or 0)
    if total >= 18 and partner >= 8:
        return "Strong"
    if total >= 10 and partner >= 4:
        return "Solid"
    if total >= 4 and partner > 0:
        return "Thin"
    return "Weak"


def _market_realism_tone(score: int) -> str:
    if score >= MARKET_REALISM_LIKELY_MIN:
        return "Likely"
    if score >= MARKET_REALISM_PLAUSIBLE_MIN:
        return "Plausible"
    if score >= MARKET_REALISM_THIN_MIN:
        return "Thin"
    return "Unlikely"


def _trade_confidence_label(score: int) -> str:
    if score >= TRADE_CONFIDENCE_HIGH_MIN:
        return "High"
    if score >= TRADE_CONFIDENCE_MEDIUM_MIN:
        return "Medium"
    return "Low"


def _trade_confidence_context(
    *,
    fit_context: Dict[str, Any] | None = None,
    market_context: Dict[str, Any] | None = None,
    reasoning_tags: List[str] | None = None,
    reasoning_summary: str = "",
) -> Dict[str, Any]:
    fit = fit_context or {}
    market = market_context or {}
    fit_score = int(fit.get("score") or 0)
    my_fit_score = int(fit.get("my_score") or 0)
    partner_fit_score = int(fit.get("partner_score") or 0)
    market_score = int(market.get("score") or 0)
    primary_reason_hits = sum(1 for tag in (reasoning_tags or []) if tag in PRIMARY_REASON_TAGS)
    has_reasoning = bool(str(reasoning_summary or "").strip())

    confidence_score = int(round(market_score * 0.62))
    confidence_score += max(-10, min(18, fit_score))
    confidence_score += max(0, min(12, partner_fit_score * 2))
    confidence_score += min(8, primary_reason_hits * 4)
    if has_reasoning:
        confidence_score += 4
    if market_score < MARKET_REALISM_PLAUSIBLE_MIN:
        confidence_score -= 12
    if bool(market.get("hard_fail")):
        confidence_score = 0
    try:
        value_delta = int(market.get("value_delta") or 0)
    except Exception:
        value_delta = 0
    if "Temporary Injury Need" in set(reasoning_tags or []) and value_delta < -700:
        confidence_score -= 24 if value_delta < -1200 else 18

    market_flags = set(market.get("flags") or [])
    if "protected_outgoing_override" in market_flags:
        confidence_score = min(confidence_score, TRADE_CONFIDENCE_HIGH_MIN - 1)

    confidence_score = max(0, min(100, confidence_score))
    confidence_label = _trade_confidence_label(confidence_score)

    surface_tier = "secondary"
    if confidence_label in {"High", "Medium"} and market_score >= MARKET_REALISM_PLAUSIBLE_MIN:
        surface_tier = "primary"

    fit_exception = (
        my_fit_score >= -8
        and not list(fit.get("my_negatives") or [])
        and value_delta >= 1200
        and "Value Arbitrage" in set(reasoning_tags or [])
    )
    headline_ready = (
        not bool(market.get("hard_fail"))
        and market_score >= TRADE_HEADLINE_REALISM_MIN
        and fit_score >= 10
        and (my_fit_score >= 0 or fit_exception)
        and partner_fit_score >= 4
        and confidence_label != "Low"
    )

    if confidence_label == "High":
        summary = "Strong fit, believable market path, and enough partner motivation to lead the board."
    elif confidence_label == "Medium":
        summary = "Useful path with a credible fit case, but acceptance still depends on timing and partner behavior."
    elif market_score < MARKET_REALISM_PLAUSIBLE_MIN:
        summary = "This path clears the engine, but the market realism is still thin enough that it should stay secondary."
    elif partner_fit_score < 4:
        summary = "Value may work, but the other manager's motivation is still light."
    else:
        summary = "The package is viable, but the recommendation confidence is not strong enough to headline."

    return {
        "score": confidence_score,
        "label": confidence_label,
        "summary": summary,
        "surface_tier": surface_tier,
        "headline_ready": headline_ready,
        "headline_fit_exception": fit_exception,
    }


def _trade_surface_sort_key(idea: Dict[str, Any]) -> tuple[int, int, int, int, int, int, int, int]:
    confidence_rank = {
        "Low": 0,
        "Medium": 1,
        "High": 2,
    }.get(str(idea.get("trade_confidence_label") or "Low"), 0)
    return (
        1 if bool(idea.get("trade_headline_ready")) else 0,
        1 if str(idea.get("trade_surface_tier") or "secondary") == "primary" else 0,
        confidence_rank,
        int(idea.get("market_realism_score") or 0),
        int(idea.get("fit_score") or 0),
        int(idea.get("partner_fit_score") or 0),
        int(idea.get("strategy_fit_score") or 0),
        int(idea.get("priority") or 0),
    )


def evaluate_trade_market_realism(
    *,
    send_assets: List[Dict[str, Any]],
    receive_assets: List[Dict[str, Any]],
    my_shape: Dict[str, Any],
    partner_shape: Dict[str, Any],
    partner_name: str,
    partner_profile: Dict[str, Any] | None = None,
    league_settings: Dict[str, Any] | None = None,
    send_score: int | None = None,
    receive_score: int | None = None,
    explicit_player_focus: bool = False,
    focused_player_ids: Sequence[str] | None = None,
) -> Dict[str, Any]:
    partner_profile = partner_profile or {}
    focused_ids = {
        str(player_id).strip()
        for player_id in (focused_player_ids or [])
        if str(player_id).strip()
    }
    score = 58
    positives: List[str] = []
    negatives: List[str] = []
    flags: List[str] = []
    hard_fail_flags: List[str] = []

    send_players = sorted(_player_assets(send_assets), key=lambda asset: int(asset.get("score") or 0), reverse=True)
    receive_players = sorted(_player_assets(receive_assets), key=lambda asset: int(asset.get("score") or 0), reverse=True)
    send_picks = _pick_assets(send_assets)
    receive_picks = _pick_assets(receive_assets)
    send_score = _score_assets(send_assets) if send_score is None else int(send_score)
    receive_score = _score_assets(receive_assets) if receive_score is None else int(receive_score)
    partner_net = send_score - receive_score
    partner_needs = set(partner_shape.get("needs") or [])
    partner_surplus = set(partner_shape.get("surplus") or [])
    send_positions = _asset_positions(send_assets)
    receive_positions = _asset_positions(receive_assets)
    partner_need_hits = send_positions & partner_needs
    partner_need_leaks = receive_positions & partner_needs
    partner_surplus_out = receive_positions & partner_surplus
    has_first_round_pick = any(_safe_int(asset.get("round"), 99) == 1 for asset in send_picks)
    partner_strategy = normalize_team_strategy(partner_shape.get("strategy") or partner_shape.get("mode"))
    net_incoming_players = len(receive_players) - len(send_players)

    if net_incoming_players > 0 and bool(my_shape.get("roster_over_limit")):
        score -= 34 + (6 * net_incoming_players)
        negatives.append("This adds roster spots while your roster is already over the practical limit.")
        flags.append("roster_limit_pressure")
        hard_fail_flags.append("roster_limit_pressure")
    elif net_incoming_players > 0 and bool(my_shape.get("roster_at_limit")):
        score -= 16 + (4 * net_incoming_players)
        negatives.append("This adds roster pressure when the cleaner move is consolidation or a one-for-one.")
        flags.append("roster_limit_pressure")

    if partner_net >= 700:
        score += 8
        positives.append(f"{partner_name} gets a clear raw-value premium.")
    elif partner_net >= 250:
        score += 4
        positives.append(f"{partner_name} gets a slight raw-value premium.")
    elif partner_net <= -1200:
        score -= 12
        negatives.append(f"{partner_name} gives up materially more raw value than the return suggests.")
        flags.append("value_gap")
    elif partner_net <= -500:
        score -= 6
        negatives.append(f"{partner_name} still pays a real value premium.")
        flags.append("value_gap")

    if partner_need_hits:
        score += min(12, 6 * len(partner_need_hits))
        positives.append(f"The offer covers a real need at {_format_pos_list(partner_need_hits)}.")
    if partner_need_leaks and not (partner_need_leaks & partner_need_hits):
        score -= min(14, 7 * len(partner_need_leaks))
        negatives.append(f"It asks {partner_name} to move from a current need position.")
        flags.append("need_leak")
        if not explicit_player_focus:
            hard_fail_flags.append("need_leak")

    best_incoming_to_partner = send_players[0] if send_players else None
    best_outgoing_from_partner = receive_players[0] if receive_players else None
    incoming_best_score = int(best_incoming_to_partner.get("score") or 0) if best_incoming_to_partner else 0
    outgoing_best_score = int(best_outgoing_from_partner.get("score") or 0) if best_outgoing_from_partner else 0
    headliner_ratio = (incoming_best_score / outgoing_best_score) if incoming_best_score and outgoing_best_score else 1.0
    partner_gets_cornerstone = bool(best_incoming_to_partner and _is_cornerstone_asset(best_incoming_to_partner, league_settings))
    partner_gives_cornerstone = bool(best_outgoing_from_partner and _is_cornerstone_asset(best_outgoing_from_partner, league_settings))
    partner_gives_premium = bool(best_outgoing_from_partner and _is_premium_market_asset(best_outgoing_from_partner, league_settings))
    user_gives_cornerstone = partner_gets_cornerstone
    user_gets_cornerstone = partner_gives_cornerstone
    settings = _pick_league_settings(league_settings)

    if best_outgoing_from_partner and best_incoming_to_partner:
        if headliner_ratio < 0.72:
            score -= 18
            negatives.append("The other side gives up the best asset without getting a comparable centerpiece back.")
            flags.append("best_asset_problem")
            hard_fail_flags.append("best_asset_problem")
        elif headliner_ratio < 0.85:
            score -= 8
            negatives.append("The incoming headline asset still trails the outgoing best asset by enough to matter in market perception.")
            flags.append("best_asset_problem")
        elif headliner_ratio >= 0.92:
            score += 6
            positives.append("The headline asset coming back is close enough to the outgoing best piece to pass a basic market check.")

    throw_in_count = sum(1 for asset in send_players[1:] if _is_throw_in_asset(asset))
    if len(send_players) >= 2 and len(receive_players) == 1 and throw_in_count > 0 and headliner_ratio < 0.9:
        score -= min(14, 7 * throw_in_count)
        negatives.append("Secondary pieces read more like throw-ins than real bridge value.")
        flags.append("throw_in_problem")
        if not has_first_round_pick:
            hard_fail_flags.append("throw_in_problem")
    elif len(send_players) >= 2 and len(receive_players) == 1 and headliner_ratio < 0.82 and not has_first_round_pick:
        score -= 10
        negatives.append("This is still a light two-for-one package from the other manager's point of view.")
        flags.append("throw_in_problem")
        hard_fail_flags.append("throw_in_problem")

    if partner_gives_premium:
        if headliner_ratio < 0.85 and not has_first_round_pick:
            score -= 12
            negatives.append("Premium market assets usually do not move for depth alone.")
            flags.append("scarcity_problem")
            hard_fail_flags.append("scarcity_problem")
        elif headliner_ratio >= 0.9 or has_first_round_pick:
            score += 4
            positives.append("The package pays a more believable premium for a scarce asset.")

    if partner_gives_cornerstone:
        if not partner_gets_cornerstone and not has_first_round_pick:
            score -= 14
            negatives.append("Cornerstone assets rarely move without a comparable cornerstone or first-round premium coming back.")
            flags.append("cornerstone_protection")
            hard_fail_flags.append("cornerstone_protection")
        elif not partner_gets_cornerstone and has_first_round_pick and headliner_ratio < 0.82:
            score -= 8
            negatives.append("A first helps, but the return still looks light for a cornerstone asset.")
            flags.append("cornerstone_protection")
            hard_fail_flags.append("cornerstone_protection")
        elif partner_gets_cornerstone:
            score += 6
            positives.append("The deal swaps one cornerstone-type asset for another, which is much closer to real market behavior.")
    if partner_gives_cornerstone and len(send_players) >= 2 and headliner_ratio < 0.88 and not has_first_round_pick:
        score -= 8
        negatives.append("This still looks light for a cornerstone-type acquisition.")
        flags.append("cornerstone_protection")
        hard_fail_flags.append("cornerstone_protection")

    focused_send_is_cornerstone = bool(
        best_incoming_to_partner
        and user_gives_cornerstone
        and str(best_incoming_to_partner.get("player_id") or "").strip() in focused_ids
    )
    extra_unfocused_sends = [
        asset
        for asset in send_players
        if str(asset.get("player_id") or "").strip() not in focused_ids
    ]
    allow_focused_core_move = bool(
        explicit_player_focus and focused_send_is_cornerstone and not extra_unfocused_sends
    )

    if user_gives_cornerstone:
        user_best_out = incoming_best_score
        user_best_in = outgoing_best_score
        user_value_delta = receive_score - send_score
        if not user_gets_cornerstone and user_value_delta < 900:
            score -= 22
            negatives.append("Your cornerstone assets should not headline a deal without a comparable cornerstone or clear value premium coming back.")
            flags.append("user_core_protection")
            if not allow_focused_core_move:
                hard_fail_flags.append("user_core_protection")
        elif user_gets_cornerstone and len(send_assets) > 1 and user_value_delta < 900 and user_best_in < user_best_out + 1000:
            score -= 18
            negatives.append("Adding extra value on top of your cornerstone needs a much clearer tier-up to headline.")
            flags.append("user_core_protection")
            hard_fail_flags.append("user_core_protection")
        elif user_gets_cornerstone and user_best_in < user_best_out + 350 and user_value_delta < 500:
            score -= 18
            negatives.append("This asks you to move a cornerstone without a clear upgrade or enough package value back.")
            flags.append("user_core_protection")
            if not allow_focused_core_move:
                hard_fail_flags.append("user_core_protection")

    user_gives_protected = any(
        _is_core_or_protected_starter(asset)
        for asset in send_players
    )
    user_best_out = incoming_best_score
    user_best_in = outgoing_best_score
    receive_has_first = any(_safe_int(asset.get("round"), 99) == 1 for asset in receive_picks)
    receive_only_low_picks = bool(receive_picks) and all(
        _safe_int(asset.get("round"), 99) >= 3
        for asset in receive_picks
    )
    clear_headline_upgrade = bool(
        user_best_in >= user_best_out + 750
        or (
            user_gets_cornerstone
            and receive_score - send_score >= 600
            and user_best_in >= user_best_out
        )
    )

    extra_protected_sends = [
        asset
        for asset in send_players
        if _is_core_or_protected_starter(asset)
        and str(asset.get("player_id") or "").strip() not in focused_ids
    ]
    focused_protected_sends = [
        asset
        for asset in send_players
        if _is_core_or_protected_starter(asset)
        and str(asset.get("player_id") or "").strip() in focused_ids
    ]
    protected_blocks_automatic_board = bool(extra_protected_sends) or (
        bool(focused_protected_sends) and not explicit_player_focus
    )

    if protected_blocks_automatic_board and not clear_headline_upgrade:
        score -= 30
        negatives.append(
            "A protected or core outgoing asset needs a clearly superior headline asset, not a depth package bridged by picks."
        )
        flags.append("protected_outgoing")
        hard_fail_flags.append("protected_outgoing")
    elif user_gives_protected:
        score -= 6
        negatives.append("This is a major core-asset move and should remain below normal automatic recommendations.")
        flags.append("protected_outgoing_override")

    if (
        user_best_out >= 4000
        and user_best_in > 0
        and user_best_in < int(round(user_best_out * 0.78))
        and not receive_has_first
        and receive_score - send_score < 1200
    ):
        score -= 24
        negatives.append("The package replaces the best outgoing asset with a materially weaker headliner.")
        flags.append("asset_quality_downgrade")
        hard_fail_flags.append("asset_quality_downgrade")

    if (
        receive_only_low_picks
        and user_best_out >= 4500
        and user_best_in < int(round(user_best_out * 0.9))
    ):
        score -= 18
        negatives.append("A third-round-or-later pick cannot bridge a major downgrade in headline asset quality.")
        flags.append("low_pick_quality_bridge")
        hard_fail_flags.append("low_pick_quality_bridge")

    if (
        settings.get("qb_format") == "1QB"
        and best_outgoing_from_partner
        and str(best_outgoing_from_partner.get("position") or "").upper() == "QB"
        and best_incoming_to_partner
        and str(best_incoming_to_partner.get("position") or "").upper() in {"RB", "WR", "TE"}
        and (
            receive_score - send_score < 700
            or (
                len(send_assets) > 1
                and int(best_outgoing_from_partner.get("score") or 0) < int(best_incoming_to_partner.get("score") or 0) + 1500
            )
        )
    ):
        score -= 18
        negatives.append("In 1QB dynasty, quarterback targets should stay low-cost unless the return is a clear value win.")
        flags.append("one_qb_qb_cost")
        hard_fail_flags.append("one_qb_qb_cost")

    if partner_surplus_out:
        score += min(6, 3 * len(partner_surplus_out))
        positives.append(f"{partner_name} is moving from {_format_pos_list(partner_surplus_out)} surplus.")

    if has_first_round_pick:
        score += 6
        positives.append("A first-round pick helps bridge market perception.")
    elif send_picks:
        score += 3
        positives.append("Owned picks make the bridge more believable.")

    send_age = _asset_avg_age(send_assets)
    receive_age = _asset_avg_age(receive_assets)
    if partner_strategy in {"rebuild", "tank"} and send_age and receive_age and send_age + 1.0 < receive_age:
        score += 5
        positives.append("The return gets younger, which fits the other timeline.")
    elif partner_strategy in {"contender", "fringe_contender"} and partner_need_hits and not any(is_injury_status(asset) for asset in send_players):
        score += 4
        positives.append("The return is usable right away for a contender build.")

    trading_style = str(partner_profile.get("trading_style") or "")
    asset_behavior = str(partner_profile.get("asset_behavior") or "")
    activity_level = str(partner_profile.get("activity_level") or "")

    if trading_style == "Passive Trader":
        score -= 6 if len(send_assets) + len(receive_assets) >= 3 else 2
        negatives.append(f"{partner_name} profiles as a passive trader.")
    elif trading_style in {"Aggressive Trader", "Deal Maker"}:
        score += 4
        positives.append(f"{partner_name} is more willing than average to engage on active trade offers.")
    elif trading_style == "Negotiator":
        score += 1

    if activity_level == "Quiet Manager":
        score -= 4
        negatives.append(f"{partner_name} is usually less active than the league average.")
    elif activity_level == "Highly Active":
        score += 3

    if asset_behavior == "Pick Hoarder":
        if send_picks:
            score += 6
            positives.append(f"{partner_name} tends to value future picks.")
        elif best_outgoing_from_partner and _is_premium_market_asset(best_outgoing_from_partner, league_settings):
            score -= 5
            negatives.append(f"{partner_name} usually wants picks back for premium pieces.")
    elif asset_behavior == "Consolidator":
        if len(send_players) >= 2 and len(receive_players) == 1:
            score -= 6
            negatives.append(f"{partner_name} usually prefers to consolidate depth into a better asset, not the reverse.")
        elif len(send_players) == 1 and len(receive_players) >= 2:
            score += 4
    elif asset_behavior == "Prospect Chaser":
        if any(0 < _asset_age(asset) <= 24 for asset in send_players):
            score += 4
            positives.append(f"{partner_name} typically values younger upside profiles.")

    deduped_hard_fail_flags = list(dict.fromkeys(hard_fail_flags))
    if deduped_hard_fail_flags:
        score = min(score, MARKET_REALISM_THIN_MIN - 1)

    score = max(0, min(100, int(round(score))))
    label = _market_realism_tone(score)
    summary_parts = negatives[:2] if score < MARKET_REALISM_PLAUSIBLE_MIN else positives[:1] + negatives[:1]
    summary = " ".join(summary_parts).strip()
    if not summary:
        summary = "The package clears the basic market and partner-fit checks."
    return {
        "score": score,
        "label": label,
        "summary": summary,
        "positives": positives,
        "negatives": negatives,
        "flags": flags,
        "hard_fail": bool(deduped_hard_fail_flags),
        "hard_fail_flags": deduped_hard_fail_flags,
        "value_delta": receive_score - send_score,
    }


def _attach_trade_assessment_fields(
    idea: Dict[str, Any],
    *,
    fit_context: Dict[str, Any] | None = None,
    market_context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    fit = fit_context or {}
    market = market_context or {}
    confidence = _trade_confidence_context(
        fit_context=fit,
        market_context=market,
        reasoning_tags=idea.get("reasoning_tags"),
        reasoning_summary=str(idea.get("reasoning_summary") or ""),
    )
    idea["fit_score"] = int(fit.get("score") or 0)
    idea["my_fit_score"] = int(fit.get("my_score") or 0)
    idea["partner_fit_score"] = int(fit.get("partner_score") or 0)
    idea["my_fit_positives"] = list(fit.get("my_positives") or [])
    idea["my_fit_negatives"] = list(fit.get("my_negatives") or [])
    idea["fit_grade"] = _fit_grade_label(fit)
    idea["fit_summary"] = str(fit.get("rationale") or "")
    idea["market_realism_score"] = int(market.get("score") or 0)
    idea["market_realism_label"] = str(market.get("label") or "Thin")
    idea["market_realism_summary"] = str(market.get("summary") or "")
    idea["market_realism_flags"] = list(market.get("flags") or [])
    idea["market_realism_hard_fail"] = bool(market.get("hard_fail"))
    idea["market_realism_hard_fail_flags"] = list(market.get("hard_fail_flags") or [])
    idea["trade_confidence_score"] = int(confidence.get("score") or 0)
    idea["trade_confidence_label"] = str(confidence.get("label") or "Low")
    idea["trade_confidence_summary"] = str(confidence.get("summary") or "")
    idea["trade_surface_tier"] = str(confidence.get("surface_tier") or "secondary")
    idea["trade_headline_ready"] = bool(confidence.get("headline_ready"))
    idea["trade_headline_fit_exception"] = bool(
        confidence.get("headline_fit_exception")
    )
    return idea


def _asset_injury_profile(assets: List[Dict[str, Any]]) -> Dict[str, Any]:
    players = _player_assets(assets)
    healthy_positions = {
        str(asset.get("position") or "").upper()
        for asset in players
        if not is_injury_status(asset)
    }
    injured_positions = {
        str(asset.get("position") or "").upper()
        for asset in players
        if is_injury_status(asset)
    }
    levels = [injury_level(asset.get("status"), asset.get("injury_status")) for asset in players]
    return {
        "healthy_positions": {pos for pos in healthy_positions if pos in CORE_POSITIONS},
        "injured_positions": {pos for pos in injured_positions if pos in CORE_POSITIONS},
        "major": sum(1 for level in levels if level == "major"),
        "moderate": sum(1 for level in levels if level == "moderate"),
        "minor": sum(1 for level in levels if level == "minor"),
    }


def _top_player_score(assets: List[Dict[str, Any]]) -> int:
    player_scores = [int(asset.get("score") or 0) for asset in _player_assets(assets)]
    return max(player_scores) if player_scores else 0


def _package_key(send_assets: List[Dict[str, Any]], receive_assets: List[Dict[str, Any]]) -> str:
    send = "|".join(sorted(str(asset["label"]) for asset in send_assets))
    receive = "|".join(sorted(str(asset["label"]) for asset in receive_assets))
    return f"{send}->{receive}"


def _make_idea(
    partner_name: str,
    send_assets: List[Dict[str, Any]],
    receive_assets: List[Dict[str, Any]],
    my_mode: str,
    partner_mode: str,
    tag: str,
    rationale: str,
    priority: int,
    reasoning_tags: List[str] | None = None,
    reasoning_summary: str = "",
    my_strategy: str = "",
    partner_strategy: str = "",
    send_score: int | None = None,
    receive_score: int | None = None,
) -> Dict[str, Any]:
    send_score = _score_assets(send_assets) if send_score is None else int(send_score)
    receive_score = _score_assets(receive_assets) if receive_score is None else int(receive_score)
    first_send = _first_player_asset(send_assets) or send_assets[0]
    first_receive = _first_player_asset(receive_assets) or receive_assets[0]

    return {
        "partner_team_name": partner_name,
        "my_player": _asset_labels(send_assets),
        "their_player": _asset_labels(receive_assets),
        "position": first_receive.get("position", ""),
        "my_score": send_score,
        "their_score": receive_score,
        "my_age": first_send.get("age", ""),
        "their_age": first_receive.get("age", ""),
        "trade_gain": int(receive_score - send_score),
        "my_mode": my_mode,
        "partner_mode": partner_mode,
        "my_strategy": team_strategy_label(my_strategy or my_mode),
        "partner_strategy": team_strategy_label(partner_strategy or partner_mode),
        "tag": tag,
        "rationale": rationale,
        "reasoning_tags": reasoning_tags or [tag],
        "reasoning_summary": reasoning_summary,
        "priority": priority,
        "my_player_id": first_send.get("player_id"),
        "their_player_id": first_receive.get("player_id"),
        "their_is_pick": first_receive.get("asset_type") == "pick",
        "send_assets": send_assets,
        "receive_assets": receive_assets,
        "send_has_pick": _has_pick(send_assets),
        "receive_has_pick": _has_pick(receive_assets),
    }


def _value_fits(send_score: int, receive_score: int, low: int = -1200, high: int = 1800) -> bool:
    diff = receive_score - send_score
    return low <= diff <= high


def _normalize_pos_list(values) -> List[str]:
    return [str(value).upper() for value in values or [] if isinstance(value, str)]


def _position_value_map(df_team: pd.DataFrame, score_field: str = "value_score") -> Dict[str, float]:
    values: Dict[str, float] = {}
    if df_team is None or df_team.empty:
        return values
    resolved_score_field = score_field if score_field in df_team.columns else "value_score"
    for pos in CORE_POSITIONS:
        pos_df = df_team[df_team["position"] == pos]
        series = (
            pos_df[resolved_score_field]
            if resolved_score_field in pos_df.columns
            else pd.Series(dtype="float64")
        )
        values[pos] = float(
            pd.to_numeric(series, errors="coerce").fillna(0).sum()
        )
    return values


def _draft_profile(
    pick_assets: List[Dict[str, Any]],
    league_capitals: List[int] | None = None,
) -> Dict[str, Any]:
    total = int(sum(int(pick.get("score") or 0) for pick in pick_assets or []))
    firsts = sum(1 for pick in pick_assets or [] if _safe_int(pick.get("round"), 0) == 1)
    seconds = sum(1 for pick in pick_assets or [] if _safe_int(pick.get("round"), 0) == 2)
    pick_count = len(pick_assets or [])
    tier = "middle"
    if league_capitals:
        series = pd.Series(league_capitals, dtype="float64")
        q25 = float(series.quantile(0.25))
        q75 = float(series.quantile(0.75))
        if total <= q25:
            tier = "low"
        elif total >= q75:
            tier = "high"
    return {
        "draft_capital": total,
        "first_rounders": firsts,
        "second_rounders": seconds,
        "pick_count": pick_count,
        "draft_capital_tier": tier,
    }


_TEAM_SHAPE_STORE: dict[str, Dict[str, Any]] = {}
_TEAM_SHAPE_USED_AT: dict[str, float] = {}
_MAX_TEAM_SHAPES = 64
_TEAM_SHAPE_STATS: dict[str, float] = {
    "hits": 0,
    "misses": 0,
    "signature_ms": 0.0,
    "lineup_ms": 0.0,
    "injury_ms": 0.0,
    "needs_ms": 0.0,
}
_SEARCH_AUDIT: dict[str, Any] = {
    "dataframe_copies": 0,
    "universe_scans": 0,
    "roster_index_calls": 0,
    "draft_context_skipped": 0,
    "streamlit_cache_data": 0,
    "strategy_curve": "",
}


def clear_team_shape_memos() -> None:
    """Drop deterministic team-shape memos (league switch / logout)."""

    _TEAM_SHAPE_STORE.clear()
    _TEAM_SHAPE_USED_AT.clear()
    reset_player_search_audit()


def reset_player_search_audit() -> None:
    _TEAM_SHAPE_STATS.update(
        {
            "hits": 0,
            "misses": 0,
            "signature_ms": 0.0,
            "lineup_ms": 0.0,
            "injury_ms": 0.0,
            "needs_ms": 0.0,
        }
    )
    _SEARCH_AUDIT.update(
        {
            "dataframe_copies": 0,
            "universe_scans": 0,
            "roster_index_calls": 0,
            "draft_context_skipped": 0,
            "streamlit_cache_data": 0,
            "strategy_curve": "",
        }
    )


def player_search_audit_snapshot() -> dict[str, Any]:
    return {
        **{key: int(value) if key in {"hits", "misses"} else round(float(value), 3)
           for key, value in _TEAM_SHAPE_STATS.items()},
        **dict(_SEARCH_AUDIT),
        "team_shape_store": team_shape_store_size(),
        "streamlit_cache_data_absent": True,
    }


def _merge_player_search_audit(diagnostics: Dict[str, Any]) -> Dict[str, Any]:
    audit = player_search_audit_snapshot()
    diagnostics["team_shape_hits"] = audit["hits"]
    diagnostics["team_shape_misses"] = audit["misses"]
    diagnostics["team_shape_lineup_ms"] = audit["lineup_ms"]
    diagnostics["team_shape_injury_ms"] = audit["injury_ms"]
    diagnostics["team_shape_needs_ms"] = audit["needs_ms"]
    diagnostics["team_shape_signature_ms"] = audit["signature_ms"]
    diagnostics["dataframe_copies"] = audit["dataframe_copies"]
    diagnostics["universe_scans"] = audit["universe_scans"]
    diagnostics["roster_index_calls"] = audit["roster_index_calls"]
    diagnostics["draft_context_skipped"] = audit["draft_context_skipped"]
    diagnostics["strategy_curve"] = audit["strategy_curve"]
    diagnostics["streamlit_cache_data_absent"] = True
    return diagnostics


def team_shape_store_size() -> int:
    return len(_TEAM_SHAPE_STORE)


@contextmanager
def _find_block(session_state, name: str):
    """Exclusive Find-search child. No-ops when HOT_PATH session is absent."""

    if session_state is None:
        yield {"cache_status": ""}
        return
    from modules import warm_route_render as wrr

    with wrr.block(
        session_state,
        name,
        owner="explicit_player_search",
        work_kind="compute",
    ) as meta:
        yield meta


def _team_shape_signature(
    df_summary: pd.DataFrame,
    roster_id: int,
    df_team: pd.DataFrame,
    score_field: str,
    pick_assets: List[Dict[str, Any]] | None,
    league_draft_capitals: List[int] | None,
    league_settings: Dict[str, Any] | None,
) -> str:
    roster_key = _safe_int(roster_id)
    summary_fp: tuple[Any, ...] = ()
    if df_summary is not None and not df_summary.empty and "roster_id" in df_summary.columns:
        roster_ids = pd.to_numeric(df_summary["roster_id"], errors="coerce")
        matched = df_summary[roster_ids == roster_key]
        if not matched.empty:
            row = matched.iloc[0]
            summary_fp = (
                _safe_int(row.get("total_score")),
                str(row.get("strategy") or row.get("mode") or ""),
                str(row.get("strengths") or ""),
                str(row.get("weaknesses") or ""),
                str(row.get("avg_age") or ""),
            )
    team_fp: tuple[Any, ...] = ()
    if df_team is not None and not df_team.empty and "player_id" in df_team.columns:
        scores = (
            pd.to_numeric(df_team[score_field], errors="coerce").fillna(0)
            if score_field in df_team.columns
            else pd.Series(0, index=df_team.index)
        )
        team_fp = tuple(
            zip(
                df_team["player_id"].astype(str).tolist(),
                [int(value) for value in scores.tolist()],
            )
        )
    pick_fp = tuple(
        sorted(int(pick.get("score") or 0) for pick in (pick_assets or []))
    )
    settings_fp = tuple(
        sorted((str(key), str(value)) for key, value in dict(league_settings or {}).items())
    )
    payload = json.dumps(
        [
            roster_key,
            str(score_field or ""),
            summary_fp,
            team_fp,
            pick_fp,
            list(league_draft_capitals or []),
            settings_fp,
        ],
        separators=(",", ":"),
        default=str,
    )
    return sha256(payload.encode("utf-8")).hexdigest()[:32]


def _index_roster_team_frames(
    df_players: pd.DataFrame,
    roster_players_map: Dict[int, List[str]],
) -> Dict[int, pd.DataFrame]:
    if df_players is None or df_players.empty or "player_id" not in df_players.columns:
        return {}
    owner: Dict[str, int] = {}
    for roster_id, player_ids in (roster_players_map or {}).items():
        rid = _safe_int(roster_id)
        if rid <= 0:
            continue
        for player_id in player_ids or []:
            key = str(player_id or "")
            if key:
                owner[key] = rid
    if not owner:
        return {}
    _SEARCH_AUDIT["roster_index_calls"] = int(_SEARCH_AUDIT.get("roster_index_calls") or 0) + 1
    mapped = df_players["player_id"].astype(str).map(owner)
    frames: Dict[int, pd.DataFrame] = {}
    for roster_id, group in df_players.groupby(mapped, sort=False):
        if pd.isna(roster_id):
            continue
        frames[int(roster_id)] = group
    return frames


_TEAM_SHAPE_WORK_COLUMNS = (
    "player_id",
    "position",
    "age",
    "years_exp",
    "status",
    "injury_status",
    "injury_risk_score",
    "news_updated",
    "name",
    "team",
    "value_score",
    "dynasty_score",
    "market_score",
    "role_score",
    "score",
    "value",
    "player_tier",
    "opportunity_label",
    "opportunity_source_flags",
    "workload_trend",
    "role",
    "role_label",
    "tier_label",
    "suggested_starter",
    "slot",
    "projected_starter",
    "depth_chart_slot",
    "depth_chart_order",
)


def _slim_team_shape_frame(df_team: pd.DataFrame, score_field: str) -> pd.DataFrame:
    """Column subset for lineup/injury/needs. Does not change row membership."""

    if df_team is None or getattr(df_team, "empty", True):
        return df_team
    wanted = [column for column in _TEAM_SHAPE_WORK_COLUMNS if column in df_team.columns]
    if score_field and score_field in df_team.columns and score_field not in wanted:
        wanted.append(str(score_field))
    if not wanted:
        return df_team
    return df_team.loc[:, wanted]


def _emit_team_shape_substages(session_state) -> None:
    if session_state is None:
        return
    from modules import warm_route_render as wrr

    audit = player_search_audit_snapshot()
    for name, key in (
        ("player_search_team_shape_signature", "signature_ms"),
        ("player_search_team_shape_lineup", "lineup_ms"),
        ("player_search_team_shape_injury", "injury_ms"),
        ("player_search_team_shape_needs", "needs_ms"),
    ):
        wrr._emit_block(
            session_state,
            name=name,
            owner="explicit_player_search",
            work_kind="compute",
            duration_ms=float(audit.get(key) or 0.0),
            cache_status="",
            exclusive=False,
        )


def _build_team_shape(
    df_summary: pd.DataFrame,
    roster_id: int,
    df_team: pd.DataFrame,
    score_field: str = "value_score",
    pick_assets: List[Dict[str, Any]] | None = None,
    league_draft_capitals: List[int] | None = None,
    league_settings: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    signature_started = time.perf_counter()
    signature = _team_shape_signature(
        df_summary,
        roster_id,
        df_team,
        score_field,
        pick_assets,
        league_draft_capitals,
        league_settings,
    )
    _TEAM_SHAPE_STATS["signature_ms"] = float(_TEAM_SHAPE_STATS["signature_ms"]) + (
        (time.perf_counter() - signature_started) * 1000.0
    )
    cached = _TEAM_SHAPE_STORE.get(signature)
    if cached is not None:
        _TEAM_SHAPE_USED_AT[signature] = time.time()
        _TEAM_SHAPE_STATS["hits"] = float(_TEAM_SHAPE_STATS["hits"]) + 1
        # Callers mutate top-level strategy/mode keys; keep the memo intact.
        return dict(cached)
    _TEAM_SHAPE_STATS["misses"] = float(_TEAM_SHAPE_STATS["misses"]) + 1
    work_team = _slim_team_shape_frame(df_team, score_field)
    metrics = get_team_vs_league(df_summary, roster_id) or {}
    strategy = normalize_team_strategy(metrics.get("strategy") or metrics.get("mode"))
    counts = (
        work_team["position"].astype(str).value_counts().to_dict()
        if work_team is not None and not work_team.empty and "position" in work_team.columns
        else {}
    )
    lineup_started = time.perf_counter()
    lineup_df = (
        suggest_optimal_lineup(work_team, league_settings, score_field=score_field)
        if work_team is not None and not work_team.empty
        else pd.DataFrame()
    )
    _TEAM_SHAPE_STATS["lineup_ms"] = float(_TEAM_SHAPE_STATS["lineup_ms"]) + (
        (time.perf_counter() - lineup_started) * 1000.0
    )
    injury_started = time.perf_counter()
    injury_context = summarize_team_injuries(work_team, lineup_df)
    _TEAM_SHAPE_STATS["injury_ms"] = float(_TEAM_SHAPE_STATS["injury_ms"]) + (
        (time.perf_counter() - injury_started) * 1000.0
    )
    needs_started = time.perf_counter()
    smart_needs, room_coverage = true_roster_needs(
        work_team,
        lineup_df,
        league_settings,
        metrics.get("weaknesses", []),
    )
    _TEAM_SHAPE_STATS["needs_ms"] = float(_TEAM_SHAPE_STATS["needs_ms"]) + (
        (time.perf_counter() - needs_started) * 1000.0
    )
    injured_starter_positions = [
        str(pos).upper()
        for pos in (injury_context.get("injured_positions") or [])
        if str(pos).upper() in CORE_POSITIONS
    ]
    injury_burden = float(metrics.get("injury_burden") or injury_context.get("injury_burden") or 0.0)
    shape = {
        "mode": team_strategy_mode(strategy),
        "strategy": strategy,
        "strategy_label": team_strategy_label(strategy),
        "needs": _normalize_pos_list(smart_needs),
        "room_coverage": room_coverage,
        "surplus": _normalize_pos_list(metrics.get("strengths", [])),
        "counts": counts,
        "minimums": _team_position_minimums(league_settings),
        "position_values": _position_value_map(work_team, score_field),
        "avg_age": metrics.get("avg_age"),
        "league_age_mean": metrics.get("league_age_mean"),
        "injury_burden": injury_burden,
        "injured_count": int(metrics.get("injured_count") or injury_context.get("injured_roster") or 0),
        "major_absences": int(metrics.get("major_absences") or injury_context.get("major_absences") or 0),
        "injured_starters": int(metrics.get("injured_starters") or injury_context.get("injured_starters") or 0),
        "injured_starter_positions": {
            pos for pos in injured_starter_positions if pos in CORE_POSITIONS
        },
        "health_flag": str(metrics.get("health_flag") or injury_context.get("health_flag") or "Stable"),
        "archetype": str(metrics.get("archetype") or metrics.get("archetype_label") or ""),
        "archetype_label": str(metrics.get("archetype_label") or metrics.get("archetype") or ""),
    }
    shape.update(_team_roster_size_context(df_team, league_settings))
    temporary_injury_need_positions = {
        pos
        for pos in shape["injured_starter_positions"]
        if pos not in set(shape["needs"] or [])
    }
    shape["temporary_injury_need_positions"] = temporary_injury_need_positions
    shape.update(_draft_profile(pick_assets or [], league_draft_capitals or []))
    if len(_TEAM_SHAPE_STORE) >= _MAX_TEAM_SHAPES:
        oldest = min(_TEAM_SHAPE_STORE, key=lambda key: _TEAM_SHAPE_USED_AT.get(key, 0.0))
        _TEAM_SHAPE_STORE.pop(oldest, None)
        _TEAM_SHAPE_USED_AT.pop(oldest, None)
    _TEAM_SHAPE_STORE[signature] = deepcopy(shape)
    _TEAM_SHAPE_USED_AT[signature] = time.time()
    return shape


def _is_core_or_protected_starter(asset: Dict[str, Any]) -> bool:
    if asset.get("asset_type") != "player":
        return False
    if bool(asset.get("is_protected")):
        return True
    role = str(asset.get("role") or "").strip().lower()
    tier_rank = _asset_tier_rank(asset)
    score = int(asset.get("score") or 0)
    age = _asset_age(asset)
    if role in {"core", "core asset", "core starter", "untouchable", "protected"}:
        return True
    if tier_rank >= TIER_MARKET_RANK["core starter"]:
        return True
    if score >= 6500:
        return True
    if 0 < age <= 25 and score >= 5200:
        return True
    if tier_rank >= TIER_MARKET_RANK["starter"] and score >= 5000:
        return True
    return False


def _automatic_outgoing_asset_allowed(
    asset: Dict[str, Any],
    *,
    explicit_player_focus: bool = False,
) -> bool:
    """Keep protected assets off automatic boards while allowing intentional focus flows."""
    return bool(explicit_player_focus or not _is_core_or_protected_starter(asset))


def _is_long_term_starter_asset(asset: Dict[str, Any]) -> bool:
    if asset.get("asset_type") != "player":
        return False
    tier_rank = _asset_tier_rank(asset)
    score = int(asset.get("score") or 0)
    age = _asset_age(asset)
    if tier_rank >= TIER_MARKET_RANK["core starter"]:
        return True
    if score >= 6500:
        return True
    if 0 < age <= 25 and score >= 5200:
        return True
    return False


def _temporary_injury_trade_guardrail(
    my_shape: Dict[str, Any],
    send_assets: List[Dict[str, Any]],
    receive_assets: List[Dict[str, Any]],
) -> Dict[str, Any]:
    temporary_positions = {
        str(pos).upper()
        for pos in (my_shape.get("temporary_injury_need_positions") or [])
        if str(pos).upper() in CORE_POSITIONS
    }
    if not temporary_positions:
        return {"applied": False, "score_delta": 0, "hard_fail": False, "tags": [], "summary": ""}

    receive_players = _player_assets(receive_assets)
    send_players = _player_assets(send_assets)
    receive_positions = _asset_positions(receive_assets)
    send_positions = _asset_positions(send_assets)
    injury_cover_positions = receive_positions & temporary_positions
    if not injury_cover_positions:
        return {"applied": False, "score_delta": 0, "hard_fail": False, "tags": [], "summary": ""}

    true_needs = set(my_shape.get("needs") or [])
    true_need_hits = receive_positions & true_needs
    incoming_best = max((int(asset.get("score") or 0) for asset in receive_players), default=0)
    outgoing_best = max((int(asset.get("score") or 0) for asset in send_players), default=0)
    incoming_long_term = any(_is_long_term_starter_asset(asset) for asset in receive_players)
    outgoing_core = any(_is_core_or_protected_starter(asset) for asset in send_players)
    same_position_cover = bool(send_positions & injury_cover_positions)
    low_cost_outgoing = (
        not send_players
        or outgoing_best <= 3600
        or all(not _is_core_or_protected_starter(asset) for asset in send_players)
    )
    strong_value_win = incoming_best >= outgoing_best + 900
    long_term_upgrade = incoming_long_term and incoming_best >= outgoing_best + 350

    tags = ["Temporary Injury Need"]
    reasons = [
        f"{_format_pos_list(injury_cover_positions)} is treated as temporary injury coverage, not a permanent roster hole."
    ]
    score_delta = -8
    hard_fail = False

    if not true_need_hits:
        tags.append("Short-Term Coverage Only")
        score_delta -= 14
        reasons.append("Prefer waiver/depth solutions unless the trade is low-cost or a clear long-term upgrade.")
    if outgoing_core and not (long_term_upgrade or strong_value_win):
        tags.append("Core Starter Protected")
        score_delta -= 45
        hard_fail = True
        reasons.append("Core starters and premium young assets are protected from short-term injury patches.")
    elif outgoing_core:
        tags.append("Core Starter Protected")
        score_delta -= 12
        reasons.append("Outgoing core value requires a clear long-term upgrade.")
    if same_position_cover and not long_term_upgrade:
        tags.append("Backup After Injury Return")
        score_delta -= 28
        hard_fail = True
        reasons.append("Same-position injury cover can become a backup once the injured starter returns.")
    elif not low_cost_outgoing and not (long_term_upgrade or strong_value_win):
        tags.append("Prefer Waiver/Depth Solution")
        score_delta -= 18
        reasons.append("The cost is too high for a temporary coverage problem.")
    if low_cost_outgoing and not outgoing_core:
        score_delta += 18
        tags.append("Low-Cost Coverage")

    return {
        "applied": True,
        "score_delta": score_delta,
        "hard_fail": hard_fail,
        "tags": tags,
        "summary": " ".join(reasons),
    }


def _player_trade_fit(
    asset: Dict[str, Any],
    role: str,
    my_shape: Dict[str, Any],
    partner_shape: Dict[str, Any] | None = None,
) -> int:
    pos = str(asset.get("position") or "").upper()
    score = 0
    if role == "Bench":
        score += 28
    elif role == "Flex":
        score += 14
    elif role == "Core":
        score -= 40

    if pos in my_shape.get("surplus", []):
        score += 10
    if pos in my_shape.get("needs", []):
        score -= 32

    if partner_shape:
        if pos in partner_shape.get("needs", []):
            score += 18
        if pos in partner_shape.get("surplus", []):
            score -= 8

    try:
        age = float(asset.get("age") or 0)
    except Exception:
        age = 0
    if age >= 27:
        score += 6
    archetype = _compatible_trade_archetype(
        normalize_team_strategy(my_shape.get("strategy") or my_shape.get("mode")),
        str(my_shape.get("archetype_label") or my_shape.get("archetype") or ""),
    )
    if (
        archetype in {"Juggernaut", "Young Competitive Team", "Asset Consolidator"}
        and 0 < age <= 25
        and (
            _asset_tier_rank(asset) >= TIER_MARKET_RANK["core starter"]
            or int(asset.get("score") or 0) >= 6000
        )
    ):
        score -= 24
    return score


def _target_trade_fit(
    asset: Dict[str, Any],
    my_shape: Dict[str, Any],
    partner_shape: Dict[str, Any],
) -> int:
    pos = str(asset.get("position") or "").upper()
    score = 0
    if pos in my_shape.get("needs", []):
        score += 34
    if pos in my_shape.get("surplus", []):
        score -= 6
    if pos in partner_shape.get("surplus", []):
        score += 8
    if pos in partner_shape.get("needs", []):
        score -= 18
    try:
        age = float(asset.get("age") or 0)
    except Exception:
        age = 0
    my_strategy = normalize_team_strategy(my_shape.get("strategy") or my_shape.get("mode"))
    if my_strategy in {"rebuild", "tank"} and 0 < age <= 25:
        score += 12 if my_strategy == "tank" else 8
    if my_strategy == "retool" and 0 < age <= 26:
        score += 5
    if team_strategy_mode(my_strategy) in {"contender", "competitive"} and 27 <= age <= 30:
        score += 5
    archetype = _compatible_trade_archetype(
        my_strategy,
        str(my_shape.get("archetype_label") or my_shape.get("archetype") or ""),
    )
    if archetype in {"Juggernaut", "Young Competitive Team", "Asset Consolidator"}:
        if _asset_tier_rank(asset) >= TIER_MARKET_RANK["star"]:
            score += 10
        if 0 < age <= 25:
            score += 4
    elif archetype == "Aging Contender" and 26 <= age <= 30:
        score += 7
    return score


def _fit_priority(
    send_assets: List[Dict[str, Any]],
    receive_assets: List[Dict[str, Any]],
    my_shape: Dict[str, Any],
    partner_shape: Dict[str, Any],
) -> int:
    total = 0
    for asset in send_assets:
        pos = str(asset.get("position") or "").upper()
        if asset.get("asset_type") == "pick":
            my_strategy = normalize_team_strategy(my_shape.get("strategy") or my_shape.get("mode"))
            if my_strategy in {"contender", "fringe_contender"}:
                total += 6
            elif my_strategy == "retool":
                total += 1
            else:
                total -= 7
            continue
        if pos in my_shape.get("surplus", []):
            total += 5
        if pos in my_shape.get("needs", []):
            total -= 22
        if pos in partner_shape.get("needs", []):
            total += 10
    for asset in receive_assets:
        pos = str(asset.get("position") or "").upper()
        if asset.get("asset_type") == "pick":
            my_strategy = normalize_team_strategy(my_shape.get("strategy") or my_shape.get("mode"))
            if my_strategy == "tank":
                total += 16
            elif my_strategy == "rebuild":
                total += 12
            elif my_strategy == "retool":
                total += 5
            else:
                total += 2
            continue
        if pos in my_shape.get("needs", []):
            total += 24
        if pos in partner_shape.get("surplus", []):
            total += 6
        if pos in partner_shape.get("needs", []):
            total -= 14
    return total


def _asset_position_counts(assets: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for asset in assets:
        if asset.get("asset_type") != "player":
            continue
        pos = str(asset.get("position") or "").upper()
        if pos in CORE_POSITIONS:
            counts[pos] = counts.get(pos, 0) + 1
    return counts


def _join_clauses(parts: List[str]) -> str:
    items = [part for part in parts if part]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _team_fit_assessment(
    shape: Dict[str, Any],
    outgoing_assets: List[Dict[str, Any]],
    incoming_assets: List[Dict[str, Any]],
    *,
    team_label: str,
    is_you: bool,
) -> Dict[str, Any]:
    positives: List[str] = []
    negatives: List[str] = []
    score = 0

    outgoing_counts = _asset_position_counts(outgoing_assets)
    incoming_counts = _asset_position_counts(incoming_assets)
    current_counts = {
        str(pos).upper(): int(count or 0)
        for pos, count in (shape.get("counts") or {}).items()
    }
    minimums = {
        str(pos).upper(): int(count or 0)
        for pos, count in (shape.get("minimums") or {}).items()
    }
    needs = set(shape.get("needs") or [])
    surplus = set(shape.get("surplus") or [])

    get_verb = "get" if is_you else "gets"
    move_verb = "move" if is_you else "moves"
    use_verb = "use" if is_you else "uses"
    spend_verb = "spend" if is_you else "spends"
    add_verb = "add" if is_you else "adds"

    for pos in CORE_POSITIONS:
        sent = outgoing_counts.get(pos, 0)
        received = incoming_counts.get(pos, 0)
        net = received - sent
        current = current_counts.get(pos, 0)
        projected = current + net
        minimum = minimums.get(pos, POSITION_MINIMUMS.get(pos, 0))

        if pos in needs and received > 0:
            score += 18
            positives.append(f"{get_verb} {pos} help")
        if pos in surplus and sent > 0:
            score += 12
            positives.append(f"{move_verb} from {pos} surplus")

        if pos in needs and sent > received:
            score -= 26
            negatives.append(f"{spend_verb} from a weak {pos} room")

        if projected < minimum and net < 0:
            score -= 18 + (6 * max(1, minimum - projected))
            negatives.append(f"create a {pos} depth problem")
        elif sent > received and projected == minimum and pos not in surplus:
            score -= 10
            negatives.append(f"thin {pos} depth")

    incoming_has_pick = any(asset.get("asset_type") == "pick" for asset in incoming_assets)
    outgoing_has_pick = any(asset.get("asset_type") == "pick" for asset in outgoing_assets)
    strategy = normalize_team_strategy(shape.get("strategy") or shape.get("mode"))
    mode = team_strategy_mode(strategy)
    if incoming_has_pick:
        if strategy == "tank":
            score += 14
            positives.append(f"{add_verb} draft capital")
        elif strategy == "rebuild":
            score += 11
            positives.append(f"{add_verb} draft capital")
        elif strategy == "retool":
            score += 6
            positives.append(f"{add_verb} future flexibility")
        elif mode == "competitive":
            score += 4
            positives.append(f"{add_verb} future flexibility")
    if outgoing_has_pick:
        if strategy == "tank":
            score -= 16
            negatives.append(f"{spend_verb} future capital")
        elif strategy == "rebuild":
            score -= 12
            negatives.append(f"{spend_verb} future capital")
        elif strategy == "retool":
            score -= 2
            negatives.append(f"{spend_verb} future flexibility")
        elif mode == "contender":
            score += 4
            positives.append(f"{use_verb} future capital to improve now")

    if not positives:
        score -= 8

    summary = ""
    if positives:
        summary = f"{team_label} {_join_clauses(positives[:2])}."

    return {
        "score": score,
        "positives": positives,
        "negatives": negatives,
        "summary": summary,
    }


def _trade_fit_context(
    my_shape: Dict[str, Any],
    partner_shape: Dict[str, Any],
    send_assets: List[Dict[str, Any]],
    receive_assets: List[Dict[str, Any]],
    partner_name: str,
) -> Dict[str, Any]:
    my_view = _team_fit_assessment(
        my_shape,
        outgoing_assets=send_assets,
        incoming_assets=receive_assets,
        team_label="You",
        is_you=True,
    )
    partner_view = _team_fit_assessment(
        partner_shape,
        outgoing_assets=receive_assets,
        incoming_assets=send_assets,
        team_label=partner_name,
        is_you=False,
    )

    combined_score = int(my_view["score"]) + int(partner_view["score"])
    rationale_parts = [part for part in [my_view["summary"], partner_view["summary"]] if part]
    return {
        "score": combined_score,
        "my_score": int(my_view["score"]),
        "partner_score": int(partner_view["score"]),
        "my_positives": list(my_view["positives"]),
        "my_negatives": list(my_view["negatives"]),
        "partner_positives": list(partner_view["positives"]),
        "partner_negatives": list(partner_view["negatives"]),
        "rationale": " ".join(rationale_parts).strip(),
    }


def _format_pos_list(values: set[str] | List[str]) -> str:
    ordered = [pos for pos in CORE_POSITIONS if pos in set(values or [])]
    return " / ".join(ordered)


def _room_need_reason(shape: Dict[str, Any], positions: set[str]) -> str:
    room_coverage = shape.get("room_coverage") or {}
    reasons = []
    for position in CORE_POSITIONS:
        if position not in positions:
            continue
        need_type = str(
            (room_coverage.get(position) or {}).get("need_type") or ""
        ).strip()
        if need_type:
            reasons.append(f"{position}: {need_type}")
    return "; ".join(reasons)


def _compatible_trade_archetype(strategy: str, archetype: str) -> str:
    strategy_key = normalize_team_strategy(strategy)
    archetype_label = str(archetype or "").strip()
    compatible = {
        "contender": {"Juggernaut", "Aging Contender", "Win-Now", "Balanced Contender"},
        "fringe_contender": {
            "Young Competitive Team",
            "One Move Away",
            "Asset Consolidator",
            "Balanced Contender",
        },
        "retool": {
            "Young Competitive Team",
            "One Move Away",
            "Asset Consolidator",
            "Retool Candidate",
        },
        "rebuild": {"Pick Hoarder", "Youth Movement", "Productive Struggle", "Full Rebuild"},
        "tank": {"Pick Hoarder", "Youth Movement", "Productive Struggle", "Full Rebuild"},
    }
    return archetype_label if archetype_label in compatible.get(strategy_key, set()) else ""


def trade_strategy_fit_context(
    my_shape: Dict[str, Any],
    send_assets: List[Dict[str, Any]],
    receive_assets: List[Dict[str, Any]],
) -> Dict[str, Any]:
    strategy = normalize_team_strategy(my_shape.get("strategy") or my_shape.get("mode"))
    archetype = _compatible_trade_archetype(
        strategy,
        str(my_shape.get("archetype_label") or my_shape.get("archetype") or ""),
    )
    label = archetype or team_strategy_label(strategy)
    send_players = _player_assets(send_assets)
    receive_players = _player_assets(receive_assets)
    outgoing_picks = _pick_assets(send_assets)
    incoming_picks = _pick_assets(receive_assets)
    send_age = _asset_avg_age(send_assets)
    receive_age = _asset_avg_age(receive_assets)
    send_top = _top_player_score(send_assets)
    receive_top = _top_player_score(receive_assets)
    value_gap = _score_assets(receive_assets) - _score_assets(send_assets)
    consolidation = (
        len(send_players) > len(receive_players)
        and receive_top >= send_top + 350
    )
    immediate_upgrade = receive_top >= send_top + 350
    younger_return = bool(
        send_age and receive_age and receive_age + 1.0 <= send_age
    )
    older_return = bool(receive_age and receive_age >= 28.5)
    outgoing_young_core = any(
        _asset_age(asset) <= 25
        and (
            _asset_tier_rank(asset) >= TIER_MARKET_RANK["core starter"]
            or str(asset.get("role") or "") == "Core"
            or int(asset.get("score") or 0) >= 6000
        )
        for asset in send_players
        if _asset_age(asset) > 0
    )

    score = 0
    reasons: List[str] = []
    risk_label = ""
    if strategy in {"rebuild", "tank"}:
        if incoming_picks:
            score += 14 if strategy == "tank" else 11
        if younger_return:
            score += 8
        if outgoing_picks:
            score -= 14 if strategy == "tank" else 10
        if older_return and not incoming_picks:
            score -= 8
            risk_label = "Timeline Risk"
        reasons.append(
            f"Because this team profiles as {team_strategy_label(strategy).lower()}, this path prioritizes picks and younger assets over short-term-only upgrades."
        )
    elif strategy in {"contender", "fringe_contender"}:
        if immediate_upgrade:
            score += 10
        if outgoing_picks and immediate_upgrade:
            score += 4
        if incoming_picks and not immediate_upgrade:
            score -= 5
        if older_return and immediate_upgrade:
            score += 3
        reasons.append(
            f"Because this team profiles as {team_strategy_label(strategy).lower()}, this path prioritizes immediate lineup help."
        )
    else:
        if value_gap >= 0:
            score += 4
        if younger_return:
            score += 5
        if outgoing_picks and not immediate_upgrade:
            score -= 6
            risk_label = "Future Value Risk"
        if incoming_picks and not receive_players:
            score -= 3
        reasons.append(
            "Because this team profiles as retooling, this path balances present help with age and future value."
        )

    if archetype in {"Juggernaut", "Young Competitive Team", "Asset Consolidator"}:
        if consolidation:
            score += 12
        if receive_top >= 7000:
            score += 5
        if outgoing_young_core:
            score -= 18
            risk_label = "Young Core Risk"
        reasons = [
            f"Because this roster is a {archetype.lower()}, this path favors consolidation into premium assets without selling young core pieces cheaply."
        ]
    elif archetype == "Aging Contender":
        if immediate_upgrade:
            score += 7
        if outgoing_picks and not immediate_upgrade:
            score -= 10
            risk_label = "Age-Cliff / Future Value Risk"
        if value_gap < -700:
            score -= 6
            risk_label = risk_label or "Age-Cliff / Future Value Risk"
        reasons = [
            "Because this roster is an aging contender, this path values immediate production but requires enough win-now benefit to justify future-value risk."
        ]
    elif archetype in {"Full Rebuild", "Pick Hoarder", "Youth Movement", "Productive Struggle"}:
        if incoming_picks:
            score += 5
        if younger_return:
            score += 4
        if outgoing_young_core:
            score -= 16
            risk_label = "Young Core Risk"
        reasons = [
            f"Because this roster is a {archetype.lower()}, this path protects young core value and favors future flexibility."
        ]
    elif archetype in {"Balanced Contender", "Retool Candidate", "One Move Away"}:
        if value_gap >= 0:
            score += 3
        if abs(value_gap) > 1400:
            score -= 6

    if value_gap <= -1800:
        score = min(score, -8)
    elif value_gap <= -1000:
        score = min(score, 0)

    score = max(-18, min(18, int(score)))
    return {
        "score": score,
        "strategy": strategy,
        "strategy_label": team_strategy_label(strategy),
        "archetype": archetype,
        "profile_label": label,
        "reason": reasons[0] if reasons and score != 0 else "",
        "risk_label": risk_label,
        "applied": bool(score),
    }


def _apply_strategy_context_to_idea(
    idea: Dict[str, Any],
    reasoning: Dict[str, Any],
    my_shape: Dict[str, Any],
) -> Dict[str, Any]:
    idea["strategy_fit_score"] = int(reasoning.get("strategy_fit_score") or 0)
    idea["strategy_fit_reason"] = str(reasoning.get("strategy_fit_reason") or "")
    idea["strategy_archetype"] = str(reasoning.get("strategy_archetype") or "")
    idea["strategy_risk_label"] = str(reasoning.get("strategy_risk_label") or "")
    idea["strategy_profile_label"] = str(
        reasoning.get("strategy_profile_label")
        or my_shape.get("strategy_label")
        or ""
    )
    idea["trade_guardrail_flags"] = list(reasoning.get("guardrail_flags") or [])
    idea["trade_guardrail_summary"] = str(reasoning.get("guardrail_summary") or "")
    idea["trade_guardrail_hard_fail"] = bool(reasoning.get("guardrail_hard_fail"))
    return idea


def _trade_reasoning_context(
    my_shape: Dict[str, Any],
    partner_shape: Dict[str, Any],
    send_assets: List[Dict[str, Any]],
    receive_assets: List[Dict[str, Any]],
    partner_name: str,
) -> Dict[str, Any]:
    tags: List[str] = []
    explanations: List[str] = []
    score = 0

    send_positions = _asset_positions(send_assets)
    receive_positions = _asset_positions(receive_assets)
    my_needs = set(my_shape.get("needs") or [])
    my_surplus = set(my_shape.get("surplus") or [])
    partner_needs = set(partner_shape.get("needs") or [])
    partner_surplus = set(partner_shape.get("surplus") or [])
    my_strategy = normalize_team_strategy(my_shape.get("strategy") or my_shape.get("mode"))
    partner_strategy = normalize_team_strategy(partner_shape.get("strategy") or partner_shape.get("mode"))
    my_mode = team_strategy_mode(my_strategy)
    partner_mode = team_strategy_mode(partner_strategy)
    strategy_context = trade_strategy_fit_context(
        my_shape,
        send_assets,
        receive_assets,
    )
    score += int(strategy_context.get("score") or 0)
    if strategy_context.get("reason"):
        explanations.insert(0, str(strategy_context["reason"]))
    injury_guardrail = _temporary_injury_trade_guardrail(
        my_shape,
        send_assets,
        receive_assets,
    )
    if injury_guardrail.get("applied"):
        score += int(injury_guardrail.get("score_delta") or 0)
        explanations.append(str(injury_guardrail.get("summary") or ""))

    my_need_hits = receive_positions & my_needs
    partner_need_hits = send_positions & partner_needs
    my_surplus_moves = send_positions & my_surplus
    partner_surplus_moves = receive_positions & partner_surplus

    if my_need_hits or partner_need_hits:
        tags.append("Need-Based")
        score += 28
        parts = []
        if my_need_hits:
            my_need_reason = _room_need_reason(my_shape, my_need_hits)
            parts.append(
                my_need_reason
                or f"you need {_format_pos_list(my_need_hits)} help"
            )
        if partner_need_hits:
            partner_need_reason = _room_need_reason(
                partner_shape,
                partner_need_hits,
            )
            parts.append(
                f"{partner_name} - {partner_need_reason}"
                if partner_need_reason
                else f"{partner_name} needs {_format_pos_list(partner_need_hits)} help"
            )
        sentence = "; ".join(parts)
        explanations.append(sentence[:1].upper() + sentence[1:] + ".")

    if my_surplus_moves or partner_surplus_moves:
        tags.append("Surplus-Based")
        score += 8
        parts = []
        if my_surplus_moves:
            parts.append(f"you can move from {_format_pos_list(my_surplus_moves)} surplus")
        if partner_surplus_moves:
            parts.append(f"{partner_name} can move from {_format_pos_list(partner_surplus_moves)} surplus")
        sentence = "; ".join(parts)
        explanations.append(sentence[:1].upper() + sentence[1:] + ".")

    outgoing_picks = _pick_assets(send_assets)
    incoming_picks = _pick_assets(receive_assets)
    if incoming_picks or outgoing_picks:
        tags.append("Draft Capital Move")
        if incoming_picks:
            if my_strategy == "tank":
                score += 22
            elif my_strategy == "rebuild" or my_shape.get("draft_capital_tier") == "low":
                score += 16
            elif my_strategy == "retool":
                score += 8
            else:
                score += 4
            explanations.append("This adds future flexibility through owned draft capital.")
        if outgoing_picks:
            if my_strategy in {"contender", "fringe_contender"} or my_shape.get("draft_capital_tier") == "high":
                score += 8
                explanations.append("You can use draft capital to improve the active roster.")
            elif my_strategy == "retool":
                score -= 4
                explanations.append("This spends future flexibility, so the roster upgrade needs to be meaningful.")
            else:
                score -= 18 if my_strategy == "tank" else 14
                explanations.append("This spends future capital, so the player return needs to matter now.")
        if _pick_assets(send_assets) and (
            partner_strategy in {"rebuild", "tank"} or partner_shape.get("draft_capital_tier") == "low"
        ):
            score += 8

    send_avg_age = _asset_avg_age(send_assets)
    receive_avg_age = _asset_avg_age(receive_assets)
    send_injury = _asset_injury_profile(send_assets)
    receive_injury = _asset_injury_profile(receive_assets)
    healthy_need_hits = receive_injury["healthy_positions"] & my_needs
    my_injury_positions = set(my_shape.get("injured_starter_positions") or [])
    partner_injury_positions = set(partner_shape.get("injured_starter_positions") or [])
    my_injury_relief = receive_injury["healthy_positions"] & my_injury_positions
    partner_injury_relief = send_injury["healthy_positions"] & partner_injury_positions
    if send_avg_age and receive_avg_age and receive_avg_age + 1.25 <= send_avg_age:
        tags.append("Age Optimization")
        score += 16 if my_strategy in {"rebuild", "tank", "retool"} else 10
        explanations.append("The return gets younger without relying only on raw value.")
    elif my_strategy in {"contender", "fringe_contender"} and receive_avg_age and 26 <= receive_avg_age <= 30:
        tags.append("Age Optimization")
        score += 5
        explanations.append("The age profile fits a win-now window.")

    send_player_count = len(_player_assets(send_assets))
    receive_player_count = len(_player_assets(receive_assets))
    if send_player_count > receive_player_count and _top_player_score(receive_assets) > _top_player_score(send_assets):
        tags.append("Roster Consolidation")
        score += 18
        explanations.append("This improves starting-lineup strength without adding extra lineup decisions.")

    if healthy_need_hits:
        tags.append("Health Relief")
        score += 8 if my_strategy in {"contender", "fringe_contender", "retool"} else 4
        explanations.append(f"The return brings healthy help at {_format_pos_list(healthy_need_hits)}.")
    if my_injury_relief:
        tags.append("Health Relief")
        if injury_guardrail.get("applied"):
            score += 3 if my_strategy in {"contender", "fringe_contender"} else 1
            explanations.append(
                f"The return brings short-term healthy cover at {_format_pos_list(my_injury_relief)}, but that need is injury-driven."
            )
        else:
            score += 12 if my_strategy in {"contender", "fringe_contender"} else 8
            explanations.append(f"Your current starters are banged up at {_format_pos_list(my_injury_relief)}, and the return brings healthy cover there.")
    try:
        partner_injury_burden = float(partner_shape.get("injury_burden") or 0.0)
    except Exception:
        partner_injury_burden = 0.0
    if partner_injury_relief and (
        partner_injury_burden >= 3.0
        or _safe_int(partner_shape.get("injured_starters"), 0) >= 1
    ):
        score += 10
        explanations.append(f"{partner_name} is dealing with injuries at {_format_pos_list(partner_injury_relief)}, so the outgoing package lines up with a real short-term need.")

    if my_strategy in {"contender", "fringe_contender"}:
        if receive_injury["major"] > 0:
            tags.append("Injury Risk")
            score -= 22
            explanations.append("A contender build should be careful about taking on major injury risk.")
        elif receive_injury["moderate"] > 0:
            tags.append("Injury Risk")
            score -= 12
            explanations.append("The return includes injured production, which adds short-term lineup risk.")
        if send_injury["major"] > 0 and receive_injury["major"] == 0:
            tags.append("Health Relief")
            score += 6
            explanations.append("It can swap out some of your current injury risk for healthier points.")
    elif my_strategy == "retool":
        if receive_injury["major"] > 0:
            tags.append("Injury Risk")
            score -= 8
            explanations.append("Retool builds should avoid paying for long injury timelines unless the upside is clear.")
    elif my_strategy in {"rebuild", "tank"} and receive_injury["major"] > 0 and incoming_picks:
        tags.append("Injury Risk")
        score += 3
        explanations.append("A rebuild can afford to absorb some injury timeline if draft value also comes back.")

    score_diff = _score_assets(receive_assets) - _score_assets(send_assets)
    if score_diff >= 500:
        tags.append("Value Arbitrage")
        score += 8
        explanations.append("The package carries a positive value gap in your favor.")

    if my_strategy in {"contender", "fringe_contender"} and (
        _top_player_score(receive_assets) >= _top_player_score(send_assets) + 500
        or outgoing_picks
    ):
        tags.append("Contender Move")
        score += 12
        explanations.append("This fits a contender by turning depth or picks into usable lineup strength.")
    if my_strategy in {"rebuild", "tank"} and (incoming_picks or (receive_avg_age and send_avg_age and receive_avg_age < send_avg_age)):
        tags.append("Rebuild Move")
        score += 18 if my_strategy == "tank" else 14
        explanations.append("This fits a rebuild by extending the roster's future outlook.")
    if my_strategy == "retool" and (
        my_need_hits or (receive_avg_age and send_avg_age and receive_avg_age <= send_avg_age)
    ):
        score += 6
        explanations.append("This fits a retool by balancing present help with future value.")

    if partner_strategy in {"rebuild", "tank"} and _pick_assets(send_assets):
        tags.append("Rebuild Move")
        score += 6
    if partner_strategy in {"contender", "fringe_contender"} and _top_player_score(send_assets) >= _top_player_score(receive_assets):
        tags.append("Contender Move")
        score += 4
    if partner_strategy in {"contender", "fringe_contender"} and partner_injury_relief:
        score += 6
        explanations.append(f"{partner_name} has a contender window and the offer supplies healthy depth where injuries are already biting.")
    if partner_strategy in {"contender", "fringe_contender"} and send_injury["major"] > 0:
        score -= 8
        explanations.append(f"{partner_name} is less likely to pay contender prices for injured production.")

    if my_needs and send_positions & my_needs and not receive_positions & my_needs:
        score -= 30
        explanations.append("It risks weakening one of your existing problem areas.")
    if partner_needs and receive_positions & partner_needs and not send_positions & partner_needs:
        score -= 18
        explanations.append(f"It asks {partner_name} to move from a position they already need.")
    if outgoing_picks and my_shape.get("draft_capital_tier") == "low" and my_strategy not in {"contender", "fringe_contender"}:
        score -= 12
    if incoming_picks and partner_shape.get("draft_capital_tier") == "low" and partner_strategy not in {"rebuild", "tank"}:
        score -= 10

    deduped_tags = []
    for tag in list(injury_guardrail.get("tags") or []) + tags:
        if tag not in deduped_tags:
            deduped_tags.append(tag)

    has_primary_reason = any(tag in PRIMARY_REASON_TAGS for tag in deduped_tags)
    if deduped_tags == ["Surplus-Based"] or not has_primary_reason:
        score -= 35
    if injury_guardrail.get("hard_fail"):
        score = min(score, -24)

    if not explanations:
        explanations.append("The recommendation needs more than a raw-value match to stay on the board.")

    return {
        "score": score,
        "tags": deduped_tags or ["Value Arbitrage"],
        "summary": " ".join(explanations[:3]),
        "strategy_fit_score": int(strategy_context.get("score") or 0),
        "strategy_fit_reason": str(strategy_context.get("reason") or ""),
        "strategy_archetype": str(strategy_context.get("archetype") or ""),
        "strategy_risk_label": str(strategy_context.get("risk_label") or ""),
        "strategy_profile_label": str(strategy_context.get("profile_label") or ""),
        "guardrail_flags": list(injury_guardrail.get("tags") or []),
        "guardrail_summary": str(injury_guardrail.get("summary") or ""),
        "guardrail_hard_fail": bool(injury_guardrail.get("hard_fail")),
    }


TRADE_PIPELINE_STAGES = (
    "partner_selection",
    "candidate_target_generation",
    "outgoing_asset_filtering",
    "package_construction",
    "package_scoring",
    "confidence_scoring",
    "protected_player_checks",
    "duplicate_package_elimination",
    "final_sorting",
)
TRADE_PIPELINE_EVENT_LABELS = {
    "partner_selection": "trade_pipe_partner",
    "candidate_target_generation": "trade_pipe_targets",
    "outgoing_asset_filtering": "trade_pipe_outgoing",
    "package_construction": "trade_pipe_construct",
    "package_scoring": "trade_pipe_score",
    "confidence_scoring": "trade_pipe_confidence",
    "protected_player_checks": "trade_pipe_protected",
    "duplicate_package_elimination": "trade_pipe_dedupe",
    "final_sorting": "trade_pipe_sort",
}


class _TradePipelineProfile:
    """Per-build timings and immutable memoization; never changes candidate semantics."""

    def __init__(self, *, cache_enabled: bool = True):
        self.cache_enabled = bool(cache_enabled)
        hot = str(__import__("os").environ.get("DYNASTYGM_HOT_PATH", "")).strip().casefold()
        self.timing_enabled = debug_enabled() or hot in {"1", "true", "yes", "on"}
        self.elapsed_ms: Dict[str, float] = defaultdict(float)
        self.calls: Dict[str, int] = defaultdict(int)
        self.cache_hits: Dict[str, int] = defaultdict(int)
        self.duplicate_evaluations = 0
        self._score_cache: Dict[tuple, int] = {}
        self._reasoning_cache: Dict[str, Dict[str, Any]] = {}
        self._market_cache: Dict[str, Dict[str, Any]] = {}
        self._fit_cache: Dict[str, Dict[str, Any]] = {}
        self._priority_cache: Dict[str, int] = {}

    @contextmanager
    def stage(self, name: str):
        self.calls[name] += 1
        if not self.timing_enabled:
            yield
            return
        started = time.perf_counter()
        try:
            yield
        finally:
            self.elapsed_ms[name] += (time.perf_counter() - started) * 1000.0

    @staticmethod
    def package_key(send_assets, receive_assets) -> str:
        return _package_key(send_assets, receive_assets)

    @staticmethod
    def _asset_score_key(assets) -> tuple:
        return tuple(
            sorted(
                (
                    str(asset.get("asset_type") or ""),
                    str(asset.get("player_id") or asset.get("label") or ""),
                    int(asset.get("score") or 0),
                )
                for asset in assets
            )
        )

    def score(self, assets) -> int:
        key = self._asset_score_key(assets)
        with self.stage("package_scoring"):
            if self.cache_enabled and key in self._score_cache:
                self.cache_hits["package_scoring"] += 1
                return self._score_cache[key]
            value = _score_assets(assets)
            if self.cache_enabled:
                self._score_cache[key] = value
            return value

    def cached(self, category: str, key: str, builder):
        stores = {
            "reasoning": self._reasoning_cache,
            "market": self._market_cache,
            "fit": self._fit_cache,
            "priority": self._priority_cache,
        }
        store = stores[category]
        if self.cache_enabled and key in store:
            self.cache_hits[category] += 1
            return store[key]
        value = builder()
        if self.cache_enabled:
            store[key] = value
        return value

    def emit(self) -> None:
        for stage in TRADE_PIPELINE_STAGES:
            record_timing(
                TRADE_PIPELINE_EVENT_LABELS[stage],
                self.elapsed_ms.get(stage, 0.0),
                category="analysis",
                result_size=self.calls.get(stage, 0),
            )
        record_timing(
            "trade_pipe_duplicates",
            0.0,
            category="analysis",
            result_size=self.duplicate_evaluations,
        )
        for category, hits in sorted(self.cache_hits.items()):
            record_timing(
                f"trade_cache_hit_{category}",
                0.0,
                category="analysis",
                result_size=hits,
            )


@runtime_trace.traced("trade_board_generation", phase="trade_generation")
def _partner_complement_score(partner_row, my_needs: List[str], my_strengths: List[str]) -> int:
    """Cheap partner order for reduced Dashboard search — not a second scorer."""

    partner_strengths = _normalize_pos_list(
        partner_row.get("strengths") if hasattr(partner_row, "get") else []
    )
    if not partner_strengths and hasattr(partner_row, "get"):
        partner_strengths = _normalize_pos_list(partner_row.get("surplus") or [])
    partner_needs = _normalize_pos_list(
        partner_row.get("needs") if hasattr(partner_row, "get") else []
    )
    return len(set(my_needs) & set(partner_strengths)) * 2 + len(
        set(my_strengths) & set(partner_needs)
    )


def build_trade_ideas(
    df_players: pd.DataFrame,
    league_id: str,
    df_summary: pd.DataFrame,
    my_roster_id: int,
    trade_block_names: List[str],
    untouchable_names: List[str],
    role_map: Dict[str, str],
    max_ideas: int = 8,
    score_field: str = "value_score",
    pick_score_multiplier: float = 1.0,
    team_strategy: str | None = None,
    team_archetype: str | None = None,
    league_settings: Dict[str, Any] | None = None,
    draft_status: Dict[str, Any] | None = None,
    adapter=None,
    allow_protected_focus: bool = False,
    _pipeline_cache_enabled: bool = True,
    search_budget: str = "",
    prefetched_rosters: List[Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    profile = _TradePipelineProfile(cache_enabled=_pipeline_cache_enabled)
    try:
        return _build_trade_ideas_impl(
            df_players,
            league_id,
            df_summary,
            my_roster_id,
            trade_block_names,
            untouchable_names,
            role_map,
            max_ideas=max_ideas,
            score_field=score_field,
            pick_score_multiplier=pick_score_multiplier,
            team_strategy=team_strategy,
            team_archetype=team_archetype,
            league_settings=league_settings,
            draft_status=draft_status,
            adapter=adapter,
            allow_protected_focus=allow_protected_focus,
            _pipeline_profile=profile,
            search_budget=search_budget,
            prefetched_rosters=prefetched_rosters,
        )
    finally:
        profile.emit()


def _build_trade_ideas_impl(
    df_players: pd.DataFrame,
    league_id: str,
    df_summary: pd.DataFrame,
    my_roster_id: int,
    trade_block_names: List[str],
    untouchable_names: List[str],
    role_map: Dict[str, str],
    max_ideas: int = 8,
    score_field: str = "value_score",
    pick_score_multiplier: float = 1.0,
    team_strategy: str | None = None,
    team_archetype: str | None = None,
    league_settings: Dict[str, Any] | None = None,
    draft_status: Dict[str, Any] | None = None,
    adapter=None,
    allow_protected_focus: bool = False,
    _pipeline_profile: _TradePipelineProfile | None = None,
    search_budget: str = "",
    prefetched_rosters: List[Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    profile = _pipeline_profile or _TradePipelineProfile(cache_enabled=False)
    ideas: List[Dict[str, Any]] = []
    seen_ideas = set()
    df_players = df_players.copy()
    if "player_id" in df_players.columns:
        df_players["player_id"] = df_players["player_id"].astype(str)

    platform_adapter = adapter or get_sleeper_adapter()
    dashboard_budget = str(search_budget or "").strip().casefold() == "dashboard"
    target_cap = 4 if dashboard_budget else 8
    outgoing_cap = 5 if dashboard_budget else 10
    partner_cap = 6 if dashboard_budget else 0
    dashboard_pool_limit = 4 if dashboard_budget else 0
    with profile.stage("partner_selection"):
        if prefetched_rosters:
            raw_rosters = list(prefetched_rosters)
            if raw_rosters and not raw_rosters[0].get("platform"):
                rosters = [platform_adapter.normalize_roster(row) for row in raw_rosters]
            else:
                rosters = raw_rosters
        else:
            rosters = platform_adapter.get_rosters(league_id)
        roster_players_map = _roster_players_map(rosters)
        player_owner_by_id = {
            str(player_id): int(roster_id)
            for roster_id, player_ids in roster_players_map.items()
            for player_id in player_ids
        }
    roster_pick_assets = _build_roster_pick_assets(
        league_id,
        rosters,
        df_summary,
        league_settings=league_settings,
        draft_status=draft_status,
        adapter=platform_adapter,
    )
    league_draft_capitals = [
        int(sum(int(pick.get("score") or 0) for pick in assets))
        for assets in roster_pick_assets.values()
    ]

    my_roster_key = _safe_int(my_roster_id)
    my_player_ids = roster_players_map.get(my_roster_key, [])
    owner_ids = df_players["player_id"].map(player_owner_by_id)
    roster_team_frames = {
        int(roster_id): frame.copy()
        for roster_id, frame in df_players.assign(_trade_owner_id=owner_ids)
        .dropna(subset=["_trade_owner_id"])
        .groupby("_trade_owner_id", sort=False)
    }
    for frame in roster_team_frames.values():
        frame.drop(columns=["_trade_owner_id"], inplace=True)
    my_team_df = roster_team_frames.get(my_roster_key, df_players.iloc[0:0].copy())

    # Keep every explicit untouchable and every asset that the shared protection
    # predicate recognizes as core. Only an intentional player-focused search may
    # evaluate a protected outgoing asset.
    keeper_names = {str(name).strip().casefold() for name in untouchable_names if str(name).strip()}
    with profile.stage("protected_player_checks"):
        for _, row in my_team_df.iterrows():
            pid = str(row["player_id"])
            role = role_map.get(pid, "Flex")
            asset = _player_asset(row, role, score_field=score_field)
            if _is_core_or_protected_starter(asset):
                keeper_names.add(str(row["name"]).strip().casefold())

    name_keys = my_team_df["name"].fillna("").astype(str).str.strip().str.casefold()
    requested_names = {str(name).strip().casefold() for name in trade_block_names if str(name).strip()}
    if trade_block_names:
        requested_mask = name_keys.isin(requested_names)
        protected_mask = name_keys.isin(keeper_names)
        my_trade_block_df = my_team_df[
            requested_mask & (~protected_mask | bool(allow_protected_focus))
        ].copy()
    else:
        my_trade_block_df = my_team_df[~name_keys.isin(keeper_names)].copy()

    if my_trade_block_df.empty:
        return []

    metrics = get_team_vs_league(df_summary, my_roster_key)
    if not metrics:
        return []

    auto_strategy = normalize_team_strategy(metrics.get("strategy") or metrics.get("mode"))
    active_strategy = normalize_team_strategy(team_strategy or auto_strategy, default=auto_strategy)
    my_mode = team_strategy_mode(active_strategy)
    my_strengths = metrics.get("strengths", []) or []
    my_strengths = _normalize_pos_list(my_strengths)
    my_shape = _build_team_shape(
        df_summary,
        my_roster_key,
        my_team_df,
        score_field,
        roster_pick_assets.get(my_roster_key, []),
        league_draft_capitals,
        league_settings=league_settings,
    )
    my_shape["strategy"] = active_strategy
    my_shape["strategy_label"] = team_strategy_label(active_strategy)
    my_shape["mode"] = my_mode
    if team_archetype:
        my_shape["archetype"] = str(team_archetype)
        my_shape["archetype_label"] = str(team_archetype)
    my_needs = _normalize_pos_list(my_shape.get("needs", []))

    pos_focus = my_needs if my_needs else ["WR", "RB", "QB", "TE"]
    movable_positions = list(dict.fromkeys(my_strengths + ["WR", "RB", "QB", "TE"]))

    my_candidates = my_trade_block_df[
        my_trade_block_df["position"].isin(movable_positions)
    ].copy()
    if my_candidates.empty:
        my_candidates = my_trade_block_df.copy()

    role_by_pid = {str(pid): role for pid, role in role_map.items()}
    my_pick_assets = [
        _pick_asset(pick, score_multiplier=pick_score_multiplier)
        for pick in roster_pick_assets.get(my_roster_key, [])
    ]
    my_pick_assets = [pick for pick in my_pick_assets if int(pick.get("round") or 99) <= 3]

    with profile.stage("outgoing_asset_filtering"):
        base_my_player_assets = [
            _player_asset(
                row,
                role_by_pid.get(str(row["player_id"]), "Flex"),
                score_field=score_field,
            )
            for _, row in my_candidates.iterrows()
            if _row_score(row, score_field) > 0
        ]
        with profile.stage("protected_player_checks"):
            base_my_player_assets = [
                asset
                for asset in base_my_player_assets
                if _automatic_outgoing_asset_allowed(
                    asset,
                    explicit_player_focus=bool(allow_protected_focus and trade_block_names),
                )
            ]

    def add_idea(idea: Dict[str, Any]) -> None:
        with profile.stage("duplicate_package_elimination"):
            key = profile.package_key(idea["send_assets"], idea["receive_assets"])
            if key in seen_ideas:
                profile.duplicate_evaluations += 1
                return
            seen_ideas.add(key)
            ideas.append(idea)

    partner_rows = []
    for _, partner_row in df_summary.iterrows():
        if _safe_int(partner_row["roster_id"]) == my_roster_key:
            continue
        partner_rows.append(partner_row)
    if dashboard_budget:
        partner_rows.sort(
            key=lambda row: _partner_complement_score(row, my_needs, my_strengths),
            reverse=True,
        )
        partner_rows = partner_rows[:partner_cap]

    for partner_row in partner_rows:
        if dashboard_pool_limit and len(ideas) >= dashboard_pool_limit:
            break
        with profile.stage("partner_selection"):
            partner_roster_id = _safe_int(partner_row["roster_id"])

        partner_name = partner_row["team_name"]
        partner_mode = partner_row["mode"]

        partner_team_df = roster_team_frames.get(
            partner_roster_id,
            df_players.iloc[0:0].copy(),
        )
        if partner_team_df.empty:
            continue
        partner_shape = _build_team_shape(
            df_summary,
            partner_roster_id,
            partner_team_df,
            score_field,
            roster_pick_assets.get(partner_roster_id, []),
            league_draft_capitals,
            league_settings=league_settings,
        )
        partner_mode = str(partner_shape.get("mode") or partner_mode)
        partner_profile = partner_row.to_dict() if hasattr(partner_row, "to_dict") else {}

        def make_reasoned_idea(
            send_assets: List[Dict[str, Any]],
            receive_assets: List[Dict[str, Any]],
            title: str,
            rationale: str,
            priority: int,
            min_reason_score: int = 8,
            min_acceptance_score: int = 56,
            fit_context: Dict[str, Any] | None = None,
        ) -> Dict[str, Any] | None:
            package_key = profile.package_key(send_assets, receive_assets)
            if package_key in seen_ideas:
                profile.duplicate_evaluations += 1
                return None
            cache_key = f"{partner_roster_id}:{package_key}"
            reasoning = profile.cached(
                "reasoning",
                cache_key,
                lambda: _trade_reasoning_context(
                    my_shape,
                    partner_shape,
                    send_assets,
                    receive_assets,
                    partner_name,
                ),
            )
            if reasoning["score"] < min_reason_score:
                return None
            market_context = profile.cached(
                "market",
                cache_key,
                lambda: evaluate_trade_market_realism(
                    send_assets=send_assets,
                    receive_assets=receive_assets,
                    my_shape=my_shape,
                    partner_shape=partner_shape,
                    partner_name=partner_name,
                    partner_profile=partner_profile,
                    league_settings=league_settings,
                    send_score=profile.score(send_assets),
                    receive_score=profile.score(receive_assets),
                ),
            )
            if market_context.get("hard_fail"):
                return None
            if int(market_context.get("score") or 0) < min_acceptance_score:
                return None
            final_rationale = " ".join(
                part
                for part in [reasoning.get("summary", ""), rationale, market_context.get("summary", "")]
                if part
            ).strip()
            with profile.stage("confidence_scoring"):
                idea = _make_idea(
                    partner_name,
                    send_assets,
                    receive_assets,
                    my_mode,
                    partner_mode,
                    title,
                    final_rationale,
                    priority + int(reasoning["score"]) + int(round((int(market_context.get("score") or 0) - 50) / 4.0)),
                    reasoning_tags=reasoning["tags"],
                    reasoning_summary=reasoning["summary"],
                    my_strategy=str(my_shape.get("strategy") or my_mode),
                    partner_strategy=str(partner_shape.get("strategy") or partner_mode),
                    send_score=profile.score(send_assets),
                    receive_score=profile.score(receive_assets),
                )
                idea = _apply_strategy_context_to_idea(idea, reasoning, my_shape)
                return _attach_trade_assessment_fields(
                    idea,
                    fit_context=fit_context,
                    market_context=market_context,
                )

        def make_package(*assets: Dict[str, Any]) -> List[Dict[str, Any]]:
            with profile.stage("package_construction"):
                return list(assets)

        def package_fit_priority(send_assets, receive_assets) -> int:
            key = f"{partner_roster_id}:{profile.package_key(send_assets, receive_assets)}"
            with profile.stage("package_scoring"):
                return profile.cached(
                    "priority",
                    key,
                    lambda: _fit_priority(send_assets, receive_assets, my_shape, partner_shape),
                )

        def package_fit_context(send_assets, receive_assets) -> Dict[str, Any]:
            key = f"{partner_roster_id}:{profile.package_key(send_assets, receive_assets)}"
            with profile.stage("package_scoring"):
                return profile.cached(
                    "fit",
                    key,
                    lambda: _trade_fit_context(
                        my_shape,
                        partner_shape,
                        send_assets,
                        receive_assets,
                        partner_name,
                    ),
                )

        my_player_assets = list(base_my_player_assets)
        with profile.stage("candidate_target_generation"):
            my_player_assets.sort(
                key=lambda asset: (
                    _player_trade_fit(
                        asset,
                        str(asset.get("role") or "Flex"),
                        my_shape,
                        partner_shape,
                    ),
                    asset["score"],
                ),
                reverse=True,
            )

            partner_player_assets = [
                _player_asset(row, score_field=score_field)
                for _, row in partner_team_df.iterrows()
                if _row_score(row, score_field) > 0
            ]
            partner_player_assets.sort(
                key=lambda asset: (
                    _target_trade_fit(asset, my_shape, partner_shape),
                    asset["score"],
                ),
                reverse=True,
            )
            partner_target_players = [
                asset
                for asset in partner_player_assets
                if asset["position"] in pos_focus
                and (
                    asset["position"] in partner_shape.get("surplus", [])
                    or asset["position"] in my_shape.get("needs", [])
                    or asset["score"] >= 6500
                )
            ] or partner_player_assets[:target_cap]
            partner_pick_assets = [
                _pick_asset(pick, score_multiplier=pick_score_multiplier)
                for pick in roster_pick_assets.get(partner_roster_id, [])
            ]
            partner_pick_assets = [pick for pick in partner_pick_assets if int(pick.get("round") or 99) <= 3]

        # 1. Consolidate two movable pieces into a real need-position starter.
        for target in partner_target_players[:target_cap]:
            if target["score"] < 2500:
                continue
            for i, first in enumerate(my_player_assets[:outgoing_cap]):
                for second in my_player_assets[i + 1 : outgoing_cap + 2]:
                    if str(first.get("position") or "").upper() in my_needs and str(first.get("position") or "").upper() not in my_strengths:
                        continue
                    if str(second.get("position") or "").upper() in my_needs and str(second.get("position") or "").upper() not in my_strengths:
                        continue
                    send_assets = make_package(first, second)
                    receive_assets = make_package(target)
                    send_score = profile.score(send_assets)
                    if target["score"] <= max(first["score"], second["score"]) + 500:
                        continue
                    if not _value_fits(send_score, target["score"], low=-1800, high=900):
                        continue
                    fit_bonus = package_fit_priority(send_assets, receive_assets)
                    if fit_bonus < 6:
                        continue
                    fit_context = package_fit_context(send_assets, receive_assets)
                    if fit_context["score"] < 0 or fit_context["partner_score"] <= 0:
                        continue
                    idea = make_reasoned_idea(
                        send_assets,
                        receive_assets,
                        "Consolidate for starter",
                        (
                            f"Uses depth or surplus pieces to buy a stronger {target['position']} while keeping your weak rooms intact. "
                            f"{fit_context['rationale']}"
                        ).strip(),
                        88 + fit_bonus + fit_context["score"],
                        min_reason_score=12,
                        min_acceptance_score=58,
                        fit_context=fit_context,
                    )
                    if idea:
                        add_idea(idea)
                        break

        # 2. Buy a need-position upgrade with one player plus one owned pick.
        if active_strategy in {"contender", "fringe_contender", "retool"} and my_pick_assets:
            for target in partner_target_players[:target_cap]:
                if target["score"] < 3500:
                    continue
                for player in my_player_assets[:outgoing_cap]:
                    player_pos = str(player.get("position") or "").upper()
                    if player_pos in my_needs and player_pos not in my_strengths:
                        continue
                    if player["position"] == target["position"] and player["score"] >= target["score"] - 500:
                        continue
                    for pick in my_pick_assets[:4]:
                        send_assets = make_package(player, pick)
                        receive_assets = make_package(target)
                        if not _value_fits(profile.score(send_assets), target["score"], low=-1800, high=700):
                            continue
                        fit_bonus = package_fit_priority(send_assets, receive_assets)
                        if fit_bonus < 4:
                            continue
                        fit_context = package_fit_context(send_assets, receive_assets)
                        if fit_context["score"] < 0 or fit_context["partner_score"] <= 0:
                            continue
                        idea = make_reasoned_idea(
                            send_assets,
                            receive_assets,
                            "Buy need-position upgrade",
                            (
                                f"Uses an owned pick plus a movable piece to address your {target['position']} need. "
                                f"{fit_context['rationale']}"
                            ).strip(),
                            78 + fit_bonus + fit_context["score"],
                            min_reason_score=10,
                            min_acceptance_score=56,
                            fit_context=fit_context,
                        )
                        if idea:
                            add_idea(idea)
                            break

        # 3. Sell an older/high-value player for a younger player plus a pick.
        if partner_pick_assets:
            for player in my_player_assets[:outgoing_cap]:
                player_pos = str(player.get("position") or "").upper()
                if player_pos in my_needs and player_pos not in my_strengths:
                    continue
                try:
                    player_age = float(player.get("age"))
                except Exception:
                    player_age = 0
                if active_strategy in {"rebuild", "tank"} and player_age < 26 and player["score"] > 3500:
                    continue
                for young_target in partner_player_assets[:14]:
                    try:
                        target_age = float(young_target.get("age"))
                    except Exception:
                        target_age = 99
                    if target_age > 25 and active_strategy in {"rebuild", "tank"}:
                        continue
                    if young_target["score"] >= player["score"]:
                        continue
                    if young_target["score"] < 1500:
                        continue
                    for pick in partner_pick_assets[:5]:
                        pick_round = int(pick.get("round") or 99)
                        if player["score"] >= 5000 and young_target["score"] < player["score"] * 0.45:
                            continue
                        if (
                            player["score"] >= 7500
                            and pick_round != 1
                            and young_target["score"] < player["score"] * 0.65
                        ):
                            continue
                        send_assets = make_package(player)
                        receive_assets = make_package(young_target, pick)
                        if not _value_fits(player["score"], profile.score(receive_assets), low=-900, high=1600):
                            continue
                        fit_bonus = package_fit_priority(send_assets, receive_assets)
                        if fit_bonus < 0:
                            continue
                        fit_context = package_fit_context(send_assets, receive_assets)
                        if fit_context["score"] < 0 or fit_context["partner_score"] <= 0:
                            continue
                        is_younger = target_age < player_age if player_age else False
                        idea = make_reasoned_idea(
                            send_assets,
                            receive_assets,
                            "Get younger plus pick" if is_younger else "Player plus pick return",
                            (
                                "Moves value out of a movable roster spot and brings back future capital with a playable return. "
                                f"{fit_context['rationale']}"
                            ).strip(),
                            72 + fit_bonus + fit_context["score"] + (10 if active_strategy == "tank" else 8 if active_strategy == "rebuild" else 0) + (5 if is_younger else 0),
                            min_reason_score=8,
                            min_acceptance_score=54,
                            fit_context=fit_context,
                        )
                        if idea:
                            add_idea(idea)
                            break

        # 4. Convert a movable player directly into owned picks.
        if active_strategy in {"rebuild", "tank"} and partner_pick_assets:
            useful_picks = partner_pick_assets[:6]
            for player in my_player_assets[:outgoing_cap]:
                player_pos = str(player.get("position") or "").upper()
                if player_pos in my_needs and player_pos not in my_strengths:
                    continue
                try:
                    player_age = float(player.get("age"))
                except Exception:
                    player_age = 0
                if player_age < 26 and player["score"] > 3000:
                    continue
                pick_packages = [make_package(pick) for pick in useful_picks]
                for i, first in enumerate(useful_picks):
                    for second in useful_picks[i + 1 :]:
                        if first.get("label") != second.get("label"):
                            pick_packages.append(make_package(first, second))
                for receive_assets in pick_packages:
                    send_assets = make_package(player)
                    if not _value_fits(player["score"], profile.score(receive_assets), low=-1300, high=2200):
                        continue
                    fit_bonus = package_fit_priority(send_assets, receive_assets)
                    if fit_bonus < 4:
                        continue
                    fit_context = package_fit_context(send_assets, receive_assets)
                    if fit_context["score"] < 0 or fit_context["partner_score"] <= 0:
                        continue
                    idea = make_reasoned_idea(
                        send_assets,
                        receive_assets,
                        "Convert veteran to picks",
                        (
                            "Moves a non-core player into draft capital that this team actually owns. "
                            f"{fit_context['rationale']}"
                        ).strip(),
                        76 + fit_bonus + fit_context["score"],
                        min_reason_score=8,
                        min_acceptance_score=52,
                        fit_context=fit_context,
                    )
                    if idea:
                        add_idea(idea)
                        break

    with profile.stage("final_sorting"):
        ideas.sort(key=_trade_surface_sort_key, reverse=True)
    selected: List[Dict[str, Any]] = []
    tag_counts: Dict[str, int] = {}
    partner_counts: Dict[str, int] = {}
    receive_counts: Dict[str, int] = {}
    for idea in ideas:
        tag = str(idea.get("tag") or "")
        partner = str(idea.get("partner_team_name") or "")
        receive = str(idea.get("their_player") or "")
        if tag_counts.get(tag, 0) >= 3:
            continue
        if partner_counts.get(partner, 0) >= 3:
            continue
        if receive_counts.get(receive, 0) >= 2:
            continue
        selected.append(idea)
        tag_counts[tag] = tag_counts.get(tag, 0) + 1
        partner_counts[partner] = partner_counts.get(partner, 0) + 1
        receive_counts[receive] = receive_counts.get(receive, 0) + 1
        if len(selected) >= max_ideas:
            return selected

    for idea in ideas:
        if idea not in selected:
            selected.append(idea)
        if len(selected) >= max_ideas:
            break

    # Diversity may skip a higher-ranked idea then append it during fill,
    # which would place it after lower-ranked survivors. Restore surface
    # rank among the selected set without changing membership or scores.
    selected.sort(key=_trade_surface_sort_key, reverse=True)
    return selected


def _find_roster_id_for_player(
    roster_players_map: Dict[int, List[str]],
    player_id: str,
) -> int:
    target = str(player_id or "")
    if not target:
        return 0
    for roster_id, player_ids in roster_players_map.items():
        if target in set(player_ids or []):
            return int(roster_id)
    return 0


def _player_hub_path_label(
    selected_asset: Dict[str, Any],
    send_assets: List[Dict[str, Any]],
    receive_assets: List[Dict[str, Any]],
    strategy: str,
    mode: str,
) -> str:
    send_players = _player_assets(send_assets)
    receive_players = _player_assets(receive_assets)
    selected_score = int(selected_asset.get("score") or 0)
    receive_score = _score_assets(receive_assets)
    has_send_pick = _has_pick(send_assets)
    has_receive_pick = _has_pick(receive_assets)
    selected_pos = str(selected_asset.get("position") or "").upper()
    strategy_key = normalize_team_strategy(strategy)

    if mode == "target_player":
        if has_send_pick and not send_players:
            return "Pick-heavy package"
        if len(send_players) == 1 and not has_send_pick:
            return "Cheapest acquisition path"
        if len(send_players) >= 2 and not has_send_pick:
            return "Surplus-for-need package"
        if has_send_pick and len(send_players) == 1:
            return "Player + pick path"
        if has_send_pick:
            return "Package-upgrade path"
        return "Best trade partner"

    if has_receive_pick and not receive_players:
        return "Trade for future picks"
    if has_receive_pick and receive_players:
        try:
            selected_age = float(selected_asset.get("age") or 0)
        except Exception:
            selected_age = 0.0
        receive_ages = [float(asset.get("age") or 0) for asset in receive_players if _safe_float(asset.get("age"), 0) > 0]
        if receive_ages and selected_age and min(receive_ages) + 1.5 < selected_age:
            return "Age-down opportunity"
        return "Sell-high opportunity"
    if len(send_players) > 1 and receive_players:
        return "Package-upgrade opportunity"
    if (
        len(receive_players) == 1
        and str(receive_players[0].get("position") or "").upper() == selected_pos
        and receive_score >= selected_score + 450
    ):
        return f"Upgrade {selected_pos} tier"
    if (
        len(receive_players) == 1
        and str(receive_players[0].get("position") or "").upper() == selected_pos
        and abs(receive_score - selected_score) <= 900
    ):
        return "Lateral value pivot"
    if strategy_key in {"contender", "fringe_contender"}:
        return "Contender move"
    if strategy_key in {"rebuild", "tank"}:
        return "Rebuild move"
    return "Roster-fit path"


def _my_player_candidate_reason(
    selected_asset: Dict[str, Any],
    my_shape: Dict[str, Any],
) -> str:
    pos = str(selected_asset.get("position") or "").upper()
    tier = str(selected_asset.get("player_tier") or "").strip()
    age = _safe_float(selected_asset.get("age"), 0.0)
    strategy = normalize_team_strategy(my_shape.get("strategy") or my_shape.get("mode"))
    surplus = set(my_shape.get("surplus") or [])
    injury_positions = set(my_shape.get("injured_starter_positions") or [])

    if pos in surplus:
        return f"{selected_asset.get('label')} is a realistic chip because {pos} is one of your surplus rooms."
    if strategy in {"rebuild", "tank"} and age >= 26:
        return f"{selected_asset.get('label')} is a candidate because an older {tier or pos} can be converted into younger value or picks."
    if strategy in {"contender", "fringe_contender"} and pos not in injury_positions:
        return f"{selected_asset.get('label')} is movable because you can use this asset to push current lineup strength without opening an injury hole at {pos}."
    if tier in {"Star", "Core Starter"}:
        return f"{selected_asset.get('label')} is one of your clearest leverage pieces if you want to change the roster shape meaningfully."
    return f"{selected_asset.get('label')} is movable because this roster can use the asset to solve a more important need."


def _my_player_solution_reason(
    selected_asset: Dict[str, Any],
    receive_assets: List[Dict[str, Any]],
    my_shape: Dict[str, Any],
) -> str:
    receive_positions = _asset_positions(receive_assets)
    needs = set(my_shape.get("needs") or [])
    strategy = normalize_team_strategy(my_shape.get("strategy") or my_shape.get("mode"))
    hits = [pos for pos in CORE_POSITIONS if pos in receive_positions and pos in needs]
    if hits:
        return f"Moving this player helps address your {', '.join(hits[:2])} weakness."
    if _has_pick(receive_assets):
        if strategy in {"rebuild", "tank"}:
            return "Moving this player extends the roster timeline by adding draft capital."
        return "Moving this player creates more flexibility for the next upgrade."
    try:
        selected_age = float(selected_asset.get("age") or 0)
    except Exception:
        selected_age = 0.0
    receive_age = _asset_avg_age(receive_assets)
    if receive_age is not None and selected_age and receive_age + 1.0 < selected_age:
        return "Moving this player refreshes the age curve without walking away from value."
    return "Moving this player improves roster fit more than it helps your current construction."


def _target_partner_reason(
    target_asset: Dict[str, Any],
    partner_shape: Dict[str, Any],
    send_assets: List[Dict[str, Any]],
    partner_name: str,
) -> str:
    pos = str(target_asset.get("position") or "").upper()
    strategy = normalize_team_strategy(partner_shape.get("strategy") or partner_shape.get("mode"))
    if pos in set(partner_shape.get("surplus") or []):
        return f"{partner_name} may move this player because {pos} is one of their stronger surplus rooms."
    if strategy in {"rebuild", "tank"} and _has_pick(send_assets):
        return f"{partner_name} may move this player because the return adds future capital that fits their timeline."
    if partner_shape.get("injured_starter_positions") and _asset_positions(send_assets) & set(partner_shape.get("injured_starter_positions") or []):
        return f"{partner_name} may move this player because your package gives healthy cover where injuries are already biting."
    return f"{partner_name} may move this player if the package helps a weaker room or improves future flexibility."


def _target_fit_reason(
    target_asset: Dict[str, Any],
    my_shape: Dict[str, Any],
) -> str:
    pos = str(target_asset.get("position") or "").upper()
    strategy = normalize_team_strategy(my_shape.get("strategy") or my_shape.get("mode"))
    age = _safe_float(target_asset.get("age"), 0.0)
    if pos in set(my_shape.get("needs") or []):
        return f"This player fits because {pos} is one of your current pressure positions."
    if strategy in {"rebuild", "tank"} and 0 < age <= 25:
        return "This player fits because the age curve lines up with a longer timeline."
    if strategy in {"contender", "fringe_contender"} and 26 <= age <= 30:
        return "This player fits because the profile helps a win-now roster immediately."
    return "This player fits because the talent tier can improve your roster flexibility even without forcing a rebuild of the depth chart."


def _select_hub_ideas(ideas: List[Dict[str, Any]], max_ideas: int) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    path_counts: Dict[str, int] = {}
    partner_counts: Dict[str, int] = {}
    for idea in ideas:
        path = str(idea.get("hub_path") or idea.get("tag") or "")
        partner = str(idea.get("partner_team_name") or "")
        if path_counts.get(path, 0) >= 2:
            continue
        if partner_counts.get(partner, 0) >= 3:
            continue
        selected.append(idea)
        path_counts[path] = path_counts.get(path, 0) + 1
        partner_counts[partner] = partner_counts.get(partner, 0) + 1
        if len(selected) >= max_ideas:
            return selected
    return selected[:max_ideas]


PLAYER_SEARCH_PACKAGE_BUDGET = 480
PLAYER_SEARCH_STRUCTURE_BUDGETS = {
    "one_for_one": 72,
    "player_plus_pick": 180,
    "player_plus_player": 72,
    "multi_asset": 96,
}
PLAYER_SEARCH_EMPTY_LEAD = (
    "We couldn't build a value-coherent package around this player "
    "from the assets currently available in your league."
)
_PLAYER_SEARCH_EMPTY_REASONS = (
    (
        "rejected_market_hard_fail",
        "Closest matches fail hard roster or asset-validity checks.",
    ),
    (
        "rejected_value_window",
        "Closest matches sit too far apart in value to be coherent.",
    ),
    (
        "rejected_partner_fit",
        "Closest matches require assets the likely trade partners don't own.",
    ),
    (
        "rejected_user_roster_fit",
        "Closest matches would strain your current roster construction.",
    ),
    (
        "rejected_acceptance",
        "Closest matches are harder to execute than a realistic partner path.",
    ),
    (
        "rejected_strategy",
        "Closest matches fight the current team strategy.",
    ),
    (
        "no_direct_match",
        "Direct player-for-player matches were not available in this league.",
    ),
)


def _empty_player_search_funnel() -> Dict[str, Any]:
    return {
        "partner_teams_considered": 0,
        "raw_packages_constructed": 0,
        "packages_containing_focal": 0,
        "one_for_one_candidates": 0,
        "player_plus_pick_candidates": 0,
        "player_plus_player_candidates": 0,
        "multi_asset_candidates": 0,
        "rejected_value_window": 0,
        "rejected_user_roster_fit": 0,
        "rejected_partner_fit": 0,
        "rejected_acceptance": 0,
        "rejected_market_hard_fail": 0,
        "market_hard_fail_total": 0,
        "market_hard_fail_unknown": 0,
        "rejected_strategy": 0,
        "deduped": 0,
        "final_strict_results": 0,
        "final_expanded_results": 0,
        "final_exploratory_results": 0,
        "candidates_scored": 0,
        "search_elapsed_ms": 0,
        "pick_universe_max_round": 4,
        "pick_universe_years": 0,
        "construction_budget_hits": 0,
        "partners_skipped_empty_join": 0,
        "closest_one_for_one_delta": None,
        "closest_player_plus_pick_delta": None,
        "closest_player_plus_player_delta": None,
        "closest_multi_asset_delta": None,
        "closest_one_for_one_stage": "",
        "closest_player_plus_pick_stage": "",
        "closest_player_plus_player_stage": "",
        "closest_multi_asset_stage": "",
        "closest_rejected_packages": [],
        "stage_ms_primary_board": 0,
        "stage_ms_construction": 0,
        "stage_ms_value_window": 0,
        "stage_ms_market": 0,
        "stage_ms_user_fit": 0,
        "stage_ms_partner_fit": 0,
        "stage_ms_acceptance": 0,
        "stage_ms_strategy": 0,
        "stage_ms_dedupe": 0,
        "stage_ms_frame_normalize": 0,
        "stage_ms_universe": 0,
        "stage_ms_roster_index": 0,
        "stage_ms_team_shape": 0,
        "stage_ms_partner_prep": 0,
        "team_shape_hits": 0,
        "team_shape_misses": 0,
        "skipped_automatic_board": 0,
    }


def _package_structure_kind(
    send_assets: List[Dict[str, Any]],
    receive_assets: List[Dict[str, Any]],
) -> str:
    send_players = _player_assets(send_assets)
    receive_players = _player_assets(receive_assets)
    send_picks = _pick_assets(send_assets)
    receive_picks = _pick_assets(receive_assets)
    player_count = len(send_players) + len(receive_players)
    pick_count = len(send_picks) + len(receive_picks)
    if player_count == 2 and pick_count == 0 and len(send_players) == 1:
        return "one_for_one"
    if player_count >= 1 and pick_count >= 1 and player_count <= 2:
        return "player_plus_pick"
    if player_count >= 2 and pick_count == 0:
        return "player_plus_player"
    return "multi_asset"


def _count_package_structure(diagnostics: Dict[str, Any], kind: str) -> None:
    key = {
        "one_for_one": "one_for_one_candidates",
        "player_plus_pick": "player_plus_pick_candidates",
        "player_plus_player": "player_plus_player_candidates",
        "multi_asset": "multi_asset_candidates",
    }.get(kind, "multi_asset_candidates")
    diagnostics[key] = _safe_int(diagnostics.get(key), 0) + 1


def _owned_search_picks(
    pick_assets: List[Dict[str, Any]],
    *,
    max_round: int = 4,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    owned = [
        pick
        for pick in (pick_assets or [])
        if 1 <= _safe_int(pick.get("round"), 99) <= max_round
    ]
    owned.sort(key=lambda asset: int(asset.get("score") or 0), reverse=True)
    return owned[:limit]


def _bounded_pick_packages(
    pick_assets: List[Dict[str, Any]],
    *,
    max_size: int = 3,
    limit: int = 12,
) -> List[List[Dict[str, Any]]]:
    packages: List[List[Dict[str, Any]]] = []
    for size in range(1, max_size + 1):
        for combo in combinations(pick_assets, size):
            labels = [str(asset.get("label") or "") for asset in combo]
            if len(set(labels)) != len(labels):
                continue
            packages.append(list(combo))
            if len(packages) >= limit:
                return packages
    return packages


def _median_int(values: List[int]) -> int:
    nums = sorted(int(value) for value in values)
    if not nums:
        return 0
    mid = len(nums) // 2
    if len(nums) % 2:
        return nums[mid]
    return int(round((nums[mid - 1] + nums[mid]) / 2.0))


def freeze_player_search_roster_map(mapping: Mapping[Any, Any] | None) -> tuple:
    rows = []
    for key, player_ids in (mapping or {}).items():
        roster_id = _safe_int(key)
        if roster_id <= 0:
            continue
        rows.append(
            (
                roster_id,
                tuple(str(pid) for pid in (player_ids or []) if str(pid or "").strip()),
            )
        )
    return tuple(sorted(rows, key=lambda item: item[0]))


def thaw_player_search_roster_map(items) -> Dict[int, List[str]]:
    thawed: Dict[int, List[str]] = {}
    for roster_id, player_ids in items or ():
        rid = _safe_int(roster_id)
        if rid <= 0:
            continue
        thawed[rid] = [str(pid) for pid in (player_ids or []) if str(pid or "").strip()]
    return thawed


def freeze_player_search_pick_assets(assets) -> tuple:
    rows = []
    iterable: List[Dict[str, Any]] = []
    if isinstance(assets, Mapping):
        for owner_id, picks in assets.items():
            for pick in picks or []:
                payload = dict(pick or {})
                payload.setdefault("owner_roster_id", owner_id)
                iterable.append(payload)
    else:
        iterable = list(assets or [])
    for pick in iterable:
        owner_id = _safe_int(pick.get("owner_roster_id"))
        if owner_id <= 0 or str(pick.get("asset_type") or "pick") != "pick":
            continue
        rows.append(
            (
                owner_id,
                str(pick.get("label") or ""),
                _safe_int(pick.get("score")),
                _safe_int(pick.get("season")),
                _safe_int(pick.get("round")),
                _safe_int(pick.get("original_roster_id")),
            )
        )
    return tuple(rows)


def thaw_player_search_pick_assets(items) -> Dict[int, List[Dict[str, Any]]]:
    by_owner: Dict[int, List[Dict[str, Any]]] = {}
    for owner_id, label, score, season, round_num, original_id in items or ():
        rid = _safe_int(owner_id)
        if rid <= 0:
            continue
        by_owner.setdefault(rid, []).append(
            {
                "asset_type": "pick",
                "label": str(label or f"{season} Round {round_num}"),
                "score": _safe_int(score),
                "season": _safe_int(season),
                "round": _safe_int(round_num),
                "original_roster_id": _safe_int(original_id) or rid,
                "owner_roster_id": rid,
            }
        )
    return by_owner


def _normalize_roster_players_map(mapping: Mapping[Any, Any] | None) -> Dict[int, List[str]]:
    normalized: Dict[int, List[str]] = {}
    for key, player_ids in (mapping or {}).items():
        roster_id = _safe_int(key)
        if roster_id <= 0:
            continue
        normalized[roster_id] = [
            str(pid) for pid in (player_ids or []) if str(pid or "").strip()
        ]
    return normalized


def _record_closest_structure(
    diagnostics: Dict[str, Any],
    kind: str,
    delta: int,
    stage: str,
) -> None:
    delta_key = {
        "one_for_one": "closest_one_for_one_delta",
        "player_plus_pick": "closest_player_plus_pick_delta",
        "player_plus_player": "closest_player_plus_player_delta",
        "multi_asset": "closest_multi_asset_delta",
    }.get(kind, "closest_multi_asset_delta")
    stage_key = delta_key.replace("_delta", "_stage")
    previous = diagnostics.get(delta_key)
    if previous is None or abs(int(delta)) < abs(_safe_int(previous)):
        diagnostics[delta_key] = int(delta)
        diagnostics[stage_key] = str(stage or "")


def _add_stage_ms(diagnostics: Dict[str, Any], key: str, started: float) -> None:
    elapsed = round((time.perf_counter() - started) * 1000, 3)
    diagnostics[key] = round(_safe_float(diagnostics.get(key), 0.0) + elapsed, 3)


def _safe_package_shape(
    send_assets: List[Dict[str, Any]],
    receive_assets: List[Dict[str, Any]],
    *,
    delta: int,
    market_context: Dict[str, Any] | None = None,
    fit_context: Dict[str, Any] | None = None,
    stage: str,
) -> Dict[str, Any]:
    send_players = _player_assets(send_assets)
    receive_players = _player_assets(receive_assets)
    send_picks = _pick_assets(send_assets)
    receive_picks = _pick_assets(receive_assets)
    market = market_context or {}
    fit = fit_context or {}
    return {
        "send_total": _score_assets(send_assets),
        "receive_total": _score_assets(receive_assets),
        "delta": int(delta),
        "send_player_count": len(send_players),
        "send_pick_count": len(send_picks),
        "receive_player_count": len(receive_players),
        "receive_pick_count": len(receive_picks),
        "structure": _package_structure_kind(send_assets, receive_assets),
        "stage": str(stage or ""),
        "hard_fail_flags": list(market.get("hard_fail_flags") or []),
        "market_score": _safe_int(market.get("score"), 0),
        "fit_score": _safe_int(fit.get("score"), 0),
        "partner_fit_score": _safe_int(fit.get("partner_score"), 0),
    }


def _record_closest_rejected_packages(
    diagnostics: Dict[str, Any],
    row: Dict[str, Any],
    *,
    limit: int = 3,
) -> None:
    closest = list(diagnostics.get("closest_rejected_packages") or [])
    closest.append(row)
    closest.sort(key=lambda item: (abs(_safe_int(item.get("delta"))), str(item.get("structure") or "")))
    diagnostics["closest_rejected_packages"] = closest[: max(1, int(limit))]


def _count_market_hard_fail(diagnostics: Dict[str, Any], flags: List[str] | None) -> None:
    diagnostics["rejected_market_hard_fail"] = (
        _safe_int(diagnostics.get("rejected_market_hard_fail"), 0) + 1
    )
    diagnostics["market_hard_fail_total"] = (
        _safe_int(diagnostics.get("market_hard_fail_total"), 0) + 1
    )
    names = [str(flag).strip() for flag in (flags or []) if str(flag).strip()]
    if not names:
        diagnostics["market_hard_fail_unknown"] = (
            _safe_int(diagnostics.get("market_hard_fail_unknown"), 0) + 1
        )
        return
    for flag in dict.fromkeys(names):
        key = f"market_hard_fail_{flag}"
        diagnostics[key] = _safe_int(diagnostics.get(key), 0) + 1


PLAYER_SEARCH_FOUNDER_KEYS = (
    "focal_found",
    "focal_value",
    "score_field_used",
    "league_teams",
    "eligible_partner_teams",
    "partner_teams_considered",
    "roster_assets_visible",
    "fantasy_relevant_player_assets",
    "future_picks_visible",
    "pick_universe_years",
    "pick_universe_max_round",
    "traded_pick_ownership_moves",
    "pick_source",
    "roster_source",
    "assets_discarded_missing_value",
    "partners_skipped_empty_join",
    "median_partner_player_value",
    "max_partner_player_value",
    "median_pick_value",
    "max_pick_value",
    "raw_packages_constructed",
    "packages_containing_focal",
    "one_for_one_candidates",
    "player_plus_pick_candidates",
    "player_plus_player_candidates",
    "multi_asset_candidates",
    "candidates_scored",
    "rejected_value_window",
    "rejected_user_roster_fit",
    "rejected_partner_fit",
    "rejected_acceptance",
    "rejected_market_hard_fail",
    "market_hard_fail_total",
    "market_hard_fail_unknown",
    "rejected_strategy",
    "deduped",
    "final_strict_results",
    "final_expanded_results",
    "final_exploratory_results",
    "search_elapsed_ms",
    "construction_budget_hits",
    "closest_one_for_one_delta",
    "closest_player_plus_pick_delta",
    "closest_player_plus_player_delta",
    "closest_multi_asset_delta",
    "closest_one_for_one_stage",
    "closest_player_plus_pick_stage",
    "closest_player_plus_player_stage",
    "closest_multi_asset_stage",
    "closest_rejected_packages",
    "stage_ms_primary_board",
    "stage_ms_construction",
    "stage_ms_value_window",
    "stage_ms_market",
    "stage_ms_user_fit",
    "stage_ms_partner_fit",
    "stage_ms_acceptance",
    "stage_ms_strategy",
    "stage_ms_dedupe",
    "stage_ms_frame_normalize",
    "stage_ms_universe",
    "stage_ms_roster_index",
    "stage_ms_team_shape",
    "stage_ms_partner_prep",
    "team_shape_hits",
    "team_shape_misses",
    "team_shape_lineup_ms",
    "team_shape_injury_ms",
    "team_shape_needs_ms",
    "team_shape_signature_ms",
    "dataframe_copies",
    "universe_scans",
    "roster_index_calls",
    "draft_context_skipped",
    "strategy_curve",
    "streamlit_cache_data_absent",
    "session_cache_status",
    "skipped_automatic_board",
)


def player_search_founder_report(search_result: Mapping[str, Any] | None) -> Dict[str, Any]:
    payload = search_result if isinstance(search_result, Mapping) else {}
    diagnostics = payload.get("diagnostics")
    diagnostics = diagnostics if isinstance(diagnostics, Mapping) else {}
    report = {}
    for key in PLAYER_SEARCH_FOUNDER_KEYS:
        if key in diagnostics:
            report[key] = diagnostics[key]
    for key, value in diagnostics.items():
        if str(key).startswith("market_hard_fail_") and key not in report:
            report[key] = value
        if str(key).startswith("presentation_") and key not in report:
            report[key] = value
    report["visible_ideas"] = len(payload.get("ideas") or [])
    report["primary_count"] = _safe_int(payload.get("primary_count"), 0)
    report["expanded_count"] = _safe_int(payload.get("expanded_count"), 0)
    report["exploratory_count"] = _safe_int(payload.get("exploratory_count"), 0)
    return report


def _mark_exploratory_idea(idea: Dict[str, Any]) -> Dict[str, Any]:
    updated = dict(idea)
    updated["hub_search_source"] = "exploratory"
    updated["trade_confidence_label"] = "Low"
    updated["trade_surface_tier"] = "secondary"
    updated["trade_headline_ready"] = False
    updated["hub_exploratory"] = True
    path = str(updated.get("hub_path") or "").strip()
    if path and "exploratory" not in path.casefold() and "harder" not in path.casefold():
        updated["hub_path"] = f"Harder to execute · {path}"
    elif not path:
        updated["hub_path"] = "Harder to execute"
    return updated


def _select_player_search_ideas(
    ideas: List[Dict[str, Any]],
    max_ideas: int,
) -> List[Dict[str, Any]]:
    primary = [idea for idea in ideas if str(idea.get("hub_search_source") or "primary") == "primary"]
    expanded = [idea for idea in ideas if str(idea.get("hub_search_source") or "") == "expanded"]
    exploratory = [idea for idea in ideas if str(idea.get("hub_search_source") or "") == "exploratory"]
    selected = _select_hub_ideas(primary, max_ideas)
    remaining = max(0, max_ideas - len(selected))
    if remaining:
        selected.extend(_select_hub_ideas(expanded, remaining))
    remaining = max(0, max_ideas - len(selected))
    if remaining and (not selected or len(selected) < min(2, max_ideas)):
        selected.extend(_select_hub_ideas(exploratory, min(3, remaining)))
    elif remaining:
        selected.extend(_select_hub_ideas(exploratory, min(2, remaining)))
    return selected[:max_ideas]


def _hub_diagnostic_summary(diagnostics: Dict[str, int] | None) -> str:
    counts = diagnostics or {}
    labels = {
        "no_direct_match": "no direct package match",
        "no_value_match": "no value match",
        "rejected_value_window": "no value match",
        "no_roster_fit": "no roster fit",
        "rejected_user_roster_fit": "no roster fit",
        "no_partner_fit": "no partner fit",
        "rejected_partner_fit": "no partner fit",
        "no_reasoning_fit": "no valid package fit",
        "rejected_acceptance": "no valid package fit",
        "no_market_realism": "no plausible acceptance path",
        "rejected_market_hard_fail": "no plausible acceptance path",
        "rejected_strategy": "no strategy fit",
    }
    ranked = sorted(
        ((key, _safe_int(value, 0)) for key, value in counts.items() if _safe_int(value, 0) > 0 and key in labels),
        key=lambda item: item[1],
        reverse=True,
    )
    if not ranked:
        return ""
    seen = []
    for key, _ in ranked:
        label = labels[key]
        if label not in seen:
            seen.append(label)
        if len(seen) >= 3:
            break
    return ", ".join(seen)


def player_search_engine_result_count(search_result: Mapping[str, Any] | None) -> int:
    payload = search_result if isinstance(search_result, Mapping) else {}
    diagnostics = payload.get("diagnostics")
    diagnostics = diagnostics if isinstance(diagnostics, Mapping) else {}
    return (
        _safe_int(diagnostics.get("final_strict_results"), 0)
        + _safe_int(diagnostics.get("final_expanded_results"), 0)
        + _safe_int(diagnostics.get("final_exploratory_results"), 0)
    )


def player_search_empty_state_copy(search_result: Mapping[str, Any] | None) -> tuple[str, str]:
    payload = search_result if isinstance(search_result, Mapping) else {}
    if payload.get("ideas"):
        return "", ""
    if player_search_engine_result_count(payload) > 0:
        return (
            "Valid packages were found but could not be displayed after validity checks.",
            "",
        )
    diagnostics = payload.get("diagnostics")
    diagnostics = diagnostics if isinstance(diagnostics, Mapping) else {}
    ranked = sorted(
        (
            (key, _safe_int(diagnostics.get(key), 0), reason)
            for key, reason in _PLAYER_SEARCH_EMPTY_REASONS
            if _safe_int(diagnostics.get(key), 0) > 0
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    if not ranked:
        return PLAYER_SEARCH_EMPTY_LEAD, ""
    return PLAYER_SEARCH_EMPTY_LEAD, ranked[0][2]


def player_hub_rejection_diagnostic(
    search_result: Mapping[str, Any] | None,
    *,
    limit: int = 10,
) -> Dict[str, Any]:
    """Sanitized DEV/TEST provenance for a real player-search zero state."""

    payload = search_result if isinstance(search_result, Mapping) else {}
    diagnostics = payload.get("diagnostics")
    diagnostics = diagnostics if isinstance(diagnostics, Mapping) else {}
    hard_stages = {"ownership", "market_realism", "trust"}
    closest = []
    for raw in list(diagnostics.get("closest_rejections") or [])[: max(0, int(limit))]:
        if not isinstance(raw, Mapping):
            continue
        stage = str(raw.get("stage") or "unknown")
        closest.append(
            {
                "assets": [str(value) for value in list(raw.get("assets") or [])],
                "send_value": _safe_int(raw.get("send_value"), 0),
                "receive_value": _safe_int(raw.get("receive_value"), 0),
                "difference": _safe_int(raw.get("difference"), 0),
                "ratio": raw.get("ratio"),
                "stage": stage,
                "reason": str(raw.get("reason") or ""),
                "constraint": "hard" if stage in hard_stages else "soft",
            }
        )
    counts = {
        key: int(value)
        for key, value in diagnostics.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }
    return {
        "counts": counts,
        "closest_rejections": closest,
        "fallback_used": bool(payload.get("fallback_used")),
        "visible_ideas": len(payload.get("ideas") or []),
    }


def _hub_search_result(
    ideas: List[Dict[str, Any]] | None = None,
    *,
    fallback_used: bool = False,
    diagnostics: Dict[str, int] | None = None,
    primary_count: int = 0,
    expanded_count: int = 0,
    exploratory_count: int = 0,
) -> Dict[str, Any]:
    return {
        "ideas": list(ideas or []),
        "fallback_used": bool(fallback_used) or int(expanded_count or 0) > 0 or int(exploratory_count or 0) > 0,
        "diagnostics": dict(diagnostics or {}),
        "diagnostic_summary": _hub_diagnostic_summary(diagnostics),
        "primary_count": int(primary_count or 0),
        "expanded_count": int(expanded_count or 0),
        "exploratory_count": int(exploratory_count or 0),
    }


def _build_my_player_fallback_ideas(
    *,
    df_summary: pd.DataFrame,
    df_players: pd.DataFrame,
    roster_players_map: Dict[int, List[str]],
    roster_pick_assets: Dict[int, List[Dict[str, Any]]],
    league_draft_capitals: List[int],
    my_roster_key: int,
    my_shape: Dict[str, Any],
    selected_asset: Dict[str, Any],
    score_field: str,
    pick_score_multiplier: float,
    active_strategy: str,
    league_settings: Dict[str, Any] | None = None,
    team_frames: Dict[int, pd.DataFrame] | None = None,
) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
    diagnostics = _empty_player_search_funnel()
    diagnostics.update(
        {
            "no_value_match": 0,
            "no_roster_fit": 0,
            "no_partner_fit": 0,
            "no_reasoning_fit": 0,
            "no_market_realism": 0,
        }
    )
    pick_years = {
        _safe_int(pick.get("season"), 0)
        for assets in (roster_pick_assets or {}).values()
        for pick in (assets or [])
        if _safe_int(pick.get("season"), 0) > 0
    }
    diagnostics["pick_universe_years"] = len(pick_years)
    my_mode = team_strategy_mode(active_strategy)
    selected_score = int(selected_asset.get("score") or 0)
    selected_age = _safe_float(selected_asset.get("age"), 0.0)
    ideas: List[Dict[str, Any]] = []
    seen: set[str] = set()
    exploratory_pool: List[Dict[str, Any]] = []

    def commit_idea(
        *,
        partner_name: str,
        partner_mode: str,
        outgoing: List[Dict[str, Any]],
        receive_assets: List[Dict[str, Any]],
        title: str,
        rationale: str,
        priority: int,
        reasoning: Dict[str, Any],
        fit_bonus: int,
        fit_context: Dict[str, Any],
        market_context: Dict[str, Any],
        source: str,
    ) -> Dict[str, Any]:
        idea = _make_idea(
            partner_name,
            outgoing,
            receive_assets,
            my_mode,
            partner_mode,
            title,
            " ".join(
                part
                for part in [
                    reasoning.get("summary", ""),
                    rationale,
                    fit_context.get("rationale", ""),
                    market_context.get("summary", ""),
                ]
                if part
            ).strip(),
            int(priority)
            + int(reasoning["score"])
            + int(fit_bonus)
            + int(fit_context["score"])
            + int(round((int(market_context.get("score") or 0) - 50) / 4.0)),
            reasoning_tags=reasoning["tags"],
            reasoning_summary=reasoning["summary"],
            my_strategy=str(my_shape.get("strategy") or my_mode),
            partner_strategy=str(partner_shape.get("strategy") or partner_mode),
        )
        idea = _apply_strategy_context_to_idea(idea, reasoning, my_shape)
        idea = _attach_trade_assessment_fields(
            idea,
            fit_context=fit_context,
            market_context=market_context,
        )
        idea["hub_mode"] = "my_player"
        idea["hub_search_source"] = source
        idea["hub_path"] = _player_hub_path_label(
            selected_asset, outgoing, receive_assets, active_strategy, "my_player"
        )
        idea["hub_candidate_reason"] = _my_player_candidate_reason(selected_asset, my_shape)
        idea["hub_solution_reason"] = _my_player_solution_reason(selected_asset, receive_assets, my_shape)
        if source == "exploratory":
            idea = _mark_exploratory_idea(idea)
        return idea

    def add_fallback_idea(
        partner_name: str,
        partner_mode: str,
        partner_shape: Dict[str, Any],
        receive_assets: List[Dict[str, Any]],
        title: str,
        rationale: str,
        priority: int,
        *,
        low: int,
        high: int,
        min_reason_score: int = 6,
        min_acceptance_score: int = 54,
        partner_profile: Dict[str, Any] | None = None,
        send_assets: List[Dict[str, Any]] | None = None,
        source: str = "expanded",
    ) -> None:
        outgoing = list(send_assets or [selected_asset])
        selected_id = str(selected_asset.get("player_id") or "")
        if not any(str(asset.get("player_id") or "") == selected_id for asset in outgoing):
            outgoing = [selected_asset] + outgoing
        construction_started = time.perf_counter()
        kind = _package_structure_kind(outgoing, receive_assets)
        structure_budget = PLAYER_SEARCH_STRUCTURE_BUDGETS.get(kind, PLAYER_SEARCH_STRUCTURE_BUDGETS["multi_asset"])
        kind_count_key = {
            "one_for_one": "one_for_one_candidates",
            "player_plus_pick": "player_plus_pick_candidates",
            "player_plus_player": "player_plus_player_candidates",
            "multi_asset": "multi_asset_candidates",
        }.get(kind, "multi_asset_candidates")
        if diagnostics["raw_packages_constructed"] >= PLAYER_SEARCH_PACKAGE_BUDGET:
            diagnostics["construction_budget_hits"] = (
                _safe_int(diagnostics.get("construction_budget_hits"), 0) + 1
            )
            return
        if _safe_int(diagnostics.get(kind_count_key), 0) >= structure_budget:
            diagnostics["construction_budget_hits"] = (
                _safe_int(diagnostics.get("construction_budget_hits"), 0) + 1
            )
            return
        diagnostics["raw_packages_constructed"] = (
            _safe_int(diagnostics.get("raw_packages_constructed"), 0) + 1
        )
        if any(str(asset.get("player_id") or "") == selected_id for asset in outgoing):
            diagnostics["packages_containing_focal"] = (
                _safe_int(diagnostics.get("packages_containing_focal"), 0) + 1
            )
        _count_package_structure(diagnostics, kind)
        _add_stage_ms(diagnostics, "stage_ms_construction", construction_started)
        key = _package_key(outgoing, receive_assets)
        send_score = _score_assets(outgoing)
        receive_score = _score_assets(receive_assets)
        delta = receive_score - send_score
        if key in seen:
            diagnostics["deduped"] = _safe_int(diagnostics.get("deduped"), 0) + 1
            _record_closest_structure(diagnostics, kind, delta, "dedupe")
            return
        value_started = time.perf_counter()
        if not _value_fits(send_score, receive_score, low=low, high=high):
            diagnostics["no_value_match"] += 1
            diagnostics["rejected_value_window"] = (
                _safe_int(diagnostics.get("rejected_value_window"), 0) + 1
            )
            _record_closest_structure(diagnostics, kind, delta, "value_window")
            _add_stage_ms(diagnostics, "stage_ms_value_window", value_started)
            return
        _add_stage_ms(diagnostics, "stage_ms_value_window", value_started)
        diagnostics["candidates_scored"] = _safe_int(diagnostics.get("candidates_scored"), 0) + 1
        market_started = time.perf_counter()
        market_context = evaluate_trade_market_realism(
            send_assets=outgoing,
            receive_assets=receive_assets,
            my_shape=my_shape,
            partner_shape=partner_shape,
            partner_name=partner_name,
            partner_profile=partner_profile,
            league_settings=league_settings,
            explicit_player_focus=True,
            focused_player_ids=[selected_id],
        )
        _add_stage_ms(diagnostics, "stage_ms_market", market_started)
        if market_context.get("hard_fail"):
            diagnostics["no_market_realism"] += 1
            _count_market_hard_fail(
                diagnostics,
                list(market_context.get("hard_fail_flags") or []),
            )
            _record_closest_structure(diagnostics, kind, delta, "market_hard_fail")
            _record_closest_rejected_packages(
                diagnostics,
                _safe_package_shape(
                    outgoing,
                    receive_assets,
                    delta=delta,
                    market_context=market_context,
                    stage="market_hard_fail",
                ),
            )
            return
        fit_started = time.perf_counter()
        fit_bonus = _fit_priority(outgoing, receive_assets, my_shape, partner_shape)
        _add_stage_ms(diagnostics, "stage_ms_user_fit", fit_started)
        partner_fit_started = time.perf_counter()
        fit_context = _trade_fit_context(
            my_shape,
            partner_shape,
            outgoing,
            receive_assets,
            partner_name,
        )
        _add_stage_ms(diagnostics, "stage_ms_partner_fit", partner_fit_started)
        reasoning_started = time.perf_counter()
        reasoning = _trade_reasoning_context(
            my_shape,
            partner_shape,
            outgoing,
            receive_assets,
            partner_name,
        )
        _add_stage_ms(diagnostics, "stage_ms_acceptance", reasoning_started)
        _add_stage_ms(diagnostics, "stage_ms_strategy", reasoning_started)
        soft_fail = None
        if fit_bonus < -8:
            soft_fail = "user_fit"
            diagnostics["no_roster_fit"] += 1
            diagnostics["rejected_user_roster_fit"] = (
                _safe_int(diagnostics.get("rejected_user_roster_fit"), 0) + 1
            )
            _record_closest_structure(diagnostics, kind, delta, "user_fit")
        elif int(fit_context["partner_score"]) < -30:
            soft_fail = "partner_fit"
            diagnostics["no_partner_fit"] += 1
            diagnostics["rejected_partner_fit"] = (
                _safe_int(diagnostics.get("rejected_partner_fit"), 0) + 1
            )
            _record_closest_structure(diagnostics, kind, delta, "partner_fit")
        elif reasoning["score"] < min_reason_score:
            soft_fail = "acceptance"
            diagnostics["no_reasoning_fit"] += 1
            diagnostics["rejected_acceptance"] = (
                _safe_int(diagnostics.get("rejected_acceptance"), 0) + 1
            )
            diagnostics["rejected_strategy"] = (
                _safe_int(diagnostics.get("rejected_strategy"), 0) + 1
            )
            _record_closest_structure(diagnostics, kind, delta, "acceptance")
        elif int(market_context.get("score") or 0) < min_acceptance_score:
            soft_fail = "acceptance"
            diagnostics["no_market_realism"] += 1
            diagnostics["rejected_acceptance"] = (
                _safe_int(diagnostics.get("rejected_acceptance"), 0) + 1
            )
            _record_closest_structure(diagnostics, kind, delta, "acceptance")
        else:
            _record_closest_structure(diagnostics, kind, delta, "accepted")
        idea = commit_idea(
            partner_name=partner_name,
            partner_mode=partner_mode,
            outgoing=outgoing,
            receive_assets=receive_assets,
            title=title,
            rationale=rationale,
            priority=priority,
            reasoning=reasoning,
            fit_bonus=fit_bonus,
            fit_context=fit_context,
            market_context=market_context,
            source="exploratory" if soft_fail else source,
        )
        if soft_fail:
            exploratory_pool.append(idea)
            return
        seen.add(key)
        ideas.append(idea)

    my_team_ids = roster_players_map.get(my_roster_key, [])
    indexed_frames = team_frames if team_frames is not None else _index_roster_team_frames(
        df_players, roster_players_map
    )
    my_team_df = indexed_frames.get(my_roster_key)
    if my_team_df is None or getattr(my_team_df, "empty", True):
        my_team_df = df_players[df_players["player_id"].isin(my_team_ids)]
    selected_id = str(selected_asset.get("player_id") or "")
    complementary_sends = []
    for _, row in my_team_df.iterrows():
        if _row_score(row, score_field) <= 0:
            continue
        if str(row.get("player_id") or "") == selected_id:
            continue
        asset = _player_asset(row, score_field=score_field)
        if not _is_core_or_protected_starter(asset):
            complementary_sends.append(asset)
    complementary_sends.sort(key=lambda asset: int(asset.get("score") or 0), reverse=True)
    complementary_sends = complementary_sends[:4]
    my_balancer_picks = _owned_search_picks(
        [
            _pick_asset(pick, score_multiplier=pick_score_multiplier)
            for pick in roster_pick_assets.get(my_roster_key, [])
        ],
        max_round=4,
        limit=8,
    )

    for _, partner_row in df_summary.iterrows():
        partner_roster_id = _safe_int(partner_row.get("roster_id"))
        if partner_roster_id <= 0 or partner_roster_id == my_roster_key:
            continue
        partner_name = str(partner_row.get("team_name") or "Partner")
        partner_player_ids = roster_players_map.get(partner_roster_id, [])
        partner_team_df = indexed_frames.get(partner_roster_id)
        if partner_team_df is None or getattr(partner_team_df, "empty", True):
            partner_team_df = df_players[df_players["player_id"].isin(partner_player_ids)]
        if partner_team_df.empty:
            diagnostics["partners_skipped_empty_join"] = (
                _safe_int(diagnostics.get("partners_skipped_empty_join"), 0) + 1
            )
            continue
        diagnostics["partner_teams_considered"] = (
            _safe_int(diagnostics.get("partner_teams_considered"), 0) + 1
        )
        shape_started = time.perf_counter()
        partner_shape = _build_team_shape(
            df_summary,
            partner_roster_id,
            partner_team_df,
            score_field,
            roster_pick_assets.get(partner_roster_id, []),
            league_draft_capitals,
            league_settings=league_settings,
        )
        _add_stage_ms(diagnostics, "stage_ms_team_shape", shape_started)
        partner_mode = str(partner_shape.get("mode") or partner_row.get("mode") or "")
        partner_profile = partner_row.to_dict() if hasattr(partner_row, "to_dict") else {}
        prep_started = time.perf_counter()
        partner_player_assets = [
            _player_asset(row, score_field=score_field)
            for _, row in partner_team_df.iterrows()
            if _row_score(row, score_field) > 0
        ]
        partner_player_assets.sort(
            key=lambda asset: abs(int(asset.get("score") or 0) - selected_score),
        )
        value_near_targets = partner_player_assets[:8]
        fit_ranked_targets = sorted(
            partner_player_assets,
            key=lambda asset: (
                _target_trade_fit(asset, my_shape, partner_shape),
                asset["score"],
            ),
            reverse=True,
        )[:8]
        partner_pick_assets = _owned_search_picks(
            [
                _pick_asset(pick, score_multiplier=pick_score_multiplier)
                for pick in roster_pick_assets.get(partner_roster_id, [])
            ],
            max_round=4,
            limit=8,
        )
        _add_stage_ms(diagnostics, "stage_ms_partner_prep", prep_started)

        for target in value_near_targets:
            add_fallback_idea(
                partner_name,
                partner_mode,
                partner_shape,
                [target],
                "Expanded one-for-one path",
                "Expanded search widens the direct value band when simple matches are scarce.",
                54,
                low=-2200,
                high=1400,
                min_reason_score=6,
                min_acceptance_score=54,
                partner_profile=partner_profile,
                send_assets=[selected_asset],
            )

        for target in value_near_targets:
            for pick in partner_pick_assets[:5]:
                add_fallback_idea(
                    partner_name,
                    partner_mode,
                    partner_shape,
                    [target, pick],
                    "Expanded player + pick path",
                    "Owned future picks balance a mid-star player when a one-for-one misses the value window.",
                    52,
                    low=-2400,
                    high=1800,
                    min_reason_score=6,
                    min_acceptance_score=54,
                    partner_profile=partner_profile,
                    send_assets=[selected_asset],
                )
            for combo in _bounded_pick_packages(partner_pick_assets[:5], max_size=2, limit=3):
                add_fallback_idea(
                    partner_name,
                    partner_mode,
                    partner_shape,
                    [target, *combo],
                    "Expanded player + picks path",
                    "Multiple owned picks can balance a player when a one-for-one misses the value window.",
                    51,
                    low=-2400,
                    high=2000,
                    min_reason_score=6,
                    min_acceptance_score=54,
                    partner_profile=partner_profile,
                    send_assets=[selected_asset],
                )

        for target in fit_ranked_targets:
            for pick in my_balancer_picks[:4]:
                add_fallback_idea(
                    partner_name,
                    partner_mode,
                    partner_shape,
                    [target],
                    "Expanded send-side pick balancer",
                    "A complementary owned pick can close a value gap without dropping the focal player.",
                    53,
                    low=-2400,
                    high=1800,
                    min_reason_score=6,
                    min_acceptance_score=54,
                    partner_profile=partner_profile,
                    send_assets=[selected_asset, pick],
                )
            for extra in complementary_sends[:2]:
                add_fallback_idea(
                    partner_name,
                    partner_mode,
                    partner_shape,
                    [target],
                    "Expanded two-for-one send",
                    "A complementary roster piece plus the focal player can reach a stronger return.",
                    52,
                    low=-2600,
                    high=1800,
                    min_reason_score=6,
                    min_acceptance_score=54,
                    partner_profile=partner_profile,
                    send_assets=[selected_asset, extra],
                )

        for i, first in enumerate(fit_ranked_targets[:5]):
            for second in fit_ranked_targets[i + 1 : 6]:
                receive_assets = [first, second]
                add_fallback_idea(
                    partner_name,
                    partner_mode,
                    partner_shape,
                    receive_assets,
                    "Expanded depth-for-upside return",
                    "Expanded search checks two-player return packages when a single asset does not clear the fit gates.",
                    50,
                    low=-2600,
                    high=2200,
                    min_reason_score=7,
                    min_acceptance_score=58,
                    partner_profile=partner_profile,
                )

        for i, first in enumerate(fit_ranked_targets[:4]):
            for j, second in enumerate(fit_ranked_targets[i + 1 : 5], start=i + 1):
                for third in fit_ranked_targets[j + 1 : 5]:
                    add_fallback_idea(
                        partner_name,
                        partner_mode,
                        partner_shape,
                        [first, second, third],
                        "Expanded three-asset return",
                        "A wider package can match an elite asset without weakening the existing safety gates.",
                        48,
                        low=-2800,
                        high=2400,
                        min_reason_score=7,
                        min_acceptance_score=58,
                        partner_profile=partner_profile,
                    )

        if partner_pick_assets:
            pick_packages = _bounded_pick_packages(
                partner_pick_assets[:6],
                max_size=3,
                limit=10,
            )
            for receive_assets in pick_packages:
                min_reason = 6 if selected_age >= 26 or normalize_team_strategy(active_strategy) in {"rebuild", "tank"} else 8
                add_fallback_idea(
                    partner_name,
                    partner_mode,
                    partner_shape,
                    receive_assets,
                    "Expanded pick-heavy return",
                    "Expanded search checks owned-pick packages when a direct player match stays thin.",
                    46,
                    low=-1800,
                    high=2600,
                    min_reason_score=min_reason,
                    min_acceptance_score=54,
                    partner_profile=partner_profile,
                )

    if not ideas and exploratory_pool:
        promoted = 0
        for idea in exploratory_pool:
            key = _package_key(idea.get("send_assets") or [], idea.get("receive_assets") or [])
            if key in seen:
                continue
            seen.add(key)
            ideas.append(_mark_exploratory_idea(idea))
            promoted += 1
            if promoted >= 3:
                break
        diagnostics["exploratory_promoted"] = promoted

    ideas.sort(
        key=lambda idea: (
            0 if str(idea.get("hub_search_source") or "") == "exploratory" else 1,
            *_trade_surface_sort_key(idea),
        ),
        reverse=True,
    )
    return ideas, diagnostics


def _player_search_universe_snapshot(
    *,
    df_players: pd.DataFrame,
    df_summary: pd.DataFrame,
    roster_players_map: Dict[int, List[str]],
    roster_pick_assets: Dict[int, List[Dict[str, Any]]],
    my_roster_key: int,
    selected_asset: Dict[str, Any],
    score_field: str,
    roster_source: str,
    pick_source: str,
    direction: str,
) -> Dict[str, Any]:
    snapshot = _empty_player_search_funnel()
    partner_player_values: List[int] = []
    pick_values: List[int] = []
    pick_years: set[int] = set()
    pick_rounds: set[int] = set()
    missing_value = 0
    roster_assets = 0
    fantasy_players = 0
    traded_moves = 0
    _SEARCH_AUDIT["universe_scans"] = int(_SEARCH_AUDIT.get("universe_scans") or 0) + 1
    owned_partner: set[str] = set()
    expected_partner_ids = 0
    id_series = (
        df_players["player_id"].astype(str)
        if df_players is not None and not df_players.empty and "player_id" in df_players.columns
        else pd.Series(dtype="object")
    )
    score_series = (
        pd.to_numeric(df_players[score_field], errors="coerce").fillna(0)
        if df_players is not None
        and not df_players.empty
        and score_field in df_players.columns
        else pd.Series(dtype="float64")
    )
    for roster_id, player_ids in roster_players_map.items():
        ids = [str(pid) for pid in (player_ids or []) if pid is not None and str(pid)]
        roster_assets += len(player_ids or [])
        if int(roster_id) == int(my_roster_key):
            continue
        expected_partner_ids += len(ids)
        owned_partner.update(ids)
    if not id_series.empty and owned_partner:
        mask = id_series.isin(owned_partner)
        scores = score_series[mask] if not score_series.empty else pd.Series(dtype="float64")
        positive = scores[scores > 0]
        fantasy_players = int(len(positive))
        partner_player_values = [int(value) for value in positive.tolist()]
        missing_value = int((scores <= 0).sum())
        missing_value += max(0, expected_partner_ids - int(mask.sum()))
    elif expected_partner_ids:
        missing_value += expected_partner_ids
    for owner_id, picks in (roster_pick_assets or {}).items():
        for pick in picks or []:
            score = _safe_int(pick.get("score"))
            pick_values.append(score)
            year = _safe_int(pick.get("season"))
            rnd = _safe_int(pick.get("round"))
            if year:
                pick_years.add(year)
            if rnd:
                pick_rounds.add(rnd)
            original = _safe_int(pick.get("original_roster_id"))
            owner = _safe_int(pick.get("owner_roster_id"), owner_id)
            if original and owner and original != owner:
                traded_moves += 1
    league_teams = max(len(roster_players_map), len(df_summary) if df_summary is not None else 0)
    eligible_partners = sum(
        1
        for roster_id in roster_players_map
        if int(roster_id) != int(my_roster_key) and roster_players_map.get(roster_id)
    )
    snapshot.update(
        {
            "focal_found": 1 if selected_asset.get("player_id") else 0,
            "focal_value": _safe_int(selected_asset.get("score")),
            "score_field_used": str(score_field or ""),
            "league_teams": int(league_teams),
            "eligible_partner_teams": int(eligible_partners),
            "roster_assets_visible": int(roster_assets),
            "fantasy_relevant_player_assets": int(fantasy_players),
            "future_picks_visible": len(pick_values),
            "pick_universe_years": len(pick_years),
            "pick_universe_max_round": max(pick_rounds) if pick_rounds else 0,
            "traded_pick_ownership_moves": int(traded_moves),
            "pick_source": str(pick_source or ""),
            "roster_source": str(roster_source or ""),
            "assets_discarded_missing_value": int(missing_value),
            "median_partner_player_value": _median_int(partner_player_values),
            "max_partner_player_value": max(partner_player_values) if partner_player_values else 0,
            "median_pick_value": _median_int(pick_values),
            "max_pick_value": max(pick_values) if pick_values else 0,
            "search_direction": str(direction or ""),
        }
    )
    return snapshot


@runtime_trace.traced("trade_board_generation", phase="trade_generation")
def build_player_trade_hub_ideas(
    df_players: pd.DataFrame,
    league_id: str,
    df_summary: pd.DataFrame,
    my_roster_id: int,
    role_map: Dict[str, str],
    untouchable_names: List[str],
    *,
    mode: str,
    selected_player_id: str,
    max_ideas: int = 8,
    score_field: str = "value_score",
    pick_score_multiplier: float = 1.0,
    team_strategy: str | None = None,
    team_archetype: str | None = None,
    league_settings: Dict[str, Any] | None = None,
    draft_status: Dict[str, Any] | None = None,
    adapter=None,
    prefetched_roster_map=None,
    prefetched_pick_assets=None,
    hot_path_state=None,
) -> Dict[str, Any]:
    mode_key = str(mode or "").strip().lower()
    player_id = str(selected_player_id or "").strip()
    if mode_key not in {"my_player", "target_player"} or not player_id:
        return _hub_search_result()

    reset_player_search_audit()
    _SEARCH_AUDIT["strategy_curve"] = str(getattr(df_players, "attrs", {}).get("strategy_curve") or "")
    _SEARCH_AUDIT["draft_context_skipped"] = 1 if prefetched_pick_assets else 0

    with _find_block(hot_path_state, "player_search_frame_prepare"):
        normalize_started = time.perf_counter()
        if "player_id" in df_players.columns:
            player_ids_col = df_players["player_id"]
            if not (
                pd.api.types.is_string_dtype(player_ids_col)
                or str(player_ids_col.dtype) == "string"
            ):
                df_players = df_players.copy()
                _SEARCH_AUDIT["dataframe_copies"] = int(_SEARCH_AUDIT["dataframe_copies"]) + 1
                df_players["player_id"] = player_ids_col.astype(str)
        selected_rows = df_players[df_players["player_id"].astype(str) == player_id]
    if selected_rows.empty:
        empty = _hub_search_result()
        empty["diagnostics"] = {
            **_empty_player_search_funnel(),
            "focal_found": 0,
            "score_field_used": str(score_field or ""),
            "stage_ms_frame_normalize": round(
                (time.perf_counter() - normalize_started) * 1000, 3
            ),
        }
        return empty
    selected_row = selected_rows.iloc[0]
    frame_normalize_ms = round((time.perf_counter() - normalize_started) * 1000, 3)

    platform_adapter = adapter or get_sleeper_adapter()
    with _find_block(hot_path_state, "player_search_pick_prepare"):
        roster_source = "adapter"
        if prefetched_roster_map:
            roster_players_map = _normalize_roster_players_map(prefetched_roster_map)
            rosters = [
                {"roster_id": roster_id, "players": player_ids}
                for roster_id, player_ids in roster_players_map.items()
            ]
            roster_source = "hydrated_context"
        else:
            rosters = platform_adapter.get_rosters(league_id)
            roster_players_map = _roster_players_map(rosters)

        pick_source = "adapter_rebuild"
        if prefetched_pick_assets:
            if isinstance(prefetched_pick_assets, Mapping):
                sample = next(iter(prefetched_pick_assets.values()), None)
                if isinstance(sample, list):
                    roster_pick_assets = {
                        _safe_int(owner): list(picks or [])
                        for owner, picks in prefetched_pick_assets.items()
                        if _safe_int(owner) > 0
                    }
                else:
                    roster_pick_assets = thaw_player_search_pick_assets(
                        freeze_player_search_pick_assets(prefetched_pick_assets)
                    )
            else:
                roster_pick_assets = thaw_player_search_pick_assets(
                    freeze_player_search_pick_assets(prefetched_pick_assets)
                )
            pick_source = "hydrated_context"
        else:
            roster_pick_assets = _build_roster_pick_assets(
                league_id,
                rosters,
                df_summary,
                league_settings=league_settings,
                draft_status=draft_status,
                adapter=platform_adapter,
            )
        league_draft_capitals = [
            int(sum(int(pick.get("score") or 0) for pick in assets))
            for assets in roster_pick_assets.values()
        ]

    my_roster_key = _safe_int(my_roster_id)
    my_player_ids = roster_players_map.get(my_roster_key, [])
    with _find_block(hot_path_state, "player_search_roster_index"):
        index_started = time.perf_counter()
        team_frames = _index_roster_team_frames(df_players, roster_players_map)
        roster_index_ms = round((time.perf_counter() - index_started) * 1000, 3)
    my_team_df = team_frames.get(my_roster_key)
    if my_team_df is None or getattr(my_team_df, "empty", True):
        my_team_df = df_players[df_players["player_id"].astype(str).isin(my_player_ids)]
    if my_team_df.empty:
        return _hub_search_result()

    metrics = get_team_vs_league(df_summary, my_roster_key)
    if not metrics:
        return _hub_search_result()
    auto_strategy = normalize_team_strategy(metrics.get("strategy") or metrics.get("mode"))
    active_strategy = normalize_team_strategy(team_strategy or auto_strategy, default=auto_strategy)
    my_mode = team_strategy_mode(active_strategy)
    with _find_block(hot_path_state, "player_search_team_shapes"):
        shape_started = time.perf_counter()
        for roster_id, team_df in team_frames.items():
            if team_df is None or getattr(team_df, "empty", True):
                continue
            _build_team_shape(
                df_summary,
                roster_id,
                team_df,
                score_field,
                roster_pick_assets.get(roster_id, []),
                league_draft_capitals,
                league_settings=league_settings,
            )
        my_shape = _build_team_shape(
            df_summary,
            my_roster_key,
            my_team_df,
            score_field,
            roster_pick_assets.get(my_roster_key, []),
            league_draft_capitals,
            league_settings=league_settings,
        )
        team_shape_ms = round((time.perf_counter() - shape_started) * 1000, 3)
    _emit_team_shape_substages(hot_path_state)
    my_shape["strategy"] = active_strategy
    my_shape["strategy_label"] = team_strategy_label(active_strategy)
    my_shape["mode"] = my_mode
    if team_archetype:
        my_shape["archetype"] = str(team_archetype)
        my_shape["archetype_label"] = str(team_archetype)

    selected_asset = _player_asset(
        selected_row,
        role_map.get(player_id, "Flex"),
        score_field=score_field,
    )
    with _find_block(hot_path_state, "player_search_universe_prepare"):
        universe_started = time.perf_counter()
        universe = _player_search_universe_snapshot(
            df_players=df_players,
            df_summary=df_summary,
            roster_players_map=roster_players_map,
            roster_pick_assets=roster_pick_assets,
            my_roster_key=my_roster_key,
            selected_asset=selected_asset,
            score_field=score_field,
            roster_source=roster_source,
            pick_source=pick_source,
            direction="send" if mode_key == "my_player" else "acquire",
        )
        universe_ms = round((time.perf_counter() - universe_started) * 1000, 3)

    if mode_key == "my_player":
        diagnostics = _empty_player_search_funnel()
        diagnostics.update(universe)
        diagnostics["stage_ms_frame_normalize"] = frame_normalize_ms
        diagnostics["stage_ms_roster_index"] = roster_index_ms
        diagnostics["stage_ms_team_shape"] = team_shape_ms
        diagnostics["stage_ms_universe"] = universe_ms
        diagnostics["no_direct_match"] = 0
        selected_idea_key = str(selected_row.get("player_id") or "")
        board_started = time.perf_counter()
        # Explicit player search already has a dedicated constructor. The
        # automatic board rebuilds league context (provider calls) and then
        # hard-fails protected outgoing assets, which includes every focal
        # player at/above the core-asset score floor.
        diagnostics["skipped_automatic_board"] = 1
        diagnostics["no_direct_match"] += 1
        _add_stage_ms(diagnostics, "stage_ms_primary_board", board_started)
        primary_selected: List[Dict[str, Any]] = []
        with _find_block(hot_path_state, "player_search_build"):
            fallback_ideas, fallback_diag = _build_my_player_fallback_ideas(
                df_summary=df_summary,
                df_players=df_players,
                roster_players_map=roster_players_map,
                roster_pick_assets=roster_pick_assets,
                league_draft_capitals=league_draft_capitals,
                my_roster_key=my_roster_key,
                my_shape=my_shape,
                selected_asset=selected_asset,
                score_field=score_field,
                pick_score_multiplier=pick_score_multiplier,
                active_strategy=active_strategy,
                league_settings=league_settings,
                team_frames=team_frames,
            )
            combined_diag = dict(diagnostics)
            _universe_keys = {
                "focal_found",
                "focal_value",
                "score_field_used",
                "league_teams",
                "eligible_partner_teams",
                "roster_assets_visible",
                "fantasy_relevant_player_assets",
                "future_picks_visible",
                "pick_universe_years",
                "pick_universe_max_round",
                "traded_pick_ownership_moves",
                "pick_source",
                "roster_source",
                "median_partner_player_value",
                "max_partner_player_value",
                "median_pick_value",
                "max_pick_value",
                "search_direction",
                "assets_discarded_missing_value",
            }
            _closest_keys = {
                "closest_one_for_one_delta",
                "closest_player_plus_pick_delta",
                "closest_player_plus_player_delta",
                "closest_multi_asset_delta",
                "closest_one_for_one_stage",
                "closest_player_plus_pick_stage",
                "closest_player_plus_player_stage",
                "closest_multi_asset_stage",
                "closest_rejected_packages",
            }
            for key, value in fallback_diag.items():
                if key in _universe_keys:
                    continue
                if key in _closest_keys:
                    combined_diag[key] = value
                    continue
                if str(key).startswith("stage_ms_"):
                    combined_diag[key] = round(
                        _safe_float(combined_diag.get(key), 0.0) + _safe_float(value, 0.0),
                        3,
                    )
                    continue
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    combined_diag[key] = _safe_int(combined_diag.get(key), 0) + _safe_int(value, 0)
                elif key not in combined_diag:
                    combined_diag[key] = value
            seen_keys = {_package_key(idea.get("send_assets") or [], idea.get("receive_assets") or []) for idea in primary_selected}
            expanded = []
            exploratory = []
            for idea in fallback_ideas:
                key = _package_key(idea.get("send_assets") or [], idea.get("receive_assets") or [])
                if key in seen_keys:
                    combined_diag["deduped"] = _safe_int(combined_diag.get("deduped"), 0) + 1
                    continue
                seen_keys.add(key)
                if str(idea.get("hub_search_source") or "") == "exploratory":
                    exploratory.append(idea)
                else:
                    expanded.append(idea)
            combined = primary_selected + expanded + exploratory
            combined.sort(
                key=lambda idea: (
                    2 if str(idea.get("hub_search_source") or "primary") == "primary" else
                    1 if str(idea.get("hub_search_source") or "") == "expanded" else 0,
                    *_trade_surface_sort_key(idea),
                ),
                reverse=True,
            )
            selected = [
                idea
                for idea in _select_player_search_ideas(combined, max_ideas)
                if any(
                    str(asset.get("player_id") or "") == selected_idea_key
                    for asset in (idea.get("send_assets") or [])
                )
            ]
            combined_diag["final_strict_results"] = sum(
                1 for idea in selected if str(idea.get("hub_search_source") or "primary") == "primary"
            )
            combined_diag["final_expanded_results"] = sum(
                1 for idea in selected if str(idea.get("hub_search_source") or "") == "expanded"
            )
            combined_diag["final_exploratory_results"] = sum(
                1 for idea in selected if str(idea.get("hub_search_source") or "") == "exploratory"
            )
            combined_diag["search_elapsed_ms"] = round(
                (time.perf_counter() - normalize_started) * 1000, 3
            )
            _merge_player_search_audit(combined_diag)
            return _hub_search_result(
                selected,
                fallback_used=bool(expanded or exploratory),
                diagnostics=combined_diag,
                primary_count=len(primary_selected),
                expanded_count=sum(1 for idea in selected if str(idea.get("hub_search_source") or "") == "expanded"),
                exploratory_count=sum(1 for idea in selected if str(idea.get("hub_search_source") or "") == "exploratory"),
            )

    target_roster_id = _find_roster_id_for_player(roster_players_map, player_id)
    if target_roster_id <= 0 or target_roster_id == my_roster_key:
        return _hub_search_result()

    partner_row_df = df_summary[pd.to_numeric(df_summary["roster_id"], errors="coerce").fillna(0).astype(int) == target_roster_id]
    if partner_row_df.empty:
        return _hub_search_result()
    partner_name = str(partner_row_df.iloc[0].get("team_name") or "Partner")
    partner_team_df = team_frames.get(target_roster_id)
    if partner_team_df is None or getattr(partner_team_df, "empty", True):
        partner_ids = roster_players_map.get(target_roster_id, [])
        partner_team_df = df_players[df_players["player_id"].astype(str).isin(partner_ids)]
        _SEARCH_AUDIT["universe_scans"] = int(_SEARCH_AUDIT["universe_scans"]) + 1
    if partner_team_df.empty:
        return _hub_search_result()
    partner_shape = _build_team_shape(
        df_summary,
        target_roster_id,
        partner_team_df,
        score_field,
        roster_pick_assets.get(target_roster_id, []),
        league_draft_capitals,
        league_settings=league_settings,
    )
    partner_mode = str(partner_shape.get("mode") or "")
    partner_profile = partner_row_df.iloc[0].to_dict() if not partner_row_df.empty else {}

    keeper_names = set(untouchable_names)
    for _, row in my_team_df.iterrows():
        pid = str(row["player_id"])
        if role_map.get(pid, "Flex") == "Core":
            keeper_names.add(str(row["name"]))

    my_candidates_df = my_team_df[~my_team_df["name"].isin(keeper_names)].copy()

    my_player_assets = [
        _player_asset(row, role_map.get(str(row["player_id"]), "Flex"), score_field=score_field)
        for _, row in my_candidates_df.iterrows()
        if _row_score(row, score_field) > 0
    ]
    my_player_assets = [asset for asset in my_player_assets if str(asset.get("player_id")) != player_id]
    my_player_assets.sort(
        key=lambda asset: (
            _player_trade_fit(asset, str(asset.get("role") or "Flex"), my_shape, partner_shape),
            asset["score"],
        ),
        reverse=True,
    )
    my_pick_assets = _owned_search_picks(
        [
            _pick_asset(pick, score_multiplier=pick_score_multiplier)
            for pick in roster_pick_assets.get(my_roster_key, [])
        ],
        max_round=4,
        limit=8,
    )
    # Core-role protection is a strict-pass preference. Progressive widening
    # may consider those assets for an elite consolidation package, but never
    # assets the user explicitly marked untouchable.
    expanded_candidates_df = my_team_df[
        ~my_team_df["name"].isin(set(untouchable_names))
    ].copy()
    expanded_player_assets = [
        _player_asset(
            row,
            role_map.get(str(row["player_id"]), "Flex"),
            score_field=score_field,
        )
        for _, row in expanded_candidates_df.iterrows()
        if _row_score(row, score_field) > 0
        and str(row.get("player_id") or "") != player_id
    ]
    expanded_player_assets.sort(
        key=lambda asset: (
            _player_trade_fit(
                asset,
                str(asset.get("role") or "Flex"),
                my_shape,
                partner_shape,
            ),
            asset["score"],
        ),
        reverse=True,
    )
    if not my_player_assets and not my_pick_assets and not expanded_player_assets:
        return _hub_search_result()

    ideas: List[Dict[str, Any]] = []
    seen = set()
    exploratory_pool: List[Dict[str, Any]] = []
    diagnostics = _empty_player_search_funnel()
    diagnostics.update(universe)
    diagnostics.update({
        "candidate_generated": 0,
        "package_constructed": 0,
        "ownership_legal": 0,
        "candidate_duplicate": 0,
        "no_value_match": 0,
        "value_window_pass": 0,
        "no_roster_fit": 0,
        "user_fit_pass": 0,
        "no_partner_fit": 0,
        "partner_fit_pass": 0,
        "no_reasoning_fit": 0,
        "acceptance_pass": 0,
        "no_market_realism": 0,
        "market_realism_pass": 0,
        "candidate_accepted": 0,
        "closest_rejections": [],
        "partner_teams_considered": 1,
    })
    search_started = time.perf_counter()

    def record_rejection(
        send_assets: List[Dict[str, Any]],
        stage: str,
        reason: str,
    ) -> None:
        send_value = _score_assets(send_assets)
        receive_value = int(selected_asset.get("score") or 0)
        row = {
            "assets": [str(asset.get("name") or asset.get("label") or "Asset") for asset in send_assets],
            "send_value": send_value,
            "receive_value": receive_value,
            "difference": send_value - receive_value,
            "ratio": round(send_value / receive_value, 4) if receive_value else None,
            "stage": stage,
            "reason": reason,
        }
        closest = list(diagnostics.get("closest_rejections") or [])
        closest.append(row)
        closest.sort(key=lambda item: (abs(int(item["difference"])), item["stage"], item["assets"]))
        diagnostics["closest_rejections"] = closest[:10]

    def value_candidate(
        send_assets: List[Dict[str, Any]],
        *,
        low: int,
        high: int,
    ) -> bool:
        diagnostics["candidate_generated"] += 1
        diagnostics["package_constructed"] += 1
        diagnostics["raw_packages_constructed"] = _safe_int(diagnostics.get("raw_packages_constructed"), 0) + 1
        diagnostics["packages_containing_focal"] = (
            _safe_int(diagnostics.get("packages_containing_focal"), 0) + 1
        )
        _count_package_structure(
            diagnostics, _package_structure_kind(send_assets, [selected_asset])
        )
        # Candidates are assembled exclusively from the active user's roster
        # and owned-pick pools; explicit untouchables were removed upstream.
        diagnostics["ownership_legal"] += 1
        if not _value_fits(
            _score_assets(send_assets),
            selected_asset["score"],
            low=low,
            high=high,
        ):
            diagnostics["no_value_match"] += 1
            diagnostics["rejected_value_window"] = _safe_int(diagnostics.get("rejected_value_window"), 0) + 1
            record_rejection(send_assets, "value_window", f"outside canonical window {low:+d} to {high:+d}")
            return False
        diagnostics["value_window_pass"] += 1
        diagnostics["candidates_scored"] = _safe_int(diagnostics.get("candidates_scored"), 0) + 1
        return True

    def add_hub_idea(
        send_assets: List[Dict[str, Any]],
        title: str,
        rationale: str,
        priority: int,
        min_reason_score: int = 8,
        min_acceptance_score: int = 56,
        low: int = -1800,
        high: int = 900,
        source: str = "primary",
        allow_soft_partner_fit: bool = False,
    ):
        key = _package_key(send_assets, [selected_asset])
        if key in seen:
            diagnostics["candidate_duplicate"] += 1
            diagnostics["deduped"] = _safe_int(diagnostics.get("deduped"), 0) + 1
            record_rejection(send_assets, "dedupe", "package identity already evaluated")
            return
        fit_bonus = _fit_priority(send_assets, [selected_asset], my_shape, partner_shape)
        fit_context = _trade_fit_context(my_shape, partner_shape, send_assets, [selected_asset], partner_name)
        partner_score = int(fit_context["partner_score"])
        reasoning = _trade_reasoning_context(my_shape, partner_shape, send_assets, [selected_asset], partner_name)
        market_context = evaluate_trade_market_realism(
            send_assets=send_assets,
            receive_assets=[selected_asset],
            my_shape=my_shape,
            partner_shape=partner_shape,
            partner_name=partner_name,
            partner_profile=partner_profile,
            league_settings=league_settings,
        )
        if market_context.get("hard_fail"):
            diagnostics["no_market_realism"] += 1
            _count_market_hard_fail(
                diagnostics,
                list(market_context.get("hard_fail_flags") or []),
            )
            flags = ", ".join(str(flag) for flag in market_context.get("hard_fail_flags") or [])
            record_rejection(send_assets, "market_realism", flags or "canonical market hard fail")
            return

        def stash_exploratory(stage: str, reason: str) -> None:
            exploratory_pool.append(
                {
                    "send_assets": list(send_assets),
                    "title": title,
                    "rationale": rationale,
                    "priority": priority,
                }
            )
            record_rejection(send_assets, stage, reason)

        if source != "exploratory":
            user_floor = 0 if source == "primary" else -8
            if fit_bonus < user_floor:
                diagnostics["no_roster_fit"] += 1
                diagnostics["rejected_user_roster_fit"] = (
                    _safe_int(diagnostics.get("rejected_user_roster_fit"), 0) + 1
                )
                stash_exploratory("user_fit", f"roster-fit score {fit_bonus} is below {user_floor}")
                return
            diagnostics["user_fit_pass"] += 1
            allow_negative_partner = (
                allow_soft_partner_fit
                and partner_score >= -30
                and len(_pick_assets(send_assets)) >= 3
                and any(_safe_int(asset.get("round"), 99) == 1 for asset in _pick_assets(send_assets))
                and normalize_team_strategy(partner_shape.get("strategy") or partner_shape.get("mode"))
                in {"retool", "rebuild", "tank"}
            )
            partner_floor = 1 if source == "primary" else -30
            if partner_score < partner_floor and not allow_negative_partner:
                diagnostics["no_partner_fit"] += 1
                diagnostics["rejected_partner_fit"] = (
                    _safe_int(diagnostics.get("rejected_partner_fit"), 0) + 1
                )
                stash_exploratory("partner_fit", f"partner-fit score {partner_score} is below {partner_floor}")
                return
            if partner_score <= 0:
                diagnostics["soft_partner_fit_widened"] = int(
                    diagnostics.get("soft_partner_fit_widened") or 0
                ) + 1
            diagnostics["partner_fit_pass"] += 1
            if reasoning["score"] < min_reason_score:
                diagnostics["no_reasoning_fit"] += 1
                diagnostics["rejected_acceptance"] = (
                    _safe_int(diagnostics.get("rejected_acceptance"), 0) + 1
                )
                diagnostics["rejected_strategy"] = (
                    _safe_int(diagnostics.get("rejected_strategy"), 0) + 1
                )
                stash_exploratory("acceptance", f"reasoning score {reasoning['score']} is below {min_reason_score}")
                return
            diagnostics["acceptance_pass"] += 1
            if int(market_context.get("score") or 0) < min_acceptance_score:
                diagnostics["no_market_realism"] += 1
                diagnostics["rejected_acceptance"] = (
                    _safe_int(diagnostics.get("rejected_acceptance"), 0) + 1
                )
                stash_exploratory(
                    "market_realism",
                    f"market score {market_context.get('score', 0)} is below {min_acceptance_score}",
                )
                return
            diagnostics["market_realism_pass"] += 1
        final_rationale = " ".join(
            part
            for part in [reasoning.get("summary", ""), rationale, fit_context.get("rationale", ""), market_context.get("summary", "")]
            if part
        ).strip()
        idea = _make_idea(
            partner_name,
            send_assets,
            [selected_asset],
            my_mode,
            partner_mode,
            title,
            final_rationale,
            int(priority) + int(reasoning["score"]) + int(fit_bonus) + int(fit_context["score"]) + int(round((int(market_context.get("score") or 0) - 50) / 4.0)),
            reasoning_tags=reasoning["tags"],
            reasoning_summary=reasoning["summary"],
            my_strategy=str(my_shape.get("strategy") or my_mode),
            partner_strategy=str(partner_shape.get("strategy") or partner_mode),
        )
        idea = _apply_strategy_context_to_idea(idea, reasoning, my_shape)
        idea = _attach_trade_assessment_fields(
            idea,
            fit_context=fit_context,
            market_context=market_context,
        )
        idea["hub_mode"] = "target_player"
        idea["hub_search_source"] = source
        idea["hub_path"] = _player_hub_path_label(selected_asset, send_assets, [selected_asset], active_strategy, "target_player")
        idea["hub_partner_reason"] = _target_partner_reason(selected_asset, partner_shape, send_assets, partner_name)
        idea["hub_target_fit_reason"] = _target_fit_reason(selected_asset, my_shape)
        if source == "exploratory":
            idea = _mark_exploratory_idea(idea)
        ideas.append(idea)
        seen.add(key)
        diagnostics["candidate_accepted"] += 1

    target_pos = str(selected_asset.get("position") or "").upper()

    for player in my_player_assets[:12]:
        if player["score"] <= 0:
            continue
        if not value_candidate([player], low=-1600, high=800):
            continue
        rationale = f"One-for-one path if {partner_name} prefers a cleaner positional swap or different roster fit."
        add_hub_idea([player], "Cheapest acquisition path", rationale, 82, min_reason_score=8, min_acceptance_score=56)

    for player in my_player_assets[:10]:
        for pick in my_pick_assets[:5]:
            send_assets = [player, pick]
            if not value_candidate(send_assets, low=-1700, high=700):
                continue
            rationale = f"Uses one movable player plus owned draft capital to buy into {target_pos} talent without forcing a full two-for-one."
            add_hub_idea(send_assets, "Player + pick acquisition", rationale, 78, min_reason_score=9, min_acceptance_score=56)

    for i, first in enumerate(my_player_assets[:10]):
                for second in my_player_assets[i + 1 : 12]:
                    send_assets = [first, second]
                    if not value_candidate(send_assets, low=-1800, high=900):
                        continue
                    rationale = f"Turns depth or surplus pieces into one stronger {target_pos} asset when a direct one-for-one is unlikely."
                    add_hub_idea(send_assets, "Surplus-for-need package", rationale, 86, min_reason_score=10, min_acceptance_score=60)

    if my_pick_assets:
        early_picks = [pick for pick in my_pick_assets if int(pick.get("round") or 99) <= 2][:4]
        for i, first in enumerate(early_picks):
            send_assets = [first]
            if value_candidate(send_assets, low=-2200, high=400):
                rationale = f"Pure-pick path if {partner_name} is more interested in future capital than lineup help."
                add_hub_idea(send_assets, "Pick-only swing", rationale, 68, min_reason_score=8, min_acceptance_score=54)
            for second in early_picks[i + 1 : 4]:
                send_assets = [first, second]
                if not value_candidate(send_assets, low=-2200, high=900):
                    continue
                rationale = f"Pick-heavy path if {partner_name} is open to future assets and your roster should keep the current starters intact."
                add_hub_idea(send_assets, "Pick-heavy package", rationale, 72, min_reason_score=9, min_acceptance_score=54)

    ideas.sort(key=_trade_surface_sort_key, reverse=True)
    primary_selected = _select_hub_ideas(ideas, max_ideas)
    primary_count = len(primary_selected)
    diagnostics["strict_candidate_count"] = int(diagnostics["candidate_generated"])
    if primary_count < min(max_ideas, 2):
        # Progressive widening runs only after the existing acquisition search
        # is exhausted. Core-role exclusion is a soft discovery preference, not
        # an ownership/value/Trust guardrail. Elite consolidation must be able
        # to consider those assets unless the user explicitly marked them
        # untouchable.
        diagnostics["expanded_soft_pool_added"] = max(
            0,
            len(expanded_player_assets) - len(my_player_assets),
        )
        for i, first in enumerate(expanded_player_assets[:10]):
            for j, second in enumerate(expanded_player_assets[i + 1 : 11], start=i + 1):
                for third in expanded_player_assets[j + 1 : 11]:
                    send_assets = [first, second, third]
                    if not value_candidate(send_assets, low=-2400, high=1200):
                        continue
                    add_hub_idea(
                        send_assets,
                        "Expanded multi-asset acquisition",
                        f"A wider depth package can reach {target_pos} value when smaller offers do not clear.",
                        74,
                        min_reason_score=9,
                        min_acceptance_score=58,
                        low=-2400,
                        high=1200,
                        source="expanded",
                    )
        for player in expanded_player_assets[:10]:
            for i, first_pick in enumerate(my_pick_assets[:4]):
                for second_pick in my_pick_assets[i + 1 : 4]:
                    send_assets = [player, first_pick, second_pick]
                    if not value_candidate(send_assets, low=-2400, high=1200):
                        continue
                    add_hub_idea(
                        send_assets,
                        "Expanded player-and-picks acquisition",
                        "A broader player-and-picks offer is considered only after smaller packages fail.",
                        72,
                        min_reason_score=9,
                        min_acceptance_score=58,
                        low=-2400,
                        high=1200,
                        source="expanded",
                    )
        for i, first in enumerate(expanded_player_assets[:8]):
            for second in expanded_player_assets[i + 1 : 9]:
                for pick in my_pick_assets[:4]:
                    send_assets = [first, second, pick]
                    if not value_candidate(send_assets, low=-2400, high=1200):
                        continue
                    add_hub_idea(
                        send_assets,
                        "Expanded consolidation acquisition",
                        "A two-player-and-pick package is considered only after the strict market is exhausted.",
                        73,
                        min_reason_score=9,
                        min_acceptance_score=58,
                        low=-2400,
                        high=1200,
                        source="expanded",
                    )
        # A premium target can be economically reachable with draft capital
        # even when no single outgoing player is a believable centerpiece.
        # Keep the search bounded to the five strongest owned picks and only
        # evaluate three- or four-pick packages after every smaller pass fails.
        bounded_picks = sorted(
            my_pick_assets,
            key=lambda asset: int(asset.get("score") or 0),
            reverse=True,
        )[:5]
        for package_size in (3, 4):
            for pick_package in combinations(bounded_picks, package_size):
                send_assets = list(pick_package)
                if not value_candidate(send_assets, low=-2400, high=1200):
                    continue
                add_hub_idea(
                    send_assets,
                    "Expanded draft-capital acquisition",
                    "A bounded multi-pick offer is considered only when smaller player and pick packages fail.",
                    70,
                    min_reason_score=9,
                    min_acceptance_score=58,
                    low=-2400,
                    high=1200,
                    source="expanded",
                    allow_soft_partner_fit=True,
                )
        ideas.sort(
            key=lambda idea: (
                2 if str(idea.get("hub_search_source") or "primary") == "primary" else
                1 if str(idea.get("hub_search_source") or "") == "expanded" else 0,
                *_trade_surface_sort_key(idea),
            ),
            reverse=True,
        )
        primary_selected = _select_player_search_ideas(ideas, max_ideas)
    if not ideas and exploratory_pool:
        for item in exploratory_pool[:12]:
            add_hub_idea(
                item["send_assets"],
                item["title"],
                item["rationale"],
                item["priority"],
                min_reason_score=0,
                min_acceptance_score=0,
                source="exploratory",
            )
        ideas.sort(
            key=lambda idea: (
                0 if str(idea.get("hub_search_source") or "") == "exploratory" else 1,
                *_trade_surface_sort_key(idea),
            ),
            reverse=True,
        )
        primary_selected = _select_player_search_ideas(ideas, max_ideas)
    diagnostics["ranking_count"] = len(ideas)
    diagnostics["final_visibility"] = len(primary_selected)
    diagnostics["expanded_candidate_count"] = max(
        0,
        int(diagnostics["candidate_generated"]) - int(diagnostics.get("strict_candidate_count") or 0),
    )
    diagnostics["search_elapsed_ms"] = round((time.perf_counter() - search_started) * 1000, 3)
    diagnostics["final_strict_results"] = sum(
        1 for idea in primary_selected if str(idea.get("hub_search_source") or "primary") == "primary"
    )
    diagnostics["final_expanded_results"] = sum(
        1 for idea in primary_selected if str(idea.get("hub_search_source") or "") == "expanded"
    )
    diagnostics["final_exploratory_results"] = sum(
        1 for idea in primary_selected if str(idea.get("hub_search_source") or "") == "exploratory"
    )
    expanded_count = diagnostics["final_expanded_results"]
    exploratory_count = diagnostics["final_exploratory_results"]
    _merge_player_search_audit(diagnostics)
    return _hub_search_result(
        primary_selected,
        fallback_used=expanded_count > 0 or exploratory_count > 0,
        diagnostics=diagnostics,
        primary_count=primary_count,
        expanded_count=expanded_count,
        exploratory_count=exploratory_count,
    )
