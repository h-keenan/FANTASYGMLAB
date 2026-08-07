"""Repeatable Trade Hub first-useful-result performance harness.

Measures stage timings for the presentation-board path using synthetic fixtures
from ``scripts/profile_trade_hub.py``. Does not call Sleeper/Supabase.

Usage:
    python scripts/measure_trade_hub_first_useful.py
    python scripts/measure_trade_hub_first_useful.py --samples 12 -o out.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules import trade_hub_first_useful
from modules import trade_hub_ui
from scripts.profile_trade_hub import FixtureSpec, build_fixture, run_trade_hub


SCENARIOS = (
    "cold_generation",
    "warm_presentation_cache",
    "strategy_change",
    "entitlement_free_vs_premium",
)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def _summarize(samples: list[float]) -> dict[str, float]:
    if not samples:
        return {"n": 0, "median_ms": 0.0, "p95_ms": 0.0, "mean_ms": 0.0}
    return {
        "n": len(samples),
        "median_ms": round(statistics.median(samples), 2),
        "p95_ms": round(_percentile(samples, 0.95), 2),
        "mean_ms": round(statistics.fmean(samples), 2),
        "min_ms": round(min(samples), 2),
        "max_ms": round(max(samples), 2),
    }


def _board_from_run(result: dict[str, Any], *, entitlement: str) -> dict[str, Any]:
    ideas = list(result.get("approved") or [])
    primary = [
        idea
        for idea in ideas
        if str(idea.get("trade_surface_tier") or "primary").strip().casefold() != "secondary"
    ]
    secondary = [
        idea
        for idea in ideas
        if str(idea.get("trade_surface_tier") or "").strip().casefold() == "secondary"
    ]
    presentation = trade_hub_ui.trade_hub_entitlement_presentation(
        primary,
        secondary,
        entitlement=entitlement,
    )
    eligible = trade_hub_ui.order_trade_hub_visible_ideas(presentation["visible_ideas"])
    return {
        "eligible_ideas": eligible,
        "presentation": presentation,
        "ranked_feed": trade_hub_ui.annotate_trade_hub_feed_categories(
            eligible, headline_idea=eligible[0] if eligible else None
        ),
        "headline_idea": eligible[0] if eligible else None,
        "board_inventory": {"accessible_count": len(eligible), "section_count": 1},
        "equivalence_fingerprint": trade_hub_first_useful.idea_equivalence_fingerprint(
            eligible
        ),
        "recommendation_one": trade_hub_first_useful.recommendation_one_identity(eligible),
    }


def measure_fixture(
    *,
    samples: int,
    entitlement: str = "premium",
) -> dict[str, Any]:
    spec = FixtureSpec(
        "12-team-superflex-primary",
        12,
        28,
        "Superflex",
        te_premium=True,
    )
    fixture = build_fixture(spec)

    cold_ms: list[float] = []
    warm_ms: list[float] = []
    strategy_ms: list[float] = []
    fingerprints: list[str] = []
    recommendation_ones: list[dict[str, Any]] = []

    for _ in range(samples):
        # Cold: full generation (dominates first-useful on cache miss).
        started = time.perf_counter()
        generated = run_trade_hub(fixture)
        cold_board = _board_from_run(generated, entitlement=entitlement)
        cold_ms.append((time.perf_counter() - started) * 1000.0)
        fingerprints.append(cold_board["equivalence_fingerprint"])
        recommendation_ones.append(cold_board["recommendation_one"])

        # Warm: session presentation memo (identical context).
        state: dict = {}
        signature = trade_hub_first_useful.build_presentation_board_signature(
            lifecycle_digest="fixture",
            league_id="fixture-league",
            roster_id="1",
            scoring_format="PPR",
            valuation_lens="dynasty_score",
            strategy="contender",
            entitlement=entitlement,
            frame_signature="fixture-frame",
            max_ideas=8,
        )

        def builder(board=cold_board):
            return dict(board)

        trade_hub_first_useful.get_or_build_presentation_board(
            state, signature=signature, builder=builder
        )
        started = time.perf_counter()
        warm_board, hit = trade_hub_first_useful.get_or_build_presentation_board(
            state, signature=signature, builder=builder
        )
        warm_ms.append((time.perf_counter() - started) * 1000.0)
        assert hit is True
        assert warm_board["equivalence_fingerprint"] == cold_board["equivalence_fingerprint"]

        # Strategy change must miss and rebuild.
        alt_signature = trade_hub_first_useful.build_presentation_board_signature(
            lifecycle_digest="fixture",
            league_id="fixture-league",
            roster_id="1",
            scoring_format="PPR",
            valuation_lens="dynasty_score",
            strategy="rebuild",
            entitlement=entitlement,
            frame_signature="fixture-frame",
            max_ideas=8,
        )
        started = time.perf_counter()
        _, alt_hit = trade_hub_first_useful.get_or_build_presentation_board(
            state,
            signature=alt_signature,
            builder=lambda: dict(cold_board),
        )
        strategy_ms.append((time.perf_counter() - started) * 1000.0)
        assert alt_hit is False

    free_board = _board_from_run(run_trade_hub(fixture), entitlement="free")
    premium_board = _board_from_run(run_trade_hub(fixture), entitlement="premium")

    return {
        "fixture": spec.label,
        "samples": samples,
        "recommendation_one_contract": (
            "complete_candidate_set_required_before_final_number_one"
        ),
        "cold_generation": _summarize(cold_ms),
        "warm_presentation_cache": _summarize(warm_ms),
        "strategy_change_miss": _summarize(strategy_ms),
        "equivalence": {
            "unique_fingerprints": len(set(fingerprints)),
            "stable": len(set(fingerprints)) == 1,
            "recommendation_one_stable": all(
                item == recommendation_ones[0] for item in recommendation_ones
            ),
            "free_visible_count": int(
                free_board["presentation"].get("visible_count") or 0
            ),
            "premium_visible_count": int(
                premium_board["presentation"].get("visible_count") or 0
            ),
            "free_fingerprint": free_board["equivalence_fingerprint"],
            "premium_fingerprint": premium_board["equivalence_fingerprint"],
        },
        "stages": list(trade_hub_first_useful.CRITICAL_PATH_STAGES),
        "cache_invalidation_matrix": {
            "account_scope": "miss",
            "league_id": "miss",
            "roster_id": "miss",
            "scoring_format": "miss",
            "valuation_lens": "miss",
            "strategy": "miss",
            "entitlement": "miss",
            "roster_state_version": "miss",
            "provider_data_version": "miss",
            "frame_signature": "miss",
            "untouchables_roles": "miss",
            "presentation_visible_count": "hit",
            "pqv_open_close": "hit",
            "alerts_gm_open_close": "hit",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("-o", "--output", type=Path, default=None)
    args = parser.parse_args()
    report = measure_fixture(samples=max(1, int(args.samples)))
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
