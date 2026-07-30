"""Sanitized deterministic CPU/allocation profiler for Trade Hub generation."""

from __future__ import annotations

import argparse
import cProfile
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import inspect
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

from modules import trade_hub_ui, trade_ideas, trust_engine
from modules.player_eligibility import annotate_player_eligibility
from modules.trust_enforcement import (
    enforce_trade_board,
    enforcement_from_player_annotations,
)


NOW = datetime(2026, 7, 30, tzinfo=timezone.utc)
POSITIONS = ("QB", "RB", "WR", "TE")
STRATEGIES = ("contender", "rebuild", "retool")


@dataclass(frozen=True)
class FixtureSpec:
    label: str
    teams: int
    roster_size: int
    qb_format: str
    te_premium: bool = False
    strategy: str = "contender"


class FixtureAdapter:
    def __init__(self, rosters: list[dict], settings: dict[str, Any]):
        self._rosters = rosters
        self._settings = settings

    def get_rosters(self, _league_id):
        return self._rosters

    def get_league(self, _league_id):
        return {
            "season": "2026",
            "settings": {"draft_rounds": 4},
            "roster_positions": [],
        }

    def get_traded_picks(self, _league_id):
        return []


def _safe_location(filename: str, lineno: int) -> str:
    path = Path(filename)
    try:
        relative = path.resolve().relative_to(Path.cwd().resolve())
        return f"./{relative.as_posix()}:{lineno}"
    except (OSError, ValueError):
        name = PureWindowsPath(filename).name if "\\" in filename else path.name
        return f"{name}:{lineno}"


def build_fixture(spec: FixtureSpec) -> dict[str, Any]:
    """Create anonymous stable fixtures without customer, league, or player data."""

    players = []
    rosters = []
    summaries = []
    position_slots = ("QB", "QB", "RB", "RB", "RB", "RB", "WR", "WR", "WR", "WR", "WR", "WR", "TE", "TE")
    for roster_id in range(1, spec.teams + 1):
        player_ids = []
        position_totals = {position: 0 for position in POSITIONS}
        for slot in range(spec.roster_size):
            player_id = f"F{roster_id:02d}-{slot:02d}"
            player_ids.append(player_id)
            position = position_slots[slot % len(position_slots)]
            score = max(
                350,
                8200 - (slot * 255) - (roster_id * 47) + ((slot % 4) * 31),
            )
            position_totals[position] += score
            injured = slot == 2 and roster_id % 4 == 0
            players.append(
                {
                    "player_id": player_id,
                    "name": player_id,
                    "full_name": player_id,
                    "position": position,
                    "fantasy_positions": [position],
                    "sport": "nfl",
                    "active": True,
                    "status": "active",
                    "team": f"T{roster_id:02d}",
                    "age": float(21 + ((slot + roster_id) % 12)),
                    "bye_week": int(5 + ((slot + roster_id) % 10)),
                    "years_exp": int(slot % 9),
                    "depth_chart_position": position,
                    "depth_chart_order": int(1 + (slot % 4)),
                    "stats_season": 2025,
                    "latest_stats_season": 2025,
                    "fantasycalc_value": float(score),
                    "value_score": int(score),
                    "dynasty_score": int(score),
                    "player_tier": (
                        "Elite" if score >= 7000 else
                        "Star" if score >= 5500 else
                        "Starter" if score >= 3500 else
                        "Depth"
                    ),
                    "injury_status": "Out" if injured else "",
                    "injury_body_part": "Lower Body" if injured else "",
                    "news_updated": NOW.timestamp(),
                    "news_updated_at": NOW.isoformat(),
                    "metadata_updated_at": NOW.isoformat(),
                    "verified_signals": {},
                }
            )
        strategy = spec.strategy if roster_id == 1 else STRATEGIES[(roster_id - 1) % len(STRATEGIES)]
        avg_age = statistics.fmean(
            player["age"] for player in players[-spec.roster_size:]
        )
        total = sum(position_totals.values())
        rosters.append(
            {
                "roster_id": roster_id,
                "owner_id": f"O{roster_id:02d}",
                "players": player_ids,
            }
        )
        summaries.append(
            {
                "roster_id": roster_id,
                "team_name": f"Fixture Team {roster_id:02d}",
                "owner_name": f"Fixture Owner {roster_id:02d}",
                "total_score": float(total),
                "starter_score": float(total * 0.68),
                "bench_score": float(total * 0.32),
                "raw_roster_score": float(total),
                "current_roster_score": float(total),
                "avg_age": float(avg_age),
                "qb_score": float(position_totals["QB"]),
                "rb_score": float(position_totals["RB"]),
                "wr_score": float(position_totals["WR"]),
                "te_score": float(position_totals["TE"]),
                "mode": trade_ideas.team_strategy_mode(strategy),
                "strategy": strategy,
                "strategy_label": trade_ideas.team_strategy_label(strategy),
                "strengths": [],
                "weaknesses": [],
                "injury_burden": float(2.0 if roster_id % 4 == 0 else 0.0),
                "injured_count": int(roster_id % 4 == 0),
                "injured_starters": int(roster_id % 4 == 0),
                "major_absences": int(roster_id % 4 == 0),
                "health_flag": "Injury Pressure" if roster_id % 4 == 0 else "Stable",
            }
        )
    settings = {
        "league_format": "Dynasty",
        "qb_format": spec.qb_format,
        "te_premium": spec.te_premium,
        "league_size": spec.teams,
        "starter_count": 10 if spec.qb_format == "Superflex" else 9,
        "qb_count": 1,
        "rb_count": 2,
        "wr_count": 3,
        "te_count": 1,
        "flex_count": 2,
        "superflex_count": 1 if spec.qb_format == "Superflex" else 0,
        "bench_count": max(0, spec.roster_size - (10 if spec.qb_format == "Superflex" else 9)),
        "taxi_count": 3,
        "ir_count": 3,
        "max_roster_size": spec.roster_size,
    }
    frame = annotate_player_eligibility(pd.DataFrame(players), now=NOW)
    return {
        "spec": spec,
        "players": frame,
        "summary": pd.DataFrame(summaries),
        "rosters": rosters,
        "settings": settings,
        "adapter": FixtureAdapter(rosters, settings),
    }


