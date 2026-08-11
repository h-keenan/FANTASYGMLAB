"""Product-wide polish + redundancy cleanup contracts."""

from __future__ import annotations

from pathlib import Path

from modules.app_styles import APP_CSS
from modules.mobile_interaction_overlay_styles import MOBILE_INTERACTION_OVERLAY_CSS
from modules.mobile_visual_polish_styles import MOBILE_VISUAL_POLISH_CSS


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
WORKSPACE = (ROOT / "modules" / "workspace_ui.py").read_text(encoding="utf-8")

SCOPED = (
    'stVerticalBlock"]:has(> div[data-testid="stElementContainer"] '
    ".mobile-gm-floating-trigger-marker)"
)
UNSCOPED = 'stVerticalBlock"]:has(.mobile-gm-floating-trigger-marker)'


def test_dead_helpers_removed():
    assert "def _candidate_note_map(" not in APP
    assert "def _safe_secret_flag(" not in APP
    assert "render_concept_band =" not in APP
    assert "def render_concept_band(" not in WORKSPACE
    assert "from modules import weekly_report_ui" not in APP.split("from modules import workspace_ui", 1)[0]
    assert "from modules import weekly_report_ui" in APP  # lazy at archived route


def test_additional_zero_caller_helpers_removed():
    """High-confidence dead helpers proven with zero production/test callers."""

    brand = (ROOT / "modules" / "brand_identity.py").read_text(encoding="utf-8")
    founder = (ROOT / "modules" / "founder_ops.py").read_text(encoding="utf-8")
    live_draft = (ROOT / "modules" / "live_draft_ui.py").read_text(encoding="utf-8")
    my_news = (ROOT / "modules" / "my_news.py").read_text(encoding="utf-8")
    premium = (ROOT / "modules" / "premium.py").read_text(encoding="utf-8")
    stripe_billing = (ROOT / "modules" / "stripe_billing.py").read_text(encoding="utf-8")
    stripe_webhook = (ROOT / "modules" / "stripe_webhook.py").read_text(encoding="utf-8")
    tail = (ROOT / "modules" / "tail_latency_diagnostics.py").read_text(encoding="utf-8")
    waivers = (ROOT / "modules" / "waivers_ui.py").read_text(encoding="utf-8")
    assert "def _read_text_asset(" not in brand
    assert "def _count_jsonl(" not in founder
    assert "def _draft_type(" not in live_draft
    assert "def _slugify_name(" not in my_news
    assert "def _lookup_secret(" not in premium
    assert "def _lookup_secret(" not in stripe_billing
    assert "def _lookup_secret(" not in stripe_webhook
    assert "def _sum_keys(" not in tail
    assert "def _badge_variant(" not in waivers
    assert "def waiver_dynasty_context(" not in waivers
    assert "def waiver_opportunity_context(" not in waivers

def test_news_cleared_on_league_switch():
    keys = APP.split("LEAGUE_SWITCH_TRANSIENT_STATE_KEYS = (", 1)[1].split(")", 1)[0]
    assert '"news"' in keys


def test_waivers_prefers_shared_roster_map():
    start = APP.index('if current_page == "waivers":')
    body = APP[start : start + 3500]
    assert "get_shared_league_context(" in body
    assert 'include_intelligence=False' in body
    assert "waiver_roster_player_map = waiver_context.get(\"roster_player_map\")" in body
    assert "if not waiver_roster_player_map:" in body


def test_trade_receive_partner_cleared_on_league_switch():
    from modules import session_integrity

    assert "trade_receive_partner" in session_integrity.TRADE_ANALYZER_PACKAGE_KEYS


def test_quiet_status_shells_share_polish_tokens():
    assert ".dg-gm-targets-quiet" in MOBILE_VISUAL_POLISH_CSS
    assert ".dg-what-changed-quiet" in MOBILE_VISUAL_POLISH_CSS
    assert ".dg-daily-briefing-quiet" in MOBILE_VISUAL_POLISH_CSS
    compact = MOBILE_VISUAL_POLISH_CSS.replace(" ", "")
    assert "padding:var(--space-sm)var(--space-md)!important" in compact


def test_dead_platform_shell_note_css_removed():
    assert ".platform-shell-note" not in APP_CSS


def test_dead_orphan_chrome_families_removed():
    """Proven-unused sole-selector chrome deleted after emitter grep."""

    for selector in (
        ".platform-header {",
        ".launch-hero {",
        ".launch-shell {",
        ".dg-page-glyph {",
        ".home-home-expander ",
        ".decision-panel-row {",
        ".decision-panel-grid-alert .decision-panel-row-top",
        ".news-feed {",
        ".player-detail-back-row {",
    ):
        assert selector not in APP_CSS
    # Live launch / page / decision chrome kept
    assert ".launch-section-title" in APP_CSS
    assert ".dg-page-meta" in APP_CSS
    assert ".decision-panel-body" in APP_CSS
    assert ".news-card" in APP_CSS


def test_quiet_feature_css_defers_chrome_to_polish():
    """Quiet shells keep layout/typography locally; shared chrome lives in polish CSS."""

    decision = (ROOT / "modules" / "decision_change_history_ui.py").read_text(encoding="utf-8")
    briefing = (ROOT / "modules" / "daily_gm_briefing_ui.py").read_text(encoding="utf-8")
    targets = (ROOT / "modules" / "gm_targets_ui.py").read_text(encoding="utf-8")
    workflow = (ROOT / "modules" / "dashboard_workflow_styles.py").read_text(encoding="utf-8")
    decision_quiet = decision.split(".dg-what-changed-quiet", 1)[1].split(".dg-what-changed-item", 1)[0]
    briefing_quiet = briefing.split(".dg-daily-briefing-quiet", 1)[1].split(
        ".dg-daily-briefing-item{", 1
    )[0]
    targets_quiet = targets.split(".dg-gm-targets-quiet", 1)[1].split("@media", 1)[0]
    clear = workflow.split(".dashboard-clear-state {", 1)[1].split(
        ".dashboard-clear-state strong", 1
    )[0]
    for chunk in (decision_quiet, briefing_quiet, targets_quiet, clear):
        assert "background:" not in chunk
        assert "border:" not in chunk or "border-inline" in chunk
        assert "padding:" not in chunk


def test_gm_orb_244_247_contracts_preserved():
    assert SCOPED in MOBILE_INTERACTION_OVERLAY_CSS
    assert SCOPED in APP_CSS
    assert UNSCOPED not in MOBILE_INTERACTION_OVERLAY_CSS
    assert UNSCOPED not in APP_CSS
    compact = MOBILE_INTERACTION_OVERLAY_CSS.replace(" ", "")
    assert "gap:0!important" in compact
    assert "width:var(--dg-gm-orb-size)!important" in compact


def test_app_css_headroom_after_cleanup():
    # Cleanup should not grow past the #237 protobuf-adjacent CSS ceiling signal.
    assert len(APP_CSS) < 390_000
