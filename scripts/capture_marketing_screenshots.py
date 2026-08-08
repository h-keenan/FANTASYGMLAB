#!/usr/bin/env python3
"""Capture real UI-harness screenshots for the public marketing landing."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "marketing"
SURFACES = (
    ("dashboard", "dashboard.png", "Today's Game Plan"),
    ("trade", "trade-hub.png", "Value change"),
    ("waivers", "waivers.png", "Waiver Priorities"),
    ("player-dossier", "player-quick-view.png", "Recommendation"),
    ("my-team", "decision-memory.png", "Roster Posture"),
)


def _wait_health(url: str, timeout: float = 60.0) -> None:
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


def _compress(path: Path, *, max_width: int = 960, quality: int = 72) -> None:
    with Image.open(path) as image:
        image = image.convert("RGB")
        if image.width > max_width:
            height = int(image.height * (max_width / image.width))
            image = image.resize((max_width, height), Image.Resampling.LANCZOS)
        image.save(path.with_suffix(".jpg"), format="JPEG", quality=quality, optimize=True)
    path.unlink(missing_ok=True)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    port = 8517
    base = f"http://127.0.0.1:{port}"
    log_path = ROOT / "artifacts" / "marketing-capture.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(ROOT / "scripts" / "ui_validation_harness.py"),
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
    try:
        _wait_health(f"{base}/_stcore/health")
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
            def _settle(target, expect_text: str) -> None:
                target.wait_for_selector("[data-ui-surface]", state="attached", timeout=30_000)
                target.wait_for_timeout(700)
                # Toggle-close Alerts if the command-bar popover stole the viewport.
                alerts = target.get_by_role("button", name="Alerts")
                if alerts.count():
                    try:
                        alerts.first.click(timeout=2_000)
                        target.wait_for_timeout(250)
                    except Exception:
                        pass
                for _ in range(3):
                    target.keyboard.press("Escape")
                    target.wait_for_timeout(120)
                target.evaluate(
                    """() => {
                      document.querySelectorAll(
                        '.dg-notification-panel, [class*="inbox_harness_open"], [data-testid="stPopoverBody"], [data-testid="stPopoverContent"]'
                      ).forEach((node) => node.remove());
                    }"""
                )
                target.locator("[data-ui-surface]").scroll_into_view_if_needed()
                target.wait_for_timeout(300)
                target.get_by_text(expect_text, exact=False).first.wait_for(
                    state="attached", timeout=30_000
                )

            for surface, filename, expect_text in SURFACES:
                page.goto(f"{base}/?surface={surface}", wait_until="networkidle", timeout=60_000)
                _settle(page, expect_text)
                png_path = OUT / filename
                page.screenshot(path=str(png_path), full_page=False)
                _compress(png_path)
                print("captured", filename.replace(".png", ".jpg"))
            # Desktop crop for hero atmosphere (dashboard only)
            desk = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
            desk.goto(f"{base}/?surface=dashboard", wait_until="networkidle", timeout=60_000)
            _settle(desk, "Today's Game Plan")
            desk_png = OUT / "dashboard-desktop.png"
            desk.screenshot(path=str(desk_png), full_page=False)
            _compress(desk_png, max_width=1280, quality=70)
            print("captured dashboard-desktop.jpg")
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    inventory = sorted(p.name for p in OUT.glob("*.jpg"))
    (OUT / "README.md").write_text(
        "# Marketing landing screenshots\n\n"
        "Captured from `scripts/ui_validation_harness.py` (real product fixtures, not mockups).\n\n"
        + "\n".join(f"- `{name}`" for name in inventory)
        + "\n",
        encoding="utf-8",
    )
    print("Wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
