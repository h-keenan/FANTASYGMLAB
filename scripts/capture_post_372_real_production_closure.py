"""Capture production-equivalent post-#372 acceptance evidence."""

from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "post-372-real-production-closure"
BASE = "http://127.0.0.1:8772"


def _wait(page) -> None:
    page.wait_for_load_state("domcontentloaded")
    page.locator('[data-testid="stAppViewContainer"]').wait_for(timeout=30_000)
    page.wait_for_timeout(1_500)


def _rect(page, selector: str):
    return page.locator(selector).first.evaluate(
        """el => { const r=el.getBoundingClientRect(), s=getComputedStyle(el); return {
          top:r.top,bottom:r.bottom,left:r.left,right:r.right,width:r.width,height:r.height,
          radius:s.borderRadius,borderTop:s.borderTopWidth,borderBottom:s.borderBottomWidth,
          paddingTop:s.paddingTop,paddingBottom:s.paddingBottom,marginTop:s.marginTop,marginBottom:s.marginBottom
        }}"""
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    evidence: dict[str, object] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for width in (390, 1440):
            page = browser.new_page(viewport={"width": width, "height": 900})

            page.goto(f"{BASE}/?surface=header-geometry")
            _wait(page)
            shell = '[aria-label="FantasyGM Lab executive command header"]'
            actions = '[class*="st-key-executive_command_actions"]'
            evidence[f"header_{width}"] = {
                "shell": _rect(page, shell),
                "actions": _rect(page, actions),
                "league": _rect(page, f'{actions} button:has-text("League")'),
                "alerts": _rect(page, f'{actions} button:has-text("Alerts")'),
                "you": _rect(page, f'{actions} button:has-text("You")'),
            }
            page.screenshot(path=str(OUT / f"header-{width}.png"), full_page=False)

            page.goto(f"{BASE}/?surface=trade")
            _wait(page)
            auto = page.locator('div[class*="what_is_auto"] button').first
            evidence[f"auto_{width}"] = _rect(page, 'div[class*="what_is_auto"] button')
            if width == 390:
                if page.get_by_role("dialog").count():
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(700)
                page.locator(".trade-summary-card .trade-summary-footer").first.click()
                page.get_by_role("dialog").wait_for()
                page.get_by_role("button", name="Open Tyrone Tracy").click()
                page.locator('[data-trade-dossier-player="11655"]').wait_for()
                evidence["tyrone_first_click"] = {
                    "dialog_count": page.get_by_role("dialog").count(),
                    "dossier_count": page.locator('[data-trade-dossier-player="11655"]').count(),
                }
                page.keyboard.press("Escape")
                page.wait_for_timeout(700)
                page.locator(".trade-summary-card .trade-summary-footer").first.click()
                page.get_by_role("dialog").wait_for()
                page.get_by_role("button", name="Open Pat Bryant").click()
                page.locator('[data-trade-dossier-player="12492"]').wait_for()
                evidence["pat_first_click"] = {
                    "dialog_count": page.get_by_role("dialog").count(),
                    "dossier_count": page.locator('[data-trade-dossier-player="12492"]').count(),
                }
                page.screenshot(path=str(OUT / "trade-detail-player-first-click-390.png"), full_page=False)
            page.close()

        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        for surface in ("league", "recaps", "dashboard", "alerts"):
            page.goto(f"{BASE}/?surface={surface}")
            _wait(page)
            page.screenshot(path=str(OUT / f"{surface}-1440.png"), full_page=False)
            if surface == "league":
                rows = page.locator(".dg-team-comparison-board .dg-ranked-row")
                page.locator(".dg-team-comparison-board").screenshot(
                    path=str(OUT / "team-comparison-1440.png")
                )
                row_metrics = []
                for index in range(rows.count()):
                    row = rows.nth(index)
                    boxes = row.locator(":scope > *").evaluate_all(
                        "els => els.map(el => {const r=el.getBoundingClientRect(); return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,text:el.innerText}})"
                    )
                    row_metrics.append(boxes)
                evidence["team_comparison_1440"] = row_metrics
            elif surface == "recaps":
                page.locator(".dg-lh-feed").screenshot(path=str(OUT / "history-feed-1440.png"))
                evidence["history_1440"] = {
                    "player_portraits": page.locator(".dg-lh-item .dg-player-portrait, .dg-lh-item img").count(),
                    "items": page.locator(".dg-lh-item").count(),
                }
            elif surface == "alerts":
                news_tab = page.get_by_text("News", exact=True)
                if news_tab.count():
                    news_tab.last.click()
                    page.wait_for_timeout(700)
                evidence["alerts_1440"] = {
                    "source_links": page.locator(".dg-alerts-headline--link").count(),
                    "player_actions": page.get_by_role("button", name="Open player").count(),
                }
        page.close()

        for width in (390, 1440):
            page = browser.new_page(viewport={"width": width, "height": 900})
            page.goto(f"{BASE}/?surface=my-team")
            _wait(page)
            cards = page.locator(".my-team-roster-core .dg-football-asset").all()
            diffs = []
            for card in cards[:3]:
                portrait = card.locator(".dg-player-portrait").first
                identity = card.locator(".dg-football-asset__body").first
                if portrait.count() and identity.count():
                    pr = portrait.bounding_box()
                    ir = identity.bounding_box()
                    if pr and ir:
                        diffs.append((pr["y"] + pr["height"] / 2) - (ir["y"] + ir["height"] / 2))
            evidence[f"my_team_center_delta_{width}"] = diffs
            page.screenshot(path=str(OUT / f"my-team-{width}.png"), full_page=False)
            page.close()
        browser.close()
    (OUT / "browser-evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
