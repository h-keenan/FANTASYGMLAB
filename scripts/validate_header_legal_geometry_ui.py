#!/usr/bin/env python3
"""Validate header + legal-link geometry at 100% zoom (deviceScaleFactor=1)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

HEADER_VIEWPORTS = (
    (320, 640),
    (390, 844),
    (430, 932),
    (768, 1024),
    (1024, 768),
    (1280, 800),
    (1440, 900),
    (1920, 1080),
)
LEGAL_VIEWPORTS = (
    (390, 844),
    (768, 1024),
    (1280, 800),
    (1440, 900),
)


def _measure_header(page) -> dict:
    return page.evaluate(
        """() => {
          const shell = document.querySelector('.dg-executive-shell');
          const brand = document.querySelector('.dg-executive-shell__brand');
          const title = document.querySelector('.dg-executive-shell__title');
          const badge = document.querySelector('.dg-executive-shell__title-row .dg-founder-badge');
          const meta = document.querySelector('.dg-executive-shell__meta')
            || document.querySelector('.dg-executive-shell__context');
          const rect = (el) => {
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return {
              x: r.x, y: r.y, width: r.width, height: r.height,
              top: r.top, bottom: r.bottom,
              centerY: r.top + r.height / 2,
            };
          };
          const buttons = [...document.querySelectorAll(
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
            const labelCenterY = lr ? lr.top + lr.height / 2 : null;
            const chevronCenterY = cr ? cr.top + cr.height / 2 : null;
            const buttonCenterY = r.top + r.height / 2;
            return {
              label: (el.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 40),
              top: r.top,
              bottom: r.bottom,
              height: r.height,
              centerY: buttonCenterY,
              labelCenterY,
              chevronCenterY,
              labelChevronDelta: (labelCenterY != null && chevronCenterY != null)
                ? Math.abs(labelCenterY - chevronCenterY) : null,
              paddingBlock: cs.paddingTop + ' ' + cs.paddingBottom,
              paddingInline: cs.paddingLeft + ' ' + cs.paddingRight,
              transform: cs.transform,
            };
          });
          return {
            vw: window.innerWidth,
            dpr: window.devicePixelRatio,
            scrollWidth: document.documentElement.scrollWidth,
            shell: rect(shell),
            brand: rect(brand),
            title: rect(title),
            badge: rect(badge),
            warRoom: rect(meta),
            commands: buttons,
          };
        }"""
    )


def _measure_legal(page) -> dict:
    return page.evaluate(
        """() => {
          const links = [...document.querySelectorAll('.legal-footer-link')].map(el => {
            const r = el.getBoundingClientRect();
            const cs = getComputedStyle(el);
            return {
              text: (el.textContent || '').trim(),
              x: r.x, y: r.y, width: r.width, height: r.height,
              paddingInline: cs.paddingLeft + ' / ' + cs.paddingRight,
              paddingBlock: cs.paddingTop + ' / ' + cs.paddingBottom,
              borderRadius: cs.borderRadius,
              background: cs.backgroundColor,
              fontSize: cs.fontSize,
              fontWeight: cs.fontWeight,
              display: cs.display,
              justifyContent: cs.justifyContent,
            };
          });
          return {
            vw: window.innerWidth,
            dpr: window.devicePixelRatio,
            scrollWidth: document.documentElement.scrollWidth,
            links,
          };
        }"""
    )


def _validate_header(metrics: dict, width: int) -> list[str]:
    failures: list[str] = []
    if abs(float(metrics.get("dpr") or 0) - 1.0) > 0.01:
        failures.append(f"dpr != 1: {metrics.get('dpr')}")
    if float(metrics.get("scrollWidth") or 0) > width + 1:
        failures.append(
            f"horizontal overflow scrollWidth={metrics.get('scrollWidth')} vw={width}"
        )
    cmds = metrics.get("commands") or []
    shell = metrics.get("shell") or {}
    if width >= 761:
        if len(cmds) < 3:
            failures.append(f"expected >=3 command cells, got {len(cmds)}")
        else:
            tops = [round(float(c["top"]), 1) for c in cmds[:3]]
            bottoms = [round(float(c["bottom"]), 1) for c in cmds[:3]]
            heights = [round(float(c["height"]), 1) for c in cmds[:3]]
            if max(tops) - min(tops) > 1.5:
                failures.append(f"command top drift: {tops}")
            if max(bottoms) - min(bottoms) > 1.5:
                failures.append(f"command bottom drift: {bottoms}")
            if len(set(heights)) != 1:
                failures.append(f"command height mismatch: {heights}")
            for c in cmds[:3]:
                if c.get("transform") not in (None, "none"):
                    failures.append(f"command transform present: {c.get('transform')}")
                delta = c.get("labelChevronDelta")
                if delta is not None and float(delta) > 2.0:
                    failures.append(f"label/chevron center delta: {delta} ({c.get('label')})")
            if shell.get("centerY") is not None:
                shell_cy = float(shell["centerY"])
                cmd_cy = float(cmds[0]["centerY"])
                if abs(shell_cy - cmd_cy) > 2.5:
                    failures.append(
                        f"shell/command centerline drift: shell={shell_cy} cmd={cmd_cy}"
                    )
                shell_h = float(shell.get("height") or 0)
                cmd_h = float(cmds[0].get("height") or 0)
                if shell_h and abs(shell_h - cmd_h) > 2.5:
                    failures.append(
                        f"shell/command height drift: shell={shell_h} cmd={cmd_h}"
                    )
    return failures


def _validate_legal(metrics: dict, width: int) -> list[str]:
    failures: list[str] = []
    links = metrics.get("links") or []
    if len(links) < 4:
        failures.append(f"expected >=4 legal links, got {len(links)}")
        return failures
    heights = {round(float(item["height"]), 1) for item in links}
    pads_i = {item["paddingInline"] for item in links}
    pads_b = {item["paddingBlock"] for item in links}
    if len(heights) != 1:
        failures.append(f"legal height mismatch: {heights}")
    if len(pads_i) != 1:
        failures.append(f"legal padding-inline mismatch: {pads_i}")
    if len(pads_b) != 1:
        failures.append(f"legal padding-block mismatch: {pads_b}")
    for item in links:
        if float(item["height"]) < 40:
            failures.append(f"legal hit target too small: {item}")
            break
        bg = str(item.get("background") or "")
        # Transparent / no CTA fill on default state.
        if "rgb(34" in bg or "linear-gradient" in bg:
            failures.append(f"legal CTA-like background: {bg}")
    if float(metrics.get("scrollWidth") or 0) > width + 1:
        failures.append(
            f"legal overflow scrollWidth={metrics.get('scrollWidth')} vw={width}"
        )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8510")
    parser.add_argument(
        "--output", default="/opt/cursor/artifacts/header-legal-geometry"
    )
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright

    artifact_dir = Path(args.output)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    results: dict = {"header": [], "legal": []}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(device_scale_factor=1)
        page = context.new_page()

        page.goto(
            args.base_url + "/?surface=header-geometry",
            wait_until="domcontentloaded",
            timeout=90000,
        )
        page.locator("[data-ui-surface='header-geometry']").wait_for(
            state="attached", timeout=90000
        )
        time.sleep(0.5)

        for width, height in HEADER_VIEWPORTS:
            page.set_viewport_size({"width": width, "height": height})
            time.sleep(0.35)
            metrics = _measure_header(page)
            shot = artifact_dir / f"header-{width}x{height}.png"
            # Clip to header band when present.
            shell = page.locator(".dg-executive-shell").first
            try:
                box = shell.bounding_box()
                actions = page.locator(
                    '[class*="st-key-executive_command_actions"]'
                ).first
                abox = actions.bounding_box() if actions.count() else None
                if box:
                    top = max(0, box["y"] - 8)
                    bottom = box["y"] + box["height"]
                    if abox:
                        bottom = max(bottom, abox["y"] + abox["height"])
                    page.screenshot(
                        path=str(shot),
                        clip={
                            "x": 0,
                            "y": top,
                            "width": width,
                            "height": min(height - top, max(80, bottom - top + 16)),
                        },
                    )
                else:
                    page.screenshot(path=str(shot))
            except Exception:
                page.screenshot(path=str(shot))
            failures = _validate_header(metrics, width)
            results["header"].append(
                {
                    "width": width,
                    "height": height,
                    "ok": not failures,
                    "failures": failures,
                    "screenshot": str(shot),
                    "metrics": metrics,
                }
            )

        page.goto(
            args.base_url + "/?surface=design-system",
            wait_until="domcontentloaded",
            timeout=90000,
        )
        page.locator("[data-ui-surface='design-system']").wait_for(
            state="attached", timeout=90000
        )
        time.sleep(0.4)
        for width, height in LEGAL_VIEWPORTS:
            page.set_viewport_size({"width": width, "height": height})
            time.sleep(0.3)
            # Scroll footer into view.
            page.evaluate(
                "() => { const el = document.querySelector('.legal-footer-links'); if (el) el.scrollIntoView({block:'center'}); }"
            )
            time.sleep(0.2)
            metrics = _measure_legal(page)
            shot = artifact_dir / f"legal-{width}x{height}.png"
            nav = page.locator(".legal-footer-links").first
            try:
                box = nav.bounding_box()
                if box:
                    page.screenshot(
                        path=str(shot),
                        clip={
                            "x": max(0, box["x"] - 12),
                            "y": max(0, box["y"] - 12),
                            "width": min(width, box["width"] + 24),
                            "height": min(height, box["height"] + 24),
                        },
                    )
                else:
                    page.screenshot(path=str(shot))
            except Exception:
                page.screenshot(path=str(shot))
            failures = _validate_legal(metrics, width)
            results["legal"].append(
                {
                    "width": width,
                    "height": height,
                    "ok": not failures,
                    "failures": failures,
                    "screenshot": str(shot),
                    "metrics": metrics,
                }
            )

        browser.close()

    summary_path = artifact_dir / "header-legal-geometry-summary.json"
    summary_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    failed = [r for r in results["header"] + results["legal"] if not r["ok"]]
    print(
        json.dumps(
            {
                "failed": len(failed),
                "header": len(results["header"]),
                "legal": len(results["legal"]),
                "summary": str(summary_path),
            },
            indent=2,
        )
    )
    for row in failed:
        print(row["width"], row.get("failures"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
