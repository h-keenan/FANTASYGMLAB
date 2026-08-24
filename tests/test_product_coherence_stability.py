from pathlib import Path

from modules import faab, founder_ops, notification_center, trade_visual_language
from modules import user_preferences


ROOT = Path(__file__).resolve().parents[1]


def test_passive_dashboard_visibility_probe_cannot_force_late_rerun():
    source = (ROOT / "modules" / "dashboard_visibility.py").read_text(encoding="utf-8")
    js = source.split('js="""', 1)[1].split('""",', 1)[0]
    assert "setTriggerValue('visibility_ack'" not in js
    assert "data-fgl-browser-dashboard-visible" in js


def test_notification_pending_is_distinct_from_caught_up():
    pending = notification_center._inbox_header_html(
        unread=0,
        active=0,
        ready=False,
    )
    ready = notification_center._inbox_header_html(
        unread=0,
        active=0,
        ready=True,
    )
    assert "Initializing" in pending
    assert "All caught up" not in pending
    assert "All caught up" in ready


def test_sleeper_faab_context_is_league_and_roster_authoritative():
    context = faab.sleeper_faab_budget_context(
        {"settings": {"waiver_budget": 150}},
        [
            {"roster_id": 1, "settings": {"waiver_budget_used": 23}},
            {"roster_id": 2, "settings": {"waiver_budget_used": 70}},
        ],
        roster_id=1,
    )
    assert context.remaining == 127
    assert context.source == "sleeper"


def test_faab_dollars_lead_when_remaining_is_known():
    guidance = faab.recommend_faab_guidance(
        5000,
        "WR",
        remaining_budget=127,
        confidence="medium",
    )
    html = faab.format_faab_block_html(guidance)
    assert f"${guidance.low_bid}–${guidance.high_bid}" in html
    assert f"{guidance.pct_low}–{guidance.pct_high}% of $127 remaining" in html


def test_manual_faab_preferences_are_league_isolated():
    settings = user_preferences.with_faab_remaining(
        {"settings": {"theme": "dark"}},
        league_id="league-a",
        remaining=42,
    )
    settings = user_preferences.with_faab_remaining(
        settings,
        league_id="league-b",
        remaining=88,
    )
    assert user_preferences.faab_remaining_for_league(settings, "league-a") == 42
    assert user_preferences.faab_remaining_for_league(settings, "league-b") == 88
    assert settings["settings"]["theme"] == "dark"


def test_trade_value_and_confidence_have_independent_labels():
    assert trade_visual_language.trade_value_band("+237") == "Fair"
    assert trade_visual_language.trade_value_band("+900") == "Favorable"
    assert trade_visual_language.trade_value_band("-991") == "Overpay"
    assert "TRADE VALUE / OVERPAY" in trade_visual_language.value_edge_html("-991")
    assert "CONFIDENCE / Low" in trade_visual_language.confidence_indicator_html("Low")


def test_founder_ops_requires_kill_switch_and_server_capability():
    enabled = {"DYNASTYGM_FOUNDER_OPS": "1"}
    assert not founder_ops.founder_ops_authorized({}, environ=enabled)
    assert founder_ops.founder_ops_authorized(
        {"auth_user": {"app_metadata": {"founder_ops": True}}},
        environ=enabled,
    )
    assert not founder_ops.founder_ops_authorized(
        {"auth_user": {"user_metadata": {"founder_ops": True}}},
        environ=enabled,
    )
    assert not founder_ops.founder_ops_authorized(
        {"account_profile": {"founder_ops": True}},
        environ=enabled,
    )
    assert not founder_ops.founder_ops_authorized(
        {"auth_user": {"app_metadata": {"founder_ops": True}}},
        environ={},
    )
