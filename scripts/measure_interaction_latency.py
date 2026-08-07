"""Repeatable interaction-latency / first-useful-content harness.

Synthetic warm-path timings — no Sleeper/Supabase. Complements Chromium
perceived-speed suites. Measures Python-side first-useful work for PQV fit
memo, Trade Review first-useful HTML, and lightweight menu milestones.

Usage:
    python scripts/measure_interaction_latency.py
    python scripts/measure_interaction_latency.py --samples 20 -o out.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules import deferred_rendering
from modules import interaction_latency
from modules import recommendation_trust_ux


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


def _fit_builder() -> dict[str, Any]:
    # Lightweight stand-in for roster-fit construction (no football pipeline).
    time.sleep(0.002)
    return {
        "roster_player_ids": {"1", "2", "3"},
        "roster_df": pd.DataFrame({"player_id": ["1", "2", "3"], "position": ["QB", "RB", "WR"]}),
        "metrics": {"strengths": ["QB"]},
        "assessment": {"needs": ["WR"]},
    }


def measure_fit_memo(*, samples: int) -> dict[str, Any]:
    cold: list[float] = []
    warm: list[float] = []
    signature = interaction_latency.build_fit_context_signature(
        league_id="L1",
        roster_id="1",
        score_field="dynasty_score",
        league_settings_key="ppr|sf",
        frame_signature="100|dynasty_score",
    )
    for _ in range(samples):
        state: dict[str, Any] = {}
        started = time.perf_counter()
        _, hit = interaction_latency.get_or_build_fit_context(
            state, signature=signature, builder=_fit_builder
        )
        cold.append((time.perf_counter() - started) * 1000.0)
        assert hit is False
        started = time.perf_counter()
        _, hit = interaction_latency.get_or_build_fit_context(
            state, signature=signature, builder=_fit_builder
        )
        warm.append((time.perf_counter() - started) * 1000.0)
        assert hit is True
    return {
        "cold_build": _summarize(cold),
        "warm_hit": _summarize(warm),
        "hit_rate": 1.0,
    }


def measure_trade_review_html(*, samples: int) -> dict[str, Any]:
    fields = {
        "Reason": "Fills the WR need under the current strategy lens.",
        "Evidence": "Partner has RB surplus and needs depth at WR.",
        "Risk": "Thin market conditions on the outbound RB.",
        "Expected outcome": "Fair · Net +120",
        "Supporting metrics": "Strong fit · High confidence · Likely market",
    }
    first_useful: list[float] = []
    with_supporting: list[float] = []
    for _ in range(samples):
        started = time.perf_counter()
        first = recommendation_trust_ux.executive_trade_detail_html(
            fields,
            verdict="Fair",
            value_delta="+120",
            confidence="High confidence",
            include_supporting=False,
        )
        first_useful.append((time.perf_counter() - started) * 1000.0)
        assert "Supporting metrics" not in first
        started = time.perf_counter()
        full = recommendation_trust_ux.executive_trade_detail_html(
            fields,
            verdict="Fair",
            value_delta="+120",
            confidence="High confidence",
            include_supporting=True,
        )
        with_supporting.append((time.perf_counter() - started) * 1000.0)
        assert "Supporting metrics" in full
    return {
        "first_useful_html": _summarize(first_useful),
        "full_with_supporting_html": _summarize(with_supporting),
        "protobuf_proxy_chars": {
            "first_useful": len(first),
            "with_supporting": len(full),
        },
    }


def measure_menu_milestones(*, samples: int) -> dict[str, Any]:
    open_ms: list[float] = []
    for _ in range(samples):
        started = time.perf_counter()
        interaction_latency.mark_interaction_milestone("gm_menu_open")
        interaction_latency.mark_interaction_milestone("alerts_compose_only")
        interaction_latency.mark_interaction_milestone("league_switcher_open")
        open_ms.append((time.perf_counter() - started) * 1000.0)
    return {"milestone_mark": _summarize(open_ms)}


def measure_deferred_gate(*, samples: int) -> dict[str, Any]:
    closed: list[float] = []
    open_path: list[float] = []
    for i in range(samples):
        state: dict[str, Any] = {}
        section = f"pqv_advanced_details_fixture_{i}"
        started = time.perf_counter()
        ready = deferred_rendering.is_deferred_section_ready(state, section)
        closed.append((time.perf_counter() - started) * 1000.0)
        assert ready is False
        deferred_rendering.mark_deferred_section_ready(state, section)
        started = time.perf_counter()
        ready = deferred_rendering.is_deferred_section_ready(state, section)
        open_path.append((time.perf_counter() - started) * 1000.0)
        assert ready is True
    return {"closed_check": _summarize(closed), "open_check": _summarize(open_path)}


def run(*, samples: int) -> dict[str, Any]:
    return {
        "samples": samples,
        "fit_context_memo": measure_fit_memo(samples=samples),
        "trade_review": measure_trade_review_html(samples=samples),
        "lightweight_menus": measure_menu_milestones(samples=samples),
        "deferred_gates": measure_deferred_gate(samples=samples),
        "latency_classes": list(interaction_latency.LATENCY_CLASSES),
        "note": (
            "Synthetic warm-path harness. Chromium tap→visible timings remain the "
            "source of truth for perceived speed (390 / 1440)."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("-o", "--output", type=Path, default=None)
    args = parser.parse_args()
    report = run(samples=max(1, int(args.samples)))
    text = json.dumps(report, indent=2)
    print(text)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
