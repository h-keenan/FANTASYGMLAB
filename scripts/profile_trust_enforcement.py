"""Profile and differentially benchmark dynamic player Trust enforcement."""

from __future__ import annotations

import argparse
import cProfile
from datetime import datetime, timezone
import io
import json
from pathlib import Path, PureWindowsPath
import pstats
import statistics
import sys
import time
import tracemalloc
from typing import Any, Callable
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules import public_player_snapshot, rankings, trust_engine
from modules.player_eligibility import (
    annotate_player_eligibility,
    eligibility_diagnostics,
)
from modules.player_identity import ensure_identity_columns
from scripts.benchmark_player_eligibility_trust import (
    _base_with_snapshot_hydration,
    _snapshot_input,
    decompose_annotation,
)


NOW = datetime(2026, 7, 30, tzinfo=timezone.utc)
PHASES = (
    "trust_fingerprint_preparation_ms",
    "trust_identity_preparation_ms",
    "trust_enforcement_ms",
    "result_assignment_ms",
    "trust_preparation_ms",
    "annotation_total_ms",
)


def _safe_profile_location(filename: str, lineno: int) -> str:
    """Return structural profiler context without exposing host path segments."""

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


def _reference_validate_player(record, *, now=None):
    """Pre-optimization validation path retained only inside this benchmark."""

    stable = trust_engine._stable_payload(record)
    payload = json.dumps(stable, sort_keys=True, separators=(",", ":"))
    return trust_engine._cached_validation(
        "player",
        trust_engine.canonical_object_key("player", record),
        payload,
        trust_engine._now_bucket(now),
    )


