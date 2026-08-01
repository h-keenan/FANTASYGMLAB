"""Summarize opt-in DYNASTYGM_RUNTIME log records without user identifiers."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics
import sys
from typing import Any, Iterable


PREFIX = "DYNASTYGM_RUNTIME "
ROUTE_LABELS = {"rankings": "league_overview"}


def parse_reports(lines: Iterable[str]) -> list[dict[str, Any]]:
    reports = []
    for raw_line in lines:
        marker = raw_line.find(PREFIX)
        if marker < 0:
            continue
        try:
            report = json.loads(raw_line[marker + len(PREFIX) :])
        except (TypeError, ValueError):
            continue
        if isinstance(report, dict) and report.get("schema") in {
            "dynastygm-runtime-trace-v1",
            "dynastygm-runtime-trace-v2",
            "dynastygm-runtime-trace-v3",
        }:
            reports.append(report)
    return reports


def _percentile_95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(0.95 * (len(ordered) - 1))))
    return round(ordered[index], 1)


def _latency_distribution(values: list[float]) -> dict[str, float]:
    return {
        "min": round(min(values), 1),
        "mean": round(statistics.fmean(values), 1),
        "p50": round(statistics.median(values), 1),
        "p95": _percentile_95(values),
        "max": round(max(values), 1),
    }


def summarize(reports: list[dict[str, Any]]) -> dict[str, Any]:
    pages: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for report in reports:
        route = str(report.get("route") or "unknown")
        pages[ROUTE_LABELS.get(route, route)].append(report)

    page_output = {}
    aggregate_duplicates: dict[str, dict[str, float]] = defaultdict(
        lambda: {"calls": 0, "total_ms": 0.0, "samples": 0}
    )
    aggregate_external: dict[str, dict[str, float]] = defaultdict(
        lambda: {"calls": 0, "total_ms": 0.0}
    )
    aggregate_counters: dict[str, int] = defaultdict(int)
    largest_frames: list[dict[str, Any]] = []

    for route, samples in sorted(pages.items()):
        totals = [float(sample.get("total_page_ms") or 0) for sample in samples]
        phases: dict[str, dict[str, float]] = defaultdict(
            lambda: {"calls": 0, "total_ms": 0.0}
        )
        functions: dict[str, dict[str, float]] = defaultdict(
            lambda: {"calls": 0, "total_ms": 0.0, "max_ms": 0.0}
        )
        duplicate_samples: dict[str, int] = defaultdict(int)
        external: dict[str, dict[str, float]] = defaultdict(
            lambda: {"calls": 0, "total_ms": 0.0}
        )
        counters: dict[str, int] = defaultdict(int)
        streamlit_bytes: list[float] = []

        for sample in samples:
            for name, entry in (sample.get("phases") or {}).items():
                phases[name]["calls"] += int(entry.get("calls") or 0)
                phases[name]["total_ms"] += float(entry.get("total_ms") or 0)
            for name, entry in (sample.get("functions") or {}).items():
                functions[name]["calls"] += int(entry.get("calls") or 0)
                functions[name]["total_ms"] += float(entry.get("total_ms") or 0)
                functions[name]["max_ms"] = max(
                    functions[name]["max_ms"],
                    float(entry.get("max_ms") or 0),
                )
            for name, calls in (sample.get("duplicate_computations") or {}).items():
                duplicate_samples[name] += int(calls or 0)
                function = (sample.get("functions") or {}).get(name) or {}
                call_count = int(function.get("calls") or calls or 0)
                extra_calls = max(0, int(calls or 0) - 1)
                aggregate_duplicates[name]["calls"] += int(calls or 0)
                aggregate_duplicates[name]["samples"] += 1
                if call_count:
                    aggregate_duplicates[name]["total_ms"] += (
                        float(function.get("total_ms") or 0) * extra_calls / call_count
                    )
            for name, value in (sample.get("counters") or {}).items():
                counters[name] += int(value or 0)
                aggregate_counters[name] += int(value or 0)
            streamlit_bytes.append(
                float((sample.get("streamlit") or {}).get("protobuf_bytes") or 0)
            )
            for source, entry in ((sample.get("external") or {}).get("by_source") or {}).items():
                external[source]["calls"] += int(entry.get("calls") or 0)
                external[source]["total_ms"] += float(entry.get("total_ms") or 0)
                aggregate_external[source]["calls"] += int(entry.get("calls") or 0)
                aggregate_external[source]["total_ms"] += float(entry.get("total_ms") or 0)
            largest_frames.extend(
                {"route": route, **frame}
                for frame in (sample.get("dataframes") or [])
                if isinstance(frame, dict)
            )

        cache_state_totals: dict[str, list[float]] = defaultdict(list)
        for sample in samples:
            cache_state = str(sample.get("cache_state") or "unknown")
            cache_state_totals[cache_state].append(
                float(sample.get("total_page_ms") or 0)
            )

        page_output[route] = {
            "samples": len(samples),
            "total_page_ms_all_cache_states": _latency_distribution(totals),
            "cache_states": {
                state: {
                    "samples": len(values),
                    "total_page_ms": _latency_distribution(values),
                }
                for state, values in sorted(cache_state_totals.items())
            },
            "phases": {
                name: {
                    "calls": int(entry["calls"]),
                    "total_ms": round(entry["total_ms"], 1),
                    "mean_per_page_ms": round(entry["total_ms"] / len(samples), 1),
                }
                for name, entry in sorted(
                    phases.items(),
                    key=lambda item: item[1]["total_ms"],
                    reverse=True,
                )
            },
            "functions": {
                name: {
                    "calls": int(entry["calls"]),
                    "total_ms": round(entry["total_ms"], 1),
                    "max_ms": round(entry["max_ms"], 1),
                }
                for name, entry in sorted(
                    functions.items(),
                    key=lambda item: item[1]["total_ms"],
                    reverse=True,
                )
            },
            "duplicates": dict(sorted(duplicate_samples.items())),
            "dataframe_operations": dict(sorted(counters.items())),
            "streamlit_protobuf_bytes": _latency_distribution(streamlit_bytes),
            "external_requests": {
                source: {
                    "calls": int(entry["calls"]),
                    "total_ms": round(entry["total_ms"], 1),
                }
                for source, entry in sorted(external.items())
            },
        }

    opportunities = []
    for name, entry in aggregate_duplicates.items():
        calls = int(entry["calls"])
        samples = int(entry["samples"])
        opportunities.append(
            {
                "type": "duplicate_computation",
                "label": name,
                "calls": calls,
                "extra_calls": max(0, calls - samples),
                "estimated_duplicate_ms": round(float(entry["total_ms"]), 1),
            }
        )
    for source, entry in aggregate_external.items():
        opportunities.append(
            {
                "type": "external_latency",
                "label": source,
                "calls": int(entry["calls"]),
                "observed_ms": round(entry["total_ms"], 1),
            }
        )
    opportunities.sort(
        key=lambda item: float(
            item.get("estimated_duplicate_ms", item.get("observed_ms", 0))
        ),
        reverse=True,
    )
    largest_frames.sort(
        key=lambda frame: int(frame.get("estimated_memory_bytes") or 0),
        reverse=True,
    )
    return {
        "schema": "dynastygm-runtime-summary-v1",
        "report_count": len(reports),
        "pages": page_output,
        "aggregate": {
            "dataframe_operations": dict(sorted(aggregate_counters.items())),
            "external_requests": {
                source: {
                    "calls": int(entry["calls"]),
                    "total_ms": round(entry["total_ms"], 1),
                }
                for source, entry in sorted(aggregate_external.items())
            },
            "largest_dataframes": largest_frames[:12],
        },
        "top_optimization_opportunities": opportunities[:5],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log_file", nargs="?", help="Runtime log file; stdin when omitted")
    parser.add_argument("-o", "--output", help="Optional JSON output path")
    args = parser.parse_args()
    if args.log_file:
        lines = Path(args.log_file).read_text(encoding="utf-8", errors="replace").splitlines()
    else:
        lines = sys.stdin
    output = json.dumps(summarize(parse_reports(lines)), indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
