"""Capture Notification Center inbox state screenshots."""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

WIDTHS = (320, 390, 430, 768, 1024, 1440)
STATES = (
    ("populated", "populated"),
    ("quiet", "quiet"),
    ("stale", "stale"),
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8510")
    parser.add_argument("--output", default="artifacts/notification-center")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for state, notify in STATES:
            for width in WIDTHS:
                page = browser.new_page(viewport={"width": width, "height": 900})
                page.goto(
                    f"{args.base_url}/?surface=dashboard&notify={notify}",
                    wait_until="domcontentloaded",
                )
                page.get_by_text("Today's Game Plan", exact=False).first.wait_for(
                    timeout=60_000
                )
                # Open Alerts popover
                alerts = page.get_by_role("button", name=lambda n: n.startswith("Alerts"))
                if alerts.count() == 0:
                    alerts = page.locator("button", has_text="Alerts")
                alerts.first.click()
                page.wait_for_timeout(500)
                page.locator(".dg-notification-panel").first.wait_for(timeout=15_000)
                filename = f"inbox-{state}-{width}.png"
                page.screenshot(path=str(output / filename), full_page=False)
                print(f"wrote {filename}", flush=True)
                page.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
