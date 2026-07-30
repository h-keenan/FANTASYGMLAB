"""Collect sanitized local Streamlit rerun and process-wall measurements."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TRACE_PREFIX = "DYNASTYGM_RUNTIME "
SAMPLE_PREFIX = "DYNASTYGM_LOCAL_E2E "


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


def _extract_report(output: str) -> dict:
    reports = [
        json.loads(line.split(" ", 1)[1])
        for line in output.splitlines()
        if line.startswith(TRACE_PREFIX)
    ]
    if not reports:
        raise RuntimeError("controlled AppTest rerun did not emit a runtime trace")
    return reports[-1]


def _run_apptest(application, *, state: str) -> dict:
    captured = io.StringIO()
    started = time.perf_counter()
    with redirect_stdout(captured):
        application.run()
    wall_ms = (time.perf_counter() - started) * 1000
    report = _extract_report(captured.getvalue())
    if application.exception:
        raise RuntimeError("controlled AppTest rerun raised an exception")
    return {
        "state": state,
        "wall_ms": round(wall_ms, 1),
        "rerun_ms": float(report.get("total_page_ms") or 0),
        "unattributed_apptest_overhead_ms": round(
            max(0.0, wall_ms - float(report.get("total_page_ms") or 0)),
            1,
        ),
        "protobuf_bytes": int(
            (report.get("streamlit") or {}).get("protobuf_bytes") or 0
        ),
        "elements": int(
            (report.get("counters") or {}).get("streamlit_elements") or 0
        ),
        "messages": int(
            (report.get("counters") or {}).get("streamlit_messages") or 0
        ),
        "milestones": report.get("milestones") or {},
        "external_calls": int((report.get("external") or {}).get("total") or 0),
        "correlation_id": report.get("correlation_id"),
    }


def _worker(mode: str, samples: int) -> int:
    process_started = time.perf_counter()
    from streamlit.testing.v1 import AppTest

    application = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    if mode == "cold":
        sample = _run_apptest(application, state="fresh_process")
        sample["process_to_apptest_complete_ms"] = round(
            (time.perf_counter() - process_started) * 1000,
            1,
        )
        print(SAMPLE_PREFIX + json.dumps(sample, sort_keys=True))
        return 0

    _run_apptest(application, state="prewarm")
    for _ in range(samples):
        print(
            SAMPLE_PREFIX
            + json.dumps(
                _run_apptest(application, state="warm_process"),
                sort_keys=True,
            )
        )
    return 0


def _samples_from_output(output: str) -> list[dict]:
    return [
        json.loads(line[len(SAMPLE_PREFIX) :])
        for line in output.splitlines()
        if line.startswith(SAMPLE_PREFIX)
    ]


def _summarize_milestones(samples: list[dict]) -> dict[str, dict[str, float]]:
    labels = sorted(
        set.intersection(
            *(
                set((sample.get("milestones") or {}).keys())
                for sample in samples
            )
        )
    )
    return {
        label: _distribution(
            [float((sample.get("milestones") or {})[label]) for sample in samples]
        )
        for label in labels
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--worker", choices=("cold", "warm"))
    parser.add_argument("-o", "--output")
    args = parser.parse_args()
    if args.samples < 10:
        raise SystemExit("--samples must be at least 10")
    if args.worker:
        return _worker(args.worker, args.samples)

    environment = dict(os.environ)
    environment["DYNASTYGM_RUNTIME_TRACE"] = "1"
    command = [sys.executable, str(Path(__file__).resolve())]
    cold: list[dict] = []
    for _ in range(args.samples):
        completed = subprocess.run(
            [*command, "--samples", str(args.samples), "--worker", "cold"],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )
        cold.extend(_samples_from_output(completed.stdout))
    warm_completed = subprocess.run(
        [*command, "--samples", str(args.samples), "--worker", "warm"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    warm = _samples_from_output(warm_completed.stdout)
    if len(cold) != args.samples or len(warm) != args.samples:
        raise RuntimeError("controlled sample matrix is incomplete")

    def summarize(samples: list[dict]) -> dict:
        return {
            "samples": len(samples),
            "wall_ms": _distribution([float(item["wall_ms"]) for item in samples]),
            "rerun_ms": _distribution([float(item["rerun_ms"]) for item in samples]),
            "unattributed_apptest_overhead_ms": _distribution(
                [float(item["unattributed_apptest_overhead_ms"]) for item in samples]
            ),
            "protobuf_bytes": _distribution(
                [float(item["protobuf_bytes"]) for item in samples]
            ),
            "elements": _distribution([float(item["elements"]) for item in samples]),
            "messages": _distribution([float(item["messages"]) for item in samples]),
            "external_calls": sum(int(item["external_calls"]) for item in samples),
            "milestones_ms": _summarize_milestones(samples),
        }

    payload = {
        "schema": "dynastygm-local-streamlit-e2e-v1",
        "environment": "local Streamlit AppTest; logged-out dashboard; no network",
        "cold_definition": "new Python process and new AppTest session",
        "warm_definition": "same process and AppTest session after one prewarm rerun",
        "cold": summarize(cold),
        "warm": summarize(warm),
        "process_to_apptest_complete_ms": _distribution(
            [float(item["process_to_apptest_complete_ms"]) for item in cold]
        ),
        "privacy": "structural timings and counts only",
    }
    serialized = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
