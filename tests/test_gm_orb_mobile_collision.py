"""GM Orb must not cover in-flow actionable controls on mobile viewports."""

from __future__ import annotations

from pathlib import Path

from modules.app_styles import APP_CSS
from modules.mobile_interaction_overlay_styles import MOBILE_INTERACTION_OVERLAY_CSS


ROOT = Path(__file__).resolve().parents[1]
OVERLAY = MOBILE_INTERACTION_OVERLAY_CSS.replace(" ", "")


def test_clearance_token_includes_orb_safe_area_and_breathing_room():
    assert "--dg-gm-orb-size: var(--touch-target-min)" in MOBILE_INTERACTION_OVERLAY_CSS
    assert "--dg-mobile-shell-clearance" in MOBILE_INTERACTION_OVERLAY_CSS
    assert "env(safe-area-inset-bottom, 0px)" in MOBILE_INTERACTION_OVERLAY_CSS
    assert "var(--space-3xl)" in MOBILE_INTERACTION_OVERLAY_CSS
    assert "var(--space-md)" in MOBILE_INTERACTION_OVERLAY_CSS


def test_stmain_is_full_height_document_owns_orb_clearance():
    assert '[data-testid="stMain"]' in MOBILE_INTERACTION_OVERLAY_CSS
    media = MOBILE_INTERACTION_OVERLAY_CSS.split("@media (max-width: 900px)", 1)[1]
    main_block = media.split('[data-testid="stMain"]', 1)[1][:900]
    assert "bottom: 0 !important" in main_block
    assert not any(
        line.strip().startswith("bottom: var(--dg-mobile-shell-clearance)")
        for line in main_block.splitlines()
    )
    assert "height: auto !important" in main_block
    assert "scroll-padding-bottom: var(--dg-mobile-shell-clearance)" in main_block
    assert "top: 0 !important" in main_block
    assert "[data-testid=\"stMainBlockContainer\"]" in media.split("[data-testid=\"stMain\"]", 1)[0]
    assert "padding-block-end: var(--dg-mobile-shell-clearance)" in media
    assert "padding-bottom: var(--dg-mobile-shell-clearance)" in media


def test_reserved_orb_band_is_not_a_shortened_scrollport():
    media = MOBILE_INTERACTION_OVERLAY_CSS.split("@media (max-width: 900px)", 1)[1]
    main_block = media.split('[data-testid="stMain"]', 1)[1][:900]
    assert "background-color: transparent !important" in main_block
    assert "background-image: none !important" in main_block
    assert not any(
        line.strip().startswith("bottom: var(--dg-mobile-shell-clearance)")
        for line in main_block.splitlines()
    )
    assert "html," not in media.split("[data-testid=\"stMain\"]", 1)[0]
    assert ".stApp," not in media.split("[data-testid=\"stMain\"]", 1)[0]
    from modules.interface_reimagining_styles import INTERFACE_REIMAGINING_CSS

    assert "background-size: 72px 72px !important" in INTERFACE_REIMAGINING_CSS
    assert ".stApp {" in INTERFACE_REIMAGINING_CSS


def test_orb_stays_fixed_44px_and_scoped():
    assert "position: fixed !important" in MOBILE_INTERACTION_OVERLAY_CSS
    assert "width:var(--dg-gm-orb-size)!important" in OVERLAY
    assert "height:var(--dg-gm-orb-size)!important" in OVERLAY
    assert (
        'stVerticalBlock"]:has(> div[data-testid="stElementContainer"] '
        ".mobile-gm-floating-trigger-marker)"
    ) in MOBILE_INTERACTION_OVERLAY_CSS
    assert 'stVerticalBlock"]:has(.mobile-gm-floating-trigger-marker)' not in MOBILE_INTERACTION_OVERLAY_CSS.replace(
        ':has(> div[data-testid="stElementContainer"] .mobile-gm-floating-trigger-marker)',
        "",
    )
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "def render_mobile_navigation_shell(" in app
    assert "gm_orb_floating_trigger_html()" in app


def test_no_page_special_case_and_no_observer():
    overlay = MOBILE_INTERACTION_OVERLAY_CSS
    assert "Open My Team" not in overlay
    assert "ResizeObserver" not in overlay
    assert "IntersectionObserver" not in overlay


