#!/usr/bin/env python3
"""App-wide performance measurement harness (PR #166).

Emits median / directional-p95 server timings, protobuf, CSS contribution,
static architecture inventory, and fixture surface walls.

Requires DYNASTYGM_RUNTIME_TRACE=1 before process startup for production AppTest
traces. Does not call live Stripe, Supabase service-role, or mutate football logic.
"""

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

# Core + support destinations exercised via production AppTest navigation.
ROUTE_DESTINATIONS = (
    "dashboard",
    "my_team",
    "waivers",
    "rankings",
    "trade_hub",
    "draft_summary",
    "premium",
)

FIXTURE_SURFACES = (
    "dashboard",
    "my-team",
    "trade",
    "waivers",
    "league",
    "navigation",
    "live-draft",
    "player-dossier",
)


def _distribution(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(0.95 * (len(ordered) - 1))))
    return {
        "n": len(ordered),
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


def _last_trace(output: str) -> dict:
    reports = _records(output, TRACE_PREFIX)
    if not reports:
        raise RuntimeError("no DYNASTYGM_RUNTIME trace emitted")
    return reports[-1]


def _session_value(application, *keys: str) -> str:
    for key in keys:
        try:
            value = application.session_state[key]
        except Exception:
            continue
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _measure_production_run(application) -> dict:
    captured = io.StringIO()
    wall_started = time.perf_counter()
    with redirect_stdout(captured):
        application.run()
    wall_ms = (time.perf_counter() - wall_started) * 1000
    if application.exception:
        raise RuntimeError(f"AppTest exception: {application.exception}")
    report = _last_trace(captured.getvalue())
    streamlit = report.get("streamlit") or {}
    css_messages = list(streamlit.get("css_messages") or [])
    css_bytes = sum(int(item.get("protobuf_bytes") or 0) for item in css_messages)
    return {
        "server_ms": round(float(report.get("total_page_ms") or 0), 1),
        "wall_ms": round(wall_ms, 1),
        "protobuf_bytes": int(streamlit.get("protobuf_bytes") or 0),
        "css_protobuf_bytes": css_bytes,
        "css_message_count": len(css_messages),
        "css_messages": [
            {
                "ordinal": item.get("ordinal"),
                "utf8_bytes": item.get("utf8_bytes"),
                "protobuf_bytes": item.get("protobuf_bytes"),
                "sha256": str(item.get("sha256") or "")[:12],
            }
            for item in css_messages
        ],
        "largest_messages": list(streamlit.get("largest_messages") or [])[:8],
        "external": report.get("external") or {},
        "counters": report.get("counters") or {},
        "milestones": report.get("milestones") or {},
        "route": _session_value(application, "current_page", "platform_nav_page"),
    }


def _navigate(application, destination: str) -> dict:
    captured = io.StringIO()
    wall_started = time.perf_counter()
    key = f"desktop_nav_{destination}"
    try:
        with redirect_stdout(captured):
            application.button(key=key).click().run()
    except Exception:
        # Guest shells may omit some desktop nav keys; force route via session.
        application.session_state["platform_nav_page"] = destination
        application.session_state["current_page"] = destination
        application.session_state["_pending_platform_route"] = destination
        with redirect_stdout(captured):
            application.run()
    wall_ms = (time.perf_counter() - wall_started) * 1000
    output = captured.getvalue()
    if application.exception:
        raise RuntimeError(f"nav to {destination} raised: {application.exception}")
    reports = _records(output, TRACE_PREFIX)
    reruns = _records(output, RERUN_PREFIX)
    report = reports[-1] if reports else {}
    streamlit = report.get("streamlit") or {}
    return {
        "destination": destination,
        "route": _session_value(application, "current_page", "platform_nav_page"),
        "server_ms": round(float(report.get("total_page_ms") or 0), 1),
        "wall_ms": round(wall_ms, 1),
        "protobuf_bytes": int(streamlit.get("protobuf_bytes") or 0),
        "explicit_rerun_events": len(reruns),
        "completed_trace_reports": len(reports),
        "external_total": int((report.get("external") or {}).get("total") or 0),
        "trace_missing": not bool(reports),
    }


def _measure_fixture_surface(surface: str) -> dict:
    from streamlit.testing.v1 import AppTest

    application = AppTest.from_file(
        str(ROOT / "scripts" / "ui_validation_harness.py"),
        default_timeout=45,
    )
    application.query_params["surface"] = surface
    started = time.perf_counter()
    application.run()
    elapsed_ms = (time.perf_counter() - started) * 1000
    if application.exception:
        raise RuntimeError(f"fixture {surface} raised: {application.exception}")
    return {"surface": surface, "wall_ms": round(elapsed_ms, 1)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--skip-fixtures", action="store_true")
    parser.add_argument(
        "-o",
        "--output",
        default=str(ROOT / "artifacts" / "measurements" / "app_wide_performance.json"),
        help="Write JSON under artifacts/measurements/ (gitignored).",
    )
    args = parser.parse_args()
    if args.samples < 3:
        raise SystemExit("--samples must be at least 3")
    if os.environ.get("DYNASTYGM_RUNTIME_TRACE") != "1":
        raise SystemExit("set DYNASTYGM_RUNTIME_TRACE=1 before process startup")

    from streamlit.testing.v1 import AppTest
    from scripts.audit_founder_beta_performance import inventory

    architecture = inventory()
    application = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)

    cold = _measure_production_run(application)
    warm_dashboard: list[dict] = []
    for _ in range(args.samples):
        warm_dashboard.append(_measure_production_run(application))

    route_samples: dict[str, list[dict]] = {route: [] for route in ROUTE_DESTINATIONS}
    # Seed on dashboard, then cycle destinations for warm route opens.
    for _ in range(args.samples):
        for destination in ROUTE_DESTINATIONS:
            try:
                route_samples[destination].append(_navigate(application, destination))
            except Exception as exc:  # noqa: BLE001 - report per-route failures
                route_samples[destination].append(
                    {
                        "destination": destination,
                        "error": f"{type(exc).__name__}: {exc}",
                        "server_ms": None,
                        "wall_ms": None,
                        "protobuf_bytes": None,
                        "explicit_rerun_events": None,
                        "external_total": None,
                    }
                )

    fixture_rows = []
    if not args.skip_fixtures:
        for surface in FIXTURE_SURFACES:
            try:
                fixture_rows.append(_measure_fixture_surface(surface))
            except Exception as exc:  # noqa: BLE001
                fixture_rows.append(
                    {"surface": surface, "error": f"{type(exc).__name__}: {exc}"}
                )

    route_summary = {}
    for destination, rows in route_samples.items():
        ok_rows = [row for row in rows if row.get("server_ms") is not None]
        route_summary[destination] = {
            "server_ms": _distribution(
                [float(row["server_ms"]) for row in ok_rows]
            ),
            "wall_ms": _distribution([float(row["wall_ms"]) for row in ok_rows]),
            "protobuf_bytes": _distribution(
                [float(row["protobuf_bytes"]) for row in ok_rows]
            ),
            "explicit_rerun_events": _distribution(
                [float(row["explicit_rerun_events"] or 0) for row in ok_rows]
            ),
            "external_total": _distribution(
                [float(row["external_total"] or 0) for row in ok_rows]
            ),
            "errors": [row.get("error") for row in rows if row.get("error")],
            "sample_count": len(ok_rows),
        }

    payload = {
        "schema": "dynastygm-app-wide-performance-v1",
        "environment": "local logged-out Streamlit AppTest; not production Render",
        "samples_per_route": args.samples,
        "architecture": {
            "explicit_reruns": architecture["explicit_rerun_count"],
            "caches": architecture["cache_count"],
            "deferred_gates": architecture["deferred_gate_count"],
            "reduced_context_calls": architecture["reduced_context_call_count"],
            "explicit_rerun_sites": architecture["explicit_reruns"],
            "cache_sites": architecture["caches"],
        },
        "production_cold": cold,
        "production_warm_dashboard": {
            "server_ms": _distribution(
                [float(row["server_ms"]) for row in warm_dashboard]
            ),
            "wall_ms": _distribution([float(row["wall_ms"]) for row in warm_dashboard]),
            "protobuf_bytes": _distribution(
                [float(row["protobuf_bytes"]) for row in warm_dashboard]
            ),
            "external_total": _distribution(
                [
                    float((row.get("external") or {}).get("total") or 0)
                    for row in warm_dashboard
                ]
            ),
        },
        "routes": route_summary,
        "fixture_surfaces": fixture_rows,
        "css_byte_contribution_cold": {
            "app_css_source_utf8": len(
                (ROOT / "modules" / "app_styles.py").read_text(encoding="utf-8").encode()
            ),
            "cold_css_protobuf_bytes": cold.get("css_protobuf_bytes"),
            "cold_css_message_count": cold.get("css_message_count"),
            "cold_total_protobuf_bytes": cold.get("protobuf_bytes"),
            "css_share_of_protobuf": round(
                (
                    float(cold.get("css_protobuf_bytes") or 0)
                    / max(1, float(cold.get("protobuf_bytes") or 1))
                )
                * 100.0,
                1,
            ),
            "messages": cold.get("css_messages"),
        },
        "budgets_suggested_warm_server_ms": {
            "dashboard": 100,
            "my_team": 150,
            "waivers": 250,
            "trade_hub_cached": 150,
            "alerts_gm": 150,
            "league_switch_first_useful": 400,
            "pqv_first_useful": 250,
            "trade_review": 250,
        },
        "notes": [
            "Wall ms includes AppTest harness overhead and is not a customer SLA.",
            "Authenticated Free/Premium with live Sleeper/Supabase remain inventoried gaps.",
            "CSS is re-injected each Streamlit rerun (framework floor).",
        ],
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
