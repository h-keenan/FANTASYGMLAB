"""Capture visual-system unification screenshots from the fixture harness."""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

CASES = (
    ("dashboard", "dashboard-1440.png", 1440, 900, "surface=dashboard&briefing=populated"),
    ("dashboard", "dashboard-390.png", 390, 844, "surface=dashboard&briefing=populated"),
    ("analyzer-builder", "analyzer-builder-1440.png", 1440, 900, "surface=trade-analyzer"),
    ("analyzer-builder", "analyzer-builder-390.png", 390, 844, "surface=trade-analyzer"),
    ("analyzer-result", "analyzer-result-1440.png", 1440, 900, "surface=trade-analyzer&toa=result"),
    ("analyzer-result", "analyzer-result-390.png", 390, 844, "surface=trade-analyzer&toa=result"),
    ("trade-hub", "trade-hub-390.png", 390, 844, "surface=trade"),
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8510")
    parser.add_argument("--output", default="artifacts/visual-system-unify")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for _label, filename, width, height, query in CASES:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(f"{args.base_url}/?{query}", wait_until="domcontentloaded")
            page.wait_for_timeout(1200)
            if "trade" == query.split("&")[0].split("=")[-1]:
                try:
                    page.get_by_text("Review package", exact=False).first.wait_for(timeout=15_000)
                    page.get_by_text("Review package", exact=False).first.click()
                    page.wait_for_timeout(800)
                except Exception:
                    pass
            page.screenshot(path=str(output / filename), full_page=True)
            page.close()
            print(f"wrote {filename}", flush=True)
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
