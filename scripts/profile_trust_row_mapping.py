"""Profile row construction alternatives for dynamic player Trust annotation."""

from __future__ import annotations

import argparse
import cProfile
from datetime import datetime, timezone
import json
from pathlib import Path, PureWindowsPath
import pstats
import statistics
import sys
import time
import tracemalloc
from typing import Any, Callable, Mapping

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules import trust_engine
from modules.player_eligibility import (
    TRUST_ANNOTATION_COLUMNS,
    _trust_validation_fingerprint,
    annotate_player_eligibility,
    eligibility_diagnostics,
    player_eligibility,
)
from modules.player_identity import ensure_identity_columns
from modules.trust_enforcement import EnforcementLevel, enforce_player_record
from scripts.benchmark_player_eligibility_trust import (
    _base_with_snapshot_hydration,
    _snapshot_input,
)
from scripts.profile_trust_enforcement import _load_real_frame


NOW = datetime(2026, 7, 30, tzinfo=timezone.utc)


def _safe_location(filename: str, lineno: int) -> str:
    windows_path = PureWindowsPath(filename)
    path = Path(filename)
    if not path.is_absolute() and windows_path.is_absolute():
        return f"{windows_path.name}:{lineno}"
    try:
        relative = path.resolve().relative_to(Path.cwd().resolve())
        return f"./{relative.as_posix()}:{lineno}"
    except (OSError, ValueError):
        name = windows_path.name if "\\" in filename else path.name
        return f"{name}:{lineno}"


def _finish_annotation(
    annotated: pd.DataFrame,
    rows: list[Mapping[str, Any]],
    *,
    now: datetime,
) -> pd.DataFrame:
    fingerprints = [_trust_validation_fingerprint(row, now=now) for row in rows]
    if TRUST_ANNOTATION_COLUMNS.issubset(annotated.columns) and all(
        str(stored or "") == current
        for stored, current in zip(
            annotated["trust_validation_fingerprint"],
            fingerprints,
        )
    ):
        return annotated
    evaluations = [player_eligibility(row, now=now) for row in rows]
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
    enforcement = [
        enforce_player_record(
            row,
            eligible=bool(evaluation["eligible"]),
            eligibility_reason=str(evaluation["reason"]),
            duplicate_ids=duplicate_ids,
            canonical_player_ids=canonical_ids,
        )
        for row, evaluation in zip(rows, evaluations)
    ]
    annotated["is_current_fantasy_eligible"] = [
        bool(evaluation["eligible"])
        and result.level is not EnforcementLevel.BLOCKED
        for evaluation, result in zip(evaluations, enforcement)
    ]
    annotated["player_eligibility_reason"] = [
        str(evaluation["reason"]) for evaluation in evaluations
    ]
    annotated["trust_enforcement"] = [result.level.value for result in enforcement]
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


def reference_annotate(
    players: pd.DataFrame,
    *,
    now: datetime | None = None,
) -> pd.DataFrame:
    """Retain the pre-optimization three-iterrows production path."""

    if players is None:
        return pd.DataFrame()
    annotated = players.copy()
    resolved_now = now or datetime.now(timezone.utc)
    if annotated.empty:
        return annotate_player_eligibility(annotated, now=resolved_now)
    fingerprints = [
        _trust_validation_fingerprint(row, now=resolved_now)
        for _, row in annotated.iterrows()
    ]
    if TRUST_ANNOTATION_COLUMNS.issubset(annotated.columns) and all(
        str(stored or "") == current
        for stored, current in zip(
            annotated["trust_validation_fingerprint"],
            fingerprints,
        )
    ):
        return annotated
    evaluations = [
        player_eligibility(row, now=resolved_now)
        for _, row in annotated.iterrows()
    ]
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
    enforcement = [
        enforce_player_record(
            row,
            eligible=bool(evaluation["eligible"]),
            eligibility_reason=str(evaluation["reason"]),
            duplicate_ids=duplicate_ids,
            canonical_player_ids=canonical_ids,
        )
        for (_, row), evaluation in zip(annotated.iterrows(), evaluations)
    ]
    annotated["is_current_fantasy_eligible"] = [
        bool(evaluation["eligible"])
        and result.level is not EnforcementLevel.BLOCKED
        for evaluation, result in zip(evaluations, enforcement)
    ]
    annotated["player_eligibility_reason"] = [
        str(evaluation["reason"]) for evaluation in evaluations
    ]
    annotated["trust_enforcement"] = [result.level.value for result in enforcement]
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