def _trust_context(fixture: dict[str, Any], raw: list[dict]) -> dict[str, Any]:
    frame = fixture["players"]
    candidate_ids = {
        str(asset.get("player_id") or "")
        for idea in raw
        for side in ("send_assets", "receive_assets")
        for asset in idea.get(side) or ()
        if isinstance(asset, dict)
        if asset.get("asset_type") == "player"
    }
    canonical = {}
    enforcement = {}
    for _, row in frame[frame["player_id"].isin(candidate_ids)].iterrows():
        player = row.to_dict()
        player_id = str(player.get("player_id") or "")
        canonical[player_id] = player
        result = enforcement_from_player_annotations(player)
        if result is not None:
            enforcement[player_id] = result
    ownership = {
        str(player_id): int(roster["roster_id"])
        for roster in fixture["rosters"]
        for player_id in roster["players"]
    }
    team_names = {
        str(row["team_name"]).casefold(): int(row["roster_id"])
        for _, row in fixture["summary"].iterrows()
    }
    return {
        "canonical_players": canonical,
        "player_enforcement": enforcement,
        "ownership_by_player": ownership,
        "valid_roster_ids": frozenset(range(1, fixture["spec"].teams + 1)),
        "my_roster_id": 1,
        "team_name_to_roster": team_names,
        "league_context_valid": True,
        "untouchable_names": frozenset(),
    }


def generate_raw(
    fixture: dict[str, Any],
    *,
    profile: trade_ideas._TradePipelineProfile | None = None,
    max_ideas: int = 20,
) -> list[dict]:
    return trade_ideas._build_trade_ideas_impl(
        fixture["players"],
        "fixture-league",
        fixture["summary"],
        1,
        [],
        [],
        {},
        max_ideas=max_ideas,
        score_field="value_score",
        pick_score_multiplier=1.0,
        team_strategy=fixture["spec"].strategy,
        league_settings=fixture["settings"],
        draft_status={
            "draft_year": 2026,
            "current_year_picks_active": True,
        },
        adapter=fixture["adapter"],
        _pipeline_profile=profile,
    )


