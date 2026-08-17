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


def test_scrollport_not_inner_block_owns_visible_orb_band():
    assert '[data-testid="stMain"]' in MOBILE_INTERACTION_OVERLAY_CSS
    main_block = MOBILE_INTERACTION_OVERLAY_CSS.split('[data-testid="stMain"]', 1)[1][:700]
    assert "bottom: var(--dg-mobile-shell-clearance)" in main_block
    assert "height: auto !important" in main_block
    assert "scroll-padding-bottom: var(--space-md)" in main_block
    assert "top: 0 !important" in main_block
    assert "@media (max-width: 900px)" in MOBILE_INTERACTION_OVERLAY_CSS


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

    html = f"""<!doctype html>
<html><head><meta charset="utf-8">{APP_CSS}
<style>
html, body, .stApp, [data-testid="stAppViewContainer"] {{
  height: 100%; margin: 0; overflow: hidden; position: relative;
}}
[data-testid="stMain"] {{
  position: absolute; left: 0; right: 0; top: 0; height: 100%; overflow: auto;
}}
.spacer {{ height: 796px; }}
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
    collisions = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width, height in ((320, 568), (320, 640), (390, 844), (430, 932)):
            page = browser.new_page(viewport={"width": width, "height": height})
            page.set_content(html, wait_until="load")
            metrics = page.evaluate(
                """() => {
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
                  const orbBtn = document.querySelector('[data-testid="stButton"] button');
                  const orb = box(orbBtn);
                  const stMain = document.querySelector('[data-testid="stMain"]');
                  const mainBox = box(stMain);
                  const hits = [];
                  for (const id of ['cta','link','expander']) {
                    const visible = intersect(box(document.getElementById(id)), mainBox);
                    if (overlaps(orb, visible)) hits.push(id);
                  }
                  const cs = getComputedStyle(stMain);
                  return {
                    orb, hits, mainBox,
                    mainBottom: cs.bottom, mainHeight: cs.height,
                    orbSize: orb && {w: orb.width, h: orb.height},
                  };
                }"""
            )
            page.close()
            if metrics["hits"]:
                collisions.append((width, height, metrics))
            assert metrics["orbSize"]["w"] == 44
            assert metrics["orbSize"]["h"] == 44
            assert metrics["orb"]["left"] < 60
            assert metrics["mainBox"]["bottom"] <= metrics["orb"]["top"] + 1
        browser.close()
    assert collisions == []