def _summary(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    p95_index = max(0, min(len(ordered) - 1, round(0.95 * (len(ordered) - 1))))
    return {
        "min_ms": round(ordered[0], 2),
        "mean_ms": round(statistics.fmean(ordered), 2),
        "median_ms": round(statistics.median(ordered), 2),
        "directional_p95_ms": round(ordered[p95_index], 2),
        "max_ms": round(ordered[-1], 2),
        "stddev_ms": round(statistics.pstdev(ordered), 2),
    }


def _load_real_frame(db_path: str) -> tuple[pd.DataFrame, tuple[str, ...]]:
    fingerprint = rankings.public_player_source_fingerprint(db_path)
    if public_player_snapshot.load_public_player_snapshot(
        db_path,
        source_fingerprint=fingerprint,
    ) is None:
        rankings.clear_public_player_cache()
        rankings.load_players(db_path)
    snapshot, output_columns, _ = _snapshot_input(db_path)
    return _base_with_snapshot_hydration(db_path, snapshot), output_columns


def _run_decomposed(
    frame: pd.DataFrame,
    validator: Callable | None,
) -> tuple[pd.DataFrame, dict[str, float]]:
    trust_engine.clear_validation_cache()
    context = (
        patch("modules.trust_enforcement.validate_player", side_effect=validator)
        if validator is not None
        else patch(
            "modules.trust_enforcement.validate_player",
            wraps=trust_engine.validate_player,
        )
    )
    with context:
        return decompose_annotation(frame, now=NOW)


def _benchmark_mode(
    frame: pd.DataFrame,
    *,
    validator: Callable | None,
    samples: int,
    warm: bool,
) -> tuple[dict[str, dict[str, float]], pd.DataFrame]:
    phase_samples: dict[str, list[float]] = {name: [] for name in PHASES}
    reference: pd.DataFrame | None = None
    context = (
        patch("modules.trust_enforcement.validate_player", side_effect=validator)
        if validator is not None
        else patch(
            "modules.trust_enforcement.validate_player",
            wraps=trust_engine.validate_player,
        )
    )
    trust_engine.clear_validation_cache()
    with context:
        if warm:
            decompose_annotation(frame, now=NOW)
        for _ in range(samples):
            if not warm:
                trust_engine.clear_validation_cache()
            annotated, phases = decompose_annotation(frame, now=NOW)
            for name in PHASES:
                phase_samples[name].append(float(phases[name]))
            if reference is None:
                reference = annotated
            else:
                pd.testing.assert_frame_equal(
                    reference,
                    annotated,
                    check_dtype=True,
                    check_exact=True,
                )
    assert reference is not None
    return {name: _summary(values) for name, values in phase_samples.items()}, reference


def _profile(
    frame: pd.DataFrame,
    validator: Callable | None,
) -> dict[str, Any]:
    profiler = cProfile.Profile()
    trust_engine.clear_validation_cache()
    context = (
        patch("modules.trust_enforcement.validate_player", side_effect=validator)
        if validator is not None
        else patch(
            "modules.trust_enforcement.validate_player",
            wraps=trust_engine.validate_player,
        )
    )
    with context:
        profiler.enable()
        decompose_annotation(frame, now=NOW)
        profiler.disable()
    stats = pstats.Stats(profiler)
    ranked = sorted(
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
    interesting = {
        "_stable_payload",
        "canonical_object_key",
        "_canonical_object_key_from_payload",
        "_validate",
        "validate_player",
        "enforce_player_record",
        "dumps",
        "loads",
        "to_dict",
        "iterrows",
    }
    return {
        "total_function_calls": int(stats.total_calls),
        "top_cumulative": ranked[:20],
        "selected_functions": [
            item
            for item in ranked
            if any(f"({name})" in item["function"] for name in interesting)
        ],
    }


def _allocation_profile(
    frame: pd.DataFrame,
    validator: Callable | None,
) -> dict[str, Any]:
    trust_engine.clear_validation_cache()
    context = (
        patch("modules.trust_enforcement.validate_player", side_effect=validator)
        if validator is not None
        else patch(
            "modules.trust_enforcement.validate_player",
            wraps=trust_engine.validate_player,
        )
    )
    tracemalloc.start()
    with context:
        started = time.perf_counter()
        decompose_annotation(frame, now=NOW)
        elapsed_ms = (time.perf_counter() - started) * 1000
    current, peak = tracemalloc.get_traced_memory()
    snapshot = tracemalloc.take_snapshot()
    tracemalloc.stop()
    statistics_by_line = snapshot.statistics("lineno")
    return {
        "elapsed_ms_with_tracemalloc": round(elapsed_ms, 2),
        "current_bytes": int(current),
        "peak_bytes": int(peak),
        "retained_allocation_blocks": int(
            sum(stat.count for stat in statistics_by_line)
        ),
        "retained_allocation_bytes": int(
            sum(stat.size for stat in statistics_by_line)
        ),
        "top_allocations": [
            {
                "location": _safe_profile_location(
                    stat.traceback[0].filename,
                    stat.traceback[0].lineno,
                ),
                "blocks": int(stat.count),
                "bytes": int(stat.size),
            }
            for stat in statistics_by_line[:15]
        ],
    }


def _diagnostic_and_schema_equivalence(
    frame: pd.DataFrame,
    output_columns: tuple[str, ...],
) -> dict[str, Any]:
    trust_engine.clear_validation_cache()
    with patch(
        "modules.trust_enforcement.validate_player",
        side_effect=_reference_validate_player,
    ):
        reference = annotate_player_eligibility(frame, now=NOW)
    reference_diagnostics = eligibility_diagnostics(reference)

    trust_engine.clear_validation_cache()
    optimized = annotate_player_eligibility(frame, now=NOW)
    optimized_diagnostics = eligibility_diagnostics(optimized)
    pd.testing.assert_frame_equal(
        reference,
        optimized,
        check_dtype=True,
        check_exact=True,
    )
    reference_restored = ensure_identity_columns(reference).loc[:, list(output_columns)]
    optimized_restored = ensure_identity_columns(optimized).loc[:, list(output_columns)]
    pd.testing.assert_frame_equal(
        reference_restored,
        optimized_restored,
        check_dtype=True,
        check_exact=True,
    )
    if reference_diagnostics != optimized_diagnostics:
        raise AssertionError("Trust diagnostics changed")
    reason_distribution = (
        reference["trust_block_reason"].fillna("").value_counts().sort_index().to_dict()
    )
    enforcement_distribution = (
        reference["trust_enforcement"].fillna("").value_counts().sort_index().to_dict()
    )
    return {
        "frame_exact": True,
        "column_order_exact": list(reference.columns) == list(optimized.columns),
        "row_order_exact": reference.index.equals(optimized.index),
        "dtypes_exact": reference.dtypes.equals(optimized.dtypes),
        "null_masks_exact": reference.isna().equals(optimized.isna()),
        "fingerprints_exact": reference[
            "trust_validation_fingerprint"
        ].equals(optimized["trust_validation_fingerprint"]),
        "diagnostics_exact": True,
        "diagnostic_event_count": 1,
        "reason_distribution": {
            str(key): int(value) for key, value in reason_distribution.items()
        },
        "enforcement_distribution": {
            str(key): int(value) for key, value in enforcement_distribution.items()
        },
        "schema_restoration_exact": True,
        "diagnostics": reference_diagnostics,
    }


def _benchmark_loader_boundary(
    db_path: str,
    *,
    validator: Callable | None,
    samples: int,
) -> dict[str, dict[str, float]]:
    measurements = {
        "snapshot_and_hydration_ms": [],
        "annotation_total_ms": [],
        "diagnostics_ms": [],
        "final_schema_restoration_ms": [],
        "complete_loader_boundary_ms": [],
    }
    context = (
        patch("modules.trust_enforcement.validate_player", side_effect=validator)
        if validator is not None
        else patch(
            "modules.trust_enforcement.validate_player",
            wraps=trust_engine.validate_player,
        )
    )
    with context:
        for _ in range(samples):
            trust_engine.clear_validation_cache()
            total_started = time.perf_counter()
            hydration_started = time.perf_counter()
            snapshot, output_columns, _ = _snapshot_input(db_path)
            hydrated = _base_with_snapshot_hydration(db_path, snapshot)
            hydration_ms = (time.perf_counter() - hydration_started) * 1000
            annotated, phases = decompose_annotation(hydrated, now=NOW)
            diagnostics_started = time.perf_counter()
            eligibility_diagnostics(annotated)
            diagnostics_ms = (time.perf_counter() - diagnostics_started) * 1000
            final_started = time.perf_counter()
            ensure_identity_columns(annotated).loc[:, list(output_columns)]
            final_ms = (time.perf_counter() - final_started) * 1000
            total_ms = (time.perf_counter() - total_started) * 1000
            measurements["snapshot_and_hydration_ms"].append(hydration_ms)
            measurements["annotation_total_ms"].append(
                float(phases["annotation_total_ms"])
            )
            measurements["diagnostics_ms"].append(diagnostics_ms)
            measurements["final_schema_restoration_ms"].append(final_ms)
            measurements["complete_loader_boundary_ms"].append(total_ms)
    return {name: _summary(values) for name, values in measurements.items()}


def _improvements(
    reference: dict[str, dict[str, float]],
    optimized: dict[str, dict[str, float]],
) -> dict[str, dict[str, float]]:
    result = {}
    for phase in PHASES:
        before = reference[phase]["median_ms"]
        after = optimized[phase]["median_ms"]
        absolute = before - after
        result[phase] = {
            "absolute_median_ms": round(absolute, 2),
            "percent_median": round((absolute / before * 100) if before else 0.0, 2),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/players.db")
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("-o", "--output")
    args = parser.parse_args()
    if args.samples < 20:
        raise SystemExit("--samples must be at least 20")

    frame, output_columns = _load_real_frame(args.db)
    equivalence = _diagnostic_and_schema_equivalence(frame, output_columns)
    reference_cold, _ = _benchmark_mode(
        frame,
        validator=_reference_validate_player,
        samples=args.samples,
        warm=False,
    )
    optimized_cold, _ = _benchmark_mode(
        frame,
        validator=None,
        samples=args.samples,
        warm=False,
    )
    reference_warm, _ = _benchmark_mode(
        frame,
        validator=_reference_validate_player,
        samples=args.samples,
        warm=True,
    )
    optimized_warm, _ = _benchmark_mode(
        frame,
        validator=None,
        samples=args.samples,
        warm=True,
    )
    reference_loader = _benchmark_loader_boundary(
        args.db,
        validator=_reference_validate_player,
        samples=args.samples,
    )
    optimized_loader = _benchmark_loader_boundary(
        args.db,
        validator=None,
        samples=args.samples,
    )
    payload = {
        "schema": "dynastygm-trust-cpu-profile-v1",
        "environment": "controlled_local_not_production",
        "rows": int(len(frame)),
        "columns": int(len(frame.columns)),
        "samples_per_mode": args.samples,
        "validation_date": NOW.date().isoformat(),
        "equivalence": equivalence,
        "cold_validation_cache": {
            "reference": reference_cold,
            "optimized": optimized_cold,
            "improvement": _improvements(reference_cold, optimized_cold),
        },
        "warm_validation_cache": {
            "reference": reference_warm,
            "optimized": optimized_warm,
            "improvement": _improvements(reference_warm, optimized_warm),
        },
        "complete_loader_boundary": {
            "reference": reference_loader,
            "optimized": optimized_loader,
            "annotation_improvement": {
                "absolute_median_ms": round(
                    reference_loader["annotation_total_ms"]["median_ms"]
                    - optimized_loader["annotation_total_ms"]["median_ms"],
                    2,
                ),
                "percent_median": round(
                    (
                        reference_loader["annotation_total_ms"]["median_ms"]
                        - optimized_loader["annotation_total_ms"]["median_ms"]
                    )
                    / reference_loader["annotation_total_ms"]["median_ms"]
                    * 100,
                    2,
                ),
            },
            "total_improvement": {
                "absolute_median_ms": round(
                    reference_loader["complete_loader_boundary_ms"]["median_ms"]
                    - optimized_loader["complete_loader_boundary_ms"]["median_ms"],
                    2,
                ),
                "percent_median": round(
                    (
                        reference_loader["complete_loader_boundary_ms"]["median_ms"]
                        - optimized_loader["complete_loader_boundary_ms"]["median_ms"]
                    )
                    / reference_loader["complete_loader_boundary_ms"]["median_ms"]
                    * 100,
                    2,
                ),
            },
        },
        "profile": {
            "reference": _profile(frame, _reference_validate_player),
            "optimized": _profile(frame, None),
        },
        "allocations": {
            "reference": _allocation_profile(frame, _reference_validate_player),
            "optimized": _allocation_profile(frame, None),
            "semantics": (
                "tracemalloc process peak and retained snapshot blocks; "
                "not total lifetime allocation events"
            ),
        },
    }
    serialized = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialized + "\n", encoding="utf-8")
    print("DYNASTYGM_TRUST_CPU_PROFILE " + json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