def records_annotate(players: pd.DataFrame, *, now: datetime = NOW) -> pd.DataFrame:
    annotated = players.copy()
    return _finish_annotation(
        annotated,
        annotated.to_dict(orient="records"),
        now=now,
    )


def tuples_annotate(players: pd.DataFrame, *, now: datetime = NOW) -> pd.DataFrame:
    annotated = players.copy()
    columns = tuple(annotated.columns)
    rows = [
        dict(zip(columns, values))
        for values in annotated.itertuples(index=False, name=None)
    ]
    return _finish_annotation(annotated, rows, now=now)


def _summary(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    p95 = max(0, min(len(ordered) - 1, round(0.95 * (len(ordered) - 1))))
    return {
        "min_ms": round(ordered[0], 2),
        "mean_ms": round(statistics.fmean(ordered), 2),
        "median_ms": round(statistics.median(ordered), 2),
        "directional_p95_ms": round(ordered[p95], 2),
        "max_ms": round(ordered[-1], 2),
        "stddev_ms": round(statistics.pstdev(ordered), 2),
    }


def _benchmark(
    frame: pd.DataFrame,
    function: Callable[..., pd.DataFrame],
    *,
    samples: int,
) -> dict[str, float]:
    elapsed = []
    for _ in range(samples):
        trust_engine.clear_validation_cache()
        started = time.perf_counter()
        function(frame, now=NOW)
        elapsed.append((time.perf_counter() - started) * 1000)
    return _summary(elapsed)


def _benchmark_loader(
    db_path: str,
    function: Callable[..., pd.DataFrame],
    *,
    samples: int,
) -> dict[str, float]:
    elapsed = []
    for _ in range(samples):
        trust_engine.clear_validation_cache()
        started = time.perf_counter()
        snapshot, output_columns, _ = _snapshot_input(db_path)
        hydrated = _base_with_snapshot_hydration(db_path, snapshot)
        annotated = function(hydrated, now=NOW)
        eligibility_diagnostics(annotated)
        ensure_identity_columns(annotated).loc[:, list(output_columns)]
        elapsed.append((time.perf_counter() - started) * 1000)
    return _summary(elapsed)


def _row_construction_benchmark(
    frame: pd.DataFrame,
    *,
    samples: int,
) -> dict[str, dict[str, float]]:
    values = {
        "three_series_passes_ms": [],
        "one_series_pass_ms": [],
        "one_series_to_dict_pass_ms": [],
    }
    for _ in range(samples):
        started = time.perf_counter()
        for _pass in range(3):
            list(frame.iterrows())
        values["three_series_passes_ms"].append(
            (time.perf_counter() - started) * 1000
        )

        started = time.perf_counter()
        rows = [row for _, row in frame.iterrows()]
        values["one_series_pass_ms"].append(
            (time.perf_counter() - started) * 1000
        )

        started = time.perf_counter()
        [row.to_dict() for row in rows]
        values["one_series_to_dict_pass_ms"].append(
            (time.perf_counter() - started) * 1000
        )
    return {name: _summary(samples_) for name, samples_ in values.items()}


def _profile(
    frame: pd.DataFrame,
    function: Callable[..., pd.DataFrame],
) -> dict[str, Any]:
    trust_engine.clear_validation_cache()
    profiler = cProfile.Profile()
    profiler.enable()
    function(frame, now=NOW)
    profiler.disable()
    stats = pstats.Stats(profiler)
    rows = sorted(
        (
            {
                "function": f"{Path(filename).name}:{line}({name})",
                "primitive_calls": int(values[0]),
                "total_calls": int(values[1]),
                "self_ms": round(float(values[2]) * 1000, 2),
                "cumulative_ms": round(float(values[3]) * 1000, 2),
            }
            for (filename, line, name), values in stats.stats.items()
        ),
        key=lambda item: item["cumulative_ms"],
        reverse=True,
    )
    interesting = (
        "iterrows",
        "to_dict",
        "_ixs",
        "_stable_payload",
        "dumps",
        "enforce_player_record",
        "validate_player",
    )
    return {
        "total_function_calls": int(stats.total_calls),
        "selected": [
            row
            for row in rows
            if any(f"({name})" in row["function"] for name in interesting)
        ],
    }


def _allocations(
    frame: pd.DataFrame,
    function: Callable[..., pd.DataFrame],
) -> dict[str, Any]:
    trust_engine.clear_validation_cache()
    tracemalloc.start()
    function(frame, now=NOW)
    current, peak = tracemalloc.get_traced_memory()
    snapshot = tracemalloc.take_snapshot()
    tracemalloc.stop()
    stats = snapshot.statistics("lineno")
    return {
        "current_bytes": int(current),
        "peak_bytes": int(peak),
        "retained_blocks": int(sum(item.count for item in stats)),
        "retained_bytes": int(sum(item.size for item in stats)),
        "top": [
            {
                "location": _safe_location(
                    item.traceback[0].filename,
                    item.traceback[0].lineno,
                ),
                "blocks": int(item.count),
                "bytes": int(item.size),
            }
            for item in stats[:15]
        ],
    }


def _assert_exact(
    frame: pd.DataFrame,
    function: Callable[..., pd.DataFrame],
) -> None:
    trust_engine.clear_validation_cache()
    expected = reference_annotate(frame, now=NOW)
    trust_engine.clear_validation_cache()
    actual = function(frame, now=NOW)
    pd.testing.assert_frame_equal(expected, actual, check_exact=True, check_dtype=True)
    if eligibility_diagnostics(expected) != eligibility_diagnostics(actual):
        raise AssertionError("diagnostics changed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/players.db")
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("-o", "--output")
    args = parser.parse_args()
    if args.samples < 20:
        raise SystemExit("--samples must be at least 20")
    frame, _ = _load_real_frame(args.db)
    candidates = {
        "reference_iterrows": reference_annotate,
        "single_iterrows_series_reuse": annotate_player_eligibility,
        "records": records_annotate,
        "itertuples": tuples_annotate,
    }
    for function in candidates.values():
        _assert_exact(frame, function)
    payload = {
        "schema": "dynastygm-trust-row-profile-v1",
        "environment": "controlled_local_not_production",
        "rows": int(len(frame)),
        "samples": int(args.samples),
        "benchmarks": {
            name: _benchmark(frame, function, samples=args.samples)
            for name, function in candidates.items()
        },
        "row_construction": _row_construction_benchmark(
            frame,
            samples=args.samples,
        ),
        "complete_loader": {
            name: _benchmark_loader(
                args.db,
                function,
                samples=args.samples,
            )
            for name, function in (
                ("reference_iterrows", reference_annotate),
                ("single_iterrows_series_reuse", annotate_player_eligibility),
            )
        },
        "profiles": {
            name: _profile(frame, function)
            for name, function in (
                ("reference_iterrows", reference_annotate),
                ("single_iterrows_series_reuse", annotate_player_eligibility),
            )
        },
        "allocations": {
            name: _allocations(frame, function)
            for name, function in (
                ("reference_iterrows", reference_annotate),
                ("single_iterrows_series_reuse", annotate_player_eligibility),
            )
        },
        "equivalence": {
            "real_frame_exact": True,
            "diagnostics_exact": True,
        },
    }
    serialized = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized + "\n", encoding="utf-8")
    print("DYNASTYGM_TRUST_ROW_PROFILE " + json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
