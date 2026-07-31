"""Measure sanitized local destination-navigation rerun structure."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import statistics
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TRACE_PREFIX = "DYNASTYGM_RUNTIME "
RERUN_PREFIX = "DYNASTYGM_RUNTIME_RERUN "


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


def _measure_action(application, destination: str) -> dict:
    captured = io.StringIO()
    started = time.perf_counter()
    with redirect_stdout(captured):
        application.button(key=f"desktop_nav_{destination}").click().run()
    wall_ms = (time.perf_counter() - started) * 1000
    output = captured.getvalue()
    reports = _records(output, TRACE_PREFIX)
    rerun_events = _records(output, RERUN_PREFIX)
    if application.exception:
        raise RuntimeError("navigation action raised a Streamlit exception")
    route = str(application.session_state["current_page"])
    query_value = application.query_params.get("page")
    query_route = (
        str(query_value[-1])
        if isinstance(query_value, list) and query_value
        else str(query_value or "")
    )
    return {
        "destination": destination,
        "route": route,
        "query_route": query_route,
        "action_script_runs": 1,
        "completed_trace_reports": len(reports),
        "explicit_rerun_events": len(rerun_events),
        "server_ms": round(
            sum(float(report.get("total_page_ms") or 0) for report in reports),
            1,
        ),
        "wall_ms": round(wall_ms, 1),
        "messages": sum(
            int((report.get("counters") or {}).get("streamlit_messages") or 0)
            for report in reports
        ),
        "protobuf_bytes": sum(
            int((report.get("streamlit") or {}).get("protobuf_bytes") or 0)
            for report in reports
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("-o", "--output")
    args = parser.parse_args()
    if args.samples < 10:
        raise SystemExit("--samples must be at least 10")
    if os.environ.get("DYNASTYGM_RUNTIME_TRACE") != "1":
        raise SystemExit("set DYNASTYGM_RUNTIME_TRACE=1 before process startup")

    from streamlit.testing.v1 import AppTest

    application = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    with redirect_stdout(io.StringIO()):
        application.run()

    primary = []
    returns = []
    for _ in range(args.samples):
        primary.append(_measure_action(application, "my_team"))
        returns.append(_measure_action(application, "dashboard"))

    path = []
    for destination in ("my_team", "waivers", "rankings", "trade_hub", "dashboard"):
        path.append(_measure_action(application, destination))

    all_actions = [*primary, *returns, *path]
    if any(
        action["route"] != action["destination"]
        or action["query_route"] != action["destination"]
        for action in all_actions
    ):
        raise RuntimeError("route and query state diverged")

    payload = {
        "schema": "dynastygm-navigation-rerun-measurement-v1",
        "environment": "local logged-out Streamlit AppTest; not production",
        "primary_transition": "dashboard_to_my_team",
        "primary_samples": args.samples,
        "primary": {
            "action_script_runs_per_action": _distribution(
                [float(item["action_script_runs"]) for item in primary]
            ),
            "completed_trace_reports_per_action": _distribution(
                [float(item["completed_trace_reports"]) for item in primary]
            ),
            "explicit_rerun_events_per_action": _distribution(
                [float(item["explicit_rerun_events"]) for item in primary]
            ),
            "server_ms": _distribution([float(item["server_ms"]) for item in primary]),
            "wall_ms": _distribution([float(item["wall_ms"]) for item in primary]),
            "messages": _distribution([float(item["messages"]) for item in primary]),
            "protobuf_bytes": _distribution(
                [float(item["protobuf_bytes"]) for item in primary]
            ),
        },
        "path": path,
        "all_routes_correct": True,
        "all_query_routes_correct": True,
    }
    serialized = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
