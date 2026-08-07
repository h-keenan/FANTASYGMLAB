"""Capture Daily GM Briefing state screenshots across viewports."""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

WIDTHS = (320, 390, 430, 768, 1024, 1280, 1440, 1600)
STATES = (
    ("populated", "populated"),
    ("single", "single"),
    ("quiet", "quiet"),
    ("free", "free"),
    ("premium", "populated"),
    ("loading", "loading"),
)


def _wait_ready(page) -> None:
    page.get_by_text("Today's Game Plan", exact=False).first.wait_for(timeout=60_000)
    page.wait_for_timeout(500)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8510")
    parser.add_argument("--output", default="artifacts/daily-gm-briefing")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for state, briefing in STATES:
            for width in WIDTHS:
                page = browser.new_page(viewport={"width": width, "height": 900})
                page.goto(
                    f"{args.base_url}/?surface=dashboard&briefing={briefing}",
                    wait_until="domcontentloaded",
                )
                _wait_ready(page)
                filename = f"briefing-{state}-{width}.png"
                page.screenshot(path=str(output / filename), full_page=False)
                if width in (390, 1280) and state in (
                    "populated",
                    "quiet",
                    "single",
                    "free",
                    "loading",
                ):
                    page.screenshot(
                        path=str(output / f"briefing-{state}-{width}-full.png"),
                        full_page=True,
                    )
                page.close()
                print(f"wrote {filename}", flush=True)
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
