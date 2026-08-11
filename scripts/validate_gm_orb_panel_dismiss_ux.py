#!/usr/bin/env python3
"""Browser-test GM Orb destination panel dismiss interactions at 100% zoom."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWPORTS = (
    (320, 640),
    (390, 844),
    (430, 932),
    (768, 1024),
    (1280, 800),
    (1440, 900),
    (1920, 1080),
)


def _orb_button(page):
    orb = page.locator('div[class*="st-key-mobile_gm_sheet_trigger_"]').first
    buttons = orb.locator("button")
    for i in range(buttons.count()):
        btn = buttons.nth(i)
        box = btn.bounding_box()
        if box and box.get("width", 0) >= 40 and box.get("height", 0) >= 40:
            return btn
    return buttons.last


def _panel(page):
    return page.locator(
        'div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker)'
    ).first


def _panel_visible(page) -> bool:
    loc = _panel(page)
    try:
        return loc.count() > 0 and loc.is_visible()
    except Exception:
        return False


def _wait_panel(page, *, open_: bool, timeout: float = 15_000) -> None:
    deadline = time.monotonic() + timeout / 1000
    while time.monotonic() < deadline:
        if _panel_visible(page) == open_:
            return
        page.wait_for_timeout(150)
    raise AssertionError(f"panel open={open_} not reached")


def _orb_in_viewport(page) -> dict:
    return page.evaluate(
        """() => {
          const vw = innerWidth, vh = innerHeight;
          const orb = document.querySelector('div[class*="st-key-mobile_gm_sheet_trigger_"]');
          const buttons = [...(orb ? orb.querySelectorAll('button') : [])];
          const btn = buttons.find(b => {
            const r = b.getBoundingClientRect();
            return r.width >= 40 && r.height >= 40;
          });
          const target = btn || orb;
          const r = target.getBoundingClientRect();
          const root = (() => {
            for (const b of document.querySelectorAll('[data-testid="stVerticalBlock"]')) {
              if (orb && (b === orb || orb.contains(b))) continue;
              if (orb && b.contains(orb)) {
                const cs = getComputedStyle(b);
                const br = b.getBoundingClientRect();
                return {position: cs.position, w: br.width, h: br.height};
              }
            }
            return null;
          })();
          return {
            dpr: devicePixelRatio,
            vw, vh,
            rect: {x:r.x,y:r.y,w:r.width,h:r.height,right:r.right,bottom:r.bottom},
            inView: r.x>=0 && r.y>=0 && r.right<=vw+0.5 && r.bottom<=vh+0.5 && r.width>=40 && r.height>=40,
            rootOk: !!root && root.position !== 'fixed' && !(root.w<=50 && root.h<=50),
            hOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
            closeDestinations: [...document.querySelectorAll('button')].some(
              b => (b.innerText||'').trim().toLowerCase() === 'close destinations'
            ),
          };
        }"""
    )


def _run_interactions(page) -> dict:
    results = {}
    orb = _orb_button(page)

    # 1) open
    orb.click()
    _wait_panel(page, open_=True)
    results["open"] = True
    assert not page.get_by_role("button", name="Close destinations").count()
    results["no_close_destinations_label"] = True
    close_btn = page.get_by_role("button", name="Close").first
    assert close_btn.count() or page.locator(
        'div[class*="st-key-mobile_sheet_close"] button'
    ).count()
    results["close_control_present"] = True

    # 2) inside non-nav click (sheet note / title) must NOT dismiss
    title = page.locator(".mobile-gm-sheet-title").first
    if title.count():
        title.click(position={"x": 4, "y": 4})
        page.wait_for_timeout(600)
        assert _panel_visible(page)
        results["inside_click_keeps_open"] = True

    # 3) Escape closes
    page.keyboard.press("Escape")
    _wait_panel(page, open_=False)
    results["escape_closes"] = True

    # 4) open again
    _orb_button(page).click()
    _wait_panel(page, open_=True)

    # 5) orb toggle closes
    _orb_button(page).click()
    _wait_panel(page, open_=False)
    results["orb_toggle_closes"] = True

    # 6) open + outside click closes
    _orb_button(page).click()
    _wait_panel(page, open_=True)
    # Click a known outside target (workspace title / page background)
    page.mouse.click(300, 40)
    _wait_panel(page, open_=False)
    results["outside_click_closes"] = True

    # 7) open + × closes
    _orb_button(page).click()
    _wait_panel(page, open_=True)
    closer = page.locator('div[class*="st-key-mobile_sheet_close"] button').first
    closer.click()
    _wait_panel(page, open_=False)
    results["explicit_close_closes"] = True

    # 8) open + destination closes
    _orb_button(page).click()
    _wait_panel(page, open_=True)
    trade = page.get_by_role("button", name="Trade Hub").first
    trade.click()
    _wait_panel(page, open_=False)
    results["destination_closes"] = True

    # 9) repeated open/close/open
    _orb_button(page).click()
    _wait_panel(page, open_=True)
    _orb_button(page).click()
    _wait_panel(page, open_=False)
    _orb_button(page).click()
    _wait_panel(page, open_=True)
    results["repeated_open_close_open"] = True

    # Dashboard/workspace still visible
    assert page.get_by_text("Founder workspace", exact=False).first.is_visible()
    results["workspace_visible"] = True
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default="http://localhost:3030/?surface=navigation",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "gm-orb-panel-dismiss-ux.json",
    )
    parser.add_argument(
        "--screenshot-dir",
        type=Path,
        default=ROOT / "artifacts" / "gm-orb-panel-dismiss-ux",
    )
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright

    report = {
        "deviceScaleFactor": 1,
        "browserZoom": "100%",
        "interactions": {},
        "viewports": [],
        "verdict": "FAIL",
        "failures": [],
    }
    args.screenshot_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        # Interaction matrix at desktop
        page = browser.new_page(
            viewport={"width": 1280, "height": 800}, device_scale_factor=1
        )
        page.goto(args.base_url, wait_until="networkidle", timeout=90_000)
        page.wait_for_timeout(1200)
        try:
            report["interactions"] = _run_interactions(page)
            page.screenshot(
                path=str(args.screenshot_dir / "panel-open-desktop.png"),
                full_page=False,
            )
        except Exception as exc:
            report["failures"].append(f"interactions: {exc}")
            page.screenshot(
                path=str(args.screenshot_dir / "interaction-failure.png"),
                full_page=False,
            )
        page.close()

        # Orb geometry across viewports (panel closed)
        for w, h in VIEWPORTS:
            page = browser.new_page(
                viewport={"width": w, "height": h}, device_scale_factor=1
            )
            page.goto(
                f"{args.base_url}&orb={w}x{h}",
                wait_until="networkidle",
                timeout=90_000,
            )
            page.wait_for_timeout(800)
            metrics = _orb_in_viewport(page)
            metrics["label"] = f"{w}x{h}"
            report["viewports"].append(metrics)
            if not metrics.get("inView") or not metrics.get("rootOk") or metrics.get(
                "hOverflow"
            ):
                report["failures"].append(f"viewport {w}x{h}: {metrics}")
            if metrics.get("closeDestinations"):
                report["failures"].append(f"viewport {w}x{h}: Close destinations label")
            page.close()
        browser.close()

    if not report["failures"] and report.get("interactions"):
        report["verdict"] = "PASS"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
