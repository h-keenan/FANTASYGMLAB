#!/usr/bin/env python3
"""Capture team-comparison and expander chrome at 390/430/1280/1440."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.app_styles import APP_CSS
from modules.league_workspace_ui import team_comparison_row_html

VIEWPORTS = (
    ("390", 390, 844),
    ("430", 430, 932),
    ("1280", 1280, 800),
    ("1440", 1440, 900),
)


def _board_html() -> str:
    rows = [
        team_comparison_row_html(
            power_rank="#1",
            franchise_rank="#4",
            team_name="Charmmanderr",
            owner_text="charliehornsby",
            archetype="Aging Contender",
            style_philosophy="Aggressive Trader · Win-Now · Pick Seller",
            activity="High Activity",
            logo_html="<div class='dg-ranked-logo'>C</div>",
            tap_class=" team-card-tappable",
            tap_attrs=" role='button' tabindex='0'",
            is_current=True,
        ),
        team_comparison_row_html(
            power_rank="#2",
            franchise_rank="#1",
            team_name="Lakefront Franchise",
            owner_text="partner",
            archetype="Pick-rich rebuilder",
            style_philosophy="Patient Trader · Rebuild · Pick Buyer",
            activity="Medium Activity",
            logo_html="<div class='dg-ranked-logo'>L</div>",
            tap_class=" team-card-tappable",
            tap_attrs=" role='button' tabindex='0'",
        ),
        team_comparison_row_html(
            power_rank="#3",
            franchise_rank="#3",
            team_name="Northside Assets",
            owner_text="Manager Three",
            archetype="Contender",
            style_philosophy="Selective Trader · Balanced · Hold Core",
            activity="Low Activity",
            logo_html="<div class='dg-ranked-logo'>N</div>",
            tap_class=" team-card-tappable",
            tap_attrs=" role='button' tabindex='0'",
        ),
    ]
    expander = """
<details data-testid="stExpander" open>
  <summary>Secondary league detail</summary>
  <div data-testid="stExpanderDetails">
    <p style="margin:0;color:var(--text-secondary);font:var(--type-supporting-metadata)">
      Scoring and health stay behind an explicit load, not a nested spreadsheet.
    </p>
  </div>
</details>
"""
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"{APP_CSS}</head><body style='margin:0;background:var(--color-bg);"
        "color:var(--text-primary);padding:16px'>"
        "<h1 style='font:var(--type-section-title);margin:0 0 12px'>Team comparison</h1>"
        "<div class='dg-ranked-board dg-team-comparison-board'>"
        + "".join(rows)
        + "</div>"
        + expander
        + "</body></html>"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "artifacts" / "data-surface-perf-polish"),
    )
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    html = _board_html()
    metrics = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for name, width, height in VIEWPORTS:
            page = browser.new_page(
                viewport={"width": width, "height": height},
                device_scale_factor=1,
            )
            page.set_content(html, wait_until="load")
            page.wait_for_timeout(200)
            measured = page.evaluate(
                """() => {
                  const board = document.querySelector('.dg-team-comparison-board');
                  const expander = document.querySelector('[data-testid="stExpanderDetails"]');
                  const row = document.querySelector('.dg-dense-row');
                  const br = board ? board.getBoundingClientRect() : null;
                  const er = expander ? expander.getBoundingClientRect() : null;
                  const rr = row ? row.getBoundingClientRect() : null;
                  const cs = expander ? getComputedStyle(expander) : null;
                  return {
                    overflowX: document.documentElement.scrollWidth > window.innerWidth + 1,
                    boardOverflowY: board ? getComputedStyle(board).overflowY : null,
                    expanderMaxHeight: cs ? cs.maxHeight : null,
                    expanderOverflow: cs ? cs.overflow : null,
                    rowHeight: rr ? Math.round(rr.height) : 0,
                    boardHeight: br ? Math.round(br.height) : 0,
                    nestedDualScroll: !!(
                      board && expander
                      && getComputedStyle(board).overflowY === 'auto'
                      && (cs.overflowY === 'auto' || cs.overflowY === 'scroll')
                    ),
                  };
                }"""
            )
            measured["viewport"] = name
            metrics.append(measured)
            page.screenshot(
                path=str(out_dir / f"team-comparison-{name}.png"),
                full_page=True,
            )
            page.close()
        browser.close()
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    failures = [
        row
        for row in metrics
        if row.get("overflowX") or row.get("nestedDualScroll")
    ]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
