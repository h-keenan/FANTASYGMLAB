import hashlib
import os
import sqlite3
import time
from functools import lru_cache
from typing import Any, Dict, Sequence

import numpy as np
import pandas as pd
import streamlit as st

from modules import performance
from modules import public_player_snapshot
from modules import runtime_trace
from modules import sleeper as sleeper_module
from modules.fantasycalc import get_dynasty_values
from modules.player_identity import ensure_identity_columns
from modules.player_eligibility import (
    annotate_player_eligibility,
    filter_current_fantasy_players,
    player_eligibility,
)
from modules.sleeper import get_players, get_season_player_stats

FANTASY_POSITIONS = {"QB", "RB", "WR", "TE", "K"}
UNRANKED_SEARCH_RANK = 9999999

# Canonical composite weights (must sum to 1.0). Market remains primary;
# production/usage is a bounded football evidence term — not a second market.
COMPOSITE_WEIGHT_MARKET = 0.48
COMPOSITE_WEIGHT_AGE = 0.20
COMPOSITE_WEIGHT_PRODUCTION = 0.10
COMPOSITE_WEIGHT_SCARCITY = 0.12
COMPOSITE_WEIGHT_ROLE = 0.04
COMPOSITE_WEIGHT_OPPORTUNITY = 0.06

# Season-sample confidence for production evidence (no per-game whiplash model).
PRODUCTION_FULL_SAMPLE_GAMES = 8.0
PRODUCTION_SCORE_FLOOR = 0.0
PRODUCTION_SCORE_CEILING = 10000.0

# Continuous dynasty age curves: piecewise-linear control points (age → multiplier).
# Designed for smooth adjacent-year movement (no giant step cliffs).
AGE_CURVE_CONTROL_POINTS: Dict[str, tuple[tuple[float, float], ...]] = {
    "QB": (
        (21.0, 1.08),
        (24.0, 1.08),
        (27.0, 1.05),
        (30.0, 1.02),
        (33.0, 0.96),
        (35.0, 0.86),
        (37.0, 0.72),
        (40.0, 0.52),
        (42.0, 0.42),
    ),
    "RB": (
        (20.0, 1.17),
        (22.0, 1.14),
        (24.0, 1.08),
        (25.0, 1.03),
        (26.0, 0.97),
        (27.0, 0.89),
        (28.0, 0.79),
        (29.0, 0.67),
        (30.0, 0.55),
        (31.0, 0.44),
        (32.0, 0.35),
        (34.0, 0.26),
    ),
    "WR": (
        (20.0, 1.16),
        (22.0, 1.14),
        (24.0, 1.10),
        (26.0, 1.05),
        (28.0, 1.00),
        (29.0, 0.94),
        (30.0, 0.86),
        (31.0, 0.76),
        (32.0, 0.66),
        (33.0, 0.56),
        (34.0, 0.48),
        (36.0, 0.38),
    ),
    "TE": (
        (21.0, 1.12),
        (23.0, 1.10),
        (25.0, 1.06),
        (27.0, 1.04),
        (29.0, 1.00),
        (30.0, 0.94),
        (31.0, 0.86),
        (32.0, 0.76),
        (33.0, 0.68),
        (35.0, 0.55),
        (37.0, 0.46),
    ),
    "K": (
        (24.0, 1.00),
        (34.0, 0.98),
        (36.0, 0.92),
        (38.0, 0.84),
        (40.0, 0.70),
        (42.0, 0.58),
    ),
}
PLAYABLE_OR_INJURED_STATUSES = {
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
    "practice squad",
}
INJURY_STATUSES = {
    "questionable",
    "doubtful",
    "out",
    "injured reserve",
    "ir",
    "pup",
    "nfi",
    "physically unable to perform",
    "non-football injury",
}


def _append_display_sentence(base: str, sentence: str) -> str:
    """Append display copy as a clean sentence without changing scoring inputs."""
    clean_base = str(base or "").strip()
    clean_sentence = str(sentence or "").strip()
    if not clean_base:
        return clean_sentence
    if clean_base[-1] not in ".!?":
        clean_base += "."
    return f"{clean_base} {clean_sentence}"


POSITION_REPLACEMENT_RANK = {
    "QB": 18,
    "RB": 36,
    "WR": 48,
    "TE": 18,
    "K": 12,
}
POSITION_SCARCITY_MULTIPLIER = {
    "QB": 0.90,
    "RB": 1.08,
    "WR": 1.00,
    "TE": 1.14,
    "K": 0.25,
}
PLAYER_COLUMNS = [
    "player_id",
    "name",
    "position",
    "team",
    "age",
    "value",
    "search_rank",
    "active",
    "status",
    "years_exp",
    "news_updated",
    "depth_chart_position",
    "depth_chart_order",
    "hashtag",
    "team_abbr",
    "injury_status",
    "sport",
    "fantasy_positions",
    "is_current_fantasy_eligible",
    "player_eligibility_reason",
    "injury_level",
    "injury_risk_score",
    "injury_multiplier",
    "age_penalty",
    "score",
    "news_factor",
    "fantasycalc_value",
    "market_score",
    "age_multiplier",
    "age_curve_score",
    "production_score",
    "production_confidence",
    "production_explanation",
    "scarcity_score",
    "role_score",
    "depth_chart_slot",
    "projected_starter",
    "opportunity_label",
    "opportunity_score",
    "opportunity_confidence",
    "opportunity_source_flags",
    "opportunity_explanation",
    "snap_share",
    "rush_share",
    "target_share",
    "route_participation",
    "opportunity_share",
    "workload_trend",
    "stats_season",
    "games_played",
    "targets",
    "receptions",
    "receiving_yards",
    "receiving_tds",
    "rush_attempts",
    "rushing_yards",
    "rushing_tds",
    "pass_attempts",
    "passing_yards",
    "passing_tds",
    "fantasy_points",
    "fantasy_points_half_ppr",
    "fantasy_points_ppr",
    "ppg",
    "risk_multiplier",
    "valuation_blend",
    "dynasty_score",
    "value_score",
]


def empty_players_table() -> pd.DataFrame:
    return pd.DataFrame(columns=PLAYER_COLUMNS)


PLAYER_STATS_FIELDS = [
    "stats_season",
    "games_played",
    "targets",
    "receptions",
    "receiving_yards",
    "receiving_tds",
    "rush_attempts",
    "rushing_yards",
    "rushing_tds",
    "pass_attempts",
    "passing_yards",
    "passing_tds",
    "fantasy_points",
    "fantasy_points_half_ppr",
    "fantasy_points_ppr",
    "ppg",
    "snap_share",
    "opportunity_share",
    "target_share",
    "rush_share",
    "route_participation",
]

PUBLIC_PLAYER_SNAPSHOT_HYDRATION_COLUMNS = (
    "name",
    "position",
    "team",
    "age",
    "active",
    "status",
    "years_exp",
    "news_updated",
    "depth_chart_position",
    "depth_chart_order",
    "hashtag",
    "team_abbr",
    "injury_status",
    "canonical_player_id",
    "sleeper_id",
    "depth_chart_slot",
    "projected_starter",
    "snap_share",
    "rush_share",
    "target_share",
    "route_participation",
    "opportunity_share",
    "injury_level",
    "injury_risk_score",
    "injury_multiplier",
    "risk_multiplier",
    *PLAYER_STATS_FIELDS,
)


def attach_player_stats(
    player_df: pd.DataFrame,
    player_stats: Dict[str, Dict[str, Any]] | None = None,
) -> pd.DataFrame:
    """Join optional season stats by stable Sleeper player_id without inventing zeroes."""
    if player_df is None or player_df.empty:
        return player_df

    stats_payload = player_stats if player_stats is not None else get_season_player_stats()
    enriched = player_df.copy()
    if not isinstance(stats_payload, dict) or not stats_payload:
        for field_name in PLAYER_STATS_FIELDS:
            if field_name not in enriched.columns:
                enriched[field_name] = None
        return enriched

    records = []
    for player_id, values in stats_payload.items():
        if not isinstance(values, dict):
            continue
        record = {"player_id": str(player_id)}
        for field_name in PLAYER_STATS_FIELDS:
            if field_name in values and values.get(field_name) is not None:
                record[field_name] = values.get(field_name)
        records.append(record)

    if not records:
        for field_name in PLAYER_STATS_FIELDS:
            if field_name not in enriched.columns:
                enriched[field_name] = None
        return enriched

    stats_df = pd.DataFrame.from_records(records).drop_duplicates("player_id", keep="last")
    stats_df["player_id"] = stats_df["player_id"].astype(str)
    enriched["player_id"] = enriched["player_id"].astype(str)
    joined = enriched.merge(stats_df, on="player_id", how="left", suffixes=("", "__stats"))
    for field_name in PLAYER_STATS_FIELDS:
        stats_field = f"{field_name}__stats"
        if stats_field not in joined.columns:
            if field_name not in joined.columns:
                joined[field_name] = None
            continue
        incoming = joined[stats_field]
        if field_name in joined.columns:
            joined[field_name] = incoming.combine_first(joined[field_name])
        else:
            joined[field_name] = incoming
        joined = joined.drop(columns=[stats_field])
    return joined


def rank_to_value(search_rank) -> int:
    """
    Convert Sleeper search_rank into a dynasty-ish value curve.
    Top players need meaningful separation; deep/unranked players should not
    tie with real starters.
    """
    try:
        rank = int(search_rank)
    except Exception:
        return 0

    if rank <= 0 or rank >= UNRANKED_SEARCH_RANK:
        return 0

    if rank <= 250:
        return int(round(10000 * ((251 - rank) / 250) ** 0.72))
    if rank <= 500:
        return int(round(2600 * ((501 - rank) / 250) ** 1.2))
    if rank <= 900:
        return int(round(500 * ((901 - rank) / 400) ** 1.3))
    return 0


def age_adjustment(age, base_value: int) -> int:
    if age is None or base_value <= 0:
        return 0

    try:
        age = float(age)
    except Exception:
        return 0

    if age <= 22:
        return int(base_value * 0.18)
    if age <= 24:
        return int(base_value * 0.12)
    if age <= 26:
        return int(base_value * 0.05)
    if age <= 28:
        return 0
    if age <= 30:
        return int(base_value * -0.10)
    if age <= 32:
        return int(base_value * -0.22)
    return int(base_value * -0.40)


def _normalize_name(name: str) -> str:
    return "".join(ch for ch in str(name or "").lower() if ch.isalnum())


def _age_curve_arrays(position: str) -> tuple[np.ndarray, np.ndarray]:
    points = AGE_CURVE_CONTROL_POINTS.get(str(position or "").upper()) or (
        (22.0, 1.0),
        (30.0, 1.0),
    )
    ages = np.asarray([float(age) for age, _ in points], dtype=float)
    multipliers = np.asarray([float(mult) for _, mult in points], dtype=float)
    return ages, multipliers


