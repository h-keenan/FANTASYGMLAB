#!/usr/bin/env python3
"""Prove GM-orb CSS scope: unscoped :has() collapses root; scoped does not.

Uses a Streamlit-shaped DOM + production overlay CSS (and a deliberately
broken unscoped variant) under Playwright Chromium. This is the binary
isolation proof for #244 — not a synthetic fixture that skips APP_CSS.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.app_styles import APP_CSS  # noqa: E402
from modules.mobile_interaction_overlay_styles import (  # noqa: E402
    MOBILE_INTERACTION_OVERLAY_CSS,
)


BROKEN_UNSCOPED_ORB_CSS = """
:root { --dg-gm-orb-size: 44px; --touch-target-min: 44px; --dg-overlay-z-nav: 1001000; }
div[data-testid="stVerticalBlock"]:has(.mobile-gm-floating-trigger-marker),
div[class*="st-key-mobile_gm_sheet_trigger_"] {
    bottom: 16px !important;
    height: var(--dg-gm-orb-size) !important;
    left: 16px !important;
    margin: 0 !important;
    overflow: hidden !important;
    padding: 0 !important;
    position: fixed !important;
    width: var(--dg-gm-orb-size) !important;
    z-index: var(--dg-overlay-z-nav) !important;
}
div[data-testid="stVerticalBlock"]:has(.mobile-gm-floating-trigger-marker) [data-testid="stButton"] button > * {
    height: 0 !important;
    opacity: 0 !important;
    overflow: hidden !important;
    width: 0 !important;
}
"""

STREAMLIT_SHAPED_HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<style>
:root {{ --touch-target-min: 44px; --color-shell: #0f1114; }}
body {{ margin: 0; background: #05070c; color: #f8fafc; font-family: sans-serif; }}
.stApp, [data-testid="stAppViewContainer"] {{ min-height: 100vh; }}
.block-container {{ padding: 1rem; }}
{css}
</style>
</head>
<body>
<div class="stApp">
  <div data-testid="stAppViewContainer">
    <section data-testid="stMain">
      <div data-testid="stMainBlockContainer" class="block-container">
        <div data-testid="stVerticalBlock" id="root-vertical">
          <div data-testid="stElementContainer">
            <h1 id="native-title">FGL NATIVE RENDER TEST</h1>
            <p id="native-copy">If you can read this, native Streamlit rendering works.</p>
            <div data-testid="stButton"><button type="button"><span>Native test button</span></button></div>
          </div>
          <div data-testid="stElementContainer">
            <h2 id="dashboard-heading">Dashboard</h2>
            <h3 id="game-plan-heading">Today's Game Plan</h3>
            <div data-testid="stButton"><button type="button"><span>Real Streamlit button</span></button></div>
          </div>
          <div data-testid="stVerticalBlock" class="st-key-mobile_gm_sheet_trigger_dashboard" id="orb-vertical">
            <div data-testid="stElementContainer">
              <div class="mobile-gm-floating-trigger-marker" aria-hidden="true"></div>
            </div>
            <div data-testid="stElementContainer">
              <div data-testid="stButton">
                <button type="button" data-testid="stBaseButton-primary">
                  <span>Open GM menu</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</div>
</body>
</html>
"""


def _measure(page) -> dict:
    return page.evaluate(
        """() => {
          const pick = (sel) => document.querySelector(sel);
          const styleOf = (el) => {
            if (!el) return null;
            const cs = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return {
              exists: true,
              childCount: el.children.length,
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
          const title = pick('#native-title');
          const root = pick('#root-vertical');
          const orb = pick('#orb-vertical');
          const block = pick('.block-container');
          const overlay = document.querySelector('.dg-startup-shell');
          return {
            stAppViewContainer: styleOf(pick('[data-testid="stAppViewContainer"]')),
            stMain: styleOf(pick('[data-testid="stMain"]')),
            blockContainer: styleOf(block),
            rootVertical: styleOf(root),
            orbVertical: styleOf(orb),
            nativeTitle: styleOf(title),
            titleTextVisible: !!(title && title.getClientRects().length
              && getComputedStyle(title).visibility !== 'hidden'
              && Number(getComputedStyle(title).opacity) > 0
              && title.getBoundingClientRect().width > 40
              && title.getBoundingClientRect().height > 10),
            gamePlanVisible: (() => {
              const el = pick('#game-plan-heading');
              if (!el) return false;
              const r = el.getBoundingClientRect();
              return r.width > 40 && r.height > 10;
            })(),
            fullscreenOverlay: !!overlay,
          };
        }"""
    )


def _run_case(browser, css: str, label: str) -> dict:
    html = STREAMLIT_SHAPED_HTML.format(css=css)
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.set_content(html, wait_until="load")
    metrics = _measure(page)
    metrics["label"] = label
    page.close()
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts/p0-gm-orb-css-proof.json"))
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright

    report = {"cases": [], "verdict": "FAIL", "offender": None}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        broken = _run_case(browser, BROKEN_UNSCOPED_ORB_CSS, "unscoped_has_collapse")
        fixed_overlay = _run_case(
            browser, MOBILE_INTERACTION_OVERLAY_CSS, "scoped_overlay_only"
        )
        fixed_app = _run_case(browser, APP_CSS, "full_APP_CSS_scoped")
        browser.close()

    report["cases"] = [broken, fixed_overlay, fixed_app]

    # Binary proof: unscoped collapses root; scoped keeps title readable.
    root_broken = broken.get("rootVertical") or {}
    root_fixed = fixed_overlay.get("rootVertical") or {}
    if not (
        root_broken.get("position") == "fixed"
        and float(root_broken.get("width") or 0) <= 50
        and float(root_broken.get("height") or 0) <= 50
    ):
        report["error"] = "expected unscoped CSS to collapse root vertical block"
        report["broken"] = broken
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    report["offender"] = (
        'div[data-testid="stVerticalBlock"]:has(.mobile-gm-floating-trigger-marker) '
        "without direct-child > scope"
    )
    report["first_breaking_layer"] = "gm_orb_mobile_interaction_css_unscoped_has"

    if not fixed_overlay["titleTextVisible"] or not fixed_app["titleTextVisible"]:
        report["error"] = "scoped CSS still hides native title"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    if root_fixed.get("position") == "fixed" or float(root_fixed.get("width") or 0) <= 50:
        report["error"] = "scoped CSS still fixed-positioned/collapsed the root vertical block"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    if fixed_overlay["orbVertical"]["position"] != "fixed":
        report["error"] = "scoped CSS failed to keep orb block fixed"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    # Broken case: title may still have layout boxes, but it lives inside the
    # 44px fixed root — production-visible area is only the orb.
    if float(broken["nativeTitle"]["width"]) > 60 and broken["rootVertical"]["overflow"] == "hidden":
        report["broken_title_clipped_in_orb_root"] = True

    report["verdict"] = "PASS"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
