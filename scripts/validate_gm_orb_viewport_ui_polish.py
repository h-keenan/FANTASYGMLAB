#!/usr/bin/env python3
"""Validate GM Orb stays inside the viewport at 100% zoom (deviceScaleFactor=1).

Uses the deterministic UI harness Dashboard surface with production APP_CSS.
Records bounding rects for every required viewport and asserts inset geometry.
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


def _measure(page) -> dict:
    return page.evaluate(
        """() => {
          const vw = window.innerWidth;
          const vh = window.innerHeight;
          const orb = document.querySelector(
            'div[class*="st-key-mobile_gm_sheet_trigger_"]'
          );
          if (!orb) {
            return {error: 'orb missing', vw, vh, dpr: window.devicePixelRatio};
          }
          const buttons = [...orb.querySelectorAll('button')];
          const btn =
            buttons.find((b) => {
              const r = b.getBoundingClientRect();
              return r.width >= 40 && r.height >= 40;
            }) || null;
          const br = orb.getBoundingClientRect();
          const btnr = btn
            ? btn.getBoundingClientRect()
            : {x: 0, y: 0, width: 0, height: 0, right: 0, bottom: 0};
          let root = null;
          for (const b of document.querySelectorAll(
            '[data-testid="stVerticalBlock"]'
          )) {
            if (b === orb || orb.contains(b)) continue;
            if (b.contains(orb)) {
              const cs = getComputedStyle(b);
              const r = b.getBoundingClientRect();
              root = {
                position: cs.position,
                overflow: cs.overflow,
                width: r.width,
                height: r.height,
              };
              break;
            }
          }
          const within = (r) =>
            r.x >= 0 &&
            r.y >= 0 &&
            r.right <= vw + 0.5 &&
            r.bottom <= vh + 0.5 &&
            r.width >= 40 &&
            r.height >= 40;
          const orbRect = {
            x: br.x,
            y: br.y,
            width: br.width,
            height: br.height,
            right: br.right,
            bottom: br.bottom,
          };
          const btnRect = {
            x: btnr.x,
            y: btnr.y,
            width: btnr.width,
            height: btnr.height,
            right: btnr.right,
            bottom: btnr.bottom,
          };
          return {
            dpr: window.devicePixelRatio,
            zoom: document.documentElement.style.zoom || '1',
            viewport: {width: vw, height: vh},
            orb: orbRect,
            button: btnRect,
            root,
            gap: getComputedStyle(orb).gap,
            display: getComputedStyle(orb).display,
            position: getComputedStyle(orb).position,
            asserts: {
              orbInViewport: within(orbRect),
              buttonInViewport: within(btnRect),
              aligned:
                Math.abs(orbRect.x - btnRect.x) < 1 &&
                Math.abs(orbRect.y - btnRect.y) < 1,
              deliberateInset:
                orbRect.x >= 8 && vh - orbRect.bottom >= 8,
              rootNotFixedOrb:
                !!root &&
                root.position !== 'fixed' &&
                !(root.width <= 50 && root.height <= 50),
              noHorizontalOverflow:
                document.documentElement.scrollWidth <=
                document.documentElement.clientWidth + 1,
            },
          };
        }"""
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default="http://localhost:3030/?surface=dashboard",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "gm-orb-viewport-ui-polish.json",
    )
    parser.add_argument(
        "--screenshot-dir",
        type=Path,
        default=ROOT / "artifacts" / "gm-orb-viewport-ui-polish",
    )
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright

    report = {
        "deviceScaleFactor": 1,
        "browserZoom": "100%",
        "viewports": [],
        "verdict": "FAIL",
    }
    args.screenshot_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        failures = []
        for width, height in VIEWPORTS:
            page = browser.new_page(
                viewport={"width": width, "height": height},
                device_scale_factor=1,
            )
            page.goto(
                f"{args.base_url}&orb_validate={width}x{height}&t={int(time.time())}",
                wait_until="networkidle",
                timeout=90_000,
            )
            page.wait_for_timeout(1200)
            metrics = _measure(page)
            metrics["label"] = f"{width}x{height}"
            report["viewports"].append(metrics)
            asserts = metrics.get("asserts") or {}
            if not all(asserts.values()):
                failures.append({"label": metrics["label"], "asserts": asserts})
            # Screenshots at key sizes
            if (width, height) in ((390, 844), (1280, 800), (1920, 1080)):
                page.screenshot(
                    path=str(
                        args.screenshot_dir / f"dashboard-{width}x{height}.png"
                    ),
                    full_page=False,
                )
                # Orb crop region
                orb = metrics.get("orb") or {}
                if orb.get("width", 0) >= 40:
                    page.screenshot(
                        path=str(
                            args.screenshot_dir / f"gm-orb-{width}x{height}.png"
                        ),
                        clip={
                            "x": max(0, orb["x"] - 8),
                            "y": max(0, orb["y"] - 8),
                            "width": min(orb["width"] + 24, width),
                            "height": min(orb["height"] + 24, height),
                        },
                    )
            page.close()
        browser.close()

    report["failures"] = failures
    report["verdict"] = "PASS" if not failures else "FAIL"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
