#!/usr/bin/env python3
"""Production-CSS-stack visibility regression for Dashboard + GM orb (#244).

Runs the deterministic UI harness (full APP_CSS including overlay) with the GM
orb present on the Dashboard surface, then asserts native Streamlit text and
Game Plan remain visible with non-zero .block-container geometry for 5s.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _measure(page) -> dict:
    return page.evaluate(
        """() => {
          const q = (s) => document.querySelector(s);
          const styleOf = (el) => {
            if (!el) return null;
            const cs = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return {
              exists: true,
              childCount: el.childElementCount,
              width: r.width,
              height: r.height,
              display: cs.display,
              visibility: cs.visibility,
              opacity: cs.opacity,
              position: cs.position,
              overflow: cs.overflow,
              zIndex: cs.zIndex,
            };
          };
          const textVisible = (text) => {
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            while (walker.nextNode()) {
              const node = walker.currentNode;
              if (!(node.nodeValue || '').includes(text)) continue;
              const el = node.parentElement;
              if (!el) continue;
              const r = el.getBoundingClientRect();
              const cs = getComputedStyle(el);
              if (cs.visibility === 'hidden' || Number(cs.opacity) === 0) continue;
              if (r.width < 20 || r.height < 8) continue;
              return true;
            }
            return false;
          };
          const shell = q('.dg-startup-shell');
          let shellCovers = false;
          if (shell) {
            const r = shell.getBoundingClientRect();
            const cs = getComputedStyle(shell);
            shellCovers = cs.display !== 'none' && cs.visibility !== 'hidden'
              && Number(cs.opacity) > 0.05 && r.width > 200 && r.height > 200;
          }
          const buttons = Array.from(document.querySelectorAll('[data-testid="stButton"] button'))
            .filter((btn) => {
              const r = btn.getBoundingClientRect();
              const cs = getComputedStyle(btn);
              return r.width > 20 && r.height > 20 && cs.visibility !== 'hidden'
                && Number(cs.opacity) > 0;
            });
          return {
            stAppViewContainer: styleOf(q('[data-testid="stAppViewContainer"]')),
            stMain: styleOf(q('[data-testid="stMain"]')),
            blockContainer: styleOf(q('.block-container')),
            nativeTitle: textVisible('FGL NATIVE RENDER TEST')
              || textVisible("Today's Game Plan"),
            dashboardHeading: textVisible('Dashboard') || textVisible('FantasyGM Lab'),
            gamePlan: textVisible("Today's Game Plan"),
            realButtonCount: buttons.length,
            fullscreenOverlayCovers: shellCovers,
          };
        }"""
    )


def _assert_visible(metrics: dict, *, label: str) -> list[str]:
    failures = []
    block = metrics.get("blockContainer") or {}
    if not block.get("exists"):
        failures.append(f"{label}: missing .block-container")
    elif float(block.get("width") or 0) < 200 or float(block.get("height") or 0) < 80:
        failures.append(f"{label}: .block-container too small: {block}")
    if not metrics.get("gamePlan"):
        failures.append(f"{label}: Today's Game Plan not visibly rendered")
    if int(metrics.get("realButtonCount") or 0) < 1:
        failures.append(f"{label}: no real Streamlit button with non-zero box")
    if metrics.get("fullscreenOverlayCovers"):
        failures.append(f"{label}: fullscreen startup shell still covers content")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8511")
    parser.add_argument("--output", type=Path, default=Path("artifacts/p0-dashboard-visibility-244"))
    parser.add_argument("--start-server", action="store_true")
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright

    server = None
    if args.start_server:
        server = subprocess.Popen(
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
                "8511",
            ],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 60
        import urllib.request

        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(args.base_url + "/_stcore/health", timeout=1) as resp:
                    if resp.status == 200:
                        break
            except Exception:
                time.sleep(0.5)
        else:
            if server:
                server.terminate()
            print("Streamlit harness failed to become healthy", file=sys.stderr)
            return 1

    args.output.mkdir(parents=True, exist_ok=True)
    report = {"viewports": {}, "verdict": "FAIL", "failures": []}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            for width, height, profile in (
                (1280, 800, "desktop"),
                (390, 844, "mobile390"),
            ):
                context = browser.new_context(viewport={"width": width, "height": height})
                page = context.new_page()
                if profile == "desktop":
                    # Slow-network profile on desktop pass.
                    def _slow(route):
                        time.sleep(0.05)
                        route.continue_()

                    page.route("**/*", _slow)
                page.goto(
                    f"{args.base_url}/?surface=dashboard",
                    wait_until="domcontentloaded",
                    timeout=120_000,
                )
                page.get_by_text("Today's Game Plan", exact=False).first.wait_for(
                    state="attached", timeout=120_000
                )
                page.wait_for_timeout(1000)
                first = _measure(page)
                page.wait_for_timeout(5000)
                second = _measure(page)
                shot = args.output / f"dashboard-{profile}.png"
                page.screenshot(path=str(shot), full_page=True)
                failures = _assert_visible(first, label=f"{profile}-t0")
                failures.extend(_assert_visible(second, label=f"{profile}-t5s"))
                report["viewports"][profile] = {
                    "width": width,
                    "height": height,
                    "t0": first,
                    "t5s": second,
                    "screenshot": str(shot),
                    "failures": failures,
                }
                report["failures"].extend(failures)
                context.close()

            # Explicit slow-network named result (reuse desktop measurements).
            report["viewports"]["slow_network"] = report["viewports"]["desktop"]
            browser.close()
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except Exception:
                server.kill()

    report["verdict"] = "PASS" if not report["failures"] else "FAIL"
    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
