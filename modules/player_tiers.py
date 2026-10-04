from __future__ import annotations

import pandas as pd

PLAYER_TIERS = (
    "Elite",
    "Star",
    "Core Starter",
    "Starter",
    "Contributor",
    "Depth",
    "Developmental",
)

DEFAULT_PLAYER_TIER_PROFILE = {
    "position_specific": False,
    "thresholds": (
        ("Elite", 0.992),
        ("Star", 0.975),
        ("Core Starter", 0.94),
        ("Starter", 0.84),
        ("Contributor", 0.66),
        ("Depth", 0.38),
        ("Developmental", 0.0),
    ),
    "weights": {
        "primary": 0.82,
        "market": 0.10,
        "scarcity": 0.08,
    },
}

PLAYER_TIER_PROFILES = {
    "default": DEFAULT_PLAYER_TIER_PROFILE,
}

TIER_COLUMN_BY_SCORE_FIELD = {
    "value_score": "value_tier",
    "dynasty_score": "dynasty_tier",
    "rebuild_score": "rebuild_tier",
}

# A player rankings.py's own opportunity/usage signal has already judged to
# have no live current role (``workload_trend == "Blocked"`` — the same
# column modules.waivers_ui.rank_priority_add_candidates gates Priority
# Adds on, for the identical reason) must never show as "Starter" tier or
# above. value_score/dynasty_score are long-horizon (draft capital, age
# curve, market) and can stay high for a young former-high-pick player long
# after his real-world role has collapsed — e.g. Chimere Dike (2026 WR,
# TEN): 7% snap share, 2 targets in 3 games, workload_trend "Blocked", yet
# high enough dynasty/value-score percentile to clear the "Starter"
# threshold below purely on legacy draft-capital/market value. Cap any
# blocked-role player's tier at "Depth" regardless of score percentile —
# same philosophy as the waiver gate, applied at the tier-tag layer instead
# of the waiver-ranking layer. A player whose opportunity reopens is
# already relabeled out of "Blocked" upstream in rankings.py, so this does
# not punish real opportunity swings, only players rankings.py itself
# judged to have no current role.
BLOCKED_ROLE_TIER_CAP = "Depth"
_TIER_RANK = {label: index for index, label in enumerate(PLAYER_TIERS)}


def score_field_tier_column(score_field: str) -> str:
    return TIER_COLUMN_BY_SCORE_FIELD.get(str(score_field or "").strip(), "player_tier")


def _safe_series(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").fillna(default).astype("float64")


def _normalized_strength(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").fillna(0).astype("float64")
    if values.empty or float(values.max()) <= 0:
        return pd.Series(0.0, index=values.index, dtype="float64")
    if values.nunique(dropna=True) <= 1:
        return pd.Series(1.0, index=values.index, dtype="float64")
    return values.rank(method="average", pct=True, ascending=True).astype("float64")


def _tier_labels_from_strength(
    strength: pd.Series,
    thresholds: tuple[tuple[str, float], ...],
) -> pd.Series:
    labels = pd.Series("Developmental", index=strength.index, dtype="object")
    for label, minimum in reversed(thresholds):
        labels = labels.mask(strength >= float(minimum), label)
    return labels


def _blocked_role_mask(df: pd.DataFrame) -> pd.Series | None:
    if "workload_trend" not in df.columns:
        return None
    normalized = df["workload_trend"].fillna("").astype(str).str.strip().str.casefold()
    blocked = normalized.eq("blocked")
    return blocked if bool(blocked.any()) else None


def _cap_blocked_role_tier(tier_labels: pd.Series, blocked: pd.Series | None) -> pd.Series:
    """Never let a role-blocked (no live current usage) player outrank
    ``BLOCKED_ROLE_TIER_CAP`` — see that constant's docstring for why."""

    if blocked is None:
        return tier_labels
    cap_rank = _TIER_RANK[BLOCKED_ROLE_TIER_CAP]
    ranks = tier_labels.map(_TIER_RANK).fillna(cap_rank)
    return tier_labels.mask(blocked & (ranks < cap_rank), BLOCKED_ROLE_TIER_CAP)


def assign_player_tiers(
    df: pd.DataFrame,
    primary_score_field: str = "dynasty_score",
    profile_name: str = "default",
    position_specific: bool | None = None,
) -> pd.DataFrame:
    if df.empty:
        return df

    profile = dict(PLAYER_TIER_PROFILES.get(profile_name, DEFAULT_PLAYER_TIER_PROFILE))
    if position_specific is None:
        position_specific = bool(profile.get("position_specific", False))
    # Reserved for future per-position tiering without changing the public API.
    _ = position_specific

    thresholds = tuple(profile.get("thresholds", DEFAULT_PLAYER_TIER_PROFILE["thresholds"]))
    weights = dict(profile.get("weights", DEFAULT_PLAYER_TIER_PROFILE["weights"]))

    out = df.copy()
    market_strength = _normalized_strength(_safe_series(out, "market_score"))
    scarcity_strength = _normalized_strength(_safe_series(out, "scarcity_score"))
    blocked_role = _blocked_role_mask(out)

    computed_columns: list[str] = []
    for score_field, tier_column in TIER_COLUMN_BY_SCORE_FIELD.items():
        if score_field not in out.columns:
            continue
        primary_scores = _safe_series(out, score_field)
        primary_strength = _normalized_strength(primary_scores)
        blended_strength = (
            primary_strength * float(weights.get("primary", 0.82))
            + market_strength * float(weights.get("market", 0.10))
            + scarcity_strength * float(weights.get("scarcity", 0.08))
        ).clip(lower=0.0, upper=1.0)
        blended_strength = blended_strength.where(primary_scores.gt(0), 0.0)
        tier_labels = _tier_labels_from_strength(blended_strength, thresholds)
        out[tier_column] = _cap_blocked_role_tier(tier_labels, blocked_role)
        computed_columns.append(tier_column)

    preferred_column = score_field_tier_column(primary_score_field)
    if preferred_column in out.columns:
        out["player_tier"] = out[preferred_column]
    elif computed_columns:
        out["player_tier"] = out[computed_columns[0]]
    else:
        out["player_tier"] = "Developmental"

    return out
