"""Premium conversion audit + intent-based upgrade contracts (#225)."""

from __future__ import annotations

from pathlib import Path

from modules import launch_analytics, premium, premium_conversion, premium_benefits


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "premium-conversion-intent-flow.md"


def test_premium_conversion_doc_exists():
    text = DOC.read_text(encoding="utf-8")
    assert "Go deeper on the decisions that matter" in text
    assert "Upgrade to Premium" in text
    assert "premium_gate_seen" in text
    assert "Experimental" in text
    assert "de7b0dd" in text
    assert "Rollback boundary" in text


def test_mobile_premium_benefit_lines_are_grounded_in_premium_included_now():
    known_titles = {title for title, _ in premium_benefits.PREMIUM_INCLUDED_NOW}
    for entry in premium_benefits.MOBILE_PREMIUM_BENEFIT_LINES:
        assert entry["title"] in known_titles

    lines = premium_benefits.mobile_premium_benefit_lines()
    assert lines == [entry["line"] for entry in premium_benefits.MOBILE_PREMIUM_BENEFIT_LINES]
    assert len(lines) == len(set(lines))


def test_mobile_premium_benefit_lines_raises_on_drift_from_web_copy(monkeypatch):
    stale_lines = premium_benefits.MOBILE_PREMIUM_BENEFIT_LINES + (
        {"title": "A title that no longer exists in PREMIUM_INCLUDED_NOW", "line": "stale"},
    )
    monkeypatch.setattr(premium_benefits, "MOBILE_PREMIUM_BENEFIT_LINES", stale_lines)

    try:
        premium_benefits.mobile_premium_benefit_lines()
    except ValueError as exc:
        assert "unknown title" in str(exc)
    else:
        raise AssertionError("Expected a drifted mobile benefit title to raise ValueError.")


def test_premium_lock_uses_upgrade_cta_and_included_line():
    html = premium.premium_lock_html(
        "Full trade board",
        "More ideas.",
        feature="Premium Trade Hub",
    )
    assert "Upgrade to Premium" in html
    assert "Included with Premium" in html
    assert "Unlock with Premium" not in html


def test_analytics_allowlist_covers_premium_funnel():
    for event in (
        "premium_gate_seen",
        "premium_cta_clicked",
        "checkout_started",
        "checkout_completed",
        "premium_checkout_cancelled",
        "premium_entitlement_activated",
    ):
        assert event in launch_analytics.TRACKED_EVENTS
    assert launch_analytics.normalize_event_name("premium_checkout_started") == "checkout_started"
    assert "prompt_surface" in launch_analytics.ALLOWED_PROP_KEYS
    assert "item_kind" in launch_analytics.ALLOWED_PROP_KEYS
    for blocked in ("email", "username", "player_name"):
        assert blocked in launch_analytics.BLOCKED_PROP_KEYS


def test_premium_comparison_uses_enforced_limits():
    from modules import gm_targets, trade_hub_presentation

    rows = {r["key"]: r for r in premium_benefits.premium_comparison()}
    assert rows["next_moves"]["free"] == f"Top {premium_benefits.FREE_NEXT_MOVE_ITEMS}"
    assert str(trade_hub_presentation.FREE_VISIBLE_IDEAS) in rows["trade_hub"]["free"]
    assert rows["gm_targets"]["free"].startswith(str(gm_targets.MAX_TARGETS_FREE))
    assert rows["gm_targets"]["pro"].startswith(str(gm_targets.MAX_TARGETS_PREMIUM))
    assert all(r["label"] and r["free"] and r["pro"] for r in rows.values())
