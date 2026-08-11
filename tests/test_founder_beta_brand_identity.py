"""Focused Founder Beta brand & identity presentation tests."""

from __future__ import annotations

from pathlib import Path

from modules import brand_identity, feedback, premium, premium_page, startup_coordinator, trade_hub_ui
from modules.app_styles import APP_CSS
from modules.brand_identity_styles import BRAND_IDENTITY_CSS


def test_brand_constants_are_fantasygm_lab():
    assert brand_identity.PRODUCT_NAME == "FantasyGM Lab"
    assert brand_identity.PRODUCT_MARK == "FGL"
    assert brand_identity.FOUNDER_BETA_LABEL == "Founder Beta"
    assert brand_identity.EXPERIMENTAL_LABEL == "[EXPERIMENTAL]"


def test_founder_beta_badge_is_compact_not_banner():
    html = brand_identity.founder_beta_badge_html(compact=True)
    assert "dg-founder-badge" in html
    assert "Founder Beta" in html
    assert "banner" not in html.casefold()
    # Compact chip avoids repeating the product name next to the shell mark.
    assert "FantasyGM Lab" not in html
    full = brand_identity.founder_beta_badge_html(compact=False)
    assert "FantasyGM Lab" in full
    assert "Founder Beta" in full
    assert "dg-brand-plate" in full


def test_startup_shell_branding_and_phase_milestones():
    markup = startup_coordinator.startup_shell_html(
        startup_coordinator.StartupPhase.LEAGUE_RESTORING
    )
    assert "FantasyGM Lab" in markup
    assert "dg-startup-mark" in markup
    assert "dg-brand-plate" in markup
    assert "Founder Beta" in markup
    assert "Loading league..." in markup
    assert "Loading your league..." not in markup
    assert "dg-startup-milestone is-current" in markup
    assert "League" in markup
    # Progress is phase ordinal, not fake animation advancement.
    progress = int((int(startup_coordinator.StartupPhase.LEAGUE_RESTORING) / 8) * 100)
    assert f"aria-valuenow='{max(10, min(96, progress))}'" in markup


def test_trade_summary_includes_screenshot_brand():
    brand = brand_identity.trade_screenshot_brand_html()
    assert "trade-summary-brand" in brand
    assert "FantasyGM Lab" in brand
    assert "Founder Beta" in brand
    assert "trade-summary-brand" in trade_hub_ui.TRADE_SUMMARY_COMPONENT_CSS


def test_premium_page_customer_ready_copy():
    html = premium_page.premium_page_html(entitlement=premium.FREE)
    assert "FantasyGM Lab" in html
    assert "Founder Beta" in html
    assert "test billing only" not in html.casefold()
    assert "DYNASTYGM_PREMIUM_OVERRIDE" not in html
    assert "developer" not in html.casefold()


def test_feedback_destination_is_repo_rooted():
    path = Path(feedback.FEEDBACK_PATH)
    assert path.is_absolute()
    assert path.name == "feedback_reports.jsonl"
    assert path.parent.name == "data"


def test_brand_identity_css_is_appended_last():
    assert ".dg-founder-badge" in APP_CSS
    assert ".trade-summary-brand" in APP_CSS
    assert "mobile-gm-floating-trigger-marker" in APP_CSS
    assert "from modules.brand_identity_styles import BRAND_IDENTITY_CSS" in Path(
        "modules/app_styles.py"
    ).read_text(encoding="utf-8")
    assert "FOUNDER_BETA_QUICK_FIX_CSS" in Path(
        "modules/app_styles.py"
    ).read_text(encoding="utf-8")
    assert "BRAND_IDENTITY_CSS" in Path(
        "modules/app_styles.py"
    ).read_text(encoding="utf-8")
    assert "+ BRAND_IDENTITY_CSS" in Path(
        "modules/app_styles.py"
    ).read_text(encoding="utf-8")
    assert BRAND_IDENTITY_CSS.strip()[:40] in APP_CSS


def test_app_wires_fantasygm_lab_surfaces():
    source = Path("app.py").read_text(encoding="utf-8")
    assert 'page_title="FantasyGM Lab"' in source
    assert "brand_identity.founder_beta_badge_html" in source
    assert "brand_identity.PRODUCT_NAME" in source
    assert "brand_identity.EXPERIMENTAL_LABEL" in source
    assert 'suffix = f" {brand_identity.EXPERIMENTAL_LABEL}"' in source
