"""Measure browser-observed latency for deterministic Streamlit controls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import time


def _distribution(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "min": round(ordered[0], 1),
        "mean": round(statistics.fmean(ordered), 1),
        "median": round(statistics.median(ordered), 1),
        "max": round(ordered[-1], 1),
    }


def _elapsed(action) -> float:
    started = time.perf_counter()
    action()
    return (time.perf_counter() - started) * 1000


def main() -> int:
    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8512")
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.samples < 10:
        raise SystemExit("--samples must be at least 10")

    results: dict[str, list[float]] = {
        "local_disclosure_browser_ms": [],
        "navigation_popover_browser_ms": [],
        "state_control_browser_ms": [],
        "state_control_server_ms": [],
        "prepared_modal_browser_ms": [],
        "prepared_modal_server_ms": [],
    }
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(args.base_url, wait_until="networkidle", timeout=60_000)

        for expected_version in range(1, args.samples + 1):
            details = page.locator('details[data-interaction="local-disclosure"]')
            results["local_disclosure_browser_ms"].append(
                _elapsed(lambda: (details.locator("summary").click(), page.wait_for_function("document.querySelector('details[data-interaction=\"local-disclosure\"]')?.open")))
            )
            details.locator("summary").click()

            results["navigation_popover_browser_ms"].append(
                _elapsed(lambda: (page.get_by_role("button", name="Open navigation").click(), page.locator('[data-interaction-ready="navigation"]').wait_for(state="visible")))
            )
            page.keyboard.press("Escape")

            state = page.locator('[data-interaction-ready="state"]')
            results["state_control_browser_ms"].append(
                _elapsed(lambda: (page.get_by_role("button", name="Change local state").click(), page.wait_for_function("v => document.querySelector('[data-interaction-ready=\"state\"]')?.dataset.version === String(v)", arg=expected_version)))
            )
            results["state_control_server_ms"].append(float(state.get_attribute("data-server-ms") or 0))

            results["prepared_modal_browser_ms"].append(
                _elapsed(lambda: (page.get_by_role("button", name="Open prepared modal").click(), page.locator('[data-interaction-ready="modal"]').wait_for(state="visible")))
            )
            modal_marker = page.locator('[data-interaction-ready="modal"]')
            results["prepared_modal_server_ms"].append(float(modal_marker.get_attribute("data-server-ms") or 0))
            page.locator('[data-testid="stDialog"] button[aria-label="Close"]').click()
            page.locator('[data-testid="stDialog"]').wait_for(state="hidden")
        browser.close()

    payload = {
        "schema": "dynastygm-streamlit-interaction-floor-v1",
        "environment": "local Chromium; deterministic Streamlit fixture; loopback network",
        "samples": args.samples,
        "measurements": {name: _distribution(values) for name, values in results.items()},
        "interpretation": {
            "local_disclosure": "browser layout only; no Streamlit rerun",
            "navigation_popover": "native Streamlit frontend interaction; no app computation",
            "state_control": "full Streamlit state rerun",
            "prepared_modal": "prepared modal opened through Streamlit interaction",
            "browser_minus_server": "loopback transport plus Streamlit frontend reconciliation and paint",
        },
        "privacy": "synthetic labels and aggregate timings only",
    }
    serialized = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