def test_fixture_bounding_boxes_keep_cta_clear_of_orb():
    import pytest

    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright

    def page_html(spacer_px: int) -> str:
        return f"""<!doctype html>
<html><head><meta charset="utf-8">{APP_CSS}
<style>
html, body, .stApp, [data-testid="stAppViewContainer"] {{
  height: 100%; margin: 0; overflow: hidden; position: relative;
}}
[data-testid="stMain"] {{
  position: absolute; left: 0; right: 0; top: 0; height: 100%; overflow: auto;
}}
.spacer {{ height: {spacer_px}px; }}
#cta {{ min-height: 44px; }}
</style></head>
<body>
<div class="stApp" data-testid="stApp">
  <div class="stAppViewContainer" data-testid="stAppViewContainer">
    <section class="stMain" data-testid="stMain">
      <div class="stMainBlockContainer block-container" data-testid="stMainBlockContainer">
        <div class="spacer"></div>
        <button type="button" id="cta">Open My Team</button>
        <a id="link" href="#rankings">League Overview</a>
        <details id="expander"><summary>More</summary><p>Body</p></details>
      </div>
      <div data-testid="stVerticalBlock">
        <div data-testid="stElementContainer">
          <div class="mobile-gm-floating-trigger-marker" aria-hidden="true"></div>
        </div>
        <div data-testid="stElementContainer">
          <div data-testid="stButton">
            <button type="button">Open GM menu</button>
          </div>
        </div>
      </div>
    </section>
  </div>
</div>
</body></html>
"""

    measure = """() => {
      const box = (el) => {
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return {top:r.top,left:r.left,right:r.right,bottom:r.bottom,width:r.width,height:r.height};
      };
      const intersect = (a,b) => {
        if (!a || !b) return null;
        const top = Math.max(a.top, b.top);
        const left = Math.max(a.left, b.left);
        const right = Math.min(a.right, b.right);
        const bottom = Math.min(a.bottom, b.bottom);
        if (right <= left + 1 || bottom <= top + 1) return null;
        return {top,left,right,bottom};
      };
      const overlaps = (a,b) => a && b && !(
        a.right<=b.left+1 || a.left>=b.right-1
        || a.bottom<=b.top+1 || a.top>=b.bottom-1
      );
      const orbRoot = document.querySelector('[class*="st-key-mobile_gm_sheet_trigger_"]')
        || document.querySelector('[data-testid="stVerticalBlock"]:has(.mobile-gm-floating-trigger-marker)');
      const orb = box(orbRoot);
      const stMain = document.querySelector('[data-testid="stMain"]');
      const block = document.querySelector('[data-testid="stMainBlockContainer"]');
      const mainBox = box(stMain);
      const hits = [];
      for (const id of ['cta','link','expander']) {
        const visible = intersect(box(document.getElementById(id)), mainBox);
        if (overlaps(orb, visible)) hits.push(id);
      }
      const cs = getComputedStyle(stMain);
      const blockCs = getComputedStyle(block);
      const view = document.querySelector('[data-testid="stAppViewContainer"]');
      const app = document.querySelector('.stApp');
      const viewCs = getComputedStyle(view);
      const appCs = getComputedStyle(app);
      const cta = box(document.getElementById('cta'));
      return {
        orb, hits, mainBox, cta,
        mainBottom: cs.bottom, mainHeight: cs.height, mainTop: cs.top,
        blockPadBottom: blockCs.paddingBottom,
        orbSize: orb && {w: orb.width, h: orb.height},
        viewBg: viewCs.backgroundColor,
        viewImage: viewCs.backgroundImage,
        appImage: appCs.backgroundImage,
        appSize: appCs.backgroundSize,
        mainBg: cs.backgroundColor,
        exposedPx: innerHeight - (mainBox && mainBox.bottom),
        viewportH: innerHeight,
        appHasGrid: (appCs.backgroundImage || '').includes('linear-gradient'),
        viewTransparent: viewCs.backgroundColor === 'rgba(0, 0, 0, 0)',
        mainTransparent: cs.backgroundColor === 'rgba(0, 0, 0, 0)',
        gap: (orb && cta) ? (orb.top - cta.bottom) : null,
      };
    }"""

    collisions = []
    viewports = ((320, 568), (320, 640), (390, 844), (393, 852), (430, 932))
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width, height in viewports:
            for kind, spacer in (
                ("short", 80),
                ("medium", max(height - 40, 120)),
                ("long", height + 900),
            ):
                page = browser.new_page(viewport={"width": width, "height": height})
                page.set_content(page_html(spacer), wait_until="load")
                top_metrics = page.evaluate(measure)
                page.evaluate(
                    """() => {
                      const main = document.querySelector('[data-testid="stMain"]');
                      if (main) main.scrollTop = main.scrollHeight;
                    }"""
                )
                metrics = page.evaluate(measure)
                page.close()
                if metrics["hits"]:
                    collisions.append((width, height, kind, metrics["hits"]))
                assert metrics["orbSize"]["w"] == 44
                assert metrics["orbSize"]["h"] == 44
                assert metrics["orb"]["left"] < 60
                assert metrics["exposedPx"] < 2, (width, height, kind, metrics["exposedPx"])
                assert metrics["mainBox"]["bottom"] >= height - 2
                assert metrics["mainBottom"] in {"0px", "0"}
                assert float(str(metrics["blockPadBottom"]).replace("px", "") or 0) >= 100
                assert metrics["cta"]["bottom"] <= metrics["orb"]["top"] - 8, (
                    width, height, kind, metrics["cta"], metrics["orb"], metrics["gap"]
                )
                assert "linear-gradient" in (metrics["appImage"] or "")
                assert metrics["appSize"].startswith("72px 72px")
                assert metrics["viewBg"] in {"rgba(0, 0, 0, 0)", "transparent"}
                assert metrics["viewImage"] in {"none", ""}
                assert metrics["mainBg"] in {"rgba(0, 0, 0, 0)", "transparent"}
                assert metrics["appHasGrid"] and metrics["viewTransparent"] and metrics["mainTransparent"]
                assert top_metrics["exposedPx"] < 2
        # Desktop: mobile inset must not apply.
        page = browser.new_page(viewport={"width": 1024, "height": 800})
        page.set_content(page_html(400), wait_until="load")
        desktop = page.evaluate(measure)
        page.close()
        assert desktop["exposedPx"] < 2
        assert desktop["mainBox"]["bottom"] >= 798
        browser.close()
    assert collisions == []
