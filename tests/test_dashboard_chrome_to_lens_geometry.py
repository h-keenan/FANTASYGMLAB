"""Chrome → Valuation Lens geometry ownership (Streamlit-shaped fixture)."""

from __future__ import annotations

from pathlib import Path

import pytest

from modules.dashboard_workflow_styles import DASHBOARD_WORKFLOW_CSS
from scripts.dashboard_chrome_to_lens_geometry import (
    MEASURE_CHROME_TO_LENS_JS,
    first_screen_fixture_html,
)


ROOT = Path(__file__).resolve().parents[1]


def test_probe_collapse_targets_layout_wrappers_not_nth_child():
    css = DASHBOARD_WORKFLOW_CSS
    assert '[data-testid="stLayoutWrapper"]:has([data-fgl-route-root])' in css
    assert '[data-testid="stLayoutWrapper"]:has([data-fgl-dashboard-root="1"])' in css
    assert '[data-testid="stLayoutWrapper"]:has([data-fgl-hydrate-slot="idle"])' in css
    assert "nth-child" not in css
    assert "translateY" not in css
    route = (ROOT / "modules" / "route_render_ownership.py").read_text(encoding="utf-8")
    assert "data-fgl-route-root" in route


def test_fixture_html_models_the_production_probe_path():
    html = first_screen_fixture_html()
    body = html.split("<body>", 1)[1]
    assert 'data-fgl-route-root="dashboard"' in body
    assert 'data-fgl-hydrate-slot="idle"' in body
    assert 'data-fgl-dashboard-root="1"' in body
    assert 'data-fgl-valuation-lens="1"' in body
    assert "st-key-executive_workspace_shell" in body
    assert body.index("st-key-executive_workspace_shell") < body.index("data-fgl-route-root")
    assert body.index("data-fgl-route-root") < body.index("data-fgl-hydrate-slot")
    assert body.index("data-fgl-hydrate-slot") < body.index("data-fgl-dashboard-root")
    assert body.index("data-fgl-dashboard-root") < body.index("data-fgl-valuation-lens")
    assert "min-height: 2.5rem" in html
    assert "flex: 1 1 auto" in html
    css = DASHBOARD_WORKFLOW_CSS
    collapse = css.split('[data-testid="stLayoutWrapper"]:has([data-fgl-route-root])', 1)[1]
    assert "display: none !important" in collapse
    for marker in (
        "[data-fgl-route-root]",
        '[data-fgl-dashboard-root="1"]',
        '[data-fgl-hydrate-slot="idle"]',
    ):
        assert f'[data-testid="stLayoutWrapper"]:has({marker})' in css


def test_fixture_collapses_route_and_hydrate_layout_wrappers_at_mobile_widths():
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright

    html = first_screen_fixture_html()
    results = {}
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Exception as exc:
            pytest.skip(f"Chromium unavailable for geometry fixture: {exc}")
        try:
            for width in (390, 430, 1440):
                page = browser.new_page(viewport={"width": width, "height": 844 if width < 800 else 900})
                page.set_content(html, wait_until="load")
                results[width] = page.evaluate(MEASURE_CHROME_TO_LENS_JS)
                page.close()
        finally:
            browser.close()

    for width, payload in results.items():
        gap = payload["gap"]
        assert gap is not None, width
        assert gap < 48, f"{width}px chrome-to-lens gap {gap}px; owner={payload.get('owner')}"
        hidden_tall = [
            row
            for row in (payload.get("contributors") or [])
            if row.get("hiddenProbe") and row.get("height", 0) > 8
        ]
        assert not hidden_tall, f"{width}px leftover probe wrappers: {hidden_tall}"
        title = (ROOT / "modules" / "daily_gm_briefing_ui.py").read_text(encoding="utf-8")
        assert "var(--type-section-title)" in title
        assert "var(--type-page-title)" not in title.split(".dg-game-plan-title{", 1)[1][:180]
