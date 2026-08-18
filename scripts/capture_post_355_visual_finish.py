"""Capture post-#355 390/1440 visual-finish screenshots and geometry."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "post-355-visual-finish"
PORT = 8522
BASE = f"http://127.0.0.1:{PORT}"


def _wait_ready(page) -> None:
    page.wait_for_selector("text=Synthetic fixture only", timeout=90_000)


def _measure_hero(page) -> dict:
    return page.evaluate(
        """() => {
          const frame = document.querySelector('.pqv-hero-portrait');
          const img = document.querySelector('.pqv-hero-portrait img, .pqv-hero-portrait .dg-player-headshot-image');
          if (!frame) return {error: 'missing hero frame'};
          const fr = frame.getBoundingClientRect();
          const cs = getComputedStyle(frame);
          const imgCs = img ? getComputedStyle(img) : null;
          const ir = img ? img.getBoundingClientRect() : null;
          return {
            frame: {w: Math.round(fr.width), h: Math.round(fr.height), square: Math.abs(fr.width - fr.height) < 1},
            imgBox: ir && {w: Math.round(ir.width), h: Math.round(ir.height), top: Math.round(ir.top - fr.top)},
            scale: cs.getPropertyValue('--dg-headshot-scale').trim(),
            focus: cs.getPropertyValue('--dg-headshot-focus').trim(),
            imgTransform: imgCs && imgCs.transform,
            imgObjectPosition: imgCs && imgCs.objectPosition,
            imgNatural: img && {w: img.naturalWidth, h: img.naturalHeight},
          };
        }"""
    )


def _measure_orb_gap(page) -> dict:
    return page.evaluate(
        """() => {
          const rows = [...document.querySelectorAll('div[class*="st-key-mobile_sheet_row_"]')];
          return rows.map(row => {
            const button = row.querySelector('button');
            if (!button) return null;
            const glyph = getComputedStyle(button, '::before');
            const label = button.querySelector('p, span') || button;
                      const t = label.getBoundingClientRect();
                      const padL = parseFloat(getComputedStyle(button).paddingLeft) || 0;
                      const glyphW = parseFloat(glyph.width) || 0;
                      const gRight = button.getBoundingClientRect().left + padL + glyphW;
            const after = getComputedStyle(button, '::after').content;
            return {
              label: (button.innerText || '').replace(/\\s+/g, ' ').trim(),
              glyphRight: Math.round(gRight),
              glyphLeft: Math.round(button.getBoundingClientRect().left + padL),
              glyphW: Math.round(glyphW),
              labelLeft: Math.round(t.left),
              gap: Math.round(t.left - gRight),
              after,
              kind: button.getAttribute('kind'),
              overlayGlyph: !!row.querySelector('.dg-gm-route-glyph'),
            };
          }).filter(Boolean);
        }"""
    )


def _measure_actions(page) -> dict:
    return page.evaluate(
        """() => {
          const root = document.querySelector('div[class*="st-key-pqv_actions_"]');
          if (!root) return {error: 'missing actions'};
          const r = root.getBoundingClientRect();
          const buttons = [...root.querySelectorAll('button')].map(b => {
            const box = b.getBoundingClientRect();
            return {label: (b.innerText||'').trim(), w: Math.round(box.width), h: Math.round(box.height)};
          });
          return {height: Math.round(r.height), width: Math.round(r.width), buttons};
        }"""
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [
            "python3",
            "-m",
            "streamlit",
            "run",
            str(ROOT / "scripts" / "ui_validation_harness.py"),
            "--server.port",
            str(PORT),
            "--server.headless",
            "true",
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    report: dict = {"port": PORT, "shots": [], "measures": {}}
    try:
        time.sleep(6)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            for width, height in ((390, 844), (1440, 900)):
                page = browser.new_page(viewport={"width": width, "height": height})
                page.goto(f"{BASE}/?surface=navigation", wait_until="networkidle", timeout=90_000)
                _wait_ready(page)
                page.get_by_role("button", name="Open GM menu").click()
                page.get_by_text("Where to go", exact=True).wait_for(timeout=30_000)
                page.wait_for_timeout(400)
                shot = OUT / f"gm-orb-{width}.png"
                page.screenshot(path=str(shot), full_page=False)
                report["shots"].append(str(shot.name))
                if width == 390:
                    report["measures"]["orb390"] = _measure_orb_gap(page)
                if width == 1440:
                    report["measures"]["orb1440"] = _measure_orb_gap(page)
                page.close()

                for player in ("tracy", "jones", "wr", "qb", "te", "missing"):
                    page = browser.new_page(viewport={"width": width, "height": height})
                    page.goto(
                        f"{BASE}/?surface=player-dossier&pqv_player={player}",
                        wait_until="networkidle",
                        timeout=90_000,
                    )
                    _wait_ready(page)
                    page.wait_for_timeout(400)
                    try:
                        page.wait_for_function(
                            "() => { const img = document.querySelector('.pqv-hero-portrait img'); return !img || img.naturalWidth > 0; }",
                            timeout=8_000,
                        )
                    except Exception:
                        pass
                    except BaseException:
                        pass
                    if width == 390 and player == "tracy":
                        report["measures"]["tracyHero"] = _measure_hero(page)
                        report["measures"]["actions390"] = _measure_actions(page)
                        page.screenshot(path=str(OUT / "390-tracy-hero.png"), full_page=False)
                        page.locator(".pqv-career-dossier, .pqv-career-glance").first.scroll_into_view_if_needed()
                        page.screenshot(path=str(OUT / "390-tracy-career-actions.png"), full_page=False)
                        page.get_by_role("button", name="STATS").click()
                        page.get_by_role("button", name="Hide details").wait_for(timeout=30_000)
                        page.wait_for_timeout(400)
                        page.get_by_text("Bio", exact=True).first.scroll_into_view_if_needed()
                        page.screenshot(path=str(OUT / "390-more-details-bio.png"), full_page=False)
                        page.get_by_text("Advanced analysis", exact=True).first.scroll_into_view_if_needed()
                        page.screenshot(path=str(OUT / "390-advanced-analysis.png"), full_page=False)
                        report["measures"]["tracyHeroAfterMore"] = _measure_hero(page)
                    if width == 1440 and player == "tracy":
                        report["measures"]["tracyHero1440"] = _measure_hero(page)
                        page.screenshot(path=str(OUT / "1440-pqv-tracy.png"), full_page=False)
                    page.screenshot(
                        path=str(OUT / f"{width}-{player}-dossier.png"),
                        full_page=False,
                    )
                    page.close()

                page = browser.new_page(viewport={"width": width, "height": height})
                page.goto(f"{BASE}/?surface=trade", wait_until="networkidle", timeout=90_000)
                _wait_ready(page)
                page.wait_for_timeout(600)
                try:
                    page.wait_for_selector(".dg-compact-asset--standard, .dg-player-headshot--standard", timeout=15_000)
                except Exception:
                    pass
                page.screenshot(path=str(OUT / f"{width}-trade-ideas.png"), full_page=False)
                if width == 390:
                    report["measures"]["tradePortrait"] = page.evaluate(
                        """() => {
                          const el = document.querySelector('.dg-compact-asset--standard .dg-compact-asset-avatar, .dg-compact-asset--standard .dg-player-headshot');
                          if (!el) return {error: 'missing standard portrait'};
                          const r = el.getBoundingClientRect();
                          return {w: Math.round(r.width), h: Math.round(r.height)};
                        }"""
                    )
                page.close()
            browser.close()
        (OUT / "measures.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report["measures"], indent=2))
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
