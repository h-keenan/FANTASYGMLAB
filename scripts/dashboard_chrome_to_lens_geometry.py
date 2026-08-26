"""Founder/test diagnostic: chrome → Valuation Lens ownership.

Static Streamlit-shaped DOM. No production JS polling. Optional Playwright
measurement lives in tests only.
"""

from __future__ import annotations

from modules.app_styles import APP_CSS
from modules.dashboard_workflow_styles import DASHBOARD_WORKFLOW_CSS
from modules.daily_gm_briefing_ui import DAILY_GM_BRIEFING_CSS
from modules.executive_command_header_styles import EXECUTIVE_COMMAND_HEADER_CSS
from modules.ux_polish_styles import FOUNDER_BETA_UX_CSS


# Streamlit 1.50+ emotion defaults that still apply after inner [hidden].
STREAMLIT_LAYOUT_DEFAULTS = """
<style>
[data-testid="stVerticalBlock"] {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
[data-testid="stLayoutWrapper"] {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-height: 2.5rem;
}
[data-testid="stElementContainer"] {
  min-height: 2.5rem;
  width: 100%;
}
[data-testid="stMarkdown"] { width: 100%; }
</style>
"""

MEASURE_CHROME_TO_LENS_JS = """() => {
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    const text = (el.innerText || "").replace(/\\s+/g, " ").trim().slice(0, 80);
    const hiddenProbe = !!(
      el.querySelector('[data-fgl-route-root]')
      || el.querySelector('[data-fgl-dashboard-root]')
      || el.querySelector('[data-fgl-hydrate-slot]')
      || el.querySelector('[data-fgl-dashboard-useful]')
      || el.querySelector('[data-fgl-dashboard-complete]')
    );
    return {
      tag: el.tagName,
      testid: el.getAttribute('data-testid') || '',
      className: String(el.className || '').slice(0, 160),
      display: cs.display,
      position: cs.position,
      height: Math.round(r.height * 10) / 10,
      minHeight: cs.minHeight,
      flexGrow: cs.flexGrow,
      flexShrink: cs.flexShrink,
      flexBasis: cs.flexBasis,
      marginTop: cs.marginTop,
      marginBottom: cs.marginBottom,
      paddingTop: cs.paddingTop,
      paddingBottom: cs.paddingBottom,
      gap: cs.gap,
      top: Math.round(r.top * 10) / 10,
      bottom: Math.round(r.bottom * 10) / 10,
      empty: !text && !el.querySelector('img,svg,input,select,button,label'),
      hiddenProbe,
      text,
    };
  };
  const chrome = document.querySelector('[class*="st-key-executive_workspace_shell"]')
    || document.querySelector('.dg-executive-shell');
  const lens = document.querySelector('[data-fgl-valuation-lens]')
    || document.querySelector('[class*="st-key-dashboard_page_context"]');
  const chromeBox = chrome ? chrome.getBoundingClientRect() : null;
  const lensBox = lens ? lens.getBoundingClientRect() : null;
  const gap = (chromeBox && lensBox) ? (lensBox.top - chromeBox.bottom) : null;
  const bandTop = chromeBox ? chromeBox.bottom : 0;
  const bandBottom = lensBox ? lensBox.top : 0;
  const contributors = [...document.querySelectorAll(
    '[data-testid="stLayoutWrapper"], [data-testid="stElementContainer"], [data-testid="stVerticalBlock"]'
  )].map(box).filter((row) => {
    if (!row || row.display === 'none') return false;
    if (!(row.height > 1)) return false;
    const overlapsBand = row.bottom > bandTop + 1 && row.top < bandBottom - 1;
    return overlapsBand && (row.hiddenProbe || row.empty);
  }).sort((a, b) => b.height - a.height);
  return {
    gap: gap == null ? null : Math.round(gap * 10) / 10,
    chrome: box(chrome),
    lens: box(lens),
    contributors,
    owner: contributors[0] || null,
  };
}"""


def first_screen_fixture_html() -> str:
    """Chrome → probe wrappers → Valuation Lens, matching production widget order."""

    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{APP_CSS}
<style>{EXECUTIVE_COMMAND_HEADER_CSS}</style>
{FOUNDER_BETA_UX_CSS}
{DASHBOARD_WORKFLOW_CSS}
{DAILY_GM_BRIEFING_CSS}
{STREAMLIT_LAYOUT_DEFAULTS}
</head><body>
<div class="stApp">
  <section data-testid="stMain" style="position:relative">
    <div class="block-container" data-testid="stMainBlockContainer">
      <div data-testid="stVerticalBlock">
        <div data-testid="stLayoutWrapper" class="st-key-application_command_header_slot">
          <div data-testid="stElementContainer">
            <div class="st-key-executive_workspace_shell" data-testid="stVerticalBlock">
              <header class="dg-executive-shell">
                <div class="dg-executive-shell__title">Dashboard</div>
                <div class="dg-executive-shell__league">Revivalry</div>
              </header>
            </div>
          </div>
        </div>
        <div data-testid="stLayoutWrapper" class="route-root-wrap">
          <div data-testid="stElementContainer">
            <div data-testid="stMarkdown">
              <span data-fgl-route-root="dashboard" hidden></span>
            </div>
          </div>
        </div>
        <div data-testid="stLayoutWrapper" class="hydrate-wrap">
          <div data-testid="stElementContainer">
            <div data-testid="stMarkdown">
              <div data-fgl-hydrate-slot="idle" hidden aria-hidden="true"></div>
            </div>
          </div>
        </div>
        <div data-testid="stLayoutWrapper" class="dashboard-root-wrap">
          <div data-testid="stElementContainer">
            <div data-testid="stMarkdown">
              <div data-fgl-dashboard-root="1" aria-hidden="true" hidden></div>
            </div>
          </div>
        </div>
        <div data-testid="stLayoutWrapper" class="st-key-dashboard_workflow">
          <div data-testid="stVerticalBlock" class="st-key-dashboard_page_context">
            <div data-fgl-valuation-lens="1">
              <label>Valuation lens</label>
              <select><option>Dynasty</option></select>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</div>
</body></html>
"""