def run_trade_hub(fixture: dict[str, Any], *, cached_raw: list[dict] | None = None):
    profile = trade_ideas._TradePipelineProfile(cache_enabled=True)
    raw = list(cached_raw) if cached_raw is not None else generate_raw(
        fixture,
        profile=profile,
    )
    board = enforce_trade_board(raw, **_trust_context(fixture, raw))
    approved = list(board.recommendations)
    headline = next(
        (idea for idea in approved if idea.get("trade_headline_ready")),
        approved[0] if approved else None,
    )
    grouped = trade_hub_ui.group_trade_hub_ideas(approved, headline_idea=headline)
    cards = [
        trade_hub_ui.trade_card_presentation_contract(idea)
        for ideas in grouped.values()
        for idea in ideas
    ]
    return {
        "raw": raw,
        "approved": approved,
        "grouped": grouped,
        "cards": cards,
        "diagnostics": {
            "blocked": board.blocked_count,
            "degraded": board.degraded_count,
            "confidence_caps": board.confidence_caps_applied,
            "reasons": list(board.blocked_reason_counts),
        },
        "pipeline": {
            "calls": dict(profile.calls),
            "cache_hits": dict(profile.cache_hits),
            "duplicates": int(profile.duplicate_evaluations),
        },
    }


def golden_result(result: dict[str, Any]) -> dict[str, Any]:
    ideas = []
    sections = {
        id(idea): section
        for section, grouped in result["grouped"].items()
        for idea in grouped
    }
    for index, idea in enumerate(result["approved"]):
        ideas.append(
            {
                "index": index,
                "partner": str(idea.get("partner_team_name") or ""),
                "send": [
                    str(asset.get("player_id") or asset.get("label") or "")
                    for asset in idea.get("send_assets") or ()
                ],
                "receive": [
                    str(asset.get("player_id") or asset.get("label") or "")
                    for asset in idea.get("receive_assets") or ()
                ],
                "my_score": int(idea.get("my_score") or 0),
                "their_score": int(idea.get("their_score") or 0),
                "trade_gain": int(idea.get("trade_gain") or 0),
                "idea_score": int(idea.get("trade_idea_score") or 0),
                "confidence": str(idea.get("trade_confidence_label") or ""),
                "market": str(idea.get("market_realism_label") or ""),
                "grade": str(idea.get("fit_grade") or ""),
                "trust": str(idea.get("trust_enforcement") or ""),
                "section": sections.get(id(idea), ""),
            }
        )
    return {
        "ideas": ideas,
        "diagnostics": result["diagnostics"],
        "counts": {
            "raw": len(result["raw"]),
            "approved": len(result["approved"]),
            "displayed": len(result["cards"]),
        },
    }


class CallCounts:
    def __init__(self):
        self.values: dict[str, int] = {}

    def wrap(self, label: str, function: Callable):
        def observed(*args, **kwargs):
            self.values[label] = self.values.get(label, 0) + 1
            return function(*args, **kwargs)
        return observed


