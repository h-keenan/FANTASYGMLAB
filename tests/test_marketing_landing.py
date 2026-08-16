"""Public Founder Beta marketing landing contracts."""

from __future__ import annotations

from pathlib import Path

from modules import brand_identity, launch_analytics, marketing_landing, premium_page


ROOT = Path(__file__).resolve().parents[1]


def test_landing_copy_answers_core_questions_without_hype():
    cold = marketing_landing.landing_hero_html() + marketing_landing.landing_body_html(
        billing_configured=False
    )
    html = marketing_landing.landing_hero_html() + marketing_landing.landing_body_html(
        billing_configured=False, detail=True, include_pricing=True
    )
    proof = marketing_landing.landing_proof_html()
    assert brand_identity.PRODUCT_NAME in cold
    assert marketing_landing.TRUST_LINE in cold
    assert marketing_landing.HERO_VALUE in cold
    assert "What it does" not in cold
    assert "How it works" in proof
    assert "Roster decisions" in proof
    assert "Next step" not in cold
    assert "Game Plan" in html
    assert "Trade Hub" in html
    assert "Waivers" in html
    assert "Decision Memory" in html
    assert "GM Targets" in html
    assert "Founder Beta" in html
    assert "Free includes" not in cold
    assert "Free includes" in html
    assert "Included now with Premium" in html
    assert "best in class" not in html.casefold()
    assert "testimonial" not in html.casefold()
    assert "Live billing is not enabled" in html


def test_landing_reuses_premium_page_positioning():
    html = marketing_landing.landing_body_html(
        billing_configured=True, detail=True, include_pricing=True
    )
    for title, _body in premium_page.FREE_INCLUDES:
        assert title in html
    for title, _body in premium_page.PREMIUM_INCLUDED_NOW[:3]:
        assert title in html
    assert "Stripe test mode" in html
    assert "No live charge will be made" in html


def test_landing_analytics_events_are_allowlisted():
    for event in (
        "landing_viewed",
        "primary_cta_clicked",
        "secondary_cta_clicked",
        "pricing_viewed",
        "signup_started",
    ):
        assert event in launch_analytics.TRACKED_EVENTS


def test_launch_screen_wires_marketing_landing():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    launch = source.split("def render_home_launch_screen", 1)[1].split("\ndef ", 1)[0]
    assert "marketing_landing.render_marketing_landing()" in launch
    assert "launch-step-grid" not in launch


def test_marketing_assets_exist():
    required = (
        "dashboard.jpg",
        "trade-share.jpg",
        "waiver-share.jpg",
        "player-share.jpg",
        "decision-memory.jpg",
        "dashboard-desktop.jpg",
        "README.md",
    )
    for name in required:
        path = ROOT / "assets" / "marketing" / name
        assert path.exists(), name
        assert path.stat().st_size > 40, name


def test_landing_css_is_not_global_app_css():
    app_styles = (ROOT / "modules" / "app_styles.py").read_text(encoding="utf-8")
    assert "MARKETING_LANDING_CSS" not in app_styles
    landing = (ROOT / "modules" / "marketing_landing.py").read_text(encoding="utf-8")
    assert "MARKETING_LANDING_CSS" in landing
