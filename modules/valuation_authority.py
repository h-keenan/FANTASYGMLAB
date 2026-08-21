"""Canonical provenance contract for values exposed to actionable workflows."""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd


VALUATION_AUTHORITY_CONTRACT_VERSION = "valuation-authority-v1"
STATUS_COLUMN = "valuation_authority_status"
SOURCE_COLUMN = "valuation_authority_source"
AUTHORITATIVE_COLUMN = "valuation_is_authoritative"
TRADE_ELIGIBLE_COLUMN = "valuation_trade_eligible"

PROVIDER_BACKED = "canonical_provider_backed"
MODEL_DERIVED = "canonical_model_derived"
RECONCILED_UNMODELED = "reconciled_unmodeled"

_LEGACY_RECONCILED_BLEND = "Sleeper rank + age/VORP/role"
_PENDING_BLEND = "Canonical valuation pending; Sleeper rank retained as identity input"


def _legacy_unmodeled_mask(frame: pd.DataFrame) -> pd.Series:
    """Identify rows #375 promoted from identity rank without model execution."""

    index = frame.index
    fantasycalc = pd.to_numeric(frame.get("fantasycalc_value", pd.Series(0, index=index)), errors="coerce").fillna(0)
    blend = frame.get("valuation_blend", pd.Series("", index=index)).fillna("").astype(str)
    role_missing = frame.get("role_score", pd.Series(pd.NA, index=index)).isna()
    opportunity_missing = frame.get("opportunity_label", pd.Series(pd.NA, index=index)).isna()
    return fantasycalc.le(0) & blend.eq(_LEGACY_RECONCILED_BLEND) & role_missing & opportunity_missing


def annotate_valuation_authority(players: pd.DataFrame) -> pd.DataFrame:
    """Annotate valuation provenance and fail unmodeled identities closed.

    Eligibility is intentionally preserved. Only actionable valuation fields are
    withheld until the canonical valuation model has produced a result.
    """

    work = players.copy()
    if work.empty:
        return work
    explicit_unmodeled = (
        work.get(STATUS_COLUMN, pd.Series("", index=work.index))
        .fillna("")
        .astype(str)
        .eq(RECONCILED_UNMODELED)
    )
    unmodeled = explicit_unmodeled | _legacy_unmodeled_mask(work)
    fantasycalc = pd.to_numeric(
        work.get("fantasycalc_value", pd.Series(0, index=work.index)), errors="coerce"
    ).fillna(0)

    work[STATUS_COLUMN] = MODEL_DERIVED
    work.loc[fantasycalc.gt(0), STATUS_COLUMN] = PROVIDER_BACKED
    work.loc[unmodeled, STATUS_COLUMN] = RECONCILED_UNMODELED
    work[SOURCE_COLUMN] = "canonical_model"
    work.loc[fantasycalc.gt(0), SOURCE_COLUMN] = "fantasycalc_plus_canonical_model"
    work.loc[unmodeled, SOURCE_COLUMN] = "sleeper_identity_only"
    work[AUTHORITATIVE_COLUMN] = ~unmodeled
    work[TRADE_ELIGIBLE_COLUMN] = ~unmodeled

    for column in ("market_score", "score", "dynasty_score", "value_score", "rebuild_score"):
        if column in work.columns:
            work.loc[unmodeled, column] = 0
    if "valuation_blend" in work.columns:
        work.loc[unmodeled, "valuation_blend"] = _PENDING_BLEND
    return work


def valuation_is_trade_eligible(asset: Mapping[str, Any]) -> bool:
    """Reject explicitly unmodeled assets while preserving legacy callers."""

    value = asset.get(TRADE_ELIGIBLE_COLUMN)
    if value is None:
        return True
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    return bool(value)
