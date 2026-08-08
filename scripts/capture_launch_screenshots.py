#!/usr/bin/env python3
"""Capture clean product screenshots for the Founder Beta launch kit.

Hygiene rules (enforced in-browser before capture):
- Close Alerts / remove notification popovers
- Close GM menu overlays
- Prefer fixture-backed harness surfaces (no private league/email data)
- Capture at 390 and 1440 viewports
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "marketing" / "launch" / "screenshots"

# surface query, basename, text that must appear, optional extra query
SURFACES: tuple[tuple[str, str, str, str], ...] = (
    ("dashboard", "dashboard-game-plan", "Today's Game Plan", ""),
    ("dashboard", "what-changed", "What Changed", "&changed=populated"),
    ("trade", "trade-hub", "Value change", ""),
    ("trade", "trade-review", "Review package", ""),
    ("waivers", "waivers", "Waiver Priorities", ""),
    ("player-dossier", "player-quick-view", "Recommendation", ""),
    ("my-team", "decision-memory", "Roster Posture", ""),
    ("my-team", "gm-targets", "Roster Posture", ""),
)

# Note: GM Targets / Decision Memory lack dedicated harness surfaces; my-team and
# dashboard What Changed stand in for roster/history proof. Feature compositions
# always label those lanes [EXPERIMENTAL]. Landing page is captured separately.


HYGIENE_JS = """
() => {
  const kill = [
    '.dg-notification-panel',
    '[data-testid="stPopoverBody"]',
    '[data-testid="stPopoverContent"]',
    '[data-testid="stPopover"]',
    '.dg-gm-sheet',
    '.dg-gm-overlay',
    '.dg-mobile-gm-overlay',
    '[class*="gm-sheet"]',
    '[class*="inbox_harness_open"]',
  ];
  for (const sel of kill) {
    document.querySelectorAll(sel).forEach((node) => node.remove());
  }
  // Hide floating GM orb so it cannot overlap marketing crops.
  document.querySelectorAll(
    '[aria-label*="GM menu"], [aria-label*="Open GM"], .dg-gm-orb, button[title*="GM menu"]'
  ).forEach((node) => { node.style.visibility = 'hidden'; });
}
"""


def _wait_health(url: str, timeout: float = 90.0) -> None:
    import urllib.request

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError(f"Streamlit health check failed: {url}")


def _settle(page, expect_text: str) -> None:
    page.wait_for_selector("[data-ui-surface]", state="attached", timeout=30_000)
    page.wait_for_timeout(600)
    for _ in range(4):
        page.keyboard.press("Escape")
        page.wait_for_timeout(80)
    alerts = page.get_by_role("button", name="Alerts")
    if alerts.count():
        try:
            # If popover is open, Escape already closed it; avoid toggling open.
            page.evaluate(HYGIENE_JS)
        except Exception:
            pass
    page.evaluate(HYGIENE_JS)
    page.locator("[data-ui-surface]").scroll_into_view_if_needed()
    page.wait_for_timeout(250)
    page.get_by_text(expect_text, exact=False).first.wait_for(state="attached", timeout=30_000)
    page.evaluate(HYGIENE_JS)


def _save_png(page, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path), full_page=False)
    with Image.open(path) as image:
        image = image.convert("RGB")
        image.save(path, format="PNG", optimize=True)


def _run_streamlit(script: Path, port: int, log_path: Path) -> subprocess.Popen:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(script),
            "--server.headless",
            "true",
            "--server.address",
            "127.0.0.1",
            "--server.port",
            str(port),
        ],
        cwd=str(ROOT),
        stdout=log_path.open("w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
    )


def _stop(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def capture(*, port: int = 8518, skip_desktop: bool = False) -> list[Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    base = f"http://127.0.0.1:{port}"
    log_path = ROOT / "artifacts" / "launch-capture.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    proc = _run_streamlit(ROOT / "scripts" / "ui_validation_harness.py", port, log_path)
    written: list[Path] = []
    try:
        _wait_health(f"{base}/_stcore/health")
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            # Mobile 390
            mobile = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
            for surface, basename, expect_text, extra in SURFACES:
                mobile.goto(
                    f"{base}/?surface={surface}{extra}",
                    wait_until="networkidle",
                    timeout=60_000,
                )
                _settle(mobile, expect_text)
                path = OUT / f"{basename}-390.png"
                _save_png(mobile, path)
                written.append(path)
                print("captured", path.name)

            if not skip_desktop:
                desk = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
                for surface, basename, expect_text, extra in SURFACES:
                    desk.goto(
                        f"{base}/?surface={surface}{extra}",
                        wait_until="networkidle",
                        timeout=60_000,
                    )
                    _settle(desk, expect_text)
                    path = OUT / f"{basename}-1440.png"
                    _save_png(desk, path)
                    written.append(path)
                    print("captured", path.name)
            browser.close()
    finally:
        _stop(proc)

    # Landing page (marketing module only — no league payload).
    landing_port = port + 1
    landing_log = ROOT / "artifacts" / "launch-landing-capture.log"
    landing_proc = _run_streamlit(
        ROOT / "scripts" / "landing_capture_harness.py",
        landing_port,
        landing_log,
    )
    try:
        landing_base = f"http://127.0.0.1:{landing_port}"
        _wait_health(f"{landing_base}/_stcore/health")
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            for width, height, scale, suffix in (
                (390, 844, 2, "390"),
                (1440, 900, 1, "1440"),
            ):
                if skip_desktop and suffix == "1440":
                    continue
                page = browser.new_page(
                    viewport={"width": width, "height": height},
                    device_scale_factor=scale,
                )
                page.goto(landing_base, wait_until="networkidle", timeout=60_000)
                page.wait_for_timeout(800)
                page.get_by_text("FantasyGM Lab", exact=False).first.wait_for(
                    state="attached", timeout=30_000
                )
                path = OUT / f"landing-{suffix}.png"
                _save_png(page, path)
                written.append(path)
                print("captured", path.name)
            browser.close()
    finally:
        _stop(landing_proc)

    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8518)
    parser.add_argument("--skip-desktop", action="store_true")
    args = parser.parse_args()
    paths = capture(port=args.port, skip_desktop=args.skip_desktop)
    print(f"Wrote {len(paths)} screenshots to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
