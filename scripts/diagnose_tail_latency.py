"""Diagnose DYNASTYGM_STARTUP tail-latency logs (#230).

Usage:
  python scripts/diagnose_tail_latency.py path/to/logs.txt
  python scripts/diagnose_tail_latency.py --synthetic
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import tail_latency_diagnostics


PREFIX = "DYNASTYGM_STARTUP "


def parse_log_text(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        idx = line.find(PREFIX)
        if idx < 0:
            continue
        payload = line[idx + len(PREFIX) :].strip()
        try:
            entry = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            rows.append(entry)
    return rows


def _field_samples(summaries: list[dict[str, Any]], field: str) -> list[float]:
    values: list[float] = []
    for row in summaries:
        raw = row.get(field)
        if isinstance(raw, (int, float)):
            values.append(float(raw))
    return values


def classify_slow_run(summary: dict[str, Any]) -> list[str]:
    owners: list[str] = []
    interactive = float(summary.get("interactive_stable_ms") or 0.0)
    if interactive <= 0:
        return ["UNKNOWN — incomplete summary"]
    auth = float(summary.get("auth_ms") or 0.0)
    provider = float(summary.get("provider_ms") or 0.0)
    prepared = float(summary.get("prepared_frame_ms") or 0.0)
    league = float(summary.get("league_context_ms") or 0.0)
    trade = float(summary.get("trade_inventory_ms") or 0.0)
    briefing = float(summary.get("briefing_assembly_ms") or 0.0)
    compose = float(summary.get("compose_ms") or 0.0)
    presentation = float(summary.get("presentation_ms") or 0.0)
    accounted = auth + provider + prepared + league + trade + briefing + compose + presentation
    temperature = str(summary.get("process_temperature") or "")
    if temperature == "PROCESS_COLD":
        owners.append("PROCESS_COLD football / empty process caches")
    if auth >= 1000:
        owners.append(f"auth/storage ~{auth:.0f}ms")
    if provider >= 1000:
        owners.append(f"provider ~{provider:.0f}ms")
    if prepared >= 1000:
        owners.append(f"prepared_frame ~{prepared:.0f}ms")
    if league + trade >= 1000:
        owners.append(f"league+trade ~{league + trade:.0f}ms")
    if briefing + compose >= 800:
        owners.append(f"briefing/compose ~{briefing + compose:.0f}ms")
    if int(summary.get("duplicate_build_count") or 0) > 0:
        owners.append(f"duplicate builds x{summary.get('duplicate_build_count')}")
    if int(summary.get("post_ready_rebuild_count") or 0) > 0:
        owners.append(f"post-READY rebuilds x{summary.get('post_ready_rebuild_count')}")
    if int(summary.get("rerun_count_before_stable") or 0) >= 4:
        owners.append(f"rerun cascade n={summary.get('rerun_count_before_stable')}")
    unexplained = max(0.0, interactive - accounted)
    if unexplained >= 2000:
        owners.append(
            f"UNEXPLAINED/gap ~{unexplained:.0f}ms "
            "(possible Render wake before process entry, Streamlit delivery, or uninstrumented work)"
        )
    return owners or ["UNKNOWN — no single owner above thresholds"]


def render_report(rows: list[dict[str, Any]]) -> str:
    summaries = [row for row in rows if row.get("kind") == "startup_trace_summary"]
    milestones = [row for row in rows if row.get("kind") == "startup_milestone"]
    duplicates = [row for row in rows if row.get("kind") == "duplicate_work"]
    post_ready = [row for row in rows if row.get("kind") == "post_ready_rebuild"]
    lines: list[str] = []
    lines.append(f"Rows parsed: {len(rows)}")
    lines.append(f"Summaries: {len(summaries)}")
    lines.append(f"Milestones: {len(milestones)}")
    lines.append(f"Duplicate-work events: {len(duplicates)}")
    lines.append(f"Post-READY rebuild events: {len(post_ready)}")
    lines.append("")

    for field, label in (
        ("loading_dismissed_ms", "loading dismissed"),
        ("first_useful_ms", "first useful"),
        ("game_plan_ready_ms", "Game Plan ready"),
        ("dashboard_complete_ms", "Dashboard complete"),
        ("interactive_stable_ms", "interactive stable"),
    ):
        stats = tail_latency_diagnostics.summarize_samples(summaries, field)
        if int(stats.get("n") or 0) == 0:
            lines.append(f"{label}: n=0")
            continue
        lines.append(
            f"{label}: n={stats['n']} median={stats['median']:.1f} "
            f"p90={stats['p90']:.1f} p95={stats['p95']:.1f} max={stats['max']:.1f}"
        )

    if summaries:
        slowest = max(
            summaries,
            key=lambda row: float(row.get("interactive_stable_ms") or row.get("first_useful_ms") or 0.0),
        )
        lines.append("")
        lines.append("Slowest summary:")
        lines.append(json.dumps(slowest, indent=2, sort_keys=True))
        lines.append("Owners:")
        for owner in classify_slow_run(slowest):
            lines.append(f"  - {owner}")

    by_temp: dict[str, int] = defaultdict(int)
    for row in summaries:
        by_temp[str(row.get("process_temperature") or "UNKNOWN")] += 1
    if by_temp:
        lines.append("")
        lines.append("Process temperature counts:")
        for key, count in sorted(by_temp.items()):
            lines.append(f"  {key}: {count}")

    overhead = tail_latency_diagnostics.estimate_diagnostics_overhead_ms()
    lines.append("")
    lines.append(f"Diagnostics overhead probe (disabled path avg ms/op): {overhead}")
    lines.append(
        "Hosting wake before Python process entry cannot be proven from in-process logs alone."
    )
    return "\n".join(lines) + "\n"


def synthetic_samples() -> list[dict[str, Any]]:
    """Honest synthetic examples encoding known architecture owners (not live prod)."""

    return [
        {
            "kind": "startup_trace_summary",
            "process_temperature": "PROCESS_COLD",
            "loading_dismissed_ms": 4200,
            "first_useful_ms": 7800,
            "game_plan_ready_ms": 9100,
            "dashboard_complete_ms": 9800,
            "interactive_stable_ms": 9800,
            "auth_ms": 2100,
            "provider_ms": 0,
            "prepared_frame_ms": 2800,
            "league_context_ms": 900,
            "trade_inventory_ms": 1100,
            "briefing_assembly_ms": 900,
            "compose_ms": 120,
            "presentation_ms": 200,
            "rerun_count_before_stable": 4,
            "duplicate_build_count": 0,
            "post_ready_rebuild_count": 0,
            "slowest_stage": "prepared_frame",
            "slowest_stage_ms": 2800,
        },
        {
            "kind": "startup_trace_summary",
            "process_temperature": "PROCESS_WARM_SESSION_COLD",
            "loading_dismissed_ms": 1800,
            "first_useful_ms": 2600,
            "game_plan_ready_ms": 2900,
            "dashboard_complete_ms": 3100,
            "interactive_stable_ms": 3100,
            "auth_ms": 1200,
            "provider_ms": 0,
            "prepared_frame_ms": 40,
            "league_context_ms": 20,
            "trade_inventory_ms": 25,
            "briefing_assembly_ms": 80,
            "compose_ms": 15,
            "presentation_ms": 120,
            "rerun_count_before_stable": 3,
            "duplicate_build_count": 0,
            "post_ready_rebuild_count": 0,
            "slowest_stage": "auth_storage_handshake",
            "slowest_stage_ms": 900,
        },
        {
            "kind": "startup_trace_summary",
            "process_temperature": "SESSION_WARM",
            "loading_dismissed_ms": 80,
            "first_useful_ms": 140,
            "game_plan_ready_ms": 160,
            "dashboard_complete_ms": 180,
            "interactive_stable_ms": 180,
            "auth_ms": 0,
            "provider_ms": 0,
            "prepared_frame_ms": 5,
            "league_context_ms": 2,
            "trade_inventory_ms": 2,
            "briefing_assembly_ms": 10,
            "compose_ms": 3,
            "presentation_ms": 40,
            "rerun_count_before_stable": 1,
            "duplicate_build_count": 0,
            "post_ready_rebuild_count": 0,
            "slowest_stage": "presentation",
            "slowest_stage_ms": 40,
        },
        {
            "kind": "startup_trace_summary",
            "process_temperature": "PROCESS_COLD",
            "loading_dismissed_ms": 6500,
            "first_useful_ms": 12100,
            "game_plan_ready_ms": 13800,
            "dashboard_complete_ms": 15200,
            "interactive_stable_ms": 15200,
            "auth_ms": 3100,
            "provider_ms": 2800,
            "prepared_frame_ms": 3200,
            "league_context_ms": 900,
            "trade_inventory_ms": 1200,
            "briefing_assembly_ms": 1100,
            "compose_ms": 150,
            "presentation_ms": 250,
            "rerun_count_before_stable": 5,
            "duplicate_build_count": 1,
            "post_ready_rebuild_count": 0,
            "slowest_stage": "prepared_frame",
            "slowest_stage_ms": 3200,
        },
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", help="Log file path")
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Report from architecture-encoded synthetic samples (not live production)",
    )
    args = parser.parse_args()
    if args.synthetic:
        rows = synthetic_samples()
        print("SYNTHETIC SAMPLE — not live production measurements")
        print(render_report(rows), end="")
        return 0
    if not args.path:
        text = sys.stdin.read()
    else:
        text = Path(args.path).read_text(encoding="utf-8", errors="replace")
    print(render_report(parse_log_text(text)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