def age_multiplier(position: str, age) -> float:
    """Continuous position-aware dynasty age multiplier (piecewise-linear).

    Missing/invalid age returns 1.0 (neutral). Curves are smooth across integer
    ages — no bucket cliffs.
    """

    try:
        age_value = float(age)
    except Exception:
        return 1.0
    if not np.isfinite(age_value):
        return 1.0

    ages, multipliers = _age_curve_arrays(position)
    return float(np.interp(age_value, ages, multipliers))


def age_multiplier_series(positions: Sequence[Any], ages: Sequence[Any]) -> pd.Series:
    """Vectorized age multipliers aligned to an input index."""

    position_series = pd.Series(list(positions)).astype(str).str.upper()
    age_series = pd.to_numeric(pd.Series(list(ages)), errors="coerce")
    out = np.ones(len(position_series), dtype=float)
    age_values = age_series.to_numpy(dtype=float)
    valid_age = np.isfinite(age_values)
    for position, points in AGE_CURVE_CONTROL_POINTS.items():
        mask = (position_series.to_numpy() == position) & valid_age
        if not mask.any():
            continue
        ages_arr = np.asarray([float(a) for a, _ in points], dtype=float)
        mults = np.asarray([float(m) for _, m in points], dtype=float)
        out[mask] = np.interp(age_values[mask], ages_arr, mults)
    return pd.Series(out, index=position_series.index, dtype=float)


def _safe_rate(total, games) -> float | None:
    try:
        games_value = float(games)
        total_value = float(total)
    except Exception:
        return None
    if not np.isfinite(games_value) or games_value <= 0:
        return None
    if not np.isfinite(total_value):
        return None
    return total_value / games_value


def production_sample_confidence(games_played) -> float:
    """0..1 confidence from season sample size. Tiny samples do not dominate."""

    try:
        games = float(games_played)
    except Exception:
        return 0.0
    if not np.isfinite(games) or games <= 0:
        return 0.0
    return float(min(1.0, games / PRODUCTION_FULL_SAMPLE_GAMES))


def _usage_quality_from_rates(position: str, *, rates: Dict[str, float | None]) -> tuple[float | None, str]:
    """Map per-game usage rates → 0..1 quality. None when evidence is insufficient."""

    position = str(position or "").upper()
    if position == "RB":
        rush = rates.get("rush_att_pg")
        tgt = rates.get("targets_pg")
        if rush is None and tgt is None:
            return None, "no RB usage rates"
        touches = (rush or 0.0) + (tgt or 0.0)
        # ~22 touches/g elite lead; ~12 solid; ~6 committee/depth
        quality = max(0.0, min(1.0, touches / 22.0))
        return quality, f"RB touches/g={touches:.1f}"
    if position == "WR":
        tgt = rates.get("targets_pg")
        rec = rates.get("receptions_pg")
        if tgt is None and rec is None:
            return None, "no WR usage rates"
        # Prefer targets; receptions as soft corroboration.
        primary = tgt if tgt is not None else (rec or 0.0) * 1.35
        quality = max(0.0, min(1.0, float(primary) / 10.0))
        return quality, f"WR targets/g={(tgt if tgt is not None else 0.0):.1f}"
    if position == "TE":
        tgt = rates.get("targets_pg")
        rec = rates.get("receptions_pg")
        if tgt is None and rec is None:
            return None, "no TE usage rates"
        primary = tgt if tgt is not None else (rec or 0.0) * 1.25
        quality = max(0.0, min(1.0, float(primary) / 7.5))
        return quality, f"TE targets/g={(tgt if tgt is not None else 0.0):.1f}"
    if position == "QB":
        att = rates.get("pass_att_pg")
        rush_yd = rates.get("rush_yd_pg")
        if att is None:
            return None, "no QB attempt rates"
        # ~34 att/g full-time starter; backups cluster much lower.
        pass_q = max(0.0, min(1.0, float(att) / 34.0))
        rush_bonus = 0.0
        if rush_yd is not None:
            rush_bonus = max(0.0, min(0.12, float(rush_yd) / 200.0))
        quality = max(0.0, min(1.0, pass_q + rush_bonus))
        return quality, f"QB pass_att/g={float(att):.1f}"
    if position == "K":
        # Kickers lack reliable usage in this feed — defer to market fallback.
        return None, "kicker usage unavailable"
    return None, "unsupported position"


def production_usage_score(
    *,
    position: str,
    market_score: float,
    games_played=None,
    targets=None,
    receptions=None,
    rush_attempts=None,
    rushing_yards=None,
    pass_attempts=None,
    years_exp=None,
) -> Dict[str, Any]:
    """Build a 0..10000 production/usage component with sample-confidence blending.

    Missing or tiny samples fall back toward market_score so rookies / injured
    low-volume seasons are not crushed by zeroes. Uses per-game rates only
    (season totals are never treated as opportunity by themselves).
    """

    try:
        market = float(market_score)
    except Exception:
        market = 0.0
    market = max(0.0, min(PRODUCTION_SCORE_CEILING, market))
    confidence = production_sample_confidence(games_played)
    rates = {
        "targets_pg": _safe_rate(targets, games_played),
        "receptions_pg": _safe_rate(receptions, games_played),
        "rush_att_pg": _safe_rate(rush_attempts, games_played),
        "rush_yd_pg": _safe_rate(rushing_yards, games_played),
        "pass_att_pg": _safe_rate(pass_attempts, games_played),
    }
    quality, detail = _usage_quality_from_rates(position, rates=rates)
    if quality is None or confidence <= 0.0:
        # Rookies / no stats: production term tracks market (neutral evidence).
        try:
            yexp = float(years_exp)
        except Exception:
            yexp = None
        rookie_note = ""
        if yexp is not None and yexp <= 0:
            rookie_note = " rookie/no NFL sample;"
        explanation = (
            f"production deferred to market ({detail};{rookie_note} confidence={confidence:.2f})"
        )
        return {
            "production_score": float(round(market, 2)),
            "production_confidence": float(confidence),
            "production_explanation": explanation.strip(),
        }

    # Map quality 0..1 onto a market-relative band so scale stays compatible.
    observed = 1800.0 + quality * 8200.0
    blended = confidence * observed + (1.0 - confidence) * market
    blended = max(PRODUCTION_SCORE_FLOOR, min(PRODUCTION_SCORE_CEILING, blended))
    explanation = (
        f"{detail}; observed={observed:.0f}; "
        f"blend={blended:.0f} (confidence={confidence:.2f})"
    )
    return {
        "production_score": float(round(blended, 2)),
        "production_confidence": float(confidence),
        "production_explanation": explanation,
    }


