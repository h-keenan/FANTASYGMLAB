#!/usr/bin/env python3
"""Browser measure: import amatl7 and time hydrate placeholder → first useful."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

USERNAME = os.environ.get("DYNASTYGM_STALL_USERNAME", "amatl7")
BASE = os.environ.get("DYNASTYGM_STALL_BASE", "http://127.0.0.1:8502")
VIEWPORT = int(os.environ.get("DYNASTYGM_STALL_VIEWPORT", "390"))


def main() -> int:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": VIEWPORT, "height": 844},
            device_scale_factor=2 if VIEWPORT <= 430 else 1,
        )
        page.set_default_timeout(120_000)
        t0 = time.perf_counter()
        page.goto(BASE, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        print(f"NAV {(time.perf_counter() - t0) * 1000:.0f}ms title={page.title()}", flush=True)

        guest = page.get_by_role("button", name="Continue as guest")
        if guest.count() and guest.first.is_visible():
            guest.first.click()
            page.wait_for_timeout(1500)
            print("CLICK continue as guest", flush=True)

        user = page.get_by_label("Sleeper username")
        if not user.count():
            user = page.locator("input").first
        user.first.fill(USERNAME)
        print("FILL username", flush=True)

        load = page.get_by_role("button", name="Load my leagues")
        if not load.count():
            load = page.get_by_role("button", name="Load leagues for user")
        t1 = time.perf_counter()
        load.first.click()
        print("CLICK load leagues", flush=True)
        page.get_by_role("button", name="Open Austin and Co.").first.wait_for(timeout=60_000)
        open_austin = page.get_by_role("button", name="Open Austin and Co.")
        if open_austin.count():
            open_austin.first.click()
            print("CLICK OPEN AUSTIN AND CO.", flush=True)
        else:
            austin = page.get_by_text("Austin and Co.", exact=False)
            if austin.count():
                austin.first.click()
                print("CLICK Austin and Co. text", flush=True)
            else:
                for name in ("Continue", "Open"):
                    btn = page.get_by_role("button", name=name)
                    if btn.count():
                        btn.first.click()
                        print(f"CLICK {name}", flush=True)
                        break

        hydrating_at = None
        useful_at = None
        deadline = time.perf_counter() + 90
        while time.perf_counter() < deadline:
            html = page.content()
            if hydrating_at is None and (
                "Updating Dashboard" in html or "data-fgl-dashboard-hydrating" in html
            ):
                hydrating_at = time.perf_counter()
                print(
                    f"HYDRATING visible after {(hydrating_at - t1) * 1000:.0f}ms from load",
                    flush=True,
                )
            if "data-fgl-dashboard-useful" in html or (
                "Today" in html and "Game Plan" in html and "Updating Dashboard" not in html
            ):
                useful_at = time.perf_counter()
                print(
                    f"USEFUL after {(useful_at - t1) * 1000:.0f}ms from load",
                    flush=True,
                )
                break
            page.wait_for_timeout(250)

        stall = None
        if hydrating_at and useful_at:
            stall = (useful_at - hydrating_at) * 1000
            print(f"STALL_HYDRATE_TO_USEFUL {stall:.0f}ms viewport={VIEWPORT}", flush=True)
        elif useful_at:
            print(
                f"USEFUL_WITHOUT_HYDRATE_MARK {(useful_at - t1) * 1000:.0f}ms",
                flush=True,
            )
        else:
            Path("/tmp/dashboard-stall-fail.html").write_text(page.content(), encoding="utf-8")
            print("TIMEOUT no useful Game Plan", flush=True)
            print(page.locator("body").inner_text()[:2000], flush=True)
            browser.close()
            return 1

        screenshot = f"/tmp/dashboard-stall-{VIEWPORT}.png"
        page.screenshot(path=screenshot, full_page=True)
        print(f"SCREENSHOT {screenshot}", flush=True)
        browser.close()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
