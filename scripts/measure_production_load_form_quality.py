"""Browser production-like load + form accessibility audit.

Measures Streamlit Chromium timings and Chrome-style form issues.
Does not mutate football contracts.

Examples:
  python scripts/measure_production_load_form_quality.py --base-url http://127.0.0.1:8501
  python scripts/measure_production_load_form_quality.py --harness-url http://127.0.0.1:8510
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

A11Y_SCRIPT = """
() => {
  const nodes = [...document.querySelectorAll('input, select, textarea')];
  const describe = (el) => ({
    tag: el.tagName.toLowerCase(),
    type: el.getAttribute('type') || '',
    name: el.getAttribute('name') || '',
    id: el.id || '',
    autocomplete: el.getAttribute('autocomplete'),
    ariaLabel: el.getAttribute('aria-label') || '',
    placeholder: el.getAttribute('placeholder') || '',
    testid: el.closest('[data-testid]')?.getAttribute('data-testid') || '',
    className: (el.className || '').toString().slice(0, 120),
  });
  const emptyAutocomplete = nodes
    .filter((el) => el.hasAttribute('autocomplete') && el.getAttribute('autocomplete') === '')
    .map(describe);
  const unlabeled = nodes.filter((el) => {
    if ((el.getAttribute('type') || '').toLowerCase() === 'hidden') return false;
    if (el.getAttribute('aria-hidden') === 'true') return false;
    const id = el.id;
    const labelledBy = el.getAttribute('aria-labelledby');
    const hasFor = id && document.querySelector(`label[for="${CSS.escape(id)}"]`);
    const wrapping = el.closest('label');
    const aria = (el.getAttribute('aria-label') || '').trim();
    const labelledByText = labelledBy
      ? labelledBy.split(/\\s+/).some((token) => {
          const node = document.getElementById(token);
          return !!(node && (node.textContent || '').trim());
        })
      : false;
    return !(hasFor || wrapping || aria || labelledByText);
  }).map(describe);
  return {
    inputCount: nodes.length,
    emptyAutocomplete,
    unlabeled,
    nodeCount: document.querySelectorAll('*').length,
  };
}
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _audit_page(page) -> dict[str, Any]:
    return page.evaluate(A11Y_SCRIPT)


def _wait_streamlit(page, timeout_ms: int = 60_000) -> None:
    page.wait_for_selector('[data-testid="stApp"]', timeout=timeout_ms)
    page.wait_for_timeout(400)


def _measure_goto(page, url: str, marker: str | None, timeout_ms: int) -> dict[str, Any]:
    started = time.perf_counter()
    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    dcl_ms = (time.perf_counter() - started) * 1000
    try:
        _wait_streamlit(page, timeout_ms=timeout_ms)
        shell_ms = (time.perf_counter() - started) * 1000
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "dcl_ms": round(dcl_ms, 1),
        }
    useful_ms = None
    stable_ms = None
    if marker:
        try:
            page.wait_for_selector(marker, timeout=timeout_ms, state="attached")
            useful_ms = (time.perf_counter() - started) * 1000
        except Exception:
            useful_ms = None
    page.wait_for_timeout(250)
    stable_ms = (time.perf_counter() - started) * 1000
    paints = page.evaluate(
        """() => {
          const nav = performance.getEntriesByType('navigation')[0];
          const paints = Object.fromEntries(
            performance.getEntriesByType('paint').map(e => [e.name, e.startTime])
          );
          return {
            firstPaint: paints['first-paint'] || null,
            firstContentfulPaint: paints['first-contentful-paint'] || null,
            domContentLoaded: nav ? nav.domContentLoadedEventEnd : null,
          };
        }"""
    )
    a11y = _audit_page(page)
    return {
        "ok": True,
        "url": url,
        "dcl_ms": round(dcl_ms, 1),
        "shell_ms": round(shell_ms, 1),
        "useful_ms": None if useful_ms is None else round(useful_ms, 1),
        "stable_ms": round(stable_ms, 1),
        "paints": paints,
        "a11y": a11y,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8501")
    parser.add_argument("--harness-url")
    parser.add_argument("--output", default=str(ROOT / "artifacts" / "production-load-form-quality.json"))
    parser.add_argument("--screenshot-dir", default=str(ROOT / "artifacts" / "production-load-form-quality"))
    parser.add_argument("--timeout-ms", type=int, default=90_000)
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright

    screenshot_dir = Path(args.screenshot_dir)
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "captured_at": _now_iso(),
        "browser": "chromium-headless playwright",
        "flows": {},
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        ws_count = {"n": 0}

        def _on_ws(_ws) -> None:
            ws_count["n"] += 1

        page.on("websocket", _on_ws)

        landing = _measure_goto(
            page,
            args.base_url,
            '[data-fgl-shell-ready="1"], [data-fgl-static-landing], [data-testid="stApp"]',
            args.timeout_ms,
        )
        landing["websocket_count"] = ws_count["n"]
        report["flows"]["cold_landing"] = landing
        page.screenshot(path=str(screenshot_dir / "cold-landing.png"), full_page=True)

        if args.harness_url:
            for surface, marker in (
                ("dashboard", '[data-fgl-dashboard-useful="1"]'),
                ("guest-landing", "[data-fgl-guest-landing='1'], [data-fgl-guest-landing=\"1\"]"),
                ("waivers", "text=Waiver"),
                ("trade", "text=Trade"),
                ("league", "text=Standings"),
            ):
                ws_count["n"] = 0
                url = f"{args.harness_url}?surface={surface.split('-')[0] if surface != 'guest-landing' else 'guest-landing'}"
                if surface == "guest-landing":
                    url = f"{args.harness_url}?surface=guest-landing"
                elif surface == "dashboard":
                    url = f"{args.harness_url}?surface=dashboard"
                elif surface == "waivers":
                    url = f"{args.harness_url}?surface=waivers"
                elif surface == "trade":
                    url = f"{args.harness_url}?surface=trade"
                elif surface == "league":
                    url = f"{args.harness_url}?surface=league"
                sample = _measure_goto(page, url, marker, args.timeout_ms)
                sample["websocket_count"] = ws_count["n"]
                report["flows"][f"harness_{surface}"] = sample
                page.screenshot(
                    path=str(screenshot_dir / f"harness-{surface}.png"),
                    full_page=True,
                )

        browser.close()

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True)[:8000])
    return 0 if report["flows"].get("cold_landing", {}).get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
