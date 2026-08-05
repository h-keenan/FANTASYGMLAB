"""Measure handoff / quick-action destination navigation rerun structure.

Compares the legacy queue+st.rerun button body pattern against the single-rerun
on_click + commit_destination_navigation pattern used by desktop/mobile nav.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import statistics
import sys
import tempfile
import time
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TRACE_PREFIX = "DYNASTYGM_RUNTIME "
RERUN_PREFIX = "DYNASTYGM_RUNTIME_RERUN "

HARNESS_TEMPLATE = """
from __future__ import annotations
import sys
from pathlib import Path
import streamlit as st

ROOT = Path(__ROOT__)
sys.path.insert(0, str(ROOT))

from modules import performance, runtime_trace
from modules.navigation_state import commit_destination_navigation, queue_destination_navigation
from modules import workspace_ui

MODE = st.query_params.get("mode", "legacy")
perf = performance.begin_rerun()
runtime_trace.begin_rerun(
    sequence=int(st.session_state.get("_trace_seq", 0)) + 1,
    cache_state="warm",
)
st.session_state["_trace_seq"] = int(st.session_state.get("_trace_seq", 0)) + 1
st.session_state.setdefault("platform_nav_page", "dashboard")
st.session_state.setdefault("current_page", "dashboard")

def queue(page_key: str, *, source: str = "dashboard_quick_action"):
    queue_destination_navigation(
        st.session_state,
        page_key,
        current_destination=st.session_state.get("platform_nav_page"),
        source=source,
    )

def commit(page_key: str, *, source: str = "dashboard_quick_action"):
    commit_destination_navigation(
        st.session_state,
        page_key,
        current_destination=st.session_state.get("platform_nav_page"),
        source=source,
    )

actions = [
    ("My Team", "my_team"),
    ("Trade Hub", "trade_hub"),
    ("Waivers", "waivers"),
    ("League Overview", "rankings"),
]

if MODE == "legacy":
    st.markdown("<div class='home-quick-nav-label'>Quick Actions</div>", unsafe_allow_html=True)
    rows = [actions[i:i+2] for i in range(0, len(actions), 2)]
    for row_idx, row in enumerate(rows):
        cols = st.columns(2)
        for col_idx, col in enumerate(cols):
            if col_idx >= len(row):
                continue
            label, route_key = row[col_idx]
            with col:
                if st.button(
                    label,
                    key=f"home_quick_action_{row_idx}_{route_key}",
                    use_container_width=True,
                    type="primary",
                ):
                    queue(route_key)
                    st.rerun()
else:
    workspace_ui.render_home_quick_actions(
        actions,
        commit_platform_destination=commit,
    )

pending = st.session_state.pop("_pending_platform_route", None)
if pending:
    st.session_state["platform_nav_page"] = pending
    st.session_state["current_page"] = pending
st.write("route", st.session_state.get("current_page"))
runtime_trace.finish_rerun(route=str(st.session_state.get("current_page") or "dashboard"))
performance.finish_rerun(perf)
"""


def _distribution(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(0.95 * (len(ordered) - 1))))
    return {
        "min": round(ordered[0], 1),
        "mean": round(statistics.fmean(ordered), 1),
        "median": round(statistics.median(ordered), 1),
        "directional_p95": round(ordered[index], 1),
        "max": round(ordered[-1], 1),
    }


def _records(output: str, prefix: str) -> list[dict]:
    return [
        json.loads(line[len(prefix) :])
        for line in output.splitlines()
        if line.startswith(prefix)
    ]


def _measure(mode: str, *, samples: int) -> list[dict]:
    from streamlit.testing.v1 import AppTest

    with tempfile.TemporaryDirectory() as tmp:
        harness_path = Path(tmp) / "handoff_rerun_harness.py"
        harness_path.write_text(
            HARNESS_TEMPLATE.replace("__ROOT__", repr(str(ROOT))),
            encoding="utf-8",
        )
        application = AppTest.from_file(str(harness_path), default_timeout=30)
        application.query_params["mode"] = mode
        with redirect_stdout(io.StringIO()):
            application.run()
        rows: list[dict] = []
        for _ in range(samples):
            application.session_state["platform_nav_page"] = "dashboard"
            application.session_state["current_page"] = "dashboard"
            captured = io.StringIO()
            started = time.perf_counter()
            with redirect_stdout(captured):
                application.button(key="home_quick_action_0_my_team").click().run()
            output = captured.getvalue()
            rerun_events = _records(output, RERUN_PREFIX)
            reports = _records(output, TRACE_PREFIX)
            if rerun_events and str(application.session_state["current_page"]) != "my_team":
                with redirect_stdout(captured):
                    application.run()
                output += captured.getvalue()
                rerun_events = _records(output, RERUN_PREFIX)
                reports = _records(output, TRACE_PREFIX)
            rows.append(
                {
                    "mode": mode,
                    "route": str(application.session_state["current_page"]),
                    "nav": str(application.session_state["platform_nav_page"]),
                    "explicit_rerun_events": len(rerun_events),
                    "completed_trace_reports": len(reports),
                    "server_ms": round(
                        sum(float(report.get("total_page_ms") or 0) for report in reports),
                        1,
                    ),
                    "wall_ms": round((time.perf_counter() - started) * 1000, 1),
                }
            )
            application.session_state["platform_nav_page"] = "dashboard"
            application.session_state["current_page"] = "dashboard"
            with redirect_stdout(io.StringIO()):
                application.run()
        return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("-o", "--output")
    args = parser.parse_args()
    if args.samples < 10:
        raise SystemExit("--samples must be at least 10")
    if os.environ.get("DYNASTYGM_RUNTIME_TRACE") != "1":
        raise SystemExit("set DYNASTYGM_RUNTIME_TRACE=1 before process startup")

    legacy = _measure("legacy", samples=args.samples)
    fixed = _measure("fixed", samples=args.samples)
    payload = {
        "schema": "dynastygm-handoff-rerun-measurement-v1",
        "environment": "local Streamlit AppTest harness; not production",
        "samples": args.samples,
        "legacy_queue_plus_rerun": {
            "explicit_rerun_events": _distribution(
                [float(row["explicit_rerun_events"]) for row in legacy]
            ),
            "wall_ms": _distribution([row["wall_ms"] for row in legacy]),
            "routes": sorted({row["route"] for row in legacy}),
        },
        "fixed_on_click_commit": {
            "explicit_rerun_events": _distribution(
                [float(row["explicit_rerun_events"]) for row in fixed]
            ),
            "wall_ms": _distribution([row["wall_ms"] for row in fixed]),
            "routes": sorted({row["route"] for row in fixed}),
        },
        "privacy": "No league, player, account, or token values.",
    }
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
