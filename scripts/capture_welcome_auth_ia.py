#!/usr/bin/env python3
"""Capture welcome/auth IA screenshots from the fixture harness."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
CASES = (
    ("anonymous-top", "guest", 390, 844, False),
    ("signin", "signin", 390, 844, False),
    ("create", "create", 390, 844, False),
    ("confirmation", "pending_definite", 390, 844, False),
    ("resend-cooldown", "pending_resend", 390, 844, False),
    ("anonymous-1440", "guest", 1440, 900, False),
    ("anonymous-full-390", "guest", 390, 844, True),
)

EXTRA_WIDTHS = (320, 393, 430, 768, 1024, 1920)


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


def _metrics(page, label: str) -> dict:
    return page.evaluate(
        """(label) => {
          const main = document.querySelector('[data-testid="stMain"]') || document.scrollingElement;
          const buttons = [...document.querySelectorAll('button')];
          const signIn = buttons.find((b) => (b.innerText || '').trim() === 'Sign in');
          const importBtn = buttons.find((b) => (b.innerText || '').includes('Import your league'));
          const guest = buttons.find((b) => (b.innerText || '').includes('Continue as guest'));
          const confirm = document.querySelector('[data-fgl-confirm="1"]');
          const status = document.querySelector('[data-fgl-confirm-status="1"]');
          const alerts = document.querySelectorAll('[data-testid="stAlert"]');
          const rect = (el) => el ? el.getBoundingClientRect() : null;
          const signRect = rect(signIn);
          const mainTop = main ? main.scrollTop : window.scrollY;
          return {
            label,
            viewport: {width: window.innerWidth, height: window.innerHeight},
            pageHeight: main ? main.scrollHeight : document.documentElement.scrollHeight,
            signInTop: signRect ? (signRect.top + mainTop) : null,
            signInInFirstScreen: signRect ? (signRect.top >= 0 && signRect.bottom <= window.innerHeight) : false,
            importTop: importBtn ? rect(importBtn).top : null,
            guestTop: guest ? rect(guest).top : null,
            confirmCount: document.querySelectorAll('[data-fgl-confirm="1"]').length,
            statusCount: document.querySelectorAll('[data-fgl-confirm-status="1"]').length,
            alertCount: alerts.length,
            primaryBeforeSignIn: signIn ? buttons.slice(0, buttons.indexOf(signIn)).filter((b) =>
              (b.getAttribute('kind') === 'primary') || b.className.includes('primary')
            ).length : null,
          };
        }""",
        label,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8510")
    parser.add_argument("--output", default="artifacts/welcome-auth-ia")
    parser.add_argument("--start-server", action="store_true")
    args = parser.parse_args()
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    output.mkdir(parents=True, exist_ok=True)
    proc = None
    if args.start_server:
        log_path = output / "streamlit.log"
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(ROOT / "scripts" / "ui_validation_harness.py"),
                "--server.headless",
                "true",
                "--server.port",
                "8510",
                "--browser.gatherUsageStats",
                "false",
            ],
            cwd=str(ROOT),
            stdout=log_path.open("w"),
            stderr=subprocess.STDOUT,
        )
        _wait_health(f"{args.base_url}/_stcore/health")
    reports = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            for name, fixture, width, height, full_page in CASES:
                page = browser.new_page(viewport={"width": width, "height": height})
                query = f"surface=guest-landing&fixture_auth={fixture}"
                page.goto(f"{args.base_url}/?{query}", wait_until="domcontentloaded")
                page.wait_for_timeout(1800)
                page.get_by_text("Import your league", exact=False).first.wait_for(timeout=20_000)
                shot = output / f"welcome-{name}.png"
                page.screenshot(path=str(shot), full_page=full_page)
                reports.append(_metrics(page, name))
                page.close()
            for width in EXTRA_WIDTHS:
                page = browser.new_page(viewport={"width": width, "height": 844 if width <= 430 else 900})
                page.goto(
                    f"{args.base_url}/?surface=guest-landing&fixture_auth=guest",
                    wait_until="domcontentloaded",
                )
                page.wait_for_timeout(1200)
                reports.append(_metrics(page, f"guest-{width}"))
                page.screenshot(path=str(output / f"welcome-guest-{width}.png"), full_page=False)
                page.close()
            browser.close()
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
    (output / "metrics.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    print(json.dumps(reports, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
