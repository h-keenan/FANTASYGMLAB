"""Capture 390/1440 production-equivalent Orb + PQV ownership screenshots."""

from __future__ import annotations

import json
from pathlib import Path

from tests.test_css_dom_ownership import _run_browser, _alpha_bbox
from scripts.css_dom_ownership_fixture import REPRESENTATIVE_PLAYERS, sleeper_fixture_bytes, headshot_facts


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "css-dom-ownership"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {"images": [], "browsers": {}, "production": {}}
    for sleeper_id, name, *_rest in REPRESENTATIVE_PLAYERS:
        payload = sleeper_fixture_bytes(sleeper_id)
        report["images"].append({"name": name, **headshot_facts(sleeper_id), **_alpha_bbox(payload)})
    for engine in ("chromium", "webkit"):
        for width in (390, 1440):
            measured = _run_browser(engine, width, "11655")
            report["browsers"][f"{engine}-{width}"] = {
                k: measured.get(k)
                for k in (
                    "error",
                    "pqvInjected",
                    "pqvAfterApp",
                    "overlayGlyph",
                    "frame",
                    "inner",
                    "imgNatural",
                    "imgComputed",
                    "orb",
                    "trade",
                )
            }
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://app.fantasygmlab.com", wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(4000)
            sw = page.evaluate(
                """() => ({
                  build: (document.querySelector('.dg-build-identity') || {}).textContent || '',
                  sw: !!navigator.serviceWorker && !!navigator.serviceWorker.controller,
                  caches: typeof caches !== 'undefined',
                  scripts: [...document.scripts].slice(0, 8).map(s => s.src).filter(Boolean),
                })"""
            )
            report["production"] = sw
            browser.close()
    except Exception as exc:
        report["production"] = {"error": str(exc)}
    (OUT / "ownership-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2)[:8000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
