"""Pinned-Chromium proof for Trade Hub landing, route ownership, and wrapping."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(base_url: str, artifact_dir: Path) -> list[dict]:
    from playwright.sync_api import sync_playwright

    artifact_dir.mkdir(parents=True, exist_ok=True)
    reports: list[dict] = []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        for width, height in ((390, 844), (1440, 900)):
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(base_url, wait_until="networkidle")
            page.evaluate(
                """
                () => {
                  window.__dgRouteBodyCounts = [document.querySelectorAll('[data-route-body]').length]
                  window.__dgRouteOwnerCounts = [document.querySelectorAll('[class*="st-key-application_route_body_slot"]').length]
                  window.__dgRouteObserver = new MutationObserver(() => {
                    window.__dgRouteBodyCounts.push(document.querySelectorAll('[data-route-body]').length)
                    window.__dgRouteOwnerCounts.push(document.querySelectorAll('[class*="st-key-application_route_body_slot"]').length)
                  })
                  window.__dgRouteObserver.observe(document.body, {childList:true, subtree:true})
                }
                """
            )
            page.get_by_role("button", name="PQV → Trade Hub").click()
            page.get_by_role("heading", name="Search Around a Player").wait_for()
            page.wait_for_timeout(500)
            report = page.evaluate(
                """
                () => {
                  window.__dgRouteObserver?.disconnect()
                  const main = document.querySelector('[data-testid="stMain"]')
                  const anchor = document.querySelector('[data-dg-scroll-anchor="trade-hub-player-search"]')
                  const important = [...document.querySelectorAll(
                    '.trade-summary-title,.trade-summary-asset-name,.trade-summary-value-label'
                  )]
                  return {
                    route_counts: window.__dgRouteBodyCounts,
                    route_owner_counts: window.__dgRouteOwnerCounts,
                    route_body_count: document.querySelectorAll('[data-route-body]').length,
                    dashboard_count: document.querySelectorAll('[data-route-body="dashboard"]').length,
                    trade_hub_count: document.querySelectorAll('[data-route-body="trade_hub"]').length,
                    anchor_top: anchor?.getBoundingClientRect().top ?? -1,
                    anchor_visible: Boolean(anchor && anchor.getBoundingClientRect().top >= 0
                      && anchor.getBoundingClientRect().top < innerHeight),
                    search_visible: [...document.querySelectorAll('h1,h2,h3')].some(
                      node => node.textContent.includes('Search Around a Player')
                        && node.getBoundingClientRect().top >= 0
                        && node.getBoundingClientRect().top < innerHeight
                    ),
                    scroll_top: Number(main?.scrollTop || 0),
                    horizontal_overflow: document.documentElement.scrollWidth
                      - document.documentElement.clientWidth,
                    clipped_labels: important
                      .filter(node => node.scrollWidth > node.clientWidth + 1)
                      .map(node => node.textContent.trim()),
                  }
                }
                """
            )
            report["width"] = width
            page.screenshot(path=str(artifact_dir / f"trade-navigation-{width}.png"))
            assert report["route_body_count"] == 1, report
            assert report["dashboard_count"] == 0, report
            assert report["trade_hub_count"] == 1, report
            assert min(report["route_owner_counts"]) == 1, report
            assert max(report["route_owner_counts"]) == 1, report
            assert max(report["route_counts"]) <= 1, report
            assert report["anchor_visible"] and report["search_visible"], report
            assert report["scroll_top"] > 0, report
            assert report["horizontal_overflow"] <= 1, report
            assert not report["clipped_labels"], report
            reports.append(report)
            page.close()
        browser.close()
    return reports


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8612")
    parser.add_argument("--artifact-dir", type=Path, default=Path(".artifacts/trade-navigation"))
    args = parser.parse_args()
    print(json.dumps(validate(args.base_url, args.artifact_dir), indent=2, sort_keys=True))
