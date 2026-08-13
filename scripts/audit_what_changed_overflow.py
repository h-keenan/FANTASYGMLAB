#!/usr/bin/env python3
"""Screenshot + overflow audit for What Changed cards at 375/390/430/1280."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "artifacts" / "post-294-what-changed"
WIDTHS = (375, 390, 430, 1280)


def _fixture_html() -> str:
    from modules.decision_change_history import DecisionChangeEvent
    from modules.decision_change_history_ui import (
        DECISION_CHANGE_HISTORY_CSS,
        decision_event_row_html,
    )
    from modules.dense_list_styles import DENSE_LIST_CSS
    from modules.design_tokens import DESIGN_TOKEN_CSS

    events = [
        DecisionChangeEvent(
            event_id="e1",
            recommendation_id="r1",
            league_id="L",
            roster_id="1",
            timestamp=1_722_000_000,
            lifecycle_transition="current->resolved",
            reason="resolved",
            category="Waivers",
            target_label="Bryce Ford-Wheaton",
            player_id="p1",
            destination="waivers",
            previous_state=None,
            current_state=None,
            summary_headline="Waiver opportunity resolved",
            summary_detail="Bryce Ford-Wheaton is no longer available in this league.",
            why_label="Recommendation no longer active",
            scoring_format="PPR",
        ),
        DecisionChangeEvent(
            event_id="e2",
            recommendation_id="r2",
            league_id="L",
            roster_id="1",
            timestamp=1_722_000_000,
            lifecycle_transition="new->current",
            reason="recommendation",
            category="Trades",
            target_label="Christopher Bartholomew Montgomery-Williams IV",
            player_id="p2",
            destination="trade_hub",
            previous_state=None,
            current_state=None,
            summary_headline="Trade window opened with a very long supporting headline for wrap",
            summary_detail=(
                "This recommendation remains the current Trade Hub priority after the "
                "latest Game Plan rebuild and should wrap instead of overflowing."
            ),
            why_label="",
            scoring_format="Half PPR",
        ),
    ]
    cards = []
    for event in events:
        review = (
            "<div class='dg-decision-history-cta'>"
            "<button type='button'>Review →</button>"
            "</div>"
            if "current" in event.lifecycle_transition.split("->")[-1]
            else ""
        )
        cards.append(
            "<div class='dg-what-changed-card st-key-dg_what_changed_card_fixture'>"
            f"{decision_event_row_html(event, include_detail=True)}"
            f"{review}</div>"
        )
    scoped = DECISION_CHANGE_HISTORY_CSS.replace("<style>", "").replace("</style>", "")
    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
{DESIGN_TOKEN_CSS}
{DENSE_LIST_CSS}
{scoped}
body{{background:var(--color-bg);color:var(--text-primary);font-family:var(--font-family-sans),sans-serif;margin:0}}
main{{box-sizing:border-box;max-width:100%;overflow-x:hidden;padding:12px}}
.dg-decision-history-cta button{{background:transparent;border:0;color:var(--text-secondary);min-height:44px}}
</style></head>
<body><main>
<h1 style="font-size:14px;font-weight:600">What Changed</h1>
{''.join(cards)}
</main></body></html>"""


def main() -> int:
    from playwright.sync_api import sync_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    html = _fixture_html()
    (OUT / "fixture.html").write_text(html, encoding="utf-8")
    report: dict = {"widths": {}}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for width in WIDTHS:
            page = browser.new_page(
                viewport={"width": width, "height": 844 if width < 1000 else 900},
                device_scale_factor=2 if width <= 430 else 1,
            )
            page.set_content(html, wait_until="load")
            metrics = page.evaluate(
                """() => {
                  const vw = document.documentElement.clientWidth;
                  const nodes = [...document.querySelectorAll('*')];
                  const overflow = nodes.filter((el) => el.scrollWidth > vw + 1).map((el) => ({
                    tag: el.tagName, className: (el.className||'').toString().slice(0,120),
                    scrollWidth: el.scrollWidth, clientWidth: el.clientWidth
                  }));
                  const values = [...document.querySelectorAll('.dg-dense-metric__value')];
                  const styles = values.map((el) => {
                    const cs = getComputedStyle(el);
                    return {
                      text: el.textContent,
                      overflow: cs.overflow,
                      textOverflow: cs.textOverflow,
                      whiteSpace: cs.whiteSpace,
                      width: el.getBoundingClientRect().width,
                      scrollWidth: el.scrollWidth,
                    };
                  });
                  const clipped = values.filter((el) => el.scrollWidth > el.clientWidth + 1);
                  return {
                    documentScrollWidth: document.documentElement.scrollWidth,
                    viewport: vw,
                    overflowCount: overflow.length,
                    overflowSample: overflow.slice(0, 8),
                    metricStyles: styles,
                    clippedMetrics: clipped.map((el) => el.textContent),
                  };
                }"""
            )
            shot = OUT / f"what-changed-{width}.png"
            page.screenshot(path=str(shot), full_page=True)
            metrics["screenshot"] = str(shot)
            report["widths"][str(width)] = metrics
            page.close()
        browser.close()
    (OUT / "overflow-report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    failures = []
    for width, metrics in report["widths"].items():
        if metrics["documentScrollWidth"] > int(width) + 2:
            failures.append(f"{width} document scroll {metrics['documentScrollWidth']}")
        if metrics["clippedMetrics"]:
            failures.append(f"{width} clipped {metrics['clippedMetrics']}")
        if int(width) <= 430:
            for style in metrics["metricStyles"]:
                if style["textOverflow"] == "ellipsis":
                    failures.append(f"{width} ellipsis on {style['text']}")
    print(json.dumps(report, indent=2))
    if failures:
        print("FAIL", *failures, sep="\n")
        return 1
    print("OK overflow contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