def _instrumented_once(fixture: dict[str, Any]) -> dict[str, Any]:
    counts = CallCounts()
    originals = {
        "team_shape": trade_ideas._build_team_shape,
        "lineup": trade_ideas.suggest_optimal_lineup,
        "team_needs": trade_ideas.true_roster_needs,
        "injury_context": trade_ideas.summarize_team_injuries,
        "team_metrics": trade_ideas.get_team_vs_league,
        "pick_team_context": trade_ideas._pick_team_context,
        "valuation_lookup": trade_ideas._row_score,
        "asset_scoring": trade_ideas._score_assets,
    }
    dataframe_counts = {"copy": 0, "merge": 0, "sort_values": 0}
    copy_sites: dict[str, dict[str, int]] = {}
    original_copy = pd.DataFrame.copy
    original_merge = pd.DataFrame.merge
    original_sort = pd.DataFrame.sort_values

    def observed_copy(frame, *args, **kwargs):
        dataframe_counts["copy"] += 1
        copied = original_copy(frame, *args, **kwargs)
        caller = inspect.currentframe().f_back
        location = "unknown"
        while caller is not None:
            filename = Path(caller.f_code.co_filename)
            if filename.name not in {"managers.py", "generic.py", "frame.py"}:
                location = _safe_location(str(filename), caller.f_lineno)
                break
            caller = caller.f_back
        details = copy_sites.setdefault(
            location,
            {"calls": 0, "max_rows": 0, "max_columns": 0, "max_bytes": 0},
        )
        details["calls"] += 1
        details["max_rows"] = max(details["max_rows"], int(len(copied)))
        details["max_columns"] = max(details["max_columns"], int(len(copied.columns)))
        details["max_bytes"] = max(
            details["max_bytes"],
            int(copied.memory_usage(index=True, deep=True).sum()),
        )
        return copied

    def observed_merge(frame, *args, **kwargs):
        dataframe_counts["merge"] += 1
        return original_merge(frame, *args, **kwargs)

    def observed_sort(frame, *args, **kwargs):
        dataframe_counts["sort_values"] += 1
        return original_sort(frame, *args, **kwargs)

    patches = [
        patch.object(trade_ideas, name, counts.wrap(label, function))
        for label, (name, function) in zip(
            originals,
            (
                ("_build_team_shape", originals["team_shape"]),
                ("suggest_optimal_lineup", originals["lineup"]),
                ("true_roster_needs", originals["team_needs"]),
                ("summarize_team_injuries", originals["injury_context"]),
                ("get_team_vs_league", originals["team_metrics"]),
                ("_pick_team_context", originals["pick_team_context"]),
                ("_row_score", originals["valuation_lookup"]),
                ("_score_assets", originals["asset_scoring"]),
            ),
        )
    ]
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patch.object(
        pd.DataFrame, "copy", observed_copy
    ), patch.object(pd.DataFrame, "merge", observed_merge), patch.object(
        pd.DataFrame, "sort_values", observed_sort
    ):
        result = run_trade_hub(fixture)
    return {
        "function_calls": counts.values,
        "dataframes": dataframe_counts,
        "copy_sites": dict(
            sorted(
                copy_sites.items(),
                key=lambda item: (
                    item[1]["max_bytes"],
                    item[1]["calls"],
                ),
                reverse=True,
            )[:12]
        ),
        "pipeline": result["pipeline"],
        "funnel": {
            "package_construction": result["pipeline"]["calls"].get("package_construction", 0),
            "scored_packages": result["pipeline"]["calls"].get("package_scoring", 0),
            "accepted_before_dedupe": result["pipeline"]["calls"].get("duplicate_package_elimination", 0),
            "duplicates": result["pipeline"]["duplicates"],
            "raw": len(result["raw"]),
            "trust_approved": len(result["approved"]),
            "displayed": len(result["cards"]),
        },
    }


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


def _benchmark(fixture, *, samples: int, warm: bool) -> dict[str, float]:
    cached = generate_raw(fixture) if warm else None
    values = []
    for _ in range(samples):
        trust_engine.clear_validation_cache()
        started = time.perf_counter()
        run_trade_hub(fixture, cached_raw=cached)
        values.append((time.perf_counter() - started) * 1000)
    return _summary(values)


def run_pick_context_reuse_experiment(fixture: dict[str, Any]):
    """Measurement-only per-invocation reuse; never installed in production."""

    original = trade_ideas._pick_team_context
    contexts: dict[int, dict[str, Any]] = {}

    def reused(roster_id, summary):
        key = int(roster_id)
        if key not in contexts:
            contexts[key] = original(roster_id, summary)
        return contexts[key]

    with patch.object(trade_ideas, "_pick_team_context", reused):
        return run_trade_hub(fixture)


def _benchmark_callable(call: Callable[[], Any], *, samples: int) -> dict[str, float]:
    values = []
    for _ in range(samples):
        trust_engine.clear_validation_cache()
        started = time.perf_counter()
        call()
        values.append((time.perf_counter() - started) * 1000)
    return _summary(values)


def _profile(fixture) -> dict[str, Any]:
    profiler = cProfile.Profile()
    profiler.enable()
    run_trade_hub(fixture)
    profiler.disable()
    stats = pstats.Stats(profiler)
    rows = sorted(
        (
            {
                "function": f"{Path(filename).name}:{line}({name})",
                "calls": int(values[1]),
                "self_ms": round(float(values[2]) * 1000, 2),
                "cumulative_ms": round(float(values[3]) * 1000, 2),
            }
            for (filename, line, name), values in stats.stats.items()
        ),
        key=lambda item: item["cumulative_ms"],
        reverse=True,
    )
    return {
        "total_calls": int(stats.total_calls),
        "top_25": rows[:25],
    }


