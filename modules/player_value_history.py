"""Rolling one-step valuation history for "what changed and why" exports.

Captures each player's composite score (``dynasty_score``/``score``) plus its
component sub-scores (``market_score``, ``age_curve_score``, ``role_score``,
``scarcity_score``, ``opportunity_score``, ``production_score``) every time
the source players.db refreshes, and diffs the new snapshot against the prior
one to report, per player, how much the overall score moved and which
component moved the most.

This is modeled on ``public_player_snapshot.py``'s fingerprint-gated
single-slot comparison pattern (reusing
``rankings.public_player_source_fingerprint`` and
``public_player_snapshot.source_fingerprint_digest`` directly rather than
reinventing fingerprinting), but it is deliberately a SEPARATE side-store.
``public_player_snapshot.py``'s contract explicitly forbids persisting
valuation/score columns (``FORBIDDEN_SNAPSHOT_COLUMNS`` includes
``market_score``, ``age_curve_score``, ``role_score``, ``dynasty_score``,
``score``, ...) because that snapshot exists only for deterministic
public-player *identity* hydration, not valuation. Valuation history is a
different concern for a different consumer (service-to-service exports —
see ``services/fantasy_content.py``), so it gets its own file next to
players.db instead of weakening that contract.

The residual ("none of the six additive components explain this") fallback
is only ever labeled "Injury or availability risk" when a real
injury/availability signal from ``rankings.py`` (``risk_multiplier``,
``non_injury_risk_multiplier``, ``injury_risk_score``) actually corroborates
it; otherwise it is labeled the honest, generic "Other factors" — see
``_risk_signal_changed``. Every returned change also carries
``snapshot_refreshed_at``, the timestamp of the valuation snapshot itself
(reusing the same fingerprint-gated ``captured_at`` this module already
persists), so a downstream consumer of ``/v1/content/feed`` can distinguish
"when the snapshot was taken" from "whenever I happened to poll the feed".
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from modules import public_player_snapshot, rankings


VALUE_HISTORY_SCHEMA_VERSION = 1

# Same composite weights rankings.compose_composite_score() uses, referenced
# by value rather than hard-coded a second time so a weight tuning there is
# automatically reflected in "why did this change" here.
_COMPONENT_WEIGHTS: dict[str, float] = {
    "market_score": rankings.COMPOSITE_WEIGHT_MARKET,
    "age_curve_score": rankings.COMPOSITE_WEIGHT_AGE,
    "production_score": rankings.COMPOSITE_WEIGHT_PRODUCTION,
    "scarcity_score": rankings.COMPOSITE_WEIGHT_SCARCITY,
    "role_score": rankings.COMPOSITE_WEIGHT_ROLE,
    "opportunity_score": rankings.COMPOSITE_WEIGHT_OPPORTUNITY,
}

RISK_DRIVER = "risk"
OTHER_DRIVER = "other"

_DRIVER_LABELS: dict[str, str] = {
    "market_score": "Market value",
    "age_curve_score": "Age-curve adjustment",
    "production_score": "On-field production",
    "scarcity_score": "Positional scarcity",
    "role_score": "Depth-chart role",
    "opportunity_score": "Opportunity/role outlook",
    RISK_DRIVER: "Injury or availability risk",
    OTHER_DRIVER: "Other factors",
}

_SCORE_COLUMN_CANDIDATES = ("dynasty_score", "score")

# Real injury/availability signals rankings.py already derives from each
# player's live ``status``/``injury_status`` (see
# rankings.apply_injury_risk_fields(), rankings.risk_multiplier(),
# rankings.non_injury_risk_multiplier()) -- captured alongside the six
# additive components solely so the residual-attribution fallback below can
# check whether an actual injury/availability input moved, rather than
# inferring "injury" purely from an unexplained score residual.
_CORROBORATION_COLUMNS: tuple[str, ...] = (
    "risk_multiplier",
    "non_injury_risk_multiplier",
    "injury_risk_score",
)
_CORROBORATION_EPSILON = 1e-6


def history_path(db_path: str | Path) -> Path:
    stem = Path(db_path).with_suffix("")
    return Path(f"{stem}.value-history.json")


def _score_column(frame: pd.DataFrame) -> str:
    for column in _SCORE_COLUMN_CANDIDATES:
        if column in frame.columns:
            return column
    return "score"


def capture_snapshot(frame: pd.DataFrame) -> dict[str, dict[str, float]]:
    """``{player_id: {"score": ..., <component columns>: ...}}`` from a loaded frame."""

    if frame is None or frame.empty or "player_id" not in frame.columns:
        return {}
    score_column = _score_column(frame)
    component_columns = [c for c in _COMPONENT_WEIGHTS if c in frame.columns]
    # Corroboration-only columns: carried through the snapshot so a later
    # diff can confirm (or fail to confirm) an actual injury/availability
    # move, but never added to _COMPONENT_WEIGHTS/tracked_total -- they are
    # not additive composite inputs.
    corroboration_columns = [c for c in _CORROBORATION_COLUMNS if c in frame.columns]
    all_columns = [*component_columns, *corroboration_columns]
    columns = [score_column, *all_columns] if score_column in frame.columns else all_columns
    if not columns:
        return {}
    work = frame.loc[:, ["player_id", *dict.fromkeys(columns)]].copy()
    work["player_id"] = work["player_id"].fillna("").astype(str)
    work = work[work["player_id"].ne("")]
    snapshot: dict[str, dict[str, float]] = {}
    for record in work.to_dict("records"):
        player_id = record.pop("player_id")
        clean: dict[str, float] = {}
        for key, value in record.items():
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                numeric = 0.0
            clean["score" if key == score_column else key] = numeric
        snapshot[player_id] = clean
    return snapshot


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f"{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def _load_state(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if int(payload.get("schema_version") or 0) != VALUE_HISTORY_SCHEMA_VERSION:
            return None
        if not isinstance(payload.get("snapshot"), dict) or not isinstance(payload.get("changes"), list):
            return None
        return payload
    except (OSError, ValueError, TypeError):
        return None


def _risk_signal_changed(previous: Mapping[str, float], current: Mapping[str, float]) -> bool:
    """True only when a real injury/availability input actually moved.

    Checks the same risk/injury fields rankings.compose_composite_score()
    derives from each player's live ``status``/``injury_status``
    (``risk_multiplier``, ``non_injury_risk_multiplier``,
    ``injury_risk_score`` -- see ``_CORROBORATION_COLUMNS``). If those
    columns were not captured in the snapshot (older snapshot predating
    this change, or a caller-supplied frame missing them), both sides
    default to ``0.0`` and this correctly returns ``False`` -- "no signal
    available" and "signal available but unchanged" are both treated as
    "cannot corroborate injury/availability", never as confirmation.
    """

    for column in _CORROBORATION_COLUMNS:
        prev_value = float(previous.get(column, 0.0))
        curr_value = float(current.get(column, 0.0))
        if abs(curr_value - prev_value) > _CORROBORATION_EPSILON:
            return True
    return False


def _driver_for_player(
    previous: Mapping[str, float], current: Mapping[str, float]
) -> tuple[str, float]:
    """Largest-magnitude weighted component contribution.

    The remainder (rounding plus anything not captured by a tracked
    additive sub-score) is attributed to ``risk`` -- "Injury or
    availability risk" -- ONLY when a real injury/availability signal
    (see ``_risk_signal_changed``) actually corroborates that read.
    Labeling an unexplained residual as "injury" without that corroboration
    would assert a specific causal claim the data does not support, so an
    uncorroborated residual is attributed to ``other`` -- "Other factors"
    -- an honest "we don't know what explains this" instead.
    """

    best_key = RISK_DRIVER
    best_contribution = 0.0
    tracked_total = 0.0
    for column, weight in _COMPONENT_WEIGHTS.items():
        prev_value = float(previous.get(column, 0.0))
        curr_value = float(current.get(column, 0.0))
        contribution = (curr_value - prev_value) * weight
        tracked_total += contribution
        if abs(contribution) > abs(best_contribution):
            best_contribution = contribution
            best_key = column
    score_delta = float(current.get("score", 0.0)) - float(previous.get("score", 0.0))
    residual = score_delta - tracked_total
    if abs(residual) > abs(best_contribution):
        best_contribution = residual
        best_key = RISK_DRIVER if _risk_signal_changed(previous, current) else OTHER_DRIVER
    return best_key, best_contribution


def diff_snapshots(
    previous: Mapping[str, Mapping[str, float]],
    current: Mapping[str, Mapping[str, float]],
) -> list[dict[str, Any]]:
    """Per-player overall-score delta plus a structured "why" since ``previous``.

    Players absent from ``previous`` (new to the pool) and players with no
    score movement are omitted — there is nothing to explain yet. Sorted by
    the largest absolute delta first, then ``player_id`` for determinism.
    """

    changes: list[dict[str, Any]] = []
    for player_id, current_components in current.items():
        previous_components = previous.get(player_id)
        if previous_components is None:
            continue
        previous_score = float(previous_components.get("score", 0.0))
        current_score = float(current_components.get("score", 0.0))
        delta = current_score - previous_score
        if delta == 0:
            continue
        driver_key, contribution = _driver_for_player(previous_components, current_components)
        direction = "increased" if contribution >= 0 else "decreased"
        driver_label = _DRIVER_LABELS.get(driver_key, "Valuation inputs")
        rounded_delta = int(round(delta))
        reason = (
            f"{driver_label} {direction}, moving the overall score "
            f"{'up' if rounded_delta > 0 else 'down'} {abs(rounded_delta)} point"
            f"{'s' if abs(rounded_delta) != 1 else ''} since the last refresh."
        )
        changes.append(
            {
                "player_id": player_id,
                "previous_score": int(round(previous_score)),
                "current_score": int(round(current_score)),
                "delta": rounded_delta,
                "driver_factor": driver_key,
                "driver_label": driver_label,
                "reason": reason,
            }
        )
    changes.sort(key=lambda row: (-abs(row["delta"]), row["player_id"]))
    return changes


def _with_snapshot_refreshed_at(
    changes: list[dict[str, Any]], captured_at: Any
) -> list[dict[str, Any]]:
    """Stamp each change with when its underlying snapshot was captured.

    ``captured_at`` comes from the same fingerprint-gated state this module
    already persists on every real refresh (see ``_atomic_write_json``
    above) -- it is the moment the *valuation snapshot* was taken, not
    "now". Reusing it (rather than a fresh ``datetime.now()`` here) is what
    lets a downstream consumer tell a snapshot refresh apart from whenever
    *they* happened to poll ``/v1/content/feed``: repeated feed reads
    between refreshes carry the same ``snapshot_refreshed_at`` value, and it
    only advances when players.db actually refreshes.
    """

    stamp = captured_at if isinstance(captured_at, str) and captured_at else None
    return [{**row, "snapshot_refreshed_at": stamp} for row in changes]


def value_changes_since_last_refresh(
    db_path: str | Path,
    frame: pd.DataFrame,
    *,
    limit: int = 40,
) -> list[dict[str, Any]]:
    """Overall-score deltas plus a structured reason, computed once per refresh.

    Gated on the same public-source fingerprint the rest of the public
    hydration pipeline uses (``rankings.public_player_source_fingerprint``):
    repeated calls between refreshes return the same cached diff instead of
    comparing a snapshot against itself (which would silently erase the
    reportable change after the first post-refresh call). The very first call
    for a given ``db_path`` has nothing to diff against and returns ``[]``
    while it captures the initial baseline.

    Fail-neutral: returns ``[]`` on any unexpected shape or I/O failure,
    never raises — this backs a read-only external export and must not take
    the feed down.
    """

    try:
        path = history_path(db_path)
        current_snapshot = capture_snapshot(frame)
        if not current_snapshot:
            return []
        fingerprint_digest = public_player_snapshot.source_fingerprint_digest(
            rankings.public_player_source_fingerprint(str(db_path))
        )
        state = _load_state(path)
        if state is not None and state.get("fingerprint") == fingerprint_digest:
            cached_changes = state.get("changes")
            if not isinstance(cached_changes, list):
                return []
            return _with_snapshot_refreshed_at(
                cached_changes[: max(0, int(limit))], state.get("captured_at")
            )

        previous_snapshot = state.get("snapshot") if state else {}
        changes = diff_snapshots(previous_snapshot or {}, current_snapshot)
        captured_at = datetime.now(timezone.utc).isoformat()
        _atomic_write_json(
            path,
            {
                "schema_version": VALUE_HISTORY_SCHEMA_VERSION,
                "fingerprint": fingerprint_digest,
                "captured_at": captured_at,
                "snapshot": current_snapshot,
                "changes": changes,
            },
        )
        return _with_snapshot_refreshed_at(changes[: max(0, int(limit))], captured_at)
    except Exception:
        return []
