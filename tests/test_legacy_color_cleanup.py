"""Founder Beta color-system cleanup: tokens own accents; leftover sky/blue is gone."""

from __future__ import annotations

from pathlib import Path

from modules.app_styles import APP_CSS
from modules.brand_identity_styles import BRAND_IDENTITY_CSS
from modules.component_family_styles import COMPONENT_FAMILY_CSS
from modules.design_tokens import DESIGN_TOKEN_CSS
from modules.mobile_interaction_overlay_styles import MOBILE_INTERACTION_OVERLAY_CSS
from modules.startup_coordinator import StartupPhase, startup_shell_html
from modules.trade_analyzer_styles import TRADE_ANALYZER_CSS


ROOT = Path(__file__).resolve().parents[1]

LEGACY_HEX = (
    "#38bdf8",
    "#7dd3fc",
    "#bae6fd",
    "#00c2ff",
    "#00d4ff",
    "#2563eb",
    "#050816",
    "#111827",
    "#e0f2fe",
    "#cffafe",
    "#0ea5e9",
    "#3b82f6",
    "#60a5fa",
)

LEGACY_RGB = (
    "56, 189, 248",
    "125, 211, 252",
    "14, 165, 233",
    "96, 165, 250",
    "37, 99, 235",
    "59, 130, 246",
)

ACTIVE_CSS_SURFACES = (
    APP_CSS,
    BRAND_IDENTITY_CSS,
    COMPONENT_FAMILY_CSS,
    MOBILE_INTERACTION_OVERLAY_CSS,
    TRADE_ANALYZER_CSS,
    startup_shell_html(StartupPhase.PAGE_READY),
    (ROOT / "app.py").read_text(encoding="utf-8"),
    (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"),
)


def _lower(text: str) -> str:
    return text.lower()


def test_streamlit_theme_matches_canonical_tokens():
    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert 'primaryColor = "#22d3ee"' in config
    assert 'backgroundColor = "#050607"' in config
    assert 'secondaryBackgroundColor = "#0f1114"' in config
    assert 'textColor = "#f8fafc"' in config
    assert "#00C2FF" not in config
    assert "#050816" not in config
    assert "#111827" not in config


def test_design_tokens_bridge_streamlit_theme_variables():
    assert "--primary-color: var(--color-accent-strong);" in DESIGN_TOKEN_CSS
    assert "--background-color: var(--color-bg);" in DESIGN_TOKEN_CSS
    assert "--color-accent: #67e8f9;" in DESIGN_TOKEN_CSS
    assert "--color-accent-strong: #22d3ee;" in DESIGN_TOKEN_CSS
    assert "--focus-ring: 0 0 0 3px rgba(103, 232, 249, 0.34);" in DESIGN_TOKEN_CSS


def test_component_family_binds_streamlit_widgets_to_tokens():
    compact = COMPONENT_FAMILY_CSS.replace(" ", "")
    assert "--primary-color:var(--color-accent-strong)" in compact
    assert "accent-color:var(--color-accent-strong)" in compact
    assert '[data-testid="stSlider"][role="slider"]' in compact
    assert '[data-testid="stTabs"][role="tab"][aria-selected="true"]' in compact
    assert "box-shadow:var(--focus-ring)!important" in compact
    assert "*:focus{" not in compact
    assert ":focus-visible" in COMPONENT_FAMILY_CSS


def test_active_css_drops_known_legacy_sky_and_streamlit_blues():
    for surface in ACTIVE_CSS_SURFACES:
        # WR's intentional semantic position color is not a legacy UI accent
        # (matched to Sleeper's own saturated WR blue, not a leftover accent).
        lowered = _lower(surface).replace('--color-position-wr: #38bdf8;', '')
        for hex_value in LEGACY_HEX:
            assert hex_value not in lowered, hex_value
        for rgb in LEGACY_RGB:
            assert rgb not in lowered, rgb


def test_intentional_brand_cyan_and_light_mark_contrast_are_retained():
    assert "--color-accent: #67e8f9;" in DESIGN_TOKEN_CSS
    assert "--color-brand-accent: #22d3ee;" in DESIGN_TOKEN_CSS
    assert "#0891b2" in BRAND_IDENTITY_CSS
    assert "var(--color-brand-accent,#22d3ee)" in BRAND_IDENTITY_CSS.replace(" ", "")
    assert "--color-success: #22c55e;" in DESIGN_TOKEN_CSS
    assert "--color-warning: #f59e0b;" in DESIGN_TOKEN_CSS
    assert "--color-danger: #ef4444;" in DESIGN_TOKEN_CSS
    assert "--color-diagnostic: #8b93ff;" in DESIGN_TOKEN_CSS


def test_focus_and_selected_states_remain_visible():
    assert "var(--focus-ring)" in APP_CSS
    assert ":focus-visible" in APP_CSS
    assert "button[kind=\"primary\"]" in APP_CSS
    assert "color: var(--color-accent) !important;" in APP_CSS or "color: var(--color-accent) !important;" in COMPONENT_FAMILY_CSS or (
        "color:var(--color-accent)!important" in COMPONENT_FAMILY_CSS.replace(" ", "")
    )
    overlay = MOBILE_INTERACTION_OVERLAY_CSS
    assert "box-shadow: var(--focus-ring)" in overlay
    assert "rgba(56, 189, 248" not in overlay


def test_chart_and_tier_presentation_use_canonical_accent():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'CHART_COLORS = ["#22d3ee", "#64748b", "#14b8a6", "#f59e0b", "#ef4444"]' in app
    assert "#2563eb" not in app
    assert "rgba(34, 211, 238, 0.16); color: #67e8f9;" in app
    assert "rgba(56, 189, 248" not in app


def test_color_cleanup_does_not_add_reruns():
    changed = [
        ROOT / "modules" / "app_styles.py",
        ROOT / "modules" / "component_family_styles.py",
        ROOT / "modules" / "design_tokens.py",
        ROOT / "modules" / "startup_coordinator.py",
        ROOT / "modules" / "brand_identity_styles.py",
        ROOT / "modules" / "mobile_interaction_overlay_styles.py",
        ROOT / "modules" / "trade_analyzer_styles.py",
        ROOT / "modules" / "marketing_landing_styles.py",
    ]
    for path in changed:
        assert "st.rerun(" not in path.read_text(encoding="utf-8")
