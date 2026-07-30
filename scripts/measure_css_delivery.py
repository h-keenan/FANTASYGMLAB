"""Measure sanitized CSS/message structure across controlled local reruns."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import hashlib
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
TRANSITIONS = (
    ("dashboard", "dashboard", "dashboard_warm"),
    ("dashboard", "my_team", "dashboard_to_my_team"),
    ("my_team", "waivers", "my_team_to_waivers"),
    ("waivers", "rankings", "waivers_to_league_overview"),
    ("rankings", "trade_hub", "league_overview_to_trade_hub"),
    ("trade_hub", "dashboard", "trade_hub_to_dashboard"),
)


def _distribution(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    ordered = sorted(values)
    p95_index = round(0.95 * (len(ordered) - 1))
    return {
        "min": round(ordered[0], 1),
        "mean": round(statistics.fmean(ordered), 1),
        "median": round(statistics.median(ordered), 1),
        "directional_p95": round(ordered[p95_index], 1),
        "max": round(ordered[-1], 1),
    }


def _trace_reports(output: str) -> list[dict]:
    return [
        json.loads(line[len(TRACE_PREFIX) :])
        for line in output.splitlines()
        if line.startswith(TRACE_PREFIX)
    ]


def _style_elements(application) -> list[dict]:
    result = []
    for ordinal, element in enumerate(application.markdown, start=1):
        body = str(element.value or "")
        if not body.lstrip().casefold().startswith("<style"):
            continue
        encoded = body.encode("utf-8")
        result.append(
            {
                "element_ordinal": ordinal,
                "css_ordinal": len(result) + 1,
                "sha256": hashlib.sha256(encoded).hexdigest(),
                "utf8_bytes": len(encoded),
            }
        )
    return result


def _install_experiment(mode: str) -> None:
    if mode == "current":
        return
    from modules import html_rendering

    original = html_rendering.inject_global_styles
    if mode == "tiny":
        def experimental_tiny(_css_or_style: str) -> None:
            original("<style>:root{}</style>")

        html_rendering.inject_global_styles = experimental_tiny
        return

    app_css_emitted = False

    def experimental_first_only(css_or_style: str) -> None:
        nonlocal app_css_emitted
        is_app_css = len(str(css_or_style or "").encode("utf-8")) > 100_000
        if is_app_css and app_css_emitted:
            return
        if is_app_css:
            app_css_emitted = True
        original(css_or_style)

    html_rendering.inject_global_styles = experimental_first_only


def _click(application, destination: str) -> dict:
    captured = io.StringIO()
    started = time.perf_counter()
    with redirect_stdout(captured):
        application.button(key=f"desktop_nav_{destination}").click().run()
    wall_ms = (time.perf_counter() - started) * 1000
    if application.exception:
        raise RuntimeError("controlled navigation raised a Streamlit exception")
    reports = _trace_reports(captured.getvalue())
    report = reports[-1] if reports else {}
    query = application.query_params.get("page")
    if isinstance(query, list):
        query = query[-1] if query else ""
    return {
        "action_script_runs": 1,
        "completed_trace_reports": len(reports),
        "explicit_rerun_events": captured.getvalue().count(
            "DYNASTYGM_RUNTIME_RERUN "
        ),
        "route_correct": str(application.session_state["current_page"]) == destination,
        "query_correct": str(query or "") == destination,
        "server_ms": report.get("total_page_ms"),
        "wall_ms": round(wall_ms, 1),
        "messages": (report.get("counters") or {}).get("streamlit_messages"),
        "protobuf_bytes": (report.get("streamlit") or {}).get("protobuf_bytes"),
        "css_messages": (report.get("streamlit") or {}).get("css_messages", []),
        "style_elements": _style_elements(application),
    }


def _summarize(samples: list[dict]) -> dict:
    numeric_keys = ("server_ms", "wall_ms", "messages", "protobuf_bytes")
    summary = {
        key: _distribution(
            [float(sample[key]) for sample in samples if sample.get(key) is not None]
        )
        for key in numeric_keys
    }
    summary.update(
        {
            "samples": len(samples),
            "completed_trace_reports": sum(
                int(sample["completed_trace_reports"]) for sample in samples
            ),
            "explicit_rerun_events": sum(
                int(sample["explicit_rerun_events"]) for sample in samples
            ),
            "all_routes_correct": all(sample["route_correct"] for sample in samples),
            "all_queries_correct": all(sample["query_correct"] for sample in samples),
            "css_message_signatures": sorted(
                {
                    tuple(
                        (
                            item["ordinal"],
                            item["sha256"],
                            item["utf8_bytes"],
                            item["protobuf_bytes"],
                        )
                        for item in sample["css_messages"]
                    )
                    for sample in samples
                    if sample["css_messages"]
                }
            ),
            "style_element_signatures": sorted(
                {
                    tuple(
                        (
                            item["css_ordinal"],
                            item["element_ordinal"],
                            item["sha256"],
                            item["utf8_bytes"],
                        )
                        for item in sample["style_elements"]
                    )
                    for sample in samples
                }
            ),
        }
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument(
        "--experiment",
        choices=("current", "tiny", "first-only"),
        default="current",
    )
    parser.add_argument("-o", "--output")
    args = parser.parse_args()
    if args.samples < 10:
        raise SystemExit("--samples must be at least 10")
    if os.environ.get("DYNASTYGM_RUNTIME_TRACE") != "1":
        raise SystemExit("set DYNASTYGM_RUNTIME_TRACE=1 before process startup")

    _install_experiment(args.experiment)
    from streamlit.testing.v1 import AppTest

    application = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    with redirect_stdout(io.StringIO()):
        application.run()

    results: dict[str, dict] = {}
    for source, destination, label in TRANSITIONS:
        samples = []
        for _ in range(args.samples):
            if str(application.session_state["current_page"]) != source:
                _click(application, source)
            samples.append(_click(application, destination))
        results[label] = _summarize(samples)

    payload = {
        "schema": "dynastygm-css-delivery-measurement-v1",
        "environment": "local logged-out Streamlit AppTest; not browser latency",
        "experiment": args.experiment,
        "samples_per_action": args.samples,
        "results": results,
    }
    serialized = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
