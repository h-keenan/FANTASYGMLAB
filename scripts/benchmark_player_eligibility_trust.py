"""Measure the public-player eligibility/Trust boundary without changing production."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import sys
import time
from typing import Any
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules import public_player_snapshot, rankings
from modules.player_eligibility import (
    EnforcementLevel,
    _trust_validation_fingerprint,
    annotate_player_eligibility,
    player_eligibility,
)
from modules.player_identity import ensure_identity_columns
from modules.trust_enforcement import enforce_player_record


def _timed(call):
    started = time.perf_counter()
    value = call()
    return value, (time.perf_counter() - started) * 1000


def _summary(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    p95_index = max(0, min(len(ordered) - 1, int(len(ordered) * 0.95 + 0.999) - 1))
    return {
        "min_ms": round(ordered[0], 2),
        "mean_ms": round(statistics.fmean(ordered), 2),
        "median_ms": round(statistics.median(ordered), 2),
        "directional_p95_ms": round(ordered[p95_index], 2),
        "max_ms": round(ordered[-1], 2),
    }


def decompose_annotation(
    players: pd.DataFrame,
    *,
    now: datetime,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Reproduce annotate_player_eligibility while timing its semantic phases."""

    phases: dict[str, float] = {}
    annotated, phases["dataframe_copy_ms"] = _timed(players.copy)
    rows = list(annotated.iterrows())

    fingerprints, phases["trust_fingerprint_preparation_ms"] = _timed(
        lambda: [
            _trust_validation_fingerprint(row, now=now)
            for _, row in rows
        ]
    )
    evaluations, phases["eligibility_derivation_ms"] = _timed(
        lambda: [player_eligibility(row, now=now) for _, row in rows]
    )

    def prepare_trust():
        player_ids = annotated.get(
            "player_id",
            pd.Series("", index=annotated.index, dtype="object"),
        ).fillna("").astype(str).str.strip()
        duplicate_ids = frozenset(
            player_id
            for player_id, count in player_ids.value_counts().items()
            if player_id and int(count) > 1
        )
        canonical_ids = frozenset(player_id for player_id in player_ids if player_id)
        return duplicate_ids, canonical_ids

    trust_inputs, phases["trust_identity_preparation_ms"] = _timed(prepare_trust)
    duplicate_ids, canonical_ids = trust_inputs
    enforcement, phases["trust_enforcement_ms"] = _timed(
        lambda: [
            enforce_player_record(
                row,
                eligible=bool(evaluation["eligible"]),
                eligibility_reason=str(evaluation["reason"]),
                duplicate_ids=duplicate_ids,
                canonical_player_ids=canonical_ids,
            )
            for (_, row), evaluation in zip(rows, evaluations)
        ]
    )

    def assign_results():
        annotated["is_current_fantasy_eligible"] = [
            bool(evaluation["eligible"])
            and result.level is not EnforcementLevel.BLOCKED
            for evaluation, result in zip(evaluations, enforcement)
        ]
        annotated["player_eligibility_reason"] = [
            str(evaluation["reason"]) for evaluation in evaluations
        ]
        annotated["trust_enforcement"] = [
            result.level.value for result in enforcement
        ]
        annotated["trust_evidence_confidence"] = [
            result.evidence.confidence.value for result in enforcement
        ]
        annotated["trust_block_reason"] = [
            result.reasons[0]
            if result.level is EnforcementLevel.BLOCKED and result.reasons
            else ""
            for result in enforcement
        ]
        annotated["trust_validation_fingerprint"] = fingerprints
        return annotated

    _, phases["result_assignment_ms"] = _timed(assign_results)
    # Production has no distinct post-derivation eligibility-validation pass.
    phases["eligibility_validation_ms"] = 0.0
    phases["trust_preparation_ms"] = (
        phases["trust_fingerprint_preparation_ms"]
        + phases["trust_identity_preparation_ms"]
    )
    phases["annotation_total_ms"] = round(
        sum(
            phases[name]
            for name in (
                "dataframe_copy_ms",
                "eligibility_derivation_ms",
                "trust_fingerprint_preparation_ms",
                "trust_identity_preparation_ms",
                "trust_enforcement_ms",
                "result_assignment_ms",
            )
        ),
        6,
    )
    return annotated, phases