def production_usage_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Production components for an entire player frame (vectorized rates)."""

    empty = pd.DataFrame(
        {
            "production_score": pd.Series(dtype=float),
            "production_confidence": pd.Series(dtype=float),
            "production_explanation": pd.Series(dtype=object),
        }
    )
    if df is None or getattr(df, "empty", True):
        return empty

    market = pd.to_numeric(
        df["market_score"] if "market_score" in df.columns else 0.0,
        errors="coerce",
    )
    if not isinstance(market, pd.Series):
        market = pd.Series(market, index=df.index, dtype=float)
    market = market.fillna(0.0).clip(lower=PRODUCTION_SCORE_FLOOR, upper=PRODUCTION_SCORE_CEILING)

    if "games_played" in df.columns:
        games = pd.to_numeric(df["games_played"], errors="coerce")
    else:
        games = pd.Series(np.nan, index=df.index, dtype=float)
    confidence = (games.fillna(0.0) / PRODUCTION_FULL_SAMPLE_GAMES).clip(lower=0.0, upper=1.0)
    confidence = confidence.where(games.fillna(0.0) > 0.0, 0.0)

    def _pg(col: str) -> pd.Series:
        if col not in df.columns:
            return pd.Series(np.nan, index=df.index, dtype=float)
        totals = pd.to_numeric(df[col], errors="coerce")
        return totals / games

    targets_pg = _pg("targets")
    receptions_pg = _pg("receptions")
    rush_att_pg = _pg("rush_attempts")
    rush_yd_pg = _pg("rushing_yards")
    pass_att_pg = _pg("pass_attempts")
    if "position" in df.columns:
        position = df["position"].astype(str).str.upper()
    else:
        position = pd.Series("", index=df.index, dtype=object)

    quality = pd.Series(np.nan, index=df.index, dtype=float)
    detail = pd.Series("unsupported position", index=df.index, dtype=object)

    rb = position == "RB"
    if bool(rb.any()):
        touches = rush_att_pg.where(rb).fillna(0.0) + targets_pg.where(rb).fillna(0.0)
        has = rush_att_pg.notna() | targets_pg.notna()
        quality.loc[rb & has] = (touches.loc[rb & has] / 22.0).clip(0.0, 1.0)
        detail.loc[rb & has] = touches.loc[rb & has].map(lambda v: f"RB touches/g={float(v):.1f}")
        detail.loc[rb & ~has] = "no RB usage rates"

    wr = position == "WR"
    if bool(wr.any()):
        primary = targets_pg.where(targets_pg.notna(), receptions_pg * 1.35)
        has = targets_pg.notna() | receptions_pg.notna()
        quality.loc[wr & has] = (primary.loc[wr & has] / 10.0).clip(0.0, 1.0)
        detail.loc[wr & has] = targets_pg.fillna(0.0).loc[wr & has].map(
            lambda v: f"WR targets/g={float(v):.1f}"
        )
        detail.loc[wr & ~has] = "no WR usage rates"

    te = position == "TE"
    if bool(te.any()):
        primary = targets_pg.where(targets_pg.notna(), receptions_pg * 1.25)
        has = targets_pg.notna() | receptions_pg.notna()
        quality.loc[te & has] = (primary.loc[te & has] / 7.5).clip(0.0, 1.0)
        detail.loc[te & has] = targets_pg.fillna(0.0).loc[te & has].map(
            lambda v: f"TE targets/g={float(v):.1f}"
        )
        detail.loc[te & ~has] = "no TE usage rates"

    qb = position == "QB"
    if bool(qb.any()):
        has = pass_att_pg.notna()
        pass_q = (pass_att_pg.loc[qb & has] / 34.0).clip(0.0, 1.0)
        rush_bonus = (rush_yd_pg.fillna(0.0).loc[qb & has] / 200.0).clip(0.0, 0.12)
        quality.loc[qb & has] = (pass_q + rush_bonus).clip(0.0, 1.0)
        detail.loc[qb & has] = pass_att_pg.loc[qb & has].map(
            lambda v: f"QB pass_att/g={float(v):.1f}"
        )
        detail.loc[qb & ~has] = "no QB attempt rates"

    k = position == "K"
    detail.loc[k] = "kicker usage unavailable"

    if "years_exp" in df.columns:
        years = pd.to_numeric(df["years_exp"], errors="coerce")
    else:
        years = pd.Series(np.nan, index=df.index, dtype=float)
    defer = quality.isna() | (confidence <= 0.0)
    observed = 1800.0 + quality.fillna(0.0) * 8200.0
    blended = confidence * observed + (1.0 - confidence) * market
    blended = blended.clip(lower=PRODUCTION_SCORE_FLOOR, upper=PRODUCTION_SCORE_CEILING)
    score = blended.where(~defer, market).round(2)

    explanation = pd.Series("", index=df.index, dtype=object)
    for idx in df.index[defer]:
        conf = float(confidence.loc[idx])
        d = str(detail.loc[idx])
        y = years.loc[idx]
        rookie = ""
        try:
            if float(y) <= 0:
                rookie = " rookie/no NFL sample;"
        except Exception:
            pass
        explanation.loc[idx] = (
            f"production deferred to market ({d};{rookie} confidence={conf:.2f})"
        )
    keep = ~defer
    explanation.loc[keep] = [
        f"{d}; observed={obs:.0f}; blend={blend:.0f} (confidence={conf:.2f})"
        for d, obs, blend, conf in zip(
            detail.loc[keep].tolist(),
            observed.loc[keep].tolist(),
            blended.loc[keep].tolist(),
            confidence.loc[keep].tolist(),
        )
    ]

    return pd.DataFrame(
        {
            "production_score": score.astype(float),
            "production_confidence": confidence.astype(float),
            "production_explanation": explanation.astype(object),
        },
        index=df.index,
    )


def role_score(position: str, depth_chart_position, market_score: float) -> int:
    if market_score <= 0:
        return 0

    position = str(position or "").upper()
    depth = str(depth_chart_position or "").upper().strip()
    if not depth:
        return 4600 if market_score >= 1000 else 2200

    if depth in {"1", f"{position}1"} or depth.endswith("1"):
        return 8500
    if depth in {"2", f"{position}2"} or depth.endswith("2"):
        return 5600
    if depth in {"3", f"{position}3"} or depth.endswith("3"):
        return 3300
    if "START" in depth or "FIRST" in depth:
        return 8000
    if "BACKUP" in depth:
        return 3600
    return 4200


def _safe_int(value, default: int | None = None) -> int | None:
    try:
        return int(float(value))
    except Exception:
        return default


def _append_source_flag(flags: list[str], flag: str):
    flag = str(flag or "").strip().lower()
    if flag and flag not in flags:
        flags.append(flag)


def _source_flag_string(flags: list[str]) -> str:
    return "|".join(str(flag).strip().lower() for flag in flags if str(flag).strip())


def depth_chart_slot(position: str, depth_chart_position, depth_chart_order=None) -> int | None:
    position = str(position or "").upper().strip()
    depth = str(depth_chart_position or "").upper().strip()
    if not depth:
        order_value = _safe_int(depth_chart_order)
        return order_value if order_value and order_value > 0 else None

    if depth in {"1", f"{position}1"} or depth.endswith("1"):
        return 1
    if depth in {"2", f"{position}2"} or depth.endswith("2"):
        return 2
    if depth in {"3", f"{position}3"} or depth.endswith("3"):
        return 3
    if "START" in depth or "FIRST" in depth:
        return 1
    if "BACKUP" in depth or "SECOND" in depth:
        return 2
    if "THIRD" in depth:
        return 3

    digits = "".join(ch for ch in depth if ch.isdigit())
    if digits:
        try:
            return max(1, int(digits[0]))
        except Exception:
            order_value = _safe_int(depth_chart_order)
            return order_value if order_value and order_value > 0 else None
    order_value = _safe_int(depth_chart_order)
    return order_value if order_value and order_value > 0 else None


def projected_starter_status(
    position: str,
    depth_chart_position,
    market_score: float = 0.0,
    depth_chart_order=None,
) -> bool:
    slot = depth_chart_slot(position, depth_chart_position, depth_chart_order)
    if slot == 1:
        return True
    try:
        market_score = float(market_score)
    except Exception:
        market_score = 0.0
    position = str(position or "").upper().strip()
    threshold = 4200
    if position == "QB":
        threshold = 5000
    elif position == "TE":
        threshold = 3800
    elif position in {"RB", "WR"}:
        threshold = 4300
    return slot is None and market_score >= threshold


def opportunity_profile(
    position: str,
    depth_chart_position,
    market_score: float,
    depth_chart_order=None,
    years_exp=None,
    age=None,
    status: str = "",
    injury_status: str = "",
) -> Dict[str, Any]:
    position = str(position or "").upper().strip()
    slot = depth_chart_slot(position, depth_chart_position, depth_chart_order)
    starter = projected_starter_status(position, depth_chart_position, market_score, depth_chart_order)
    injury_key = injury_level(status, injury_status)
    source_flags: list[str] = []
    try:
        market_score = float(market_score)
    except Exception:
        market_score = 0.0
    try:
        years_exp = float(years_exp)
    except Exception:
        years_exp = 99.0
    try:
        age = float(age)
    except Exception:
        age = 99.0

    young_upside = age <= 24 or years_exp <= 2
    high_market = market_score >= 2800
    elite_market = market_score >= 5200
    if str(depth_chart_position or "").strip() or _safe_int(depth_chart_order):
        _append_source_flag(source_flags, "sleeper_depth")
    if _safe_int(depth_chart_order):
        _append_source_flag(source_flags, "depth_chart_order")

    confidence = 84 if slot == 1 else 74 if slot == 2 else 66 if slot and slot >= 3 else 48

    if starter:
        if injury_key in {"major", "moderate"}:
            label = "Starter At Risk"
            score = 6600 if injury_key == "major" else 7200
            explanation = "Player projects as the starter, but current injury status makes the workload less stable than a normal lead option."
            confidence = max(confidence, 78)
        elif elite_market:
            label = "Elite Opportunity"
            score = 9200
            explanation = "Player is projected starter with a clear front-line workload profile."
            confidence = max(confidence, 90)
        else:
            label = "Strong Opportunity"
            score = 7600
            explanation = "Player is projected starter and should hold usable weekly volume."
            confidence = max(confidence, 82)
    elif slot == 2:
        if position == "RB" and high_market:
            label = "Committee Back"
            score = 5600
            explanation = "Player shares workload with another back and profiles more like a committee piece than a locked-in feature runner."
            confidence = max(confidence, 80)
        elif position == "RB":
            if young_upside or market_score >= 1500:
                label = "Backup With Upside"
                score = 4300
                explanation = "Player currently sits second on the depth chart but still has a credible path to more work."
                confidence = max(confidence, 72)
            else:
                label = "Handcuff"
                score = 3200
                explanation = "Player is mainly a backup runner whose value jumps if the starter misses time."
                confidence = max(confidence, 76)
        elif young_upside or high_market:
            label = "Backup With Upside"
            score = 4200
            explanation = "Player currently sits second on the depth chart but has enough talent or youth to grow into a bigger role."
            confidence = max(confidence, 72)
        else:
            label = "Buried Depth"
            score = 2200
            explanation = "Player currently sits second on the depth chart without a strong weekly workload signal."
            confidence = max(confidence, 68)
    elif slot and slot >= 3:
        if young_upside and market_score >= 1200:
            label = "Backup With Upside"
            score = 3000
            explanation = "Player is buried on the depth chart today but still has some developmental path to relevance."
            confidence = max(confidence, 62)
        elif position == "RB" and market_score >= 900:
            label = "Handcuff"
            score = 2400
            explanation = "Player is deep on the depth chart and mostly profiles as injury-contingent depth."
            confidence = max(confidence, 70)
        else:
            label = "Buried Depth"
            score = 1600
            explanation = "Player is buried on the current depth chart and lacks a clean workload path."
            confidence = max(confidence, 72)
    else:
        if elite_market:
            label = "Strong Opportunity"
            score = 7000
            explanation = "Depth-chart role is unclear in the current feed, so opportunity is estimated from market context and starting-role probability."
            confidence = 58
        elif high_market or young_upside:
            label = "Backup With Upside"
            score = 4000
            explanation = "Depth-chart role is unclear, but the underlying talent and age profile keep some opportunity alive."
            confidence = 44
        else:
            label = "Buried Depth"
            score = 2200
            explanation = "Depth-chart role is unclear and there is not enough supporting signal to project stable opportunity."
            confidence = 34
        _append_source_flag(source_flags, "market_inference")
        _append_source_flag(source_flags, "depth_unknown")

    if injury_key == "major":
        # Starter At Risk already baked a reduced opportunity score — do not
        # apply a second injury haircut inside the same component.
        if label != "Starter At Risk":
            score = int(round(score * 0.82))
            explanation += " Current injury status materially suppresses near-term opportunity."
            confidence = max(28, confidence - 10)
        else:
            confidence = max(28, confidence - 4)
        _append_source_flag(source_flags, "injury_overlay")
    elif injury_key == "moderate":
        if label != "Starter At Risk":
            score = int(round(score * 0.90))
            explanation += " Injury risk is pulling down short-term workload confidence."
            confidence = max(32, confidence - 6)
        else:
            confidence = max(32, confidence - 3)
        _append_source_flag(source_flags, "injury_overlay")
    elif injury_key == "minor":
        score = int(round(score * 0.96))
        confidence = max(36, confidence - 3)
        _append_source_flag(source_flags, "injury_overlay")

    if label == "Elite Opportunity":
        workload_trend = "Stable"
    elif label in {"Strong Opportunity", "Committee Back"}:
        workload_trend = "Stable"
    elif label in {"Starter At Risk"}:
        workload_trend = "Fragile"
    elif label == "Backup With Upside":
        workload_trend = "Rising"
    elif label == "Handcuff":
        workload_trend = "Contingent"
    else:
        workload_trend = "Blocked"

    _append_source_flag(source_flags, "usage_unavailable")

    return {
        "depth_chart_slot": int(slot or 0),
        "projected_starter": bool(starter),
        "opportunity_label": label,
        "opportunity_score": int(max(0, min(10000, score))),
        "opportunity_confidence": int(max(0, min(100, confidence))),
        "opportunity_source_flags": _source_flag_string(source_flags),
        "opportunity_explanation": explanation,
        "snap_share": None,
        "rush_share": None,
        "target_share": None,
        "route_participation": None,
        "opportunity_share": None,
        "workload_trend": workload_trend,
    }


def _opportunity_group_sort_key(row: pd.Series) -> tuple:
    slot = pd.to_numeric(pd.Series([row.get("depth_chart_slot")]), errors="coerce").fillna(99).iloc[0]
    if not slot or slot <= 0:
        slot = 99
    projected = 0 if bool(row.get("projected_starter")) else 1
    market = -float(pd.to_numeric(pd.Series([row.get("market_score")]), errors="coerce").fillna(0).iloc[0])
    age = float(pd.to_numeric(pd.Series([row.get("age")]), errors="coerce").fillna(99).iloc[0])
    return (slot, projected, market, age)


def enrich_opportunity_context(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    enriched = df.copy()
    if "team" not in enriched.columns or "position" not in enriched.columns:
        return enriched

    enriched["opportunity_label"] = enriched.get("opportunity_label", "").fillna("").astype(str)
    enriched["opportunity_explanation"] = enriched.get("opportunity_explanation", "").fillna("").astype(str)
    enriched["workload_trend"] = enriched.get("workload_trend", "Unknown").fillna("Unknown").astype(str)
    enriched["opportunity_score"] = pd.to_numeric(enriched.get("opportunity_score"), errors="coerce").fillna(0).astype(int)
    enriched["opportunity_confidence"] = pd.to_numeric(
        enriched.get("opportunity_confidence", pd.Series(0, index=enriched.index)),
        errors="coerce",
    ).fillna(0).astype(int)
    enriched["opportunity_source_flags"] = enriched.get(
        "opportunity_source_flags",
        pd.Series("", index=enriched.index, dtype="object"),
    ).fillna("").astype(str)
    enriched["market_score"] = pd.to_numeric(
        enriched.get("market_score", pd.Series(0.0, index=enriched.index)),
        errors="coerce",
    ).fillna(0.0)
    enriched["depth_chart_slot"] = pd.to_numeric(
        enriched.get("depth_chart_slot", pd.Series(0, index=enriched.index)),
        errors="coerce",
    ).fillna(0).astype(int)
    enriched["depth_chart_order"] = pd.to_numeric(
        enriched.get("depth_chart_order", pd.Series(0, index=enriched.index)),
        errors="coerce",
    ).fillna(0).astype(int)
    enriched["years_exp"] = pd.to_numeric(
        enriched.get("years_exp", pd.Series(99.0, index=enriched.index)),
        errors="coerce",
    ).fillna(99.0)
    enriched["age"] = pd.to_numeric(
        enriched.get("age", pd.Series(99.0, index=enriched.index)),
        errors="coerce",
    ).fillna(99.0)

    for (_, _), group in enriched.groupby(
        [
            enriched["team"].fillna("").astype(str).str.upper(),
            enriched["position"].fillna("").astype(str).str.upper(),
        ],
        sort=False,
    ):
        if group.empty:
            continue
        if len(group) == 1:
            idx = group.index[0]
            label = str(enriched.at[idx, "opportunity_label"] or "")
            if label in {"Strong Opportunity", "Elite Opportunity"} and enriched.at[idx, "workload_trend"] == "Stable":
                enriched.at[idx, "opportunity_explanation"] = (
                    str(enriched.at[idx, "opportunity_explanation"]).rstrip(".")
                    + " Depth-chart competition looks light inside the current team feed."
                )
                enriched.at[idx, "opportunity_confidence"] = int(
                    max(0, min(100, int(enriched.at[idx, "opportunity_confidence"] or 0) + 4))
                )
            continue

        ordered = sorted(group.index.tolist(), key=lambda idx: _opportunity_group_sort_key(enriched.loc[idx]))
        for order_idx, idx in enumerate(ordered):
            current = enriched.loc[idx]
            current_slot = int(current.get("depth_chart_slot") or (order_idx + 1))
            label = str(current.get("opportunity_label") or "")
            explanation = str(current.get("opportunity_explanation") or "").rstrip(".")
            workload_trend = str(current.get("workload_trend") or "Unknown")
            score = int(current.get("opportunity_score") or 0)
            confidence = int(current.get("opportunity_confidence") or 0)
            market = float(current.get("market_score") or 0.0)
            source_flags = [
                part.strip().lower()
                for part in str(current.get("opportunity_source_flags") or "").split("|")
                if part.strip()
            ]
            ahead = [enriched.loc[other_idx] for other_idx in ordered[:order_idx]]
            behind = [enriched.loc[other_idx] for other_idx in ordered[order_idx + 1 :]]
            ahead_injury = any(injury_level(row.get("status"), row.get("injury_status")) in {"major", "moderate"} for row in ahead)
            next_player = behind[0] if behind else None
            next_market = float(next_player.get("market_score") or 0.0) if next_player is not None else 0.0
            young_upside = float(current.get("age") or 99.0) <= 24 or float(current.get("years_exp") or 99.0) <= 2

            if current_slot == 1:
                if next_player is not None and next_market >= market * 0.72 and label in {"Strong Opportunity", "Elite Opportunity"}:
                    label = "Starter At Risk"
                    score = max(6200, int(round(score * 0.88)))
                    explanation = (
                        "Player is still the projected starter, but the next option on the depth chart carries enough weight to threaten a truly secure workload"
                    )
                    workload_trend = "Fragile"
                    confidence = min(100, max(confidence, 82))
                    _append_source_flag(source_flags, "team_competition")
                elif label == "Starter At Risk" and next_player is not None:
                    explanation = explanation + " There is also credible pressure behind him on the current depth chart"
                    workload_trend = "Fragile"
                    confidence = min(100, max(confidence, 80))
                    _append_source_flag(source_flags, "team_competition")
            else:
                if ahead_injury and label in {"Backup With Upside", "Handcuff", "Committee Back"}:
                    score = min(10000, score + (900 if label == "Backup With Upside" else 650))
                    workload_trend = "Rising"
                    if label == "Handcuff" and young_upside:
                        label = "Backup With Upside"
                    explanation = _append_display_sentence(
                        explanation,
                        "Player benefits from injury uncertainty ahead on the depth chart.",
                    )
                    confidence = min(100, max(confidence, 78))
                    _append_source_flag(source_flags, "team_competition")
                    _append_source_flag(source_flags, "injury_overlay")
                elif label == "Backup With Upside" and current_slot == 2:
                    explanation = _append_display_sentence(
                        explanation,
                        "Player projects for increased opportunity if the room softens or the starter misses time.",
                    )
                    workload_trend = "Rising"
                    confidence = min(100, max(confidence, 76))
                    _append_source_flag(source_flags, "team_competition")
                elif label == "Buried Depth" and current_slot >= 3 and any(
                    injury_level(row.get("status"), row.get("injury_status")) in {"major", "moderate"} for row in ahead[:2]
                ):
                    explanation = _append_display_sentence(
                        explanation,
                        "There is at least some injury-driven path to short-term opportunity ahead.",
                    )
                    workload_trend = "Rising"
                    confidence = min(100, max(confidence, 68))
                    _append_source_flag(source_flags, "team_competition")
                    _append_source_flag(source_flags, "injury_overlay")

            enriched.at[idx, "opportunity_label"] = label
            enriched.at[idx, "opportunity_score"] = int(max(0, min(10000, score)))
            enriched.at[idx, "opportunity_confidence"] = int(max(0, min(100, confidence)))
            enriched.at[idx, "opportunity_source_flags"] = _source_flag_string(source_flags)
            enriched.at[idx, "opportunity_explanation"] = explanation.rstrip(".") + "."
            enriched.at[idx, "workload_trend"] = workload_trend

    return enriched


@runtime_trace.traced(
    "injury_level",
    phase="injury_processing",
    counter="injury_parsing",
)
def injury_level(status: str, injury_status: str = "") -> str:
    """Classify injury severity from status strings.

    Presentation/parsing helper only — cached because identical status pairs are
    evaluated thousands of times per cold load without changing outcomes.
    """

    return _injury_level_cached(
        str(status or "").strip().lower(),
        str(injury_status or "").strip().lower(),
    )


@lru_cache(maxsize=4096)
def _injury_level_cached(status: str, injury_status: str) -> str:
    healthy_markers = {"", "none", "healthy", "active"}
    major_terms = {
        "injured reserve",
        "ir",
        "reserve",
        "pup",
        "nfi",
        "physically unable to perform",
        "non-football injury",
        "season-ending",
        "season ending",
        "out for season",
        "out for the season",
        "torn acl",
        "torn achilles",
    }
    moderate_terms = {"out", "doubtful"}
    minor_terms = {"questionable", "probable", "limited", "day-to-day"}

    def has_term(text: str, terms: set[str]) -> bool:
        return any(term in text for term in terms if term)

    if status in major_terms or has_term(status, major_terms) or has_term(injury_status, major_terms):
        return "major"
    if status in moderate_terms or has_term(status, moderate_terms) or has_term(injury_status, moderate_terms):
        return "moderate"
    if status in minor_terms or has_term(status, minor_terms) or has_term(injury_status, minor_terms):
        return "minor"
    if injury_status and injury_status not in healthy_markers:
        return "minor"
    return "healthy"


def injury_multiplier(status: str, injury_status: str = "") -> float:
    level = injury_level(status, injury_status)
    if level == "major":
        return 0.68
    if level == "moderate":
        return 0.80
    if level == "minor":
        return 0.95
    return 1.0


def injury_risk_score(status: str, injury_status: str = "") -> float:
    level = injury_level(status, injury_status)
    if level == "major":
        return 2.0
    if level in {"moderate", "minor"}:
        return 1.0
    return 0.0


def risk_multiplier(status: str, team: str, search_rank, injury_status: str = "") -> float:
    status = str(status or "").strip().lower()
    if not team or not str(team).strip():
        return 0.35
    injury_risk = injury_multiplier(status, injury_status)
    base_risk = 1.0
    if status and status not in PLAYABLE_OR_INJURED_STATUSES and status != "active":
        base_risk = 0.72
    try:
        rank = int(float(search_rank))
    except Exception:
        rank = UNRANKED_SEARCH_RANK
    if rank >= UNRANKED_SEARCH_RANK:
        base_risk = min(base_risk, 0.80)
    return min(base_risk, injury_risk)


def current_availability_multiplier(status: str, team: str, search_rank, injury_status: str = "") -> float:
    """
    Current-season availability should be more sensitive to injury than dynasty value.
    This is intentionally harsher than risk_multiplier() and is only used for
    current/team-strength style calculations.
    """
    status = str(status or "").strip().lower()
    if not team or not str(team).strip():
        return 0.35

    base_risk = 1.0
    if status and status not in PLAYABLE_OR_INJURED_STATUSES and status != "active":
        base_risk = 0.72
    try:
        rank = int(float(search_rank))
    except Exception:
        rank = UNRANKED_SEARCH_RANK
    if rank >= UNRANKED_SEARCH_RANK:
        base_risk = min(base_risk, 0.80)

    level = injury_level(status, injury_status)
    if level == "major":
        injury_risk = 0.42
    elif level == "moderate":
        injury_risk = 0.72
    elif level == "minor":
        injury_risk = 0.93
    else:
        injury_risk = 1.0
    return min(base_risk, injury_risk)


def is_injury_status(row_or_status) -> bool:
    if isinstance(row_or_status, dict):
        raw_status = row_or_status.get("status")
        raw_injury_status = row_or_status.get("injury_status")
    else:
        try:
            raw_status = row_or_status.get("status")
            raw_injury_status = row_or_status.get("injury_status")
        except Exception:
            raw_status = row_or_status
            raw_injury_status = ""

    return injury_level(raw_status, raw_injury_status) != "healthy"


def _injury_value_score(row) -> tuple[float, str]:
    for field in ("market_score", "dynasty_score", "value_score", "score", "role_score", "value"):
        value = pd.to_numeric(pd.Series([row.get(field)]), errors="coerce").iloc[0]
        if pd.notna(value) and float(value) > 0:
            return min(100.0, float(value)), field
    return 0.0, ""


def _format_injury_number(value) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return "0"
    return str(int(round(float(number))))


def _injury_freshness(news_updated) -> tuple[float, str, float | None]:
    updated_at = pd.to_numeric(pd.Series([news_updated]), errors="coerce").iloc[0]
    if pd.isna(updated_at) or float(updated_at) <= 0:
        return 0.70, "update unknown", None
    updated_at = float(updated_at)
    if updated_at > 10_000_000_000:
        updated_at /= 1000.0
    age_days = max(0.0, (time.time() - updated_at) / (24 * 60 * 60))
    if age_days <= 14:
        return 1.0, "current", age_days
    if age_days <= 45:
        return 0.90, "recent", age_days
    if age_days <= 60:
        return 0.75, "aging", age_days
    return 0.55, "stale", age_days


def _injury_future_asset_profile(row) -> bool:
    age = pd.to_numeric(pd.Series([row.get("age")]), errors="coerce").iloc[0]
    years_exp = pd.to_numeric(pd.Series([row.get("years_exp")]), errors="coerce").iloc[0]
    young_asset = (pd.notna(age) and float(age) <= 23.0) or (
        pd.notna(years_exp) and float(years_exp) <= 1.0
    )
    if not young_asset:
        return False

    role_text = " ".join(
        str(row.get(field) or "").strip().lower()
        for field in (
            "role",
            "role_label",
            "player_tier",
            "tier_label",
            "opportunity_label",
            "workload_trend",
        )
    )
    depth_slot = pd.to_numeric(
        pd.Series([row.get("depth_chart_slot", row.get("depth_chart_order"))]),
        errors="coerce",
    ).iloc[0]
    source_flags = str(row.get("opportunity_source_flags") or "").lower()
    future_labels = (
        "developmental",
        "rookie",
        "prospect",
        "stash",
        "backup with upside",
        "buried depth",
        "handcuff",
        "blocked",
    )
    return (
        any(label in role_text for label in future_labels)
        or (pd.notna(depth_slot) and float(depth_slot) >= 2.0)
        or ("depth_unknown" in source_flags and pd.notna(years_exp) and float(years_exp) <= 1.0)
    )


def _injury_weekly_role(row) -> bool:
    if _injury_future_asset_profile(row):
        return False
    opportunity = str(row.get("opportunity_label") or "").strip().lower()
    depth_slot = pd.to_numeric(
        pd.Series([row.get("depth_chart_slot", row.get("depth_chart_order"))]),
        errors="coerce",
    ).iloc[0]
    return bool(
        row.get("projected_starter")
        or (pd.notna(depth_slot) and float(depth_slot) == 1.0)
        or opportunity
        in {
            "elite opportunity",
            "strong opportunity",
            "starter at risk",
            "committee back",
        }
    )


def _injury_roster_relevance(row) -> tuple[float, str]:
    if _injury_future_asset_profile(row):
        return 1.05, "future asset"
    if bool(row.get("_injured_starter")) or _injury_weekly_role(row):
        return 1.35, "starter"
    role_text = " ".join(
        str(row.get(field) or "").strip().lower()
        for field in ("role", "role_label", "player_tier", "tier_label")
    )
    if any(label in role_text for label in ("core", "elite", "star", "untouchable")):
        return 1.20, "core asset"
    if any(label in role_text for label in ("starter", "contributor", "flex")):
        return 0.90, "contributor"
    return 0.65, "depth"


def _healthy_position_cover(roster: pd.DataFrame, injured_row) -> bool:
    position = str(injured_row.get("position") or "").strip().upper()
    player_id = str(injured_row.get("player_id") or "").strip()
    if not position:
        return False
    candidates = roster[
        roster.get("position", pd.Series("", index=roster.index))
        .fillna("")
        .astype(str)
        .str.upper()
        .eq(position)
    ].copy()
    if player_id and "player_id" in candidates.columns:
        candidates = candidates[
            candidates["player_id"].fillna("").astype(str).ne(player_id)
        ]
    if candidates.empty:
        return False
    healthy = candidates[~candidates.apply(is_injury_status, axis=1)].copy()
    if healthy.empty:
        return False
    for _, candidate in healthy.iterrows():
        value_score, _ = _injury_value_score(candidate)
        opportunity = str(candidate.get("opportunity_label") or "").strip().lower()
        if (
            _injury_weekly_role(candidate)
            or value_score >= 35.0
            or opportunity in {"backup with upside", "handcuff"}
        ):
            return True
    return False


@runtime_trace.traced("summarize_team_injuries", phase="injury_processing")
def summarize_team_injuries(
    roster_df: pd.DataFrame,
    lineup_df: pd.DataFrame | None = None,
) -> Dict[str, Any]:
    if roster_df is None or roster_df.empty:
        return {
            "injured_roster": 0,
            "injured_starters": 0,
            "major_absences": 0,
            "injury_risk_total": 0.0,
            "injury_burden": 0.0,
            "injured_bench_players": 0,
            "major_injury_count": 0,
            "major_injured_starters": 0,
            "active_injured_starters": 0,
            "lineup_injured_starters": 0,
            "future_asset_injury_count": 0,
            "covered_future_injury_count": 0,
            "injury_impact_score": 0.0,
            "injury_value_impact": 0.0,
            "active_injury_impact_score": 0.0,
            "future_injury_impact_score": 0.0,
            "injury_impact_flag": "Injury Data Unavailable",
            "injury_data_quality": "missing",
            "injury_data_note": "No roster injury data is available.",
            "injured_positions": [],
            "injury_need_positions": set(),
            "active_injury_positions": [],
            "future_injury_positions": [],
            "covered_future_injury_positions": [],
            "key_injuries": [],
            "top_injury_impact_players": [],
            "top_injury_impact_summary": "",
            "actionable_injury_players": [],
            "actionable_injury_summary": "",
            "health_flag": "Stable",
        }

    roster = roster_df.copy()
    if "injury_risk_score" in roster.columns:
        risk_scores = pd.to_numeric(roster["injury_risk_score"], errors="coerce").fillna(0.0)
    else:
        risk_scores = roster.apply(
            lambda row: injury_risk_score(row.get("status"), row.get("injury_status")),
            axis=1,
        )
    injury_flags = roster.apply(is_injury_status, axis=1)
    injured_roster = int(injury_flags.sum())
    major_flags = roster.apply(
        lambda row: injury_level(row.get("status"), row.get("injury_status")) == "major",
        axis=1,
    )
    major_absences = int(major_flags.sum())

    lineup_source = lineup_df if lineup_df is not None else pd.DataFrame()
    starters = (
        lineup_source[lineup_source["suggested_starter"].fillna(False)].copy()
        if not lineup_source.empty and "suggested_starter" in lineup_source.columns
        else pd.DataFrame()
    )
    injured_starters = int(starters.apply(is_injury_status, axis=1).sum()) if not starters.empty else 0
    injured_positions = (
        starters.loc[starters.apply(is_injury_status, axis=1), "position"]
        .fillna("")
        .astype(str)
        .str.upper()
        .tolist()
        if not starters.empty
        else []
    )
    unique_positions = [pos for pos in dict.fromkeys(injured_positions) if pos]

    labeled = roster.copy()
    labeled["_injury_level"] = labeled.apply(
        lambda row: injury_level(row.get("status"), row.get("injury_status")),
        axis=1,
    )
    labeled["_injury_risk_score"] = pd.to_numeric(risk_scores, errors="coerce").fillna(0.0)
    starter_ids = {
        str(pid)
        for pid in starters.get("player_id", pd.Series(dtype="object")).fillna("").astype(str).tolist()
        if pid
    }
    labeled["_injured_starter"] = (
        labeled.get("player_id", pd.Series("", index=labeled.index))
        .fillna("")
        .astype(str)
        .isin(starter_ids)
    )
    injured_labeled = labeled[labeled["_injury_level"].ne("healthy")].copy()
    injured_bench_players = int((~injured_labeled["_injured_starter"]).sum())
    major_injured_starters = int(
        (
            injured_labeled["_injured_starter"]
            & injured_labeled["_injury_level"].eq("major")
        ).sum()
    )

    severity_multipliers = {"major": 1.0, "moderate": 0.55, "minor": 0.12, "healthy": 0.0}
    injury_impacts: list[dict[str, Any]] = []
    for injury_index, injury_row in injured_labeled.iterrows():
        severity = str(injury_row.get("_injury_level") or "healthy")
        severity_multiplier = severity_multipliers.get(severity, 0.12)
        player_value, value_field = _injury_value_score(injury_row)
        relevance_multiplier, relevance_label = _injury_roster_relevance(injury_row)
        future_asset = relevance_label == "future asset"
        active_weekly_player = not future_asset and (
            bool(injury_row.get("_injured_starter"))
            or _injury_weekly_role(injury_row)
        )
        has_position_cover = _healthy_position_cover(labeled, injury_row)
        freshness_multiplier, freshness_label, freshness_days = _injury_freshness(
            injury_row.get("news_updated")
        )
        contribution = player_value * severity_multiplier * relevance_multiplier * freshness_multiplier
        labeled.loc[injury_index, "_injury_value_score"] = player_value
        labeled.loc[injury_index, "_injury_value_field"] = value_field
        labeled.loc[injury_index, "_injury_relevance"] = relevance_label
        labeled.loc[injury_index, "_injury_freshness"] = freshness_label
        labeled.loc[injury_index, "_injury_impact_contribution"] = contribution
        status_context = str(
            injury_row.get("injury_status") or injury_row.get("status") or severity
        ).strip()
        injury_impacts.append(
            {
                "player_id": str(injury_row.get("player_id") or "").strip(),
                "name": str(injury_row.get("name") or "").strip(),
                "position": str(injury_row.get("position") or "").strip().upper(),
                "team": str(injury_row.get("team") or "").strip().upper(),
                "injury_level": severity,
                "injury_status": status_context,
                "player_value_score": round(player_value, 1),
                "value_field": value_field,
                "roster_relevance": relevance_label,
                "future_asset": future_asset,
                "active_weekly_player": active_weekly_player,
                "suggested_starter": bool(injury_row.get("_injured_starter"))
                and not future_asset,
                "has_position_cover": has_position_cover,
                "severity_multiplier": severity_multiplier,
                "relevance_multiplier": relevance_multiplier,
                "freshness_multiplier": freshness_multiplier,
                "freshness_label": freshness_label,
                "freshness_days": round(freshness_days, 1) if freshness_days is not None else None,
                "impact_contribution": round(contribution, 1),
            }
        )
    injury_impacts.sort(
        key=lambda item: (
            float(item.get("impact_contribution") or 0),
            float(item.get("player_value_score") or 0),
        ),
        reverse=True,
    )
    injury_impact_score = float(
        sum(float(item.get("impact_contribution") or 0) for item in injury_impacts)
    )
    active_injury_impacts = [
        item for item in injury_impacts if bool(item.get("active_weekly_player"))
    ]
    future_injury_impacts = [
        item for item in injury_impacts if bool(item.get("future_asset"))
    ]
    active_injury_impact_score = float(
        sum(float(item.get("impact_contribution") or 0) for item in active_injury_impacts)
    )
    future_injury_impact_score = float(
        sum(float(item.get("impact_contribution") or 0) for item in future_injury_impacts)
    )
    active_injured_starters = len(active_injury_impacts)
    lineup_injured_starters = sum(
        1
        for item in active_injury_impacts
        if bool(item.get("suggested_starter"))
    )
    future_asset_injury_count = len(future_injury_impacts)
    covered_future_injury_count = sum(
        1 for item in future_injury_impacts if bool(item.get("has_position_cover"))
    )
    active_injury_positions = list(
        dict.fromkeys(
            str(item.get("position") or "").upper()
            for item in active_injury_impacts
            if str(item.get("position") or "").strip()
        )
    )
    future_injury_positions = list(
        dict.fromkeys(
            str(item.get("position") or "").upper()
            for item in future_injury_impacts
            if str(item.get("position") or "").strip()
        )
    )
    covered_future_injury_positions = list(
        dict.fromkeys(
            str(item.get("position") or "").upper()
            for item in future_injury_impacts
            if item.get("has_position_cover") and str(item.get("position") or "").strip()
        )
    )
    injury_need_positions = {
        str(item.get("position") or "").upper()
        for item in active_injury_impacts
        if not item.get("has_position_cover") and str(item.get("position") or "").strip()
    }
    top_injury_impact_players = injury_impacts[:3]

    has_status_fields = any(column in roster.columns for column in ("status", "injury_status"))
    status_values = []
    for column in ("status", "injury_status"):
        if column in roster.columns:
            status_values.extend(
                roster[column].fillna("").astype(str).str.strip().str.lower().tolist()
            )
    has_status_values = any(value for value in status_values)
    injury_data_quality = "available"
    injury_data_note = "Current roster status fields are available."
    if not has_status_fields:
        injury_data_quality = "missing"
        injury_data_note = "Player injury status fields are unavailable."
    elif not has_status_values:
        injury_data_quality = "uncertain"
        injury_data_note = "Player injury status fields are present but contain no current status values."
    elif injury_impacts:
        freshness_labels = {str(item.get("freshness_label") or "") for item in injury_impacts}
        if freshness_labels == {"update unknown"}:
            injury_data_quality = "uncertain"
            injury_data_note = "Injury flags are present, but their update timing is unavailable."
        elif freshness_labels == {"stale"}:
            injury_data_quality = "stale"
            injury_data_note = "All identified injury updates are more than 60 days old."
        elif "update unknown" in freshness_labels or "stale" in freshness_labels:
            injury_data_quality = "uncertain"
            injury_data_note = "Some identified injuries have missing or stale supporting updates."

    actionable_injury_players = [
        item
        for item in injury_impacts
        if (
            float(item.get("impact_contribution") or 0) >= 10.0
            or (
                item.get("roster_relevance") == "starter"
                and item.get("injury_level") in {"major", "moderate"}
            )
        )
    ][:3]

    major_active_injured_starters = sum(
        1
        for item in active_injury_impacts
        if item.get("injury_level") == "major"
    )
    if active_injury_impact_score >= 150.0 or major_active_injured_starters >= 2:
        injury_impact_flag = "Injury Crisis"
    elif major_active_injured_starters >= 1:
        injury_impact_flag = "Major Starter Absence"
    elif active_injury_impact_score >= 70.0:
        injury_impact_flag = "Significant Injury Impact"
    elif active_injured_starters >= 1 and active_injury_impact_score >= 35.0:
        injury_impact_flag = "Starter Availability Concern"
    elif future_injury_impact_score >= 35.0:
        injury_impact_flag = "Future Asset Health Watch"
    elif injury_impact_score >= 18.0:
        injury_impact_flag = "Health Watch"
    elif injury_data_quality == "missing":
        injury_impact_flag = "Injury Data Unavailable"
    elif injury_data_quality in {"uncertain", "stale"}:
        injury_impact_flag = "Health Status Uncertain"
    else:
        injury_impact_flag = "Stable"

    key_injuries = []
    for item in top_injury_impact_players:
        name = str(item.get("name") or "").strip()
        position = str(item.get("position") or "").strip().upper()
        if name:
            key_injuries.append(f"{name} ({position or 'Player'})")
    top_injury_impact_summary = " | ".join(
        (
            f"{item.get('name')} ({item.get('position') or 'Player'}"
            + (f", {item.get('team')}" if item.get("team") else "")
            + f") - {item.get('injury_status') or item.get('injury_level')}"
            + f", value {_format_injury_number(item.get('player_value_score'))}"
            + f", impact {_format_injury_number(item.get('impact_contribution'))}"
            + f", {item.get('freshness_label')}"
        )
        for item in top_injury_impact_players
        if item.get("name")
    )
    actionable_injury_summary = " | ".join(
        (
            f"{item.get('name')} ({item.get('position') or 'Player'}"
            + (f", {item.get('team')}" if item.get("team") else "")
            + f") - {item.get('injury_status') or item.get('injury_level')}"
            + f", {item.get('roster_relevance')}"
            + f", impact {_format_injury_number(item.get('impact_contribution'))}"
            + f", {item.get('freshness_label')}"
        )
        for item in actionable_injury_players
        if item.get("name")
    )

    injury_risk_total = float(pd.to_numeric(risk_scores, errors="coerce").fillna(0.0).sum())
    injury_burden = float(injury_risk_total + (injured_starters * 1.5))
    if injury_burden >= 6 or injured_starters >= 3:
        health_flag = "Injury Crisis"
    elif injury_burden >= 3 or injured_starters >= 2:
        health_flag = "Injury Hit"
    elif injury_burden > 0:
        health_flag = "Health Watch"
    else:
        health_flag = "Stable"

    return {
        "injured_roster": injured_roster,
        "injured_starters": injured_starters,
        "major_absences": major_absences,
        "injury_risk_total": injury_risk_total,
        "injury_burden": injury_burden,
        "injured_bench_players": injured_bench_players,
        "major_injury_count": major_absences,
        "major_injured_starters": major_injured_starters,
        "major_active_injured_starters": major_active_injured_starters,
        "active_injured_starters": active_injured_starters,
        "lineup_injured_starters": lineup_injured_starters,
        "future_asset_injury_count": future_asset_injury_count,
        "covered_future_injury_count": covered_future_injury_count,
        "injury_impact_score": float(injury_impact_score),
        "injury_value_impact": float(injury_impact_score),
        "active_injury_impact_score": active_injury_impact_score,
        "future_injury_impact_score": future_injury_impact_score,
        "injury_impact_flag": injury_impact_flag,
        "injury_data_quality": injury_data_quality,
        "injury_data_note": injury_data_note,
        "injured_positions": unique_positions,
        "injury_need_positions": injury_need_positions,
        "active_injury_positions": active_injury_positions,
        "future_injury_positions": future_injury_positions,
        "covered_future_injury_positions": covered_future_injury_positions,
        "key_injuries": key_injuries,
        "top_injury_impact_players": top_injury_impact_players,
        "top_injury_impact_summary": top_injury_impact_summary,
        "actionable_injury_players": actionable_injury_players,
        "actionable_injury_summary": actionable_injury_summary,
        "health_flag": health_flag,
    }


def _prepare_fantasycalc_values() -> pd.DataFrame:
    csv_started = time.perf_counter()
    fc = get_dynasty_values()
    performance.record_timing(
        "public_player_fantasycalc_csv_parse",
        (time.perf_counter() - csv_started) * 1000,
        category="data",
    )
    if fc.empty:
        return pd.DataFrame(columns=["fc_key", "fantasycalc_value"])

    fc = fc.copy()
    fc["name_key"] = fc["name"].map(_normalize_name)
    fc["position_key"] = fc["position"].astype(str).str.upper()
    fc["fc_key"] = fc["name_key"] + "|" + fc["position_key"]
    fc["fantasycalc_value"] = pd.to_numeric(fc["value"], errors="coerce").fillna(0)
    fc = fc[fc["fantasycalc_value"] > 0]
    if fc.empty:
        return pd.DataFrame(columns=["fc_key", "fantasycalc_value"])

    fc = fc.sort_values("fantasycalc_value", ascending=False)
    return fc[["fc_key", "fantasycalc_value"]].drop_duplicates("fc_key")


def apply_valuation_model(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()
    df["value"] = pd.to_numeric(df["value"], errors="coerce").fillna(0).astype(float)
    df["search_rank_num"] = pd.to_numeric(df["search_rank"], errors="coerce").fillna(UNRANKED_SEARCH_RANK)
    df["name_key"] = df["name"].map(_normalize_name)
    df["position_key"] = df["position"].astype(str).str.upper()
    df["fc_key"] = df["name_key"] + "|" + df["position_key"]

    fc = _prepare_fantasycalc_values()
    if not fc.empty:
        df = df.merge(fc, on="fc_key", how="left")
    else:
        df["fantasycalc_value"] = 0
    df["fantasycalc_value"] = pd.to_numeric(df["fantasycalc_value"], errors="coerce").fillna(0)

    fc_max = float(df["fantasycalc_value"].max() or 0)
    if fc_max > 0:
        df["fantasycalc_score"] = (df["fantasycalc_value"] / fc_max * 10000).clip(0, 11000)
        has_fc = df["fantasycalc_score"] > 0
        df["market_score"] = df["value"].astype(float)
        df.loc[has_fc, "market_score"] = (
            df.loc[has_fc, "value"] * 0.42 + df.loc[has_fc, "fantasycalc_score"] * 0.58
        )
        df["valuation_blend"] = "Sleeper rank + FantasyCalc market + age/VORP/role"
        df.loc[~has_fc, "valuation_blend"] = "Sleeper rank + age/VORP/role"
    else:
        df["fantasycalc_score"] = 0
        df["market_score"] = df["value"].astype(float)
        df["valuation_blend"] = "Sleeper rank + age/VORP/role"

    replacement_values = {}
    for pos, replacement_rank in POSITION_REPLACEMENT_RANK.items():
        pos_values = (
            df.loc[df["position"].astype(str).str.upper() == pos, "market_score"]
            .sort_values(ascending=False)
            .reset_index(drop=True)
        )
        if pos_values.empty:
            replacement_values[pos] = 0.0
        else:
            idx = min(max(replacement_rank - 1, 0), len(pos_values) - 1)
            replacement_values[pos] = float(pos_values.iloc[idx])

    df["age_multiplier"] = age_multiplier_series(df["position"], df.get("age"))
    df["age_curve_score"] = (df["market_score"] * df["age_multiplier"]).clip(0, 12000)
    df["scarcity_score"] = df.apply(
        lambda row: max(
            0.0,
            float(row["market_score"])
            - replacement_values.get(str(row["position"]).upper(), 0.0),
        )
        * POSITION_SCARCITY_MULTIPLIER.get(str(row["position"]).upper(), 1.0),
        axis=1,
    ).clip(0, 10000)
    df["role_score"] = df.apply(
        lambda row: role_score(row["position"], row.get("depth_chart_position"), row["market_score"]),
        axis=1,
    )
    opportunity_df = df.apply(
        lambda row: pd.Series(
            opportunity_profile(
                row.get("position"),
                row.get("depth_chart_position"),
                row.get("market_score"),
                row.get("depth_chart_order"),
                row.get("years_exp"),
                row.get("age"),
                row.get("status"),
                row.get("injury_status"),
            )
        ),
        axis=1,
    )
    for column in opportunity_df.columns:
        df[column] = opportunity_df[column]
    df = enrich_opportunity_context(df)
    production_df = production_usage_frame(df)
    for column in production_df.columns:
        df[column] = production_df[column]
    df["injury_level"] = df.apply(
        lambda row: injury_level(row.get("status"), row.get("injury_status")),
        axis=1,
    )
    df["injury_risk_score"] = df.apply(
        lambda row: injury_risk_score(row.get("status"), row.get("injury_status")),
        axis=1,
    )
    df["injury_multiplier"] = df.apply(
        lambda row: injury_multiplier(row.get("status"), row.get("injury_status")),
        axis=1,
    )
    df["risk_multiplier"] = df.apply(
        lambda row: risk_multiplier(
            row.get("status"),
            row.get("team"),
            row.get("search_rank"),
            row.get("injury_status"),
        ),
        axis=1,
    )

    composite = (
        df["market_score"] * COMPOSITE_WEIGHT_MARKET
        + df["age_curve_score"] * COMPOSITE_WEIGHT_AGE
        + pd.to_numeric(df["production_score"], errors="coerce").fillna(df["market_score"])
        * COMPOSITE_WEIGHT_PRODUCTION
        + df["scarcity_score"] * COMPOSITE_WEIGHT_SCARCITY
        + df["role_score"] * COMPOSITE_WEIGHT_ROLE
        + pd.to_numeric(df["opportunity_score"], errors="coerce").fillna(0.0)
        * COMPOSITE_WEIGHT_OPPORTUNITY
    )
    df["score"] = (composite * df["risk_multiplier"]).clip(lower=0).round().astype(int)
    df["age_penalty"] = (df["age_curve_score"] - df["market_score"]).round().astype(int)
    df["news_factor"] = 0.0
    df["dynasty_score"] = df["score"]
    df["value_score"] = df["score"]
    df["valuation_blend"] = (
        df["valuation_blend"].astype(str) + " + production/usage"
    )

    cleanup_cols = ["search_rank_num", "name_key", "position_key", "fc_key", "fantasycalc_score"]
    return df.drop(columns=[col for col in cleanup_cols if col in df.columns])


def normalize_player_record(pid: str, p: Dict[str, Any]) -> Dict[str, Any]:
    name = p.get("full_name") or p.get("name") or ""
    position = (p.get("position") or "").upper()
    if position == "PK":
        position = "K"
    team = p.get("team") or ""
    age = p.get("age")
    status_raw = str(p.get("status") or "").strip()
    status = status_raw.lower()
    years_exp = p.get("years_exp")
    news_updated = p.get("news_updated")
    depth_chart_position = p.get("depth_chart_position") or ""
    depth_chart_order = p.get("depth_chart_order")
    hashtag = p.get("hashtag") or ""
    team_abbr = p.get("team_abbr") or ""
    injury_status = p.get("injury_status") or p.get("injury_notes") or ""

    try:
        age = float(age) if age is not None else None
    except Exception:
        age = None

    fantasy_positions = FANTASY_POSITIONS

    if position not in fantasy_positions:
        base_value = 0
    else:
        base_value = rank_to_value(p.get("search_rank"))
        if position == "K":
            try:
                rank = int(float(p.get("search_rank")))
            except Exception:
                rank = None
            if rank is not None and rank > 0 and rank < UNRANKED_SEARCH_RANK:
                if rank <= 40:
                    base_value = max(base_value, 3200)
                elif rank <= 80:
                    base_value = max(base_value, 2600)
                elif rank <= 120:
                    base_value = max(base_value, 2100)
                elif rank <= 180:
                    base_value = max(base_value, 1600)
                elif rank <= 260:
                    base_value = max(base_value, 1200)
                elif rank <= 360:
                    base_value = max(base_value, 900)
                elif rank <= 500:
                    base_value = max(base_value, 600)
                elif rank <= 700:
                    base_value = max(base_value, 400)
                elif rank <= 900:
                    base_value = max(base_value, 250)
                else:
                    base_value = max(base_value, 150)

    return {
        "player_id": pid,
        "name": name,
        "position": position,
        "team": team,
        "age": age,
        "value": base_value,
        "search_rank": p.get("search_rank"),
        "active": p.get("active"),
        "status": status_raw,
        "years_exp": years_exp,
        "news_updated": news_updated,
        "depth_chart_position": depth_chart_position,
        "depth_chart_order": depth_chart_order,
        "hashtag": hashtag,
        "team_abbr": team_abbr,
        "injury_status": injury_status,
        "sport": p.get("sport") or "",
        "fantasy_positions": "|".join(str(pos).upper() for pos in (p.get("fantasy_positions") or []) if pos),
    }


@runtime_trace.traced("player_metadata_construction", phase="loading_data")
def build_players_table(db_path: str, refresh: bool = False) -> pd.DataFrame:
    """
    Fetch all players from Sleeper, engineer dynasty metrics, save to SQLite,
    and return a DataFrame of active fantasy players.[web:4]
    """
    sleeper_started = time.perf_counter()
    players = get_players(refresh=refresh)
    performance.record_timing(
        "public_player_sleeper_json_parse",
        (time.perf_counter() - sleeper_started) * 1000,
        category="data",
    )
    normalization_started = time.perf_counter()
    records = []
    for pid, p in players.items():
        rec = normalize_player_record(pid, p)
        if not rec["name"]:
            continue
        if rec["position"] not in FANTASY_POSITIONS:
            continue
        records.append(rec)

    df = pd.DataFrame.from_records(records)
    performance.record_timing(
        "public_player_record_normalization",
        (time.perf_counter() - normalization_started) * 1000,
        category="data",
    )
    if df.empty:
        return empty_players_table()

    eligibility_started = time.perf_counter()
    df = filter_current_fantasy_players(df, surface="public_player_build")
    performance.record_timing(
        "public_player_eligibility",
        (time.perf_counter() - eligibility_started) * 1000,
        category="data",
    )
    if df.empty:
        return empty_players_table()

    df["status"] = df["status"].astype(object)
    df["years_exp"] = df["years_exp"].astype(object)
    df["news_updated"] = df["news_updated"].astype(object)
    df["depth_chart_position"] = df["depth_chart_position"].astype(object)
    df["depth_chart_order"] = df["depth_chart_order"].astype(object)
    df["hashtag"] = df["hashtag"].astype(object)
    df["team_abbr"] = df["team_abbr"].astype(object)
    df["injury_status"] = df["injury_status"].astype(object)

    copy_started = time.perf_counter()
    df = ensure_identity_columns(df)
    performance.record_timing(
        "public_player_identity_copy",
        (time.perf_counter() - copy_started) * 1000,
        category="data",
    )
    # Attach season usage before valuation so production/usage can enter the
    # composite without inventing zeroes when the feed is empty.
    stats_started = time.perf_counter()
    player_stats = get_season_player_stats()
    performance.record_timing(
        "public_player_stats_json_parse",
        (time.perf_counter() - stats_started) * 1000,
        category="data",
    )
    merge_started = time.perf_counter()
    df = attach_player_stats(df, player_stats)
    performance.record_timing(
        "public_player_stats_merge",
        (time.perf_counter() - merge_started) * 1000,
        category="data",
    )
    valuation_started = time.perf_counter()
    df = apply_valuation_model(df)
    performance.record_timing(
        "public_player_value_normalization_and_merge",
        (time.perf_counter() - valuation_started) * 1000,
        category="data",
    )

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    df.to_sql("players", conn, if_exists="replace", index=False)
    conn.close()

    return ensure_identity_columns(df)


def _load_players_without_snapshot(db_path: str) -> pd.DataFrame:
    if not os.path.exists(db_path):
        return ensure_identity_columns(build_players_table(db_path))

    sqlite_started = time.perf_counter()
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query("SELECT * FROM players", conn)
    finally:
        conn.close()
    performance.record_timing(
        "public_player_sqlite_query",
        (time.perf_counter() - sqlite_started) * 1000,
        category="data",
    )

    if df.empty:
        return ensure_identity_columns(build_players_table(db_path, refresh=True))

    required_meta = [
        "status",
        "years_exp",
        "news_updated",
        "depth_chart_position",
        "depth_chart_order",
        "hashtag",
        "team_abbr",
        "injury_status",
        "fantasycalc_value",
        "market_score",
        "age_curve_score",
        "production_score",
        "production_confidence",
        "scarcity_score",
        "role_score",
        "depth_chart_slot",
        "projected_starter",
        "opportunity_label",
        "opportunity_score",
        "opportunity_confidence",
        "opportunity_source_flags",
        "opportunity_explanation",
        "snap_share",
        "rush_share",
        "target_share",
        "route_participation",
        "opportunity_share",
        "workload_trend",
        "injury_risk_score",
        "risk_multiplier",
        "valuation_blend",
    ]
    if any(col not in df.columns for col in required_meta):
        return ensure_identity_columns(build_players_table(db_path, refresh=True))

    if "position" not in df.columns:
        return ensure_identity_columns(build_players_table(db_path, refresh=True))

    for col in required_meta:
        if col not in df.columns:
            df[col] = None

    stats_started = time.perf_counter()
    player_stats = get_season_player_stats()
    performance.record_timing(
        "public_player_stats_json_parse",
        (time.perf_counter() - stats_started) * 1000,
        category="data",
    )
    merge_started = time.perf_counter()
    df = attach_player_stats(df, player_stats)
    performance.record_timing(
        "public_player_stats_merge",
        (time.perf_counter() - merge_started) * 1000,
        category="data",
    )

    normalization_started = time.perf_counter()
    df["injury_level"] = df.apply(
        lambda row: injury_level(row.get("status"), row.get("injury_status")),
        axis=1,
    )
    df["injury_risk_score"] = df.apply(
        lambda row: injury_risk_score(row.get("status"), row.get("injury_status")),
        axis=1,
    )
    df["injury_multiplier"] = df.apply(
        lambda row: injury_multiplier(row.get("status"), row.get("injury_status")),
        axis=1,
    )
    old_risk = pd.to_numeric(df.get("risk_multiplier"), errors="coerce").fillna(1.0)
    old_risk = old_risk.mask(old_risk <= 0, 1.0)
    df["risk_multiplier"] = df.apply(
        lambda row: risk_multiplier(
            row.get("status"),
            row.get("team"),
            row.get("search_rank"),
            row.get("injury_status"),
        ),
        axis=1,
    )
    if "score" in df.columns:
        base_score = pd.to_numeric(df["score"], errors="coerce").fillna(0) / old_risk
        updated_score = (base_score * pd.to_numeric(df["risk_multiplier"], errors="coerce").fillna(1.0)).clip(lower=0)
        df["score"] = updated_score.round().astype(int)
        for col in ["dynasty_score", "value_score"]:
            if col in df.columns:
                df[col] = updated_score.round().astype(int)

    for col in ["dynasty_score", "value_score", "news_factor"]:
        if col not in df.columns:
            if col == "news_factor":
                df[col] = 0.0
            else:
                df[col] = df.get("score", 0)

    performance.record_timing(
        "public_player_normalization",
        (time.perf_counter() - normalization_started) * 1000,
        category="data",
    )
    eligibility_started = time.perf_counter()
    df = annotate_player_eligibility(df)
    performance.record_timing(
        "public_player_eligibility",
        (time.perf_counter() - eligibility_started) * 1000,
        category="data",
    )

    kicker_is_stale = False
    if "position" in df.columns and "search_rank" in df.columns:
        kicker_mask = df["position"].astype(str).str.upper() == "K"
        kicker_ranks = pd.to_numeric(df.loc[kicker_mask, "search_rank"], errors="coerce")
        kicker_valid = kicker_mask & kicker_ranks.lt(UNRANKED_SEARCH_RANK)
        if kicker_valid.any():
            kicker_is_stale = (df.loc[kicker_valid, "value"].fillna(0) == 0).any()

    if (
        "search_rank" not in df.columns
        or df["dynasty_score"].max() <= 100
        or "K" not in df["position"].astype(str).str.upper().unique()
        or kicker_is_stale
    ):
        return ensure_identity_columns(build_players_table(db_path, refresh=True))

    return ensure_identity_columns(df)


def _refresh_risk_adjusted_scores(
    df: pd.DataFrame,
    old_risk: pd.Series,
) -> pd.DataFrame:
    refreshed = df.copy()
    normalized_old_risk = pd.to_numeric(old_risk, errors="coerce").fillna(1.0)
    normalized_old_risk = normalized_old_risk.mask(normalized_old_risk <= 0, 1.0)
    if "score" in refreshed.columns:
        base_score = pd.to_numeric(refreshed["score"], errors="coerce").fillna(0)
        base_score = base_score / normalized_old_risk
        updated_score = (
            base_score
            * pd.to_numeric(
                refreshed.get("risk_multiplier"),
                errors="coerce",
            ).fillna(1.0)
        ).clip(lower=0)
        refreshed["score"] = updated_score.round().astype(int)
        for column in ("dynasty_score", "value_score"):
            if column in refreshed.columns:
                refreshed[column] = updated_score.round().astype(int)
    for column in ("dynasty_score", "value_score", "news_factor"):
        if column not in refreshed.columns:
            refreshed[column] = 0.0 if column == "news_factor" else refreshed.get("score", 0)
    return refreshed


def _load_snapshot_base_frame(db_path: str) -> pd.DataFrame | None:
    if not os.path.exists(db_path):
        return None
    started = time.perf_counter()
    try:
        conn = sqlite3.connect(db_path)
        try:
            frame = pd.read_sql_query("SELECT * FROM players", conn)
        finally:
            conn.close()
    except Exception:
        return None
    performance.record_timing(
        "public_player_snapshot_sqlite_query",
        (time.perf_counter() - started) * 1000,
        category="data",
    )
    return frame if not frame.empty and "player_id" in frame.columns else None


def _load_players_from_snapshot(
    db_path: str,
    source_fingerprint: tuple[tuple[str, bool, int, int], ...],
) -> pd.DataFrame | None:
    started = time.perf_counter()
    snapshot = public_player_snapshot.load_public_player_snapshot(
        db_path,
        source_fingerprint=source_fingerprint,
    )
    if snapshot is None:
        return None
    base = _load_snapshot_base_frame(db_path)
    if base is None:
        public_player_snapshot.invalidate_public_player_snapshot(db_path)
        return None
    base_player_ids = base["player_id"].fillna("").astype(str).reset_index(drop=True)
    snapshot_player_ids = (
        snapshot.frame["player_id"].fillna("").astype(str).reset_index(drop=True)
    )
    if not base_player_ids.equals(snapshot_player_ids):
        public_player_snapshot.invalidate_public_player_snapshot(db_path)
        return None
    old_risk = pd.to_numeric(base.get("risk_multiplier"), errors="coerce").fillna(1.0)
    hydrated = base.copy()
    for column in snapshot.frame.columns:
        if column != "player_id":
            hydrated[column] = snapshot.frame[column].reset_index(drop=True)
    hydrated = _refresh_risk_adjusted_scores(hydrated, old_risk)
    hydrated = annotate_player_eligibility(hydrated)
    hydrated = ensure_identity_columns(hydrated)
    if (
        not snapshot.output_columns
        or any(column not in hydrated.columns for column in snapshot.output_columns)
    ):
        public_player_snapshot.invalidate_public_player_snapshot(db_path)
        return None
    hydrated = hydrated.loc[:, list(snapshot.output_columns)]
    performance.record_timing(
        "public_player_snapshot_load",
        (time.perf_counter() - started) * 1000,
        category="data",
    )
    return hydrated


def _save_players_snapshot(
    db_path: str,
    hydrated: pd.DataFrame,
    source_fingerprint: tuple[tuple[str, bool, int, int], ...],
) -> None:
    started = time.perf_counter()
    try:
        hydration_columns = [
            column
            for column in PUBLIC_PLAYER_SNAPSHOT_HYDRATION_COLUMNS
            if column in hydrated.columns
        ]
        snapshot = public_player_snapshot.build_public_player_snapshot(
            hydrated,
            hydration_columns=hydration_columns,
        )
        metadata = public_player_snapshot.save_public_player_snapshot(
            db_path,
            snapshot,
            source_fingerprint=source_fingerprint,
            output_columns=hydrated.columns,
        )
        performance.record_timing(
            "public_player_snapshot_build",
            (time.perf_counter() - started) * 1000,
            category="data",
            result_size=int(metadata.get("row_count") or 0),
        )
    except Exception:
        public_player_snapshot.invalidate_public_player_snapshot(db_path)


def _load_players_uncached(db_path: str) -> pd.DataFrame:
    source_fingerprint = public_player_source_fingerprint(db_path)
    snapshot_frame = _load_players_from_snapshot(db_path, source_fingerprint)
    if snapshot_frame is not None:
        return snapshot_frame
    hydrated = _load_players_without_snapshot(db_path)
    refreshed_fingerprint = public_player_source_fingerprint(db_path)
    _save_players_snapshot(db_path, hydrated, refreshed_fingerprint)
    return hydrated


def _public_file_fingerprint(path: str) -> tuple[bool, int, int]:
    try:
        stat = os.stat(path)
        return True, int(stat.st_size), int(stat.st_mtime_ns)
    except OSError:
        return False, 0, 0


def public_player_source_fingerprint(db_path: str) -> tuple[tuple[str, bool, int, int], ...]:
    """Fingerprint public-only inputs without user, league, roster, or auth state."""
    stats_path = sleeper_module.PLAYER_STATS_CACHE_TEMPLATE.format(
        season=sleeper_module.default_player_stats_season()
    )
    sources = (
        ("sqlite", db_path),
        ("sleeper_metadata", sleeper_module.PLAYERS_CACHE_PATH),
        ("fantasycalc", "data/fantasycalc_values.csv"),
        ("season_stats", stats_path),
    )
    return tuple(
        (category, *_public_file_fingerprint(path))
        for category, path in sources
    )


def public_player_fingerprint_category(
    fingerprint: tuple[tuple[str, bool, int, int], ...],
) -> str:
    digest = hashlib.sha256(repr(fingerprint).encode("utf-8")).hexdigest()[:8]
    present = sum(1 for _, exists, _, _ in fingerprint if exists)
    return f"pub{present}of{len(fingerprint)}_{digest}"


@st.cache_data(show_spinner=False, max_entries=4)
def _cached_public_players(
    db_path: str,
    source_fingerprint: tuple[tuple[str, bool, int, int], ...],
) -> tuple[pd.DataFrame, dict[str, int]]:
    del source_fingerprint
    created_ns = time.time_ns()
    frame = _load_players_uncached(db_path)
    return frame, {
        "created_ns": created_ns,
        "row_count": int(len(frame)),
        "memory_bytes": int(frame.memory_usage(index=True, deep=True).sum()),
    }


def clear_public_player_cache() -> None:
    _cached_public_players.clear()


def load_players(db_path: str) -> pd.DataFrame:
    """Return a mutation-isolated cached normalized public-player frame."""
    fingerprint = public_player_source_fingerprint(db_path)
    started_ns = time.time_ns()
    started = time.perf_counter()
    frame, metadata = _cached_public_players(db_path, fingerprint)
    elapsed_ms = (time.perf_counter() - started) * 1000
    cache_status = (
        "hit"
        if int(metadata.get("created_ns") or 0) < started_ns
        else "miss"
    )
    performance.record_timing(
        "public_player_cache_retrieval",
        elapsed_ms,
        category="data",
    )
    performance.record_cache_event(
        "public_player_data",
        cache_status,
        elapsed_ms=elapsed_ms,
        result_size=int(metadata.get("row_count") or len(frame)),
        result_memory_bytes=int(metadata.get("memory_bytes") or 0),
        fingerprint_category=public_player_fingerprint_category(fingerprint),
        invalidation_reason=(
            "source_fingerprint_changed_or_process_cold"
            if cache_status == "miss"
            else ""
        ),
    )
    return frame


def is_probably_stale_free_agent(row) -> bool:
    """Identify free agents that are likely stale/retired and should be deprioritized."""
    if not player_eligibility(row)["eligible"]:
        return True
    position = str(row.get("position") or "").upper()
    if position == "K":
        return False

    status = str(row.get("status") or "").strip().lower()
    if status and status not in {
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
        "practice squad",
    }:
        return True

    age = row.get("age")
    try:
        age = float(age) if age is not None else None
    except Exception:
        age = None

    if age is not None and age >= 40:
        return True

    search_rank = row.get("search_rank")
    try:
        search_rank = int(float(search_rank))
    except Exception:
        search_rank = None

    news_updated = row.get("news_updated")
    if news_updated is not None:
        try:
            last_updated = float(news_updated) / 1000.0
        except Exception:
            last_updated = None
        if last_updated is not None and time.time() - last_updated > 365 * 24 * 60 * 60:
            if search_rank is None or search_rank >= 150:
                return True
            if age is not None and age >= 30 and search_rank >= 120:
                return True
            depth_position = str(row.get("depth_chart_position") or "").strip()
            if not depth_position and search_rank is not None and search_rank >= 100:
                return True

    years_exp = row.get("years_exp")
    try:
        years_exp = int(years_exp) if years_exp is not None else None
    except Exception:
        years_exp = None
    if years_exp is not None and years_exp >= 12 and age is not None and age >= 35:
        if search_rank is None or search_rank >= 120:
            return True

    return False
