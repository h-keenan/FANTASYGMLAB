#!/usr/bin/env python3
"""Forensic header ownership capture — rendered DOM, not CSS source inference."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

VIEWPORTS = ((1280, 800), (1440, 900))
OUT = Path("/opt/cursor/artifacts/header-ownership-forensics")


MEASURE_JS = r"""
() => {
  const chain = (el) => {
    const parts = [];
    let cur = el;
    for (let i = 0; cur && i < 16; i++) {
      const testid = cur.getAttribute && cur.getAttribute('data-testid');
      const cls = (cur.className && typeof cur.className === 'string')
        ? cur.className.split(/\s+/).filter(Boolean).slice(0, 6).join('.')
        : '';
      const key = cls.match(/st-key-[A-Za-z0-9_]+/);
      parts.push({
        tag: cur.tagName,
        testid: testid || null,
        key: key ? key[0] : null,
        cls: cls.slice(0, 140),
      });
      cur = cur.parentElement;
    }
    return parts;
  };
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      x: r.x, y: r.y, width: r.width, height: r.height,
      top: r.top, bottom: r.bottom, left: r.left, right: r.right,
      centerY: r.top + r.height / 2,
      centerX: r.left + r.width / 2,
      display: cs.display,
      alignItems: cs.alignItems,
      justifyContent: cs.justifyContent,
      flex: cs.flex,
      flexDirection: cs.flexDirection,
      gridTemplateColumns: cs.gridTemplateColumns,
      padding: cs.padding,
      paddingTop: cs.paddingTop,
      paddingBottom: cs.paddingBottom,
      paddingLeft: cs.paddingLeft,
      paddingRight: cs.paddingRight,
      margin: cs.margin,
      lineHeight: cs.lineHeight,
      fontSize: cs.fontSize,
      fontWeight: cs.fontWeight,
      fontFamily: cs.fontFamily,
      textTransform: cs.textTransform,
      letterSpacing: cs.letterSpacing,
      transform: cs.transform,
      minHeight: cs.minHeight,
      heightCss: cs.height,
      gap: cs.gap,
      columnGap: cs.columnGap,
      rowGap: cs.rowGap,
      verticalAlign: cs.verticalAlign,
      position: cs.position,
      topCss: cs.top,
    };
  };
  const glyphBox = (el) => {
    if (!el) return null;
    const text = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
    if (!text) return box(el);
    try {
      const range = document.createRange();
      // Prefer first text node for glyph bounds
      const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
      let node = walker.nextNode();
      let best = null;
      while (node) {
        if (node.nodeValue && node.nodeValue.trim()) {
          range.selectNodeContents(node);
          const r = range.getBoundingClientRect();
          if (r.height > 0 && r.width > 0) {
            best = {
              text: node.nodeValue.trim().slice(0, 40),
              top: r.top, bottom: r.bottom, height: r.height, width: r.width,
              centerY: r.top + r.height / 2,
              centerX: r.left + r.width / 2,
            };
            break;
          }
        }
        node = walker.nextNode();
      }
      return best;
    } catch (e) {
      return null;
    }
  };

  const shell = document.querySelector('.dg-executive-shell');
  const brand = document.querySelector('.dg-executive-shell__brand');
  const title = document.querySelector('.dg-executive-shell__title');
  const badge = document.querySelector('.dg-executive-shell__title-row .dg-founder-badge');
  const room = document.querySelector('.dg-executive-shell__room');
  const league = document.querySelector('.dg-executive-shell__league');
  const status = document.querySelector('.dg-executive-shell__status');
  const meta = document.querySelector('.dg-executive-shell__meta');
  const workspace = document.querySelector('[class*="st-key-executive_workspace_shell"]');
  const actions = document.querySelector('[class*="st-key-executive_command_actions"]');

  const buttons = [...document.querySelectorAll(
    '[class*="st-key-executive_command_actions"] div[class*="st-key-executive_command_cell_"] button'
  )].filter(el => el.getBoundingClientRect().width > 0);

  const cmds = buttons.map((btn) => {
    const label = btn.querySelector('p, span:not([aria-hidden="true"])');
    const chevron = btn.querySelector('svg') || btn.querySelector('[aria-hidden="true"]');
    const inner = btn.querySelector(':scope > div');
    return {
      labelText: (btn.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 48),
      button: box(btn),
      buttonChain: chain(btn),
      inner: box(inner),
      labelBox: box(label),
      labelGlyph: glyphBox(label),
      chevronBox: box(chevron),
      chevronGlyph: glyphBox(chevron),
    };
  });

  return {
    dpr: window.devicePixelRatio,
    vw: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    workspace: { box: box(workspace), chain: workspace ? chain(workspace) : [] },
    shell: { box: box(shell), chain: shell ? chain(shell) : [] },
    brand: { box: box(brand), chain: brand ? chain(brand) : [] },
    title: { box: box(title), glyph: glyphBox(title), chain: title ? chain(title) : [] },
    badge: { box: box(badge), glyph: glyphBox(badge), chain: badge ? chain(badge) : [] },
    room: { box: box(room), glyph: glyphBox(room) },
    leagueIdentity: { box: box(league), glyph: glyphBox(league) },
    status: { box: box(status), glyph: glyphBox(status) },
    meta: { box: box(meta) },
    actions: { box: box(actions), chain: actions ? chain(actions) : [] },
    commands: cmds,
  };
}
"""


def analyze(metrics: dict) -> dict:
    cmds = metrics.get("commands") or []
    deltas = []
    for c in cmds:
        btn = c.get("button") or {}
        lg = c.get("labelGlyph") or {}
        cg = c.get("chevronGlyph") or c.get("chevronBox") or {}
        cell_cy = btn.get("centerY")
        text_cy = lg.get("centerY")
        chev_cy = cg.get("centerY")
        deltas.append(
            {
                "label": c.get("labelText"),
                "cell_h": btn.get("height"),
                "cell_top": btn.get("top"),
                "cell_bottom": btn.get("bottom"),
                "cell_cy": cell_cy,
                "text_cy": text_cy,
                "chev_cy": chev_cy,
                "text_vs_cell": None
                if cell_cy is None or text_cy is None
                else round(text_cy - cell_cy, 2),
                "chev_vs_text": None
                if text_cy is None or chev_cy is None
                else round(chev_cy - text_cy, 2),
                "transform": btn.get("transform"),
                "lineHeight": btn.get("lineHeight"),
                "fontSize": btn.get("fontSize"),
                "paddingBlock": f"{btn.get('paddingTop')}/{btn.get('paddingBottom')}",
                "alignItems": btn.get("alignItems"),
            }
        )
    title_g = (metrics.get("title") or {}).get("glyph") or {}
    title_b = (metrics.get("title") or {}).get("box") or {}
    shell = (metrics.get("shell") or {}).get("box") or {}
    return {
        "shell_cy": shell.get("centerY"),
        "title_box_cy": title_b.get("centerY"),
        "title_glyph_cy": title_g.get("centerY"),
        "commands": deltas,
        "text_cy_spread": None
        if len(deltas) < 3
        else round(
            max(d["text_cy"] for d in deltas if d["text_cy"] is not None)
            - min(d["text_cy"] for d in deltas if d["text_cy"] is not None),
            2,
        ),
        "cell_height_set": sorted({round(d["cell_h"] or 0, 2) for d in deltas}),
    }


def assert_clean(analysis: dict) -> list[str]:
    failures: list[str] = []
    cmds = analysis.get("commands") or []
    if len(cmds) < 3:
        return [f"expected 3 commands, got {len(cmds)}"]
    heights = {round(c.get("cell_h") or 0, 1) for c in cmds[:3]}
    if len(heights) != 1:
        failures.append(f"cell height mismatch: {heights}")
    tops = {round(c.get("cell_top") or 0, 1) for c in cmds[:3]}
    bottoms = {round(c.get("cell_bottom") or 0, 1) for c in cmds[:3]}
    if len(tops) != 1:
        failures.append(f"cell top mismatch: {tops}")
    if len(bottoms) != 1:
        failures.append(f"cell bottom mismatch: {bottoms}")
    text_cys = [c["text_cy"] for c in cmds[:3] if c.get("text_cy") is not None]
    if len(text_cys) == 3 and max(text_cys) - min(text_cys) > 1.0:
        failures.append(f"text centerY spread: {text_cys}")
    for c in cmds[:3]:
        if c.get("transform") not in (None, "none"):
            failures.append(f"transform on {c.get('label')}: {c.get('transform')}")
        if c.get("text_vs_cell") is not None and abs(float(c["text_vs_cell"])) > 1.5:
            failures.append(f"text vs cell {c.get('label')}: {c.get('text_vs_cell')}")
        if c.get("chev_vs_text") is not None and abs(float(c["chev_vs_text"])) > 1.0:
            failures.append(f"chev vs text {c.get('label')}: {c.get('chev_vs_text')}")
    return failures


def main() -> int:
    import argparse

    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="after", choices=("before", "after", "capture"))
    parser.add_argument("--base-url", default="http://127.0.0.1:8510")
    parser.add_argument("--assert-clean", action="store_true")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    report = {"viewports": [], "before_or_after": args.label, "assert_failures": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(device_scale_factor=1)
        page = context.new_page()
        page.goto(
            args.base_url.rstrip("/") + "/?surface=header-geometry",
            wait_until="domcontentloaded",
            timeout=90000,
        )
        page.locator("[data-ui-surface='header-geometry']").wait_for(
            state="attached", timeout=90000
        )
        time.sleep(0.6)
        for w, h in VIEWPORTS:
            page.set_viewport_size({"width": w, "height": h})
            time.sleep(0.4)
            metrics = page.evaluate(MEASURE_JS)
            analysis = analyze(metrics)
            shot = OUT / f"header-forensic-{args.label}-{w}x{h}.png"
            page.screenshot(path=str(shot), clip={"x": 0, "y": 0, "width": w, "height": 120})
            fails = assert_clean(analysis) if args.assert_clean else []
            report["viewports"].append(
                {
                    "width": w,
                    "height": h,
                    "screenshot": str(shot),
                    "analysis": analysis,
                    "metrics": metrics,
                    "assert_failures": fails,
                }
            )
            report["assert_failures"].extend([f"{w}x{h}: {f}" for f in fails])
            print(f"=== {w}x{h} dpr={metrics.get('dpr')} ===")
            print(json.dumps(analysis, indent=2))
            if fails:
                print("FAILURES", fails)
        browser.close()
    path = OUT / f"forensic-{args.label}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("wrote", path)
    if args.assert_clean and report["assert_failures"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
