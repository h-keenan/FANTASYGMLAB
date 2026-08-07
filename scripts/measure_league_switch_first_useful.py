"""Repeatable league-switch first-useful-workspace harness.

Synthetic session-state measurements — no Sleeper/Supabase calls.

Usage:
    python scripts/measure_league_switch_first_useful.py
    python scripts/measure_league_switch_first_useful.py --samples 12 -o out.json
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

from modules import league_switch_first_useful
from modules import prepared_player_frame
from modules import session_integrity
from modules import trade_hub_first_useful


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


def _seed_league_state(state: dict[str, Any], *, league_id: str, frame_sig: str) -> None:
    state["selected_league_id"] = league_id
    state["selected_league_name"] = f"League {league_id}"
    state["role_map"] = {"1": "Core"}
    state["canonical_recommendation_narrative"] = {
        "league_id": league_id,
        "action": "Trade",
    }
    state["activity_inbox_snapshot"] = {"league_id": league_id, "records": [{"id": "x"}]}
    state["_decision_change_history_events"] = [{"league_id": league_id}]
    state[prepared_player_frame.FRAME_KEY] = pd.DataFrame(
        {"player_id": ["1", "2"], "dynasty_score": [100, 90]}
    )
    state[prepared_player_frame.SIGNATURE_KEY] = frame_sig
    state[prepared_player_frame.SHELL_BUNDLE_KEY] = {"league": league_id}
    state[prepared_player_frame.SHELL_SIGNATURE_KEY] = f"shell|{league_id}"
    state[prepared_player_frame.SHARED_CONTEXT_KEY] = {
        f"frame|shell|{league_id}|roster|score|settings|0|1|1|1|1|1": {
            "league_summary": "ok",
            "league_id": league_id,
        }
    }
    trade_hub_first_useful.get_or_build_presentation_board(
        state,
        signature=f"board|{league_id}",
        builder=lambda: {
            "eligible_ideas": [{"partner_roster_id": "2", "tag": "X"}],
            "equivalence_fingerprint": "fp",
        },
    )


def _simulate_league_switch_cleanup(
    state: dict[str, Any],
    *,
    previous_league_id: str,
    next_league_id: str,
) -> dict[str, Any]:
    """Mirror production league-scoped cleanup without Streamlit."""

    league_switch_first_useful.begin_switch_guard(
        state,
        previous_league_id=previous_league_id,
        next_league_id=next_league_id,
        next_league_name=f"League {next_league_id}",
        preserved_route="dashboard",
    )
    started = time.perf_counter()
    for key in (
        "role_map",
        "canonical_recommendation_narrative",
        "player_quick_view_player_id",
        "player_detail_player_id",
        "executive_workflow_return",
    ):
        state.pop(key, None)
    state.pop("activity_inbox_snapshot", None)
    state.pop("_decision_change_history_events", None)
    session_integrity.clear_trade_analyzer_package(state)
    prepared_player_frame.clear_league_scoped_prepared_memos(
        state,
        previous_league_id=previous_league_id,
    )
    cleanup_ms = (time.perf_counter() - started) * 1000.0
    league_switch_first_useful.mark_cleanup_complete(state)
    state["selected_league_id"] = next_league_id
    state["selected_league_name"] = f"League {next_league_id}"
    guard = league_switch_first_useful.consume_switch_guard(state) or {}
    return {
        "cleanup_ms": cleanup_ms,
        "frame_retained": prepared_player_frame.FRAME_KEY in state,
        "shell_cleared": prepared_player_frame.SHELL_BUNDLE_KEY not in state,
        "trade_hub_cleared": trade_hub_first_useful.PRESENTATION_CACHE_KEY not in state
        or not state.get(trade_hub_first_useful.PRESENTATION_CACHE_KEY),
        "shared_other_league_retained": any(
            f"|{previous_league_id}|" in str(key)
            for key in (state.get(prepared_player_frame.SHARED_CONTEXT_KEY) or {})
        ),
        "narrative_cleared": "canonical_recommendation_narrative" not in state,
        "inbox_cleared": "activity_inbox_snapshot" not in state,
        "role_map_cleared": "role_map" not in state,
        "guard": guard,
    }


def measure(*, samples: int) -> dict[str, Any]:
    frame_sig = "pub|Dynasty|dynasty_score|settings|PPR|True|balanced|2025|2"
    warm_ab: list[float] = []
    warm_ba: list[float] = []
    rapid_abc: list[float] = []
    frame_retain_flags: list[bool] = []
    stale_flash_ok = True

    for _ in range(samples):
        state: dict[str, Any] = {}
        _seed_league_state(state, league_id="A", frame_sig=frame_sig)
        result_ab = _simulate_league_switch_cleanup(
            state, previous_league_id="A", next_league_id="B"
        )
        warm_ab.append(result_ab["cleanup_ms"])
        frame_retain_flags.append(result_ab["frame_retained"])
        if not (
            result_ab["shell_cleared"]
            and result_ab["trade_hub_cleared"]
            and result_ab["narrative_cleared"]
            and result_ab["inbox_cleared"]
            and result_ab["role_map_cleared"]
            and result_ab["frame_retained"]
        ):
            stale_flash_ok = False

        # Seed League B artifacts then switch back to A.
        _seed_league_state(state, league_id="B", frame_sig=frame_sig)
        # Restore A's shared context that would have survived.
        store = state.setdefault(prepared_player_frame.SHARED_CONTEXT_KEY, {})
        store[f"frame|shell|A|roster|score|settings|0|1|1|1|1|1"] = {
            "league_id": "A",
            "league_summary": "ok",
        }
        result_ba = _simulate_league_switch_cleanup(
            state, previous_league_id="B", next_league_id="A"
        )
        warm_ba.append(result_ba["cleanup_ms"])

        # Rapid A→B→C
        state = {}
        _seed_league_state(state, league_id="A", frame_sig=frame_sig)
        started = time.perf_counter()
        _simulate_league_switch_cleanup(state, previous_league_id="A", next_league_id="B")
        _seed_league_state(state, league_id="B", frame_sig=frame_sig)
        final = _simulate_league_switch_cleanup(
            state, previous_league_id="B", next_league_id="C"
        )
        rapid_abc.append((time.perf_counter() - started) * 1000.0)
        if state.get("selected_league_id") != "C" or not final["frame_retained"]:
            stale_flash_ok = False

    return {
        "samples": samples,
        "first_useful_definition": (
            "shell + League B identity + no stale League A overlays/memos"
        ),
        "warm_a_to_b_cleanup": _summarize(warm_ab),
        "warm_b_to_a_cleanup": _summarize(warm_ba),
        "rapid_a_b_c_cleanup": _summarize(rapid_abc),
        "prepared_frame_retained_rate": round(
            sum(1 for flag in frame_retain_flags if flag) / max(1, len(frame_retain_flags)),
            3,
        ),
        "stale_flash_contract_ok": stale_flash_ok,
        "artifact_scope": dict(league_switch_first_useful.ARTIFACT_SCOPE),
        "stages": list(league_switch_first_useful.CRITICAL_PATH_STAGES),
        "invalidation_matrix": {
            "valued_ranked_frame": "retain if signature matches; miss on scoring/lens change",
            "shell_chrome": "clear",
            "shared_league_context_other_leagues": "retain",
            "trade_hub_board_memo": "clear",
            "narrative_pqv_trade_detail": "clear",
            "inbox_history": "clear",
            "role_map": "clear",
            "trade_analyzer_package": "clear",
            "public_player_static": "retain (global)",
            "st_cache_data_league_stacks": "retain (keyed by league_id)",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("-o", "--output", type=Path, default=None)
    args = parser.parse_args()
    report = measure(samples=max(1, int(args.samples)))
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report.get("stale_flash_contract_ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
