#!/usr/bin/env python3
"""Capture dense-list hierarchy screenshots at 100% zoom (deviceScaleFactor=1)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

VIEWPORTS = (
    ("desktop", 1440, 900),
    ("430", 430, 932),
    ("390", 390, 844),
    ("320", 320, 640),
)

SURFACES = (
    ("league", "league-rankings"),
    ("my-team", "my-team"),
    ("trade", "trade-hub"),
    ("waivers", "waivers"),
)


def _wait_ready(page, timeout_ms: int = 45000) -> None:
    page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=timeout_ms)
    page.wait_for_timeout(800)


def _measure_ranked(page) -> dict:
    return page.evaluate(
        """() => {
          const rows = [...document.querySelectorAll('.dg-ranked-row.dg-dense-row')];
          const first = rows[0];
          if (!first) return {rowCount: 0};
          const r = first.getBoundingClientRect();
          const metric = first.querySelector('.dg-dense-metric, .dg-ranked-metric');
          const mr = metric ? metric.getBoundingClientRect() : null;
          const exception = first.querySelector('.dg-dense-exception');
          const scrollWidth = document.documentElement.scrollWidth;
          return {
            rowCount: rows.length,
            rowHeight: Math.round(r.height * 10) / 10,
            rowWidth: Math.round(r.width * 10) / 10,
            metricAttached: !!(metric && mr && mr.height > 0),
            hasException: !!exception,
            overflowX: scrollWidth > window.innerWidth + 1,
            viewport: window.innerWidth,
          };
        }"""
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8510")
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "artifacts" / "dense-list-hierarchy"),
    )
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for surface, slug in SURFACES:
            for name, width, height in VIEWPORTS:
                if surface != "league" and name not in {"desktop", "390"}:
                    continue
                context = browser.new_context(
                    viewport={"width": width, "height": height},
                    device_scale_factor=1,
                )
                page = context.new_page()
                url = f"{args.base_url}/?surface={surface}"
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                _wait_ready(page)
                shot = out_dir / f"{slug}-{name}.png"
                page.screenshot(path=str(shot), full_page=True)
                measure = _measure_ranked(page) if surface == "league" else {}
                results.append(
                    {
                        "surface": surface,
                        "viewport": name,
                        "width": width,
                        "height": height,
                        "screenshot": str(shot),
                        "measure": measure,
                    }
                )
                context.close()
        browser.close()

    summary = out_dir / "summary.json"
    summary.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps({"ok": True, "count": len(results), "summary": str(summary)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
