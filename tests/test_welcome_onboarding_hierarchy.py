"""Welcome / onboarding funnel hierarchy — conversion clarity pass."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from modules import account_ui
from modules import app_styles
from modules import auth_supabase
from modules import marketing_landing
from modules import marketing_landing_styles


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
LANDING = (ROOT / "modules" / "marketing_landing.py").read_text(encoding="utf-8")
ACCOUNT = (ROOT / "modules" / "account_ui.py").read_text(encoding="utf-8")
IMPORT_UI = (ROOT / "modules" / "platform_import_ui.py").read_text(encoding="utf-8")


def test_cold_landing_has_first_screen_intents_without_pricing():
    cold_fn = LANDING.split("def render_marketing_landing(", 1)[1].split(
        "def render_marketing_landing_deferred(", 1
    )[0]
    assert "landing_primary_cta" in cold_fn
    assert "landing_secondary_cta" in cold_fn
    assert "landing_guest_cta" in cold_fn
    assert "landing_pricing_cta" not in cold_fn
    assert "landing_body_html" not in cold_fn


def test_deferred_pricing_renders_after_import_in_launch_screen():
    launch = APP.split("def render_home_launch_screen", 1)[1].split("\ndef ", 1)[0]
    assert "render_platform_import_panel" in launch
    assert "render_marketing_landing_deferred()" in launch
    assert "if not compact:" in launch


def test_section_order_contract_matches_funnel():
    """Hero → first-screen intents. Import precedes collapsed account; pending/sign-in precede import."""

    early = APP.split("with st.container(key=\"early_launch_account_decision\")", 1)[1].split(
        "startup_coordinator.log_startup_milestone(",
        1,
    )[0]
    assert "render_marketing_landing()" in early
    assert "welcome_flow_state" in early
    launch = APP.split("def render_home_launch_screen", 1)[1].split("\ndef ", 1)[0]
    assert "launch_account_should_precede_import" in launch
    assert "fgl-import-league" in IMPORT_UI
    assert "data-fgl-landing-deferred" in LANDING


def test_guest_default_and_compact_account_copy():
    state: dict = {}
    with patch.object(marketing_landing.st, "session_state", state), patch.object(
        marketing_landing.st, "markdown"
    ), patch.object(marketing_landing.st, "button", return_value=False), patch.object(
        marketing_landing.st, "columns", return_value=[MagicMock(), MagicMock()]
    ):
        # columns context managers
        for col in marketing_landing.st.columns.return_value:
            col.__enter__ = MagicMock(return_value=col)
            col.__exit__ = MagicMock(return_value=False)
        marketing_landing.render_marketing_landing()
    assert state.get("launch_auth_mode") in (None, "", "guest")
    assert marketing_landing.welcome_flow_state(state) == "welcome"

    assert "Choose how to continue" in ACCOUNT
    assert "Guest · import next" not in ACCOUNT
    assert "Continue as guest instead" not in ACCOUNT
    assert ACCOUNT.count("import a Sleeper league as a guest") == 0
    assert "Browsing as guest. Import a league below" not in ACCOUNT


def test_pending_confirmation_skips_optional_account_intro():
    config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
    state: dict = {}
    auth_supabase.enter_pending_email_confirmation(state, "user@example.com")
    markdown_html: list[str] = []

    def _markdown(body, **_kwargs):
        markdown_html.append(str(body))

    with patch.object(account_ui.st, "session_state", state), patch.object(
        account_ui.st, "markdown", side_effect=_markdown
    ), patch.object(account_ui.st, "button", return_value=False), patch.object(
        account_ui.st, "caption"
    ), patch.object(account_ui.st, "info"), patch.object(account_ui.st, "success"), patch.object(
        account_ui.st, "warning"
    ):
        account_ui.render_mobile_auth_entry(config=config)
    joined = " ".join(markdown_html)
    assert "account-confirm-card" in joined or "Check your email" in joined
    assert "Guest · import next" not in joined
    assert "Save your leagues" not in joined
    assert "Save leagues later" not in joined


def test_hero_cta_count_and_primary_label():
    assert marketing_landing.APP_PRIMARY_CTA_LABEL == "Import Sleeper League"
    assert marketing_landing.SECONDARY_CTA_LABEL == "Sign in"
    assert marketing_landing.GUEST_CTA_LABEL == "Continue as guest"
    cold_fn = LANDING.split("def render_marketing_landing(", 1)[1].split(
        "def render_marketing_landing_deferred(", 1
    )[0]
    assert cold_fn.count("st.button(") == 4
    assert 'type="primary"' in cold_fn
    assert 'type="secondary"' in cold_fn


def test_app_css_unchanged_by_landing_pass():
    # Landing spacing overrides live in MARKETING_LANDING_CSS, not APP_CSS.
    assert "MARKETING_LANDING_CSS" not in (ROOT / "modules" / "app_styles.py").read_text(
        encoding="utf-8"
    )
    assert "fgl-landing__section--deferred" in marketing_landing_styles.MARKETING_LANDING_CSS
    # Guard authenticated protobuf: APP_CSS must not absorb landing styles.
    assert "fgl-landing__hero" not in app_styles.APP_CSS
    assert len(app_styles.APP_CSS) < 400_000


def test_static_landing_removes_duplicate_import_cta_block():
    html = (ROOT / "static" / "landing" / "index.html").read_text(encoding="utf-8")
    assert html.count("Import your league") == 1
    assert 'id="get-started"' not in html
    assert "Next step" not in html
    assert "Next —" not in html
    assert html.index('id="how-it-works"') < html.index('id="pricing"')
