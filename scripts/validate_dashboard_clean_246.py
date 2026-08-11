#!/usr/bin/env python3
"""Clean Dashboard visibility regression after P0 diagnostic cleanup (#246).

Uses the deterministic UI harness with full production APP_CSS + GM orb on the
Dashboard surface. Asserts no diagnostic UI and no root-collapse regression.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DIAGNOSTIC_NEEDLES = (
    "FGL_P0_",
    "FGL NATIVE RENDER",
    "DASHBOARD_CANARY_",
    "FGL DASHBOARD MINIMAL",
    "FGL_P0_TEST_BUTTON",
    "Native test button",
)

VIEWPORTS = (
    (1280, 800, "desktop1280"),
    (430, 844, "mobile430"),
    (390, 844, "mobile390"),
    (320, 720, "mobile320"),
)


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
              if (r.width < 16 || r.height < 8) continue;
              return true;
            }
            return false;
          };
          const bodyText = document.body && document.body.innerText
            ? document.body.innerText : '';
          const shell = q('.dg-startup-shell');
          let shellCovers = false;
          if (shell) {
            const r = shell.getBoundingClientRect();
            const cs = getComputedStyle(shell);
            shellCovers = cs.display !== 'none' && cs.visibility !== 'hidden'
              && Number(cs.opacity) > 0.05 && r.width > 200 && r.height > 200;
          }
          const root = q('#root-vertical')
            || q('[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"]')
            || q('[data-testid="stVerticalBlock"]');
          const orb = q('.st-key-mobile_gm_sheet_trigger_dashboard')
            || q('[class*="st-key-mobile_gm_sheet_trigger_"]')
            || q('.mobile-gm-floating-trigger-marker')?.closest('[data-testid="stVerticalBlock"]');
          const buttons = Array.from(
            document.querySelectorAll('[data-testid="stButton"] button')
          ).filter((btn) => {
            const label = (btn.innerText || btn.getAttribute('aria-label') || '');
            if (/open gm menu/i.test(label)) return false;
            const r = btn.getBoundingClientRect();
            const cs = getComputedStyle(btn);
            return r.width > 24 && r.height > 20 && cs.visibility !== 'hidden'
              && Number(cs.opacity) > 0;
          });
          return {
            stAppViewContainer: styleOf(q('[data-testid="stAppViewContainer"]')),
            stMain: styleOf(q('[data-testid="stMain"]')),
            blockContainer: styleOf(q('.block-container')),
            dashboardRoot: styleOf(root),
            gmOrbBlock: styleOf(orb),
            gamePlanVisible: textVisible("Today's Game Plan"),
            whatChangedVisible: textVisible('What Changed'),
            deepAnalysisVisible: textVisible('Deep Analysis'),
            lensVisible: textVisible('Lens') || textVisible('Valuation') || textVisible('Archetype'),
            ctaCount: buttons.length,
            fullscreenOverlayCovers: shellCovers,
            bodyTextSample: bodyText.slice(0, 2000),
            scrollWidth: document.documentElement.scrollWidth,
            clientWidth: document.documentElement.clientWidth,
          };
        }"""
    )


def _assert_clean(metrics: dict, *, label: str, viewport_width: int) -> list[str]:
    failures = []
    root = metrics.get("dashboardRoot") or {}
    block = metrics.get("blockContainer") or {}
    orb = metrics.get("gmOrbBlock") or {}
    if not block.get("exists"):
        failures.append(f"{label}: missing .block-container")
    elif float(block.get("width") or 0) < 200:
        failures.append(f"{label}: .block-container too narrow: {block}")
    if not root.get("exists"):
        failures.append(f"{label}: missing dashboard root vertical block")
    else:
        width = float(root.get("width") or 0)
        if width <= 50:
            failures.append(f"{label}: dashboard root collapsed to orb size: {root}")
        if root.get("position") == "fixed" and width <= 60:
            failures.append(f"{label}: dashboard root is fixed/orb-sized: {root}")
        if width < max(200, viewport_width * 0.4):
            failures.append(f"{label}: dashboard root too narrow for viewport: {root}")
    if not metrics.get("gamePlanVisible"):
        failures.append(f"{label}: Today's Game Plan not visible")
    if int(metrics.get("ctaCount") or 0) < 1:
        failures.append(f"{label}: no normal CTA button visible")
    if not orb.get("exists"):
        failures.append(f"{label}: GM orb block missing")
    else:
        if orb.get("position") != "fixed":
            failures.append(f"{label}: GM orb not fixed: {orb}")
        ow = float(orb.get("width") or 0)
        oh = float(orb.get("height") or 0)
        if ow < 36 or ow > 56 or oh < 36 or oh > 56:
            failures.append(f"{label}: GM orb size not ~44px: {orb}")
    if metrics.get("fullscreenOverlayCovers"):
        failures.append(f"{label}: fullscreen startup overlay still covers content")
    body = str(metrics.get("bodyTextSample") or "")
    for needle in DIAGNOSTIC_NEEDLES:
        if needle in body:
            failures.append(f"{label}: diagnostic text still visible: {needle}")
    if "taking longer than usual" in body.casefold():
        failures.append(f"{label}: soft-deadline caption left on ready Dashboard")
    scroll_w = int(metrics.get("scrollWidth") or 0)
    client_w = int(metrics.get("clientWidth") or 0)
    if scroll_w > client_w + 8:
        failures.append(
            f"{label}: unexpected horizontal clipping/overflow {scroll_w}>{client_w}"
        )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8512")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/p0-dashboard-clean-246"),
    )
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
                "8512",
            ],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(
                    args.base_url + "/_stcore/health", timeout=1
                ) as resp:
                    if resp.status == 200:
                        break
            except Exception:
                time.sleep(0.5)
        else:
            if server:
                server.terminate()
            print("Streamlit harness failed health check", file=sys.stderr)
            return 1

    args.output.mkdir(parents=True, exist_ok=True)
    report = {"viewports": {}, "verdict": "FAIL", "failures": []}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            for width, height, name in VIEWPORTS:
                context = browser.new_context(viewport={"width": width, "height": height})
                page = context.new_page()
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
                shot = args.output / f"dashboard-{name}.png"
                page.screenshot(path=str(shot), full_page=True)
                failures = _assert_clean(first, label=f"{name}-t0", viewport_width=width)
                failures.extend(
                    _assert_clean(second, label=f"{name}-t5s", viewport_width=width)
                )
                report["viewports"][name] = {
                    "width": width,
                    "height": height,
                    "t0": first,
                    "t5s": second,
                    "screenshot": str(shot),
                    "failures": failures,
                    "dashboard_root_t5s": second.get("dashboardRoot"),
                    "gm_orb_t5s": second.get("gmOrbBlock"),
                    "overlay_t5s": second.get("fullscreenOverlayCovers"),
                }
                report["failures"].extend(failures)
                context.close()
            browser.close()
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except Exception:
                server.kill()

    report["verdict"] = "PASS" if not report["failures"] else "FAIL"
    (args.output / "report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
