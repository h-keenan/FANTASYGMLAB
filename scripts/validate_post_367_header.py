"""Validate the real command-header renderer at mobile and desktop widths."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8611")
    parser.add_argument("--output", default="artifacts/post-367-header")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {}
    failures: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        for width in (390, 1440):
            page = browser.new_page(viewport={"width": width, "height": 844})
            page.goto(args.base_url, wait_until="networkidle")
            page.wait_for_selector(".dg-executive-shell")
            metrics = page.evaluate(
                """() => {
                  const visible = el => {
                    const r = el.getBoundingClientRect();
                    const s = getComputedStyle(el);
                    return r.width > 0 && r.height > 0 && s.display !== 'none';
                  };
                  const buttons = [...document.querySelectorAll(
                    '[class*="st-key-executive_command_actions"] button[data-testid="stPopoverButton"]'
                  )].filter(visible);
                  const wrappers = [...document.querySelectorAll(
                    '[class*="st-key-executive_command_actions"] [data-testid="stPopover"] > div[aria-haspopup="true"]'
                  )].filter(visible);
                  return {
                    headers: document.querySelectorAll('.dg-executive-shell').length,
                    startupHeroes: document.querySelectorAll('.app-hero').length,
                    routeTitles: [...document.querySelectorAll('.dg-executive-shell__title')].map(el => el.textContent.trim()),
                    labels: buttons.map(el => el.innerText.replace(/\\s+/g, ' ').trim()),
                    buttonRadii: buttons.map(el => getComputedStyle(el).borderRadius),
                    wrapperRadii: wrappers.map(el => getComputedStyle(el).borderRadius),
                    shellRadii: [...document.querySelectorAll('.dg-executive-shell,[class*="st-key-executive_workspace_shell"]')].filter(visible).map(el => getComputedStyle(el).borderRadius),
                    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                    exceptions: document.querySelectorAll('[data-testid="stException"]').length,
                  };
                }"""
            )
            page.screenshot(path=str(output / f"header-{width}x844.png"), full_page=True)
            if metrics["headers"] != 1:
                failures.append(f"{width}: settled header count {metrics['headers']}")
            if metrics["startupHeroes"]:
                failures.append(f"{width}: authenticated startup hero remained")
            if metrics["labels"][:3] != ["LEAGUE expand_more", "ALERTS expand_more", "YOU expand_more"]:
                failures.append(f"{width}: command labels {metrics['labels']}")
            radii = metrics["buttonRadii"] + metrics["wrapperRadii"] + metrics["shellRadii"]
            if not radii or any(radius != "0px" for radius in radii):
                failures.append(f"{width}: rounded visible command surface {radii}")
            if metrics["overflow"] > 1 or metrics["exceptions"]:
                failures.append(f"{width}: overflow/exceptions {metrics}")

            page.evaluate(
                """() => {
                  window.__post367HeaderCounts = [];
                  const sample = () => window.__post367HeaderCounts.push(
                    document.querySelectorAll('.dg-executive-shell').length
                  );
                  sample();
                  new MutationObserver(sample).observe(document.body, {childList:true, subtree:true});
                }"""
            )
            page.get_by_role("button", name="Switch route", exact=True).click()
            page.wait_for_function(
                """() => document.querySelectorAll(
                  '[class*="st-key-executive_command_actions"] button[data-testid="stPopoverButton"]'
                ).length === 3""",
                timeout=10_000,
            )
            page.wait_for_timeout(1200)
            transition = page.evaluate(
                """() => ({
                  counts: window.__post367HeaderCounts,
                  current: document.querySelectorAll('.dg-executive-shell').length,
                  titles: [...document.querySelectorAll('.dg-executive-shell__title')].map(el => el.textContent.trim()),
                  startupHeroes: document.querySelectorAll('.app-hero').length,
                  exceptions: document.querySelectorAll('[data-testid="stException"]').length,
                })"""
            )
            page.screenshot(path=str(output / f"header-route-transition-{width}x844.png"), full_page=True)
            if (
                not transition["counts"]
                or min(transition["counts"]) != 1
                or max(transition["counts"]) != 1
                or transition["current"] != 1
            ):
                failures.append(f"{width}: transition header counts {transition['counts']}")
            if len(transition["titles"]) != 1 or transition["startupHeroes"] or transition["exceptions"]:
                failures.append(f"{width}: transition ownership {transition}")
            report[str(width)] = {"settled": metrics, "transition": transition}
            page.close()
        browser.close()

    report["failures"] = failures
    (output / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