def _snapshot_input(db_path: str) -> tuple[pd.DataFrame, tuple[str, ...], dict[str, float]]:
    fingerprint = rankings.public_player_source_fingerprint(db_path)
    deserialize_samples: list[float] = []
    original_read_pickle = pd.read_pickle

    def timed_read_pickle(*args, **kwargs):
        result, elapsed = _timed(lambda: original_read_pickle(*args, **kwargs))
        deserialize_samples.append(elapsed)
        return result

    with patch("modules.public_player_snapshot.pd.read_pickle", side_effect=timed_read_pickle):
        snapshot, total_ms = _timed(
            lambda: public_player_snapshot.load_public_player_snapshot(
                db_path,
                source_fingerprint=fingerprint,
            )
        )
    if snapshot is None:
        raise RuntimeError("valid public-player snapshot is required")
    deserialize_ms = sum(deserialize_samples)
    return snapshot.frame, snapshot.output_columns, {
        "snapshot_load_total_ms": total_ms,
        "snapshot_deserialization_ms": deserialize_ms,
        "snapshot_validation_and_isolation_ms": max(0.0, total_ms - deserialize_ms),
    }


def _base_with_snapshot_hydration(db_path: str, snapshot: pd.DataFrame) -> pd.DataFrame:
    base = rankings._load_snapshot_base_frame(db_path)
    if base is None:
        raise RuntimeError("public-player SQLite base is unavailable")
    old_risk = pd.to_numeric(base.get("risk_multiplier"), errors="coerce").fillna(1.0)
    hydrated = base.copy()
    for column in snapshot.columns:
        if column != "player_id":
            hydrated[column] = snapshot[column].reset_index(drop=True)
    return rankings._refresh_risk_adjusted_scores(hydrated, old_risk)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/players.db")
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("-o", "--output")
    args = parser.parse_args()
    if args.samples < 10:
        raise SystemExit("--samples must be at least 10")

    db_path = str(Path(args.db))
    fingerprint = rankings.public_player_source_fingerprint(db_path)
    if public_player_snapshot.load_public_player_snapshot(
        db_path,
        source_fingerprint=fingerprint,
    ) is None:
        rankings.clear_public_player_cache()
        rankings.load_players(db_path)

    now = datetime.now(timezone.utc)
    phase_samples: dict[str, list[float]] = {}
    reference: pd.DataFrame | None = None
    output_columns: tuple[str, ...] = ()
    memory_bytes = 0
    snapshot_bytes = 0

    for _ in range(args.samples):
        snapshot, output_columns, snapshot_phases = _snapshot_input(db_path)
        hydrated = _base_with_snapshot_hydration(db_path, snapshot)
        decomposed, phases = decompose_annotation(hydrated, now=now)
        expected = annotate_player_eligibility(hydrated, now=now)
        pd.testing.assert_frame_equal(expected, decomposed, check_dtype=True)

        def restore_schema():
            isolated = ensure_identity_columns(decomposed)
            return isolated.loc[:, list(output_columns)]

        restored, final_ms = _timed(restore_schema)
        phases.update(snapshot_phases)
        phases["final_copy_schema_restoration_ms"] = final_ms
        phases["measured_loader_boundary_ms"] = (
            snapshot_phases["snapshot_load_total_ms"]
            + phases["annotation_total_ms"]
            + final_ms
        )
        for name, elapsed in phases.items():
            phase_samples.setdefault(name, []).append(float(elapsed))
        if reference is None:
            reference = restored
        else:
            pd.testing.assert_frame_equal(reference, restored, check_dtype=True)
        memory_bytes = int(restored.memory_usage(index=True, deep=True).sum())
        data_path, metadata_path = public_player_snapshot.snapshot_paths(db_path)
        snapshot_bytes = int(data_path.stat().st_size + metadata_path.stat().st_size)

    payload: dict[str, Any] = {
        "benchmark": "public_player_eligibility_trust",
        "environment": "controlled_local_not_production",
        "samples": args.samples,
        "rows": int(len(reference)) if reference is not None else 0,
        "columns": int(len(reference.columns)) if reference is not None else 0,
        "hydrated_memory_bytes": memory_bytes,
        "snapshot_bytes": snapshot_bytes,
        "exact_annotation_equivalence": True,
        "repeated_load_equivalence": True,
        "phases": {
            name: _summary(samples)
            for name, samples in sorted(phase_samples.items())
        },
    }
    serialized = json.dumps(payload, sort_keys=True, indent=2)
    if args.output:
        Path(args.output).write_text(serialized + "\n", encoding="utf-8")
    print("PUBLIC_PLAYER_ELIGIBILITY_TRUST_BENCHMARK " + json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