def _allocations(fixture) -> dict[str, Any]:
    tracemalloc.start()
    run_trade_hub(fixture)
    current, peak = tracemalloc.get_traced_memory()
    snapshot = tracemalloc.take_snapshot()
    tracemalloc.stop()
    stats = snapshot.statistics("lineno")
    return {
        "current_bytes": int(current),
        "peak_bytes": int(peak),
        "retained_blocks": int(sum(stat.count for stat in stats)),
        "retained_bytes": int(sum(stat.size for stat in stats)),
        "top_15": [
            {
                "location": _safe_location(
                    stat.traceback[0].filename,
                    stat.traceback[0].lineno,
                ),
                "blocks": int(stat.count),
                "bytes": int(stat.size),
            }
            for stat in stats[:15]
        ],
    }


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary-samples", type=int, default=20)
    parser.add_argument("--other-samples", type=int, default=10)
    parser.add_argument("-o", "--output")
    parser.add_argument("--golden-output")
    args = parser.parse_args()
    if args.primary_samples < 20 or args.other_samples < 10:
        raise SystemExit("sample counts must be at least 20 primary / 10 other")
    specs = (
        FixtureSpec("8-team-1qb-shallow", 8, 22, "1QB"),
        FixtureSpec("8-team-superflex", 8, 26, "Superflex"),
        FixtureSpec("12-team-1qb-deep", 12, 28, "1QB", te_premium=True, strategy="rebuild"),
        FixtureSpec("12-team-superflex-primary", 12, 28, "Superflex", te_premium=True),
        FixtureSpec("14-team-superflex-deep", 14, 30, "Superflex", te_premium=True, strategy="retool"),
    )
    fixtures = {spec.label: build_fixture(spec) for spec in specs}
    matrix = {}
    golden = {}
    for label, fixture in fixtures.items():
        samples = args.primary_samples if "primary" in label else args.other_samples
        cold = _benchmark(fixture, samples=samples, warm=False)
        warm = _benchmark(fixture, samples=samples, warm=True)
        first = run_trade_hub(fixture)
        cached = run_trade_hub(fixture, cached_raw=first["raw"])
        expected = golden_result(first)
        if golden_result(cached) != expected:
            raise AssertionError(f"cached/uncached output differs for {label}")
        matrix[label] = {
            "cold": cold,
            "warm_raw_cache_hit": warm,
            "players": int(len(fixture["players"])),
            "teams": fixture["spec"].teams,
            "roster_size": fixture["spec"].roster_size,
            "counts": expected["counts"],
            "golden_fingerprint": _fingerprint(expected),
        }
        golden[label] = expected
    primary = fixtures["12-team-superflex-primary"]
    primary_reference = run_trade_hub(primary)
    primary_experiment = run_pick_context_reuse_experiment(primary)
    if golden_result(primary_experiment) != golden_result(primary_reference):
        raise AssertionError("pick-context reuse experiment changed Trade Hub output")
    first_raw = [dict(primary_reference["raw"][0])] if primary_reference["raw"] else []
    blocked_raw = [dict(first_raw[0])] if first_raw else []
    if blocked_raw:
        blocked_raw[0]["send_assets"] = [
            {
                **blocked_raw[0]["send_assets"][0],
                "player_id": "UNKNOWN-FIXTURE-ID",
            }
        ]
    edge_cases = {
        "zero_trust_approved": golden_result(
            run_trade_hub(primary, cached_raw=blocked_raw)
        ),
        "one_recommendation": golden_result(
            run_trade_hub(primary, cached_raw=first_raw)
        ),
        "empty_raw_board": golden_result(
            run_trade_hub(primary, cached_raw=[])
        ),
    }
    payload = {
        "schema": "dynastygm-trade-hub-profile-v1",
        "environment": "controlled-local-synthetic-no-customer-data",
        "validation_date": NOW.date().isoformat(),
        "timing_matrix": matrix,
        "primary_calls": _instrumented_once(primary),
        "cpu": _profile(primary),
        "allocations": _allocations(primary),
        "pick_context_reuse_experiment": {
            "reference": _benchmark_callable(
                lambda: run_trade_hub(primary),
                samples=args.primary_samples,
            ),
            "reuse_once_per_roster": _benchmark_callable(
                lambda: run_pick_context_reuse_experiment(primary),
                samples=args.primary_samples,
            ),
            "output_exact": True,
            "scope": "measurement-only-not-production",
        },
        "golden_fingerprints": {
            label: _fingerprint(value) for label, value in golden.items()
        },
    }
    serialized = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized + "\n", encoding="utf-8")
    if args.golden_output:
        output = Path(args.golden_output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                {
                    "schema": "dynastygm-trade-hub-golden-v1",
                    "fixtures": golden,
                    "edge_cases": edge_cases,
                },
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
    print("DYNASTYGM_TRADE_HUB_PROFILE " + json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
