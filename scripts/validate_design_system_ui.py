#!/usr/bin/env python3
"""Validate design-system geometry at 100% zoom (deviceScaleFactor=1).

Asserts computed styles for disclosures, deep analysis, filters, legal footer,
trade cards, and desktop header command-cell bounding boxes across viewports.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

VIEWPORTS = (
    (320, 640),
    (390, 844),
    (430, 932),
    (768, 1024),
    (1280, 800),
    (1440, 900),
    (1920, 1080),
)

SQUARE_RADII = {"0px", "0"}


def _parse_radius(value: str) -> set[str]:
    parts = [part.strip() for part in str(value or "").replace("/", " ").split() if part.strip()]
    return set(parts) or {"missing"}


def _is_square(radius: str) -> bool:
    parts = _parse_radius(radius)
    return parts.issubset(SQUARE_RADII)


def _measure(page) -> dict:
    return page.evaluate(
        """() => {
          const vw = window.innerWidth;
          const scrollWidth = document.documentElement.scrollWidth;
          const expanders = [...document.querySelectorAll('div[data-testid="stExpander"]')].map(el => {
            const cs = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            const summary = el.querySelector('summary');
            const scs = summary ? getComputedStyle(summary) : null;
            const sr = summary ? summary.getBoundingClientRect() : null;
            return {
              radius: cs.borderRadius,
              background: cs.backgroundColor,
              border: cs.borderTopColor,
              height: r.height,
              summaryHeight: sr ? sr.height : null,
              summaryRadius: scs ? scs.borderRadius : null,
            };
          });
          const deepButtons = [...document.querySelectorAll(
            '[class*="dashboard_deep_analysis_nav"] [data-testid="stButton"] button'
          )].map(el => {
            const cs = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return {radius: cs.borderRadius, height: r.height, background: cs.backgroundColor};
          });
          const footer = [...document.querySelectorAll('.legal-footer-link')].map(el => {
            const cs = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return {
              radius: cs.borderRadius,
              height: r.height,
              background: cs.backgroundColor,
              fontWeight: cs.fontWeight,
            };
          });
          const inputs = [...document.querySelectorAll(
            'div[class*="st-key-player_asset_explorer_"] input, div[data-testid="stTextInput"] input'
          )].slice(0, 3).map(el => {
            const cs = getComputedStyle(el);
            return {radius: cs.borderRadius, height: el.getBoundingClientRect().height};
          });
          const pills = [...document.querySelectorAll('div[data-testid="stPills"] button')].slice(0, 4).map(el => {
            const cs = getComputedStyle(el);
            return {radius: cs.borderRadius, height: el.getBoundingClientRect().height};
          });
          const trade = [...document.querySelectorAll('.trade-summary-card, .trade-idea-card')].slice(0, 2).map(el => {
            const cs = getComputedStyle(el);
            return {radius: cs.borderRadius, background: cs.backgroundColor};
          });
          const commandButtons = [...document.querySelectorAll(
            '[class*="st-key-executive_command_actions"] div[class*="st-key-executive_command_cell_"] button'
          )].filter(el => {
            const r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0;
          }).map(el => {
            const r = el.getBoundingClientRect();
            const cs = getComputedStyle(el);
            const chevron = el.querySelector('svg') || el.querySelector('[aria-hidden="true"]');
            const cr = chevron ? chevron.getBoundingClientRect() : null;
            const label = el.querySelector('p, span:not([aria-hidden="true"])');
            const lr = label ? label.getBoundingClientRect() : null;
            return {
              label: (el.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 40),
              top: r.top,
              height: r.height,
              width: r.width,
              left: r.left,
              right: r.right,
              centerX: r.left + r.width / 2,
              labelCenterX: lr ? lr.left + lr.width / 2 : null,
              chevronCenterY: cr ? cr.top + cr.height / 2 : null,
              buttonCenterY: r.top + r.height / 2,
              radius: cs.borderRadius,
              paddingInline: cs.paddingInline || `${cs.paddingLeft} ${cs.paddingRight}`,
            };
          });
          const orb = document.querySelector('div[class*="st-key-mobile_gm_sheet_trigger_"]');
          const orbBox = orb ? orb.getBoundingClientRect() : null;
          return {
            vw,
            dpr: window.devicePixelRatio,
            scrollWidth,
            overflow: scrollWidth > vw + 1,
            expanders,
            deepButtons,
            footer,
            inputs,
            pills,
            trade,
            commandButtons,
            orb: orbBox ? {width: orbBox.width, height: orbBox.height, bottom: orbBox.bottom, left: orbBox.left} : null,
          };
        }"""
    )


def _assert_square_family(name: str, items: list[dict], failures: list[str]) -> None:
    if not items:
        failures.append(f"{name}: missing")
        return
    radii = {_is_square(item.get("radius", "")) for item in items}
    if False in radii:
        failures.append(f"{name}: non-square radius {[item.get('radius') for item in items]}")


def validate(page, width: int, height: int, artifact_dir: Path) -> dict:
    page.set_viewport_size({"width": width, "height": height})
    page.goto(
        f"http://127.0.0.1:8510/?surface=design-system",
        wait_until="domcontentloaded",
        timeout=60000,
    )
    page.wait_for_selector("[data-ui-surface='design-system']", timeout=60000)
    time.sleep(0.6)
    metrics = _measure(page)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    shot = artifact_dir / f"design-system-{width}x{height}.png"
    page.screenshot(path=str(shot), full_page=True)
    failures: list[str] = []
    if abs(float(metrics.get("dpr") or 0) - 1.0) > 0.01:
        failures.append(f"dpr != 1: {metrics.get('dpr')}")
    if metrics.get("overflow"):
        failures.append(f"horizontal overflow scrollWidth={metrics.get('scrollWidth')} vw={width}")
    _assert_square_family("expanders", metrics.get("expanders") or [], failures)
    _assert_square_family("deepButtons", metrics.get("deepButtons") or [], failures)
    _assert_square_family("footer", metrics.get("footer") or [], failures)
    _assert_square_family("inputs", metrics.get("inputs") or [], failures)
    _assert_square_family("trade", metrics.get("trade") or [], failures)
    pills = metrics.get("pills") or []
    if pills:
        # Segmented filters may remain capsule-shaped.
        non_capsule = [
            item.get("radius")
            for item in pills
            if "999px" not in str(item.get("radius") or "")
            and not _is_square(str(item.get("radius") or ""))
            and "50%" not in str(item.get("radius") or "")
        ]
        # Accept either segment (999) or control (0); reject mid-card radii.
        mid = []
        for item in pills:
            radius = str(item.get("radius") or "")
            if any(token in radius for token in ("12px", "14px", "16px", "18px")):
                mid.append(radius)
        if mid:
            failures.append(f"pills using card radii: {mid}")
    footer = metrics.get("footer") or []
    for item in footer:
        try:
            if float(item.get("height") or 0) < 40:
                failures.append(f"footer hit target too small: {item.get('height')}")
                break
        except (TypeError, ValueError):
            failures.append(f"footer height unreadable: {item}")
            break
    cells = metrics.get("commandButtons") or []
    if width >= 761 and len(cells) >= 3:
        tops = [round(float(cell["top"]), 1) for cell in cells[:3]]
        heights = {round(float(cell["height"]), 1) for cell in cells[:3]}
        if max(tops) - min(tops) > 1.5:
            failures.append(f"command top drift: {tops}")
        if len(heights) != 1:
            failures.append(f"command height mismatch: {heights}")
        centers = [
            abs(float(cell["chevronCenterY"]) - float(cell["buttonCenterY"]))
            for cell in cells[:3]
            if cell.get("chevronCenterY") is not None
        ]
        if centers and max(centers) > 2.0:
            failures.append(f"chevron vertical centering drift: {centers}")
        # Optical centering: label+chevron group should sit near cell center.
        optical = []
        for cell in cells[:3]:
            if cell.get("labelCenterX") is None:
                continue
            optical.append(abs(float(cell["labelCenterX"]) - float(cell["centerX"])))
        # Labels alone are left of chevron; allow room for the pair.
        if optical and max(optical) > max(48.0, width * 0.08):
            failures.append(f"command label optical drift: {optical}")
    orb = metrics.get("orb")
    if orb and (float(orb.get("width") or 0) > 80 or float(orb.get("height") or 0) > 80):
        failures.append(f"orb geometry regression: {orb}")
    return {
        "width": width,
        "height": height,
        "ok": not failures,
        "failures": failures,
        "screenshot": str(shot),
        "metrics": metrics,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8510")
    parser.add_argument("--output", default="artifacts/design-system-ui")
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright

    artifact_dir = ROOT / args.output
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(device_scale_factor=1)
        page = context.new_page()
        # Warm
        page.goto(args.base_url + "/?surface=design-system", wait_until="domcontentloaded", timeout=90000)
        page.wait_for_selector("[data-ui-surface='design-system']", timeout=90000)
        for width, height in VIEWPORTS:
            results.append(validate(page, width, height, artifact_dir))
        browser.close()
    summary = artifact_dir / "design-system-summary.json"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps(results, indent=2), encoding="utf-8")
    failed = [row for row in results if not row["ok"]]
    print(json.dumps({"failed": len(failed), "viewports": len(results), "summary": str(summary)}, indent=2))
    for row in failed:
        print(row["width"], row["failures"])
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
