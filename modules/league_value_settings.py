"""League-specific player valuation: settings detection and the valuation lens.

Extracted from `app.py` so the mobile API can share the exact same valuation
math as the web app instead of re-deriving it — see the repository's
existing "share one engine" precedent in `services/mobile_api_service.py`.
This is a pure code move: no weights, formulas, or guardrails changed.
`app.py` re-exports every name here unchanged, and its existing valuation
tests (`tests/test_player_valuation.py`, `tests/test_valuation_archetypes.py`,
etc., which `import app` and call `app.apply_valuation_lens` and friends)
continue to exercise this exact code through that re-export.

Only `resolve_league_value_settings` changed shape: the original read
`st.session_state` directly for manual overrides, which doesn't exist
outside Streamlit. It now takes an explicit `overrides` mapping instead
(any `.get(key, default)`-shaped object — `st.session_state` itself, a
plain dict, or nothing at all). `app.py`'s call site passes
`st.session_state` as that mapping, so its behavior is unchanged.

Does not invent a new ranking formula, retune weights, or add providers —
same rule as `modules/canonical_player_ranking.py`.
"""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from modules.player_tiers import assign_player_tiers
from modules.rankings import current_availability_multiplier


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_positive_int(value, default: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return parsed if parsed > 0 else default


def _safe_nonnegative_int(value, default: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return parsed if parsed >= 0 else default


def format_score_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    score_cols = [
        "value",
        "market_score",
        "age_penalty",
        "scarcity_score",
        "role_score",
        "score",
        "base_score",
        "rebuild_score",
        "dynasty_score",
        "value_score",
        "league_dynasty_score",
        "league_value_score",
        "league_rebuild_score",
        "strategy_score",
    ]
    for col in score_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).round().astype(int)
    return df


VALUATION_LENS_TO_SCORE_FIELD = {
    "Dynasty": "dynasty_score",
    "Rebuild": "rebuild_score",
    "Non-Dynasty": "value_score",
}

DEFAULT_LEAGUE_VALUE_SETTINGS = {
    "league_format": "Dynasty",
    "scoring_format": "PPR",
    "qb_format": "1QB",
    "te_premium": False,
    "qb_count": 1,
    "rb_count": 2,
    "wr_count": 3,
    "te_count": 1,
    "starter_count": 9,
    "flex_count": 2,
    "regular_flex_count": 1,
    "wrrb_flex_count": 1,
    "superflex_count": 0,
    "k_count": 0,
    "bench_count": 0,
    "taxi_count": 0,
    "ir_count": 0,
    "other_starter_count": 0,
    "league_size": 12,
}


def valuation_score_field(valuation_lens: str) -> str:
    return VALUATION_LENS_TO_SCORE_FIELD.get(valuation_lens, "dynasty_score")


def detect_league_value_settings_from_payload(league: dict | None) -> dict:
    """Normalize a Sleeper-shaped league payload into valuation settings.

    Pure helper for automatic league-context detection — no UI overrides, no
    network. Missing fields keep DEFAULT_LEAGUE_VALUE_SETTINGS with source
    ``default`` (never silently pretend imported Standard is PPR).
    """

    settings = dict(DEFAULT_LEAGUE_VALUE_SETTINGS)
    settings["_sources"] = {key: "default" for key in DEFAULT_LEAGUE_VALUE_SETTINGS}
    settings["_detected_scoring"] = {}
    settings["_keeper_mode"] = False
    if not isinstance(league, dict) or not league:
        return settings

    scoring = league.get("scoring_settings") if isinstance(league.get("scoring_settings"), dict) else {}
    league_settings = league.get("settings") if isinstance(league.get("settings"), dict) else {}
    roster_positions = [
        str(pos or "").upper()
        for pos in league.get("roster_positions", []) or []
    ]

    league_type = league_settings.get("type")
    if league_type is not None:
        type_int = _safe_nonnegative_int(league_type, 0)
        # Sleeper: 0=redraft, 1=keeper, 2=dynasty. Keepers share dynasty horizon
        # math today; expose explicit keeper flag for downstream honesty.
        if type_int == 0:
            settings["league_format"] = "Redraft"
            settings["_keeper_mode"] = False
        elif type_int == 1:
            settings["league_format"] = "Dynasty"
            settings["_keeper_mode"] = True
        else:
            settings["league_format"] = "Dynasty"
            settings["_keeper_mode"] = False
        settings["_sources"]["league_format"] = "Sleeper"

    # Only rewrite scoring_format when reception scoring is actually present.
    # Missing ``rec`` must remain the default with source=default — never treat
    # an empty scoring blob as proof of PPR.
    if "rec" in scoring:
        rec_score = _safe_float(scoring.get("rec"), 0.0)
        if rec_score >= 0.95:
            settings["scoring_format"] = "PPR"
        elif rec_score >= 0.45:
            settings["scoring_format"] = "Half-PPR"
        else:
            settings["scoring_format"] = "Standard"
        settings["_sources"]["scoring_format"] = "Sleeper"
        settings["_detected_scoring"]["rec"] = rec_score

    te_bonus_keys = [
        "bonus_rec_te",
        "rec_bonus_te",
        "te_rec_bonus",
        "bonus_fd_te",
        "te_fd_bonus",
    ]
    te_bonus_present = any(key in scoring for key in te_bonus_keys)
    settings["te_premium"] = any(
        _safe_float(scoring.get(key), 0.0) > 0
        for key in te_bonus_keys
    )
    if te_bonus_present:
        settings["_sources"]["te_premium"] = "Sleeper"
        settings["_detected_scoring"]["te_premium_keys"] = {
            key: _safe_float(scoring.get(key), 0.0)
            for key in te_bonus_keys
            if key in scoring
        }

    # Detected-but-unused scoring facts (do not fake support).
    for key in ("pass_td", "pass_int", "fum_lost", "bonus_rec_yd_100", "bonus_rush_yd_100", "fd_rec", "fd_rush"):
        if key in scoring:
            settings["_detected_scoring"][key] = _safe_float(scoring.get(key), 0.0)

    qb_count = roster_positions.count("QB")
    rb_count = roster_positions.count("RB")
    wr_count = roster_positions.count("WR")
    te_count = roster_positions.count("TE")
    k_count = roster_positions.count("K")
    superflex_count = sum(1 for pos in roster_positions if pos in {"SUPER_FLEX", "OP"})
    if qb_count >= 2:
        settings["qb_format"] = "2QB"
    elif superflex_count:
        settings["qb_format"] = "Superflex"
    else:
        settings["qb_format"] = "1QB"
    if roster_positions:
        settings["_sources"]["qb_format"] = "Sleeper"
        settings["qb_count"] = max(1, qb_count)
        settings["rb_count"] = rb_count if rb_count > 0 else settings["rb_count"]
        settings["wr_count"] = wr_count if wr_count > 0 else settings["wr_count"]
        settings["te_count"] = te_count if te_count > 0 else settings["te_count"]
        settings["k_count"] = k_count
        settings["superflex_count"] = superflex_count
        for key in ["qb_count", "rb_count", "wr_count", "te_count", "k_count", "superflex_count"]:
            settings["_sources"][key] = "Sleeper"

    bench_slots = {"BN", "BE", "BENCH", "IR", "TAXI"}
    bench_positions = {"BN", "BE", "BENCH"}
    starter_positions = [
        pos for pos in roster_positions if pos and pos not in bench_slots
    ]
    if starter_positions:
        settings["starter_count"] = len(starter_positions)
        settings["_sources"]["starter_count"] = "Sleeper"
    regular_flex_positions = [
        pos
        for pos in starter_positions
        if pos not in {"SUPER_FLEX", "OP"}
        and ("FLEX" in pos or pos in {"W/R/T", "RB/WR/TE", "WR/RB/TE"})
    ]
    wrrb_flex_positions = [
        pos
        for pos in starter_positions
        if pos in {"W/R", "WR/RB", "RB/WR", "WRRB_FLEX"}
    ]
    if starter_positions:
        settings["regular_flex_count"] = len(regular_flex_positions)
        settings["wrrb_flex_count"] = len(wrrb_flex_positions)
        settings["flex_count"] = len(regular_flex_positions) + len(wrrb_flex_positions)
        counted_core = (
            int(settings["qb_count"])
            + int(settings["rb_count"])
            + int(settings["wr_count"])
            + int(settings["te_count"])
            + int(settings["k_count"])
            + int(settings["flex_count"])
            + int(settings["superflex_count"])
        )
        settings["other_starter_count"] = max(0, len(starter_positions) - counted_core)
        for key in ["flex_count", "regular_flex_count", "wrrb_flex_count", "other_starter_count"]:
            settings["_sources"][key] = "Sleeper"

    bench_count = sum(1 for pos in roster_positions if pos in bench_positions)
    taxi_count = sum(1 for pos in roster_positions if pos == "TAXI")
    ir_count = _safe_nonnegative_int(league_settings.get("reserve_slots"), 0)
    if not ir_count:
        ir_count = sum(1 for pos in roster_positions if pos == "IR")
    if roster_positions or ir_count:
        settings["bench_count"] = bench_count
        settings["taxi_count"] = taxi_count
        settings["ir_count"] = ir_count
        settings["_sources"]["bench_count"] = "Sleeper"
        settings["_sources"]["taxi_count"] = "Sleeper"
        settings["_sources"]["ir_count"] = "Sleeper"

    settings["league_size"] = _safe_positive_int(
        league.get("total_rosters") or league_settings.get("num_teams"),
        settings["league_size"],
    )
    if league.get("total_rosters") or league_settings.get("num_teams"):
        settings["_sources"]["league_size"] = "Sleeper"
    return settings


def detect_league_value_settings(league_id: str | None, *, league: dict | None = None) -> dict:
    """Detect settings for a league. Pass ``league`` (a Sleeper league payload)
    to avoid an extra network call when the caller already has it."""

    if not league_id:
        settings = dict(DEFAULT_LEAGUE_VALUE_SETTINGS)
        settings["_sources"] = {key: "default" for key in DEFAULT_LEAGUE_VALUE_SETTINGS}
        settings["_detected_scoring"] = {}
        settings["_keeper_mode"] = False
        return settings
    if league is None:
        from modules.sleeper import get_league

        league = get_league(league_id)
    return detect_league_value_settings_from_payload(league or {})


def resolve_league_value_settings(
    auto_settings: dict,
    overrides: Mapping[str, Any] | None = None,
) -> dict:
    """Layer manual overrides on top of auto-detected settings.

    ``overrides`` is any ``.get(key, default)``-shaped mapping keyed the same
    way the web app's sidebar controls are (``league_format_override``,
    ``league_scoring_override``, etc.) — ``st.session_state`` itself, in the
    web app's case. Defaults to no overrides (every key is treated as "Auto").
    """

    overrides = overrides if overrides is not None else {}
    settings = dict(DEFAULT_LEAGUE_VALUE_SETTINGS)
    settings.update(auto_settings or {})
    sources = dict((auto_settings or {}).get("_sources", {}))
    settings["_sources"] = sources

    format_override = overrides.get("league_format_override", "Auto")
    if format_override != "Auto":
        settings["league_format"] = format_override
        sources["league_format"] = "manual"

    scoring_override = overrides.get("league_scoring_override", "Auto")
    if scoring_override != "Auto":
        settings["scoring_format"] = scoring_override
        sources["scoring_format"] = "manual"

    qb_override = overrides.get("league_qb_override", "Auto")
    if qb_override != "Auto":
        settings["qb_format"] = qb_override
        settings["qb_count"] = 2 if qb_override == "2QB" else 1
        settings["superflex_count"] = 1 if qb_override == "Superflex" else 0
        sources["qb_format"] = "manual"
        sources["qb_count"] = "manual"
        sources["superflex_count"] = "manual"

    te_override = overrides.get("league_te_premium_override", "Auto")
    if te_override != "Auto":
        settings["te_premium"] = te_override == "Yes"
        sources["te_premium"] = "manual"

    for key, override_key in [
        ("rb_count", "league_rb_count_override"),
        ("wr_count", "league_wr_count_override"),
        ("te_count", "league_te_count_override"),
    ]:
        override = overrides.get(override_key, "Auto")
        if override != "Auto":
            settings[key] = _safe_nonnegative_int(override, settings[key])
            sources[key] = "manual"

    starter_override = overrides.get("league_starters_override", "Auto")
    if starter_override != "Auto":
        settings["starter_count"] = _safe_positive_int(starter_override, settings["starter_count"])
        sources["starter_count"] = "manual"

    flex_override = overrides.get("league_flex_override", "Auto")
    if flex_override != "Auto":
        settings["flex_count"] = _safe_nonnegative_int(flex_override, settings["flex_count"])
        settings["regular_flex_count"] = settings["flex_count"]
        settings["wrrb_flex_count"] = 0
        sources["flex_count"] = "manual"
        sources["regular_flex_count"] = "manual"
        sources["wrrb_flex_count"] = "manual"

    bench_override = overrides.get("league_bench_override", "Auto")
    if bench_override != "Auto":
        settings["bench_count"] = _safe_nonnegative_int(bench_override, settings["bench_count"])
        sources["bench_count"] = "manual"

    taxi_override = overrides.get("league_taxi_override", "Auto")
    if taxi_override != "Auto":
        settings["taxi_count"] = _safe_nonnegative_int(taxi_override, settings["taxi_count"])
        sources["taxi_count"] = "manual"

    ir_override = overrides.get("league_ir_override", "Auto")
    if ir_override != "Auto":
        settings["ir_count"] = _safe_nonnegative_int(ir_override, settings["ir_count"])
        sources["ir_count"] = "manual"

    league_size_override = overrides.get("league_size_override", "Auto")
    if league_size_override != "Auto":
        settings["league_size"] = _safe_positive_int(league_size_override, settings["league_size"])
        sources["league_size"] = "manual"

    if starter_override == "Auto":
        core_count = (
            int(settings.get("qb_count") or 0)
            + int(settings.get("rb_count") or 0)
            + int(settings.get("wr_count") or 0)
            + int(settings.get("te_count") or 0)
            + int(settings.get("k_count") or 0)
            + int(settings.get("flex_count") or 0)
            + int(settings.get("superflex_count") or 0)
            + int(settings.get("other_starter_count") or 0)
        )
        if core_count > 0:
            settings["starter_count"] = core_count

    return settings


def league_value_settings_key(settings: dict) -> str:
    return "|".join(
        [
            str(settings.get("league_format", "Dynasty")),
            str(settings.get("scoring_format", "PPR")),
            str(settings.get("qb_format", "1QB")),
            str(bool(settings.get("te_premium"))),
            str(bool(settings.get("_keeper_mode"))),
            str(int(settings.get("qb_count") or 0)),
            str(int(settings.get("rb_count") or 0)),
            str(int(settings.get("wr_count") or 0)),
            str(int(settings.get("te_count") or 0)),
            str(int(settings.get("starter_count") or 0)),
            str(int(settings.get("flex_count") or 0)),
            str(int(settings.get("regular_flex_count") or 0)),
            str(int(settings.get("wrrb_flex_count") or 0)),
            str(int(settings.get("superflex_count") or 0)),
            str(int(settings.get("k_count") or 0)),
            str(int(settings.get("bench_count") or 0)),
            str(int(settings.get("taxi_count") or 0)),
            str(int(settings.get("ir_count") or 0)),
            str(int(settings.get("other_starter_count") or 0)),
            str(int(settings.get("league_size") or 0)),
        ]
    )


def _receiving_intensity_series(df: pd.DataFrame) -> pd.Series:
    """0..1 receiving-role intensity from stats when present, else opportunity.

    Uses targets/receptions and, when rushing volume exists, down-weights pure
    early-down runners. Missing usage falls back to opportunity_score — never
    invents precision.
    """

    index = df.index
    targets = pd.to_numeric(df.get("targets", pd.Series(float("nan"), index=index)), errors="coerce")
    receptions = pd.to_numeric(
        df.get("receptions", pd.Series(float("nan"), index=index)), errors="coerce"
    )
    rushes = pd.to_numeric(
        df.get("rush_attempts", pd.Series(float("nan"), index=index)), errors="coerce"
    )
    opportunity = pd.to_numeric(
        df.get("opportunity_score", pd.Series(0.0, index=index)), errors="coerce"
    ).fillna(0.0)
    has_usage = targets.fillna(0).gt(0) | receptions.fillna(0).gt(0)
    usage_intensity = ((targets.fillna(0) * 0.7) + (receptions.fillna(0) * 0.3)).clip(0, 120) / 120.0
    # When rush volume dominates targets, pull intensity down (early-down RB).
    rush_vals = rushes.fillna(0)
    tgt_vals = targets.fillna(0)
    has_rush_context = has_usage & rush_vals.gt(0)
    catch_share = (tgt_vals / (tgt_vals + rush_vals * 0.35)).clip(0.15, 1.0)
    usage_intensity = usage_intensity.where(~has_rush_context, usage_intensity * catch_share)
    fallback = (opportunity / 9200.0).clip(0.20, 1.0)
    return usage_intensity.where(has_usage, fallback).clip(0.0, 1.0)


def _passing_intensity_series(df: pd.DataFrame) -> pd.Series:
    """0..1 QB passing involvement for optional pass-TD scoring differentials."""

    index = df.index
    pass_tds = pd.to_numeric(
        df.get("passing_tds", pd.Series(float("nan"), index=index)), errors="coerce"
    )
    pass_yards = pd.to_numeric(
        df.get("passing_yards", pd.Series(float("nan"), index=index)), errors="coerce"
    )
    opportunity = pd.to_numeric(
        df.get("opportunity_score", pd.Series(0.0, index=index)), errors="coerce"
    ).fillna(0.0)
    has_usage = pass_tds.fillna(0).gt(0) | pass_yards.fillna(0).gt(0)
    usage = ((pass_tds.fillna(0) / 30.0) * 0.55 + (pass_yards.fillna(0) / 4000.0) * 0.45).clip(0, 1)
    fallback = (opportunity / 9200.0).clip(0.25, 1.0)
    return usage.where(has_usage, fallback).clip(0.0, 1.0)


def league_settings_adjustment_components(
    df: pd.DataFrame, league_settings: dict | None
) -> dict[str, pd.Series]:
    """Decompose league-context multipliers into independently testable factors.

    Product of components (clipped) equals the combined settings multiplier.
    Identity factor is 1.0 when a concept does not apply to a row.
    """

    settings = dict(DEFAULT_LEAGUE_VALUE_SETTINGS)
    settings.update(league_settings or {})
    index = df.index
    ones = pd.Series(1.0, index=index, dtype="float64")
    positions = (
        df["position"].fillna("").astype(str).str.upper()
        if "position" in df.columns
        else pd.Series("", index=index, dtype="object")
    )
    ages = pd.to_numeric(df.get("age", pd.Series(float("nan"), index=index)), errors="coerce")
    receiving = _receiving_intensity_series(df)
    passing = _passing_intensity_series(df)

    scoring = ones.copy()
    scoring_format = str(settings.get("scoring_format") or "PPR")
    if scoring_format == "Half-PPR":
        wr_te_factor = 1.0 - (0.015 * receiving)
        rb_factor = 1.0 + (0.04 * (1.0 - receiving))
        scoring = scoring.mask(positions == "RB", rb_factor)
        scoring = scoring.mask(positions == "WR", wr_te_factor)
        scoring = scoring.mask(positions == "TE", wr_te_factor)
    elif scoring_format == "Standard":
        wr_te_factor = 1.0 - (0.05 * receiving.clip(lower=0.35))
        rb_factor = 1.0 + (0.10 * (1.0 - receiving))
        scoring = scoring.mask(positions == "RB", rb_factor)
        scoring = scoring.mask(positions == "WR", wr_te_factor)
        scoring = scoring.mask(positions == "TE", wr_te_factor)

    qb_scarcity = ones.copy()
    qb_format = str(settings.get("qb_format") or "1QB")
    if qb_format == "Superflex":
        qb_scarcity = qb_scarcity.mask(positions == "QB", 1.35)
    elif qb_format == "2QB":
        qb_scarcity = qb_scarcity.mask(positions == "QB", 1.55)

    te_premium = ones.copy()
    if settings.get("te_premium"):
        te_premium_factor = 1.0 + (0.18 * receiving.clip(lower=0.35))
        te_premium = te_premium.mask(positions == "TE", te_premium_factor)

    starter_demand = ones.copy()
    rb_delta = int(settings.get("rb_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["rb_count"]) - DEFAULT_LEAGUE_VALUE_SETTINGS["rb_count"]
    wr_delta = int(settings.get("wr_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["wr_count"]) - DEFAULT_LEAGUE_VALUE_SETTINGS["wr_count"]
    te_delta = int(settings.get("te_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["te_count"]) - DEFAULT_LEAGUE_VALUE_SETTINGS["te_count"]
    starter_demand = starter_demand.mask(positions == "RB", 1 + max(-2, min(3, rb_delta)) * 0.035)
    starter_demand = starter_demand.mask(positions == "WR", 1 + max(-3, min(3, wr_delta)) * 0.030)
    starter_demand = starter_demand.mask(positions == "TE", 1 + max(-1, min(2, te_delta)) * 0.050)

    starter_count = int(settings.get("starter_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["starter_count"])
    flex_count = int(settings.get("flex_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["flex_count"])
    league_size = int(settings.get("league_size") or DEFAULT_LEAGUE_VALUE_SETTINGS["league_size"])
    starter_pressure = max(-0.18, min(0.35, ((starter_count * league_size) - 108) / 108))
    lineup_boost = 1 + starter_pressure * 0.18
    team_pressure = ones.mask(positions.isin(["QB", "RB", "WR", "TE"]), lineup_boost)

    flex_delta = max(-2, min(4, flex_count - DEFAULT_LEAGUE_VALUE_SETTINGS["flex_count"]))
    flex_adj = ones.mask(positions.isin(["RB", "WR", "TE"]), 1 + flex_delta * 0.018)

    deep_1qb = ones.copy()
    if league_size > 12 and qb_format == "1QB":
        deep_1qb = deep_1qb.mask(positions == "QB", 1 + min(league_size - 12, 8) * 0.012)

    roster_depth = ones.copy()
    reserve_depth = (
        int(settings.get("bench_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["bench_count"])
        + int(settings.get("taxi_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["taxi_count"])
        + int(settings.get("ir_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["ir_count"])
    )
    if reserve_depth > 0:
        reserve_delta = max(-6, min(12, reserve_depth - 8))
        youth_boost = 1 + (reserve_delta * 0.010)
        taxi_delta = max(0, min(6, int(settings.get("taxi_count") or 0)))
        taxi_boost = 1 + (taxi_delta * 0.020)
        young_skill = positions.isin(["QB", "RB", "WR", "TE"]) & ages.le(25)
        stash_core = positions.isin(["QB", "RB", "WR", "TE"]) & ages.le(23)
        roster_depth = roster_depth.mask(young_skill, youth_boost)
        if taxi_delta > 0:
            roster_depth = roster_depth.mask(stash_core, roster_depth * taxi_boost)

    pass_td = ones.copy()
    detected = (settings.get("_detected_scoring") or {}) if isinstance(settings.get("_detected_scoring"), dict) else {}
    pass_td_points = _safe_float(detected.get("pass_td"), 0.0)
    # Only model the common 6-pt vs ~4-pt gap; ignore exotic values.
    if pass_td_points >= 5.5:
        pass_td = pass_td.mask(positions == "QB", 1.0 + (0.045 * passing.clip(lower=0.30)))
    elif 0 < pass_td_points < 4.5:
        pass_td = pass_td.mask(positions == "QB", 1.0 - (0.025 * passing.clip(lower=0.30)))

    horizon = ones.copy()
    # Keeper sits between dynasty (1.0) and redraft current-blend elsewhere.
    if settings.get("_keeper_mode") and settings.get("league_format") != "Redraft":
        # Mild youth preference vs pure dynasty; not a second age curve.
        horizon = horizon.mask(ages.le(24) & positions.isin(["QB", "RB", "WR", "TE"]), 1.03)
        horizon = horizon.mask(ages.ge(30) & positions.isin(["RB", "WR", "TE"]), 0.97)

    components = {
        "league_adj_scoring": scoring.astype(float),
        "league_adj_qb_scarcity": qb_scarcity.astype(float),
        "league_adj_te_premium": te_premium.astype(float),
        "league_adj_starter_demand": starter_demand.astype(float),
        "league_adj_team_pressure": team_pressure.astype(float),
        "league_adj_flex": flex_adj.astype(float),
        "league_adj_deep_1qb": deep_1qb.astype(float),
        "league_adj_roster_depth": roster_depth.astype(float),
        "league_adj_pass_td": pass_td.astype(float),
        "league_adj_horizon": horizon.astype(float),
    }
    combined = ones.copy()
    for series in components.values():
        combined = combined * series
    components["league_settings_multiplier"] = combined.clip(lower=0.35, upper=2.2)
    return components


def _league_settings_multiplier(df: pd.DataFrame, league_settings: dict | None) -> pd.Series:
    return league_settings_adjustment_components(df, league_settings)["league_settings_multiplier"]


def apply_valuation_lens(
    df: pd.DataFrame,
    valuation_lens: str,
    league_settings: dict | None = None,
) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()
    dynasty_scores = (
        pd.to_numeric(df["dynasty_score"], errors="coerce").fillna(0)
        if "dynasty_score" in df.columns
        else pd.Series(0, index=df.index, dtype="float64")
    )
    # Canonical/base football value from rankings — never overwritten by league math.
    if "score" in df.columns:
        base_scores = pd.to_numeric(df["score"], errors="coerce").fillna(dynasty_scores)
    else:
        base_scores = dynasty_scores.copy()
    df["base_score"] = base_scores.clip(lower=0).round().astype(int)
    df["score"] = df["base_score"]

    value_scores = (
        pd.to_numeric(df["value_score"], errors="coerce").fillna(0)
        if "value_score" in df.columns
        else pd.Series(0, index=df.index, dtype="float64")
    )
    ages = (
        pd.to_numeric(df["age"], errors="coerce")
        if "age" in df.columns
        else pd.Series(float("nan"), index=df.index, dtype="float64")
    )
    positions = (
        df["position"].fillna("").astype(str).str.upper()
        if "position" in df.columns
        else pd.Series("", index=df.index, dtype="object")
    )
    years_exp = (
        pd.to_numeric(df["years_exp"], errors="coerce")
        if "years_exp" in df.columns
        else pd.Series(float("nan"), index=df.index, dtype="float64")
    )
    market_scores = (
        pd.to_numeric(df["market_score"], errors="coerce").fillna(0)
        if "market_score" in df.columns
        else value_scores
    )
    role_scores = (
        pd.to_numeric(df["role_score"], errors="coerce").fillna(0)
        if "role_score" in df.columns
        else value_scores
    )
    opportunity_scores = (
        pd.to_numeric(df["opportunity_score"], errors="coerce").fillna(0)
        if "opportunity_score" in df.columns
        else role_scores
    )
    scarcity_scores = (
        pd.to_numeric(df["scarcity_score"], errors="coerce").fillna(0)
        if "scarcity_score" in df.columns
        else pd.Series(0, index=df.index, dtype="float64")
    )
    risk_multiplier = (
        pd.to_numeric(df["risk_multiplier"], errors="coerce").fillna(1.0)
        if "risk_multiplier" in df.columns
        else pd.Series(1.0, index=df.index, dtype="float64")
    )
    current_risk_multiplier = df.apply(
        lambda row: current_availability_multiplier(
            row.get("status"),
            row.get("team"),
            row.get("search_rank"),
            row.get("injury_status"),
        ),
        axis=1,
    )

    # Current-season lens from base components (not from already league-adjusted scores).
    current_scores = (
        market_scores * 0.64
        + role_scores * 0.11
        + opportunity_scores * 0.10
        + scarcity_scores * 0.10
        + base_scores * 0.05
    ) * pd.to_numeric(current_risk_multiplier, errors="coerce").fillna(risk_multiplier)
    value_pre_league = current_scores.clip(lower=0)

    league_format = str((league_settings or {}).get("league_format") or "Dynasty")
    keeper_mode = bool((league_settings or {}).get("_keeper_mode"))
    # Horizon blend uses base dynasty vs current — redraft < keeper < dynasty.
    if league_format == "Redraft":
        dynasty_pre_league = (base_scores * 0.40) + (value_pre_league * 0.60)
    elif keeper_mode:
        dynasty_pre_league = (base_scores * 0.70) + (value_pre_league * 0.30)
    else:
        dynasty_pre_league = base_scores.astype(float)

    rebuild_base = (dynasty_pre_league * 0.82) + (value_pre_league * 0.18)
    rebuild_multiplier = pd.Series(1.0, index=df.index, dtype="float64")
    rebuild_multiplier = rebuild_multiplier.mask(ages.le(22), 1.18)
    rebuild_multiplier = rebuild_multiplier.mask(ages.gt(22) & ages.le(24), 1.10)
    rebuild_multiplier = rebuild_multiplier.mask(ages.gt(24) & ages.le(26), 1.04)
    rebuild_multiplier = rebuild_multiplier.mask((positions == "RB") & ages.ge(28), 0.72)
    rebuild_multiplier = rebuild_multiplier.mask((positions == "WR") & ages.ge(30), 0.82)
    rebuild_multiplier = rebuild_multiplier.mask((positions == "TE") & ages.ge(31), 0.86)
    rebuild_multiplier = rebuild_multiplier.mask((positions == "QB") & ages.ge(34), 0.90)

    rookie_bonus = pd.Series(0.0, index=df.index, dtype="float64")
    rookie_bonus = rookie_bonus.mask(years_exp.le(1) & dynasty_pre_league.ge(1800), 180.0)
    rebuild_pre_league = ((rebuild_base * rebuild_multiplier) + rookie_bonus).clip(lower=0)

    components = league_settings_adjustment_components(df, league_settings)
    for name, series in components.items():
        if name == "league_settings_multiplier":
            df[name] = pd.to_numeric(series, errors="coerce").fillna(1.0)
        else:
            df[name] = pd.to_numeric(series, errors="coerce").fillna(1.0).round(4)
    settings_multiplier = components["league_settings_multiplier"]

    df["league_dynasty_score"] = (dynasty_pre_league * settings_multiplier).clip(lower=0).round().astype(int)
    df["league_value_score"] = (value_pre_league * settings_multiplier).clip(lower=0).round().astype(int)
    df["league_rebuild_score"] = (rebuild_pre_league * settings_multiplier).clip(lower=0).round().astype(int)

    # Active lens fields are league-adjusted (compat). base_score stays canonical.
    df["dynasty_score"] = df["league_dynasty_score"]
    df["value_score"] = df["league_value_score"]
    df["rebuild_score"] = df["league_rebuild_score"]

    df = assign_player_tiers(
        df,
        primary_score_field=valuation_score_field(valuation_lens),
    )
    return format_score_columns(df)
