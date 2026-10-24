"""Founder Analytics aggregation, privacy, and internal-traffic exclusion."""

from __future__ import annotations

import json
from pathlib import Path

from modules import founder_analytics
from modules import launch_analytics as la


def test_internal_routes_do_not_write_product_events(tmp_path, monkeypatch):
    path = tmp_path / "e.jsonl"
    monkeypatch.setattr(la, "ENABLED", True)
    monkeypatch.setattr(la, "ANALYTICS_PATH", str(path))
    la.clear_emitted()
    state = {}
    assert la.track_page_view("founder_labs", state=state, changed=True) is False
    assert la.track_route_opened("founder_ops", state=state, changed=True) is False
    assert (
        la.track_event(
            "page_view",
            props={"route": "founder_labs", "source_surface": "navigation"},
            state=state,
        )
        is False
    )
    assert (
        la.track_feature_use(
            "gm_orb",
            action="destination_selected",
            state=state,
            extra={"destination": "founder_labs"},
        )
        is False
    )
    assert not path.exists()
    assert la.track_page_view("dashboard", state=state, changed=True) is True
    assert path.is_file()


def test_corrupt_and_missing_jsonl_are_tolerated(tmp_path, monkeypatch):
    missing = tmp_path / "missing.jsonl"
    monkeypatch.setattr(la, "ANALYTICS_PATH", str(missing))
    report = founder_analytics.build_report(window_key="all", path=missing, writes_enabled=False)
    assert report["event_count"] == 0
    assert report["storage"]["exists"] is False
    assert report["unavailable"]

    broken = tmp_path / "broken.jsonl"
    broken.write_text("{not json\n{\"event\":\"pqv_opened\",\"ts\":1}\n", encoding="utf-8")
    report = founder_analytics.build_report(window_key="all", path=broken, writes_enabled=True)
    assert report["event_count"] == 1
    blob = json.dumps(report)
    assert "email" not in blob
    assert "@" not in blob
    assert "user-live" not in blob


def test_window_filters_and_counts(tmp_path, monkeypatch):
    path = tmp_path / "e.jsonl"
    now = 1_700_000_000.0
    rows = [
        {"event": "session_started", "ts": now - 100, "anon_id": "anon_a", "session_key": "anon_a", "user_key": "acct_1", "props": {}},
        {"event": "pqv_opened", "ts": now - 100, "anon_id": "anon_a", "session_key": "anon_a", "user_key": "acct_1", "props": {}},
        {"event": "checkout_started", "ts": now - 100, "anon_id": "anon_a", "session_key": "anon_a", "props": {"interval": "monthly"}},
        {"event": "pqv_opened", "ts": now - 10 * 86400, "anon_id": "anon_b", "session_key": "anon_b", "props": {}},
        {"event": "application_error", "ts": now - 50, "anon_id": "anon_a", "session_key": "anon_a", "props": {"error_class": "timeout"}},
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    day = founder_analytics.build_report(window_key="24h", path=path, now=now, writes_enabled=True)
    week = founder_analytics.build_report(window_key="7d", path=path, now=now, writes_enabled=True)
    all_rows = founder_analytics.build_report(window_key="all", path=path, now=now, writes_enabled=True)
    assert day["event_count"] == 4
    assert week["event_count"] == 4
    assert all_rows["event_count"] == 5
    pqv = [row for row in day["decision_engagement"] if row["event"] == "pqv_opened"][0]
    assert pqv["count"] == 1
    assert day["checkout_intervals"]["monthly"] == 1
    assert day["errors"]["timeout"] == 1
    assert day["storage"]["kind"] == "host_local_jsonl"
    assert "not all-user" in day["storage"]["scope_label"].casefold() or "this host" in day["storage"]["scope_label"].casefold()


def test_build_report_does_not_append_events(tmp_path, monkeypatch):
    path = tmp_path / "e.jsonl"
    path.write_text(
        json.dumps({"event": "dashboard_reached", "ts": 10, "anon_id": "anon_z"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(la, "ENABLED", True)
    monkeypatch.setattr(la, "ANALYTICS_PATH", str(path))
    before = path.read_text(encoding="utf-8")
    founder_analytics.build_report(window_key="all", path=path, writes_enabled=True)
    assert path.read_text(encoding="utf-8") == before


def _onb(anon, action, step=None, idx=None, experience=None):
    props = {"feature": "onboarding", "action": action}
    if step:
        props["step"] = step
    if idx is not None:
        props["step_index"] = idx
    if experience:
        props["experience"] = experience
    return {"event": "feature_use", "anon_id": anon, "props": props}


def test_onboarding_funnel_none_without_data():
    assert founder_analytics._onboarding_funnel([]) is None
    other = [{"event": "feature_use", "anon_id": "a", "props": {"feature": "paywall", "action": "viewed"}}]
    assert founder_analytics._onboarding_funnel(other) is None


def test_onboarding_funnel_aggregation():
    rows = []
    for u in ("a", "b", "c", "d"):
        rows.append(_onb(u, "step_viewed", "value", 0))
    for u in ("a", "b", "c"):
        rows.append(_onb(u, "step_viewed", "level", 2))
    rows.append(_onb("a", "step_viewed", "level", 2))
    rows.append(_onb("d", "skipped", "value", 0))
    rows.append(_onb("a", "experience_selected", experience="new"))
    rows.append(_onb("b", "experience_selected", experience="expert"))
    rows.append(_onb("c", "experience_selected", experience="expert"))
    rows.append(_onb("a", "completed", "level", 2, "new"))
    rows.append(_onb("b", "completed", "level", 2, "expert"))
    funnel = founder_analytics._onboarding_funnel(rows)
    assert funnel["started_users"] == 4
    assert [s["step"] for s in funnel["steps"]] == ["value", "level"]
    assert funnel["steps"][0]["drop_off_pct"] is None
    assert funnel["steps"][1]["users"] == 3 and funnel["steps"][1]["drop_off_pct"] == 25.0
    assert funnel["steps"][0]["skipped_users"] == 1
    assert funnel["skip_rate_pct"] == 25.0
    assert funnel["completion_rate_pct"] == 50.0
    assert funnel["experience"]["expert"] == {"users": 2, "pct": 66.7}


def test_onboarding_props_pass_allowlist():
    clean = la._safe_props({"step": "gameplan", "step_index": 0, "experience": "new", "email": "x@y.z"})
    assert clean == {"step": "gameplan", "step_index": 0, "experience": "new"}


def _espn_row(result, feature="league_import", action="failed"):
    return {"event": "feature_use", "props": {"feature": feature, "action": action, "result": result}}


def test_espn_import_outcomes_none_without_data():
    assert founder_analytics._espn_import_outcomes([]) is None
    assert founder_analytics._espn_import_outcomes([_espn_row("espn_private", action="completed")]) is None
    assert founder_analytics._espn_import_outcomes([_espn_row("bogus")]) is None


def test_espn_import_outcomes_counts():
    rows = [_espn_row("espn_private"), _espn_row("espn_private"), _espn_row("espn_not_found"), _espn_row("espn_error")]
    out = founder_analytics._espn_import_outcomes(rows)
    assert out == {"espn_private": 2, "espn_not_found": 1, "espn_error": 1, "total_failed": 4, "private_pct": 50.0}


def test_onboarding_funnel_separates_legacy_ten_step_ids():
    rows = []
    for u in ("o1", "o2", "o3"):  # old 10-step flow
        rows.append(_onb(u, "step_viewed", "gameplan", 0))
        rows.append(_onb(u, "step_viewed", "connect", 8))
        rows.append(_onb(u, "step_viewed", "level", 9))
    for u in ("n1", "n2"):  # new 3-step flow
        rows.append(_onb(u, "step_viewed", "value", 0))
        rows.append(_onb(u, "step_viewed", "connect", 1))
        rows.append(_onb(u, "step_viewed", "level", 2))
    rows.append(_onb("n1", "step_viewed", "paywall", 3))
    funnel = founder_analytics._onboarding_funnel(rows)
    assert [(s["step"], s["users"]) for s in funnel["steps"]] == [
        ("value", 2),
        ("connect", 2),
        ("level", 2),
        ("paywall", 1),
    ]
    assert [s["step"] for s in funnel["legacy_steps"]] == ["gameplan", "connect", "level"]
    assert funnel["legacy_steps"][0]["users"] == 3


def test_onboarding_funnel_stitches_anon_to_account_and_bounds_rates():
    pre = _onb("anon_1", "step_viewed", "value", 0)
    post = _onb("anon_1", "step_viewed", "connect", 1)
    post.update(user_key="acct_x")
    done = _onb("anon_2", "completed", "level", 2, "new")  # no step_viewed stored
    funnel = founder_analytics._onboarding_funnel([pre, post, done])
    assert funnel["steps"][0]["users"] == 1 and funnel["steps"][1]["users"] == 1
    assert funnel["started_users"] == 2
    assert funnel["completion_rate_pct"] == 50.0


def test_identity_map_ignores_anon_shared_by_two_accounts():
    a = {"anon_id": "anon_s", "user_key": "acct_1"}
    b = {"anon_id": "anon_s", "user_key": "acct_2"}
    assert founder_analytics._identity_map([a, b]) == {}


def _billing(event_id, event_type, entitlement, transition="", provider="stripe", user="u-1"):
    return {
        "provider": provider, "event_id": event_id, "event_type": event_type, "user_id": user,
        "outcome": "applied", "entitlement": entitlement, "trial_transition": transition,
        "received_at": "2026-10-23T12:00:00+00:00",
    }


def test_billing_lifecycle_rows_derive_trial_subscribed_churned():
    rows = [
        _billing("1", "customer.subscription.created", "premium", "started"),
        _billing("2", "checkout.session.completed", "premium", "", user="u-2"),
        _billing("3", "customer.subscription.updated", "premium", "converted"),
        _billing("4", "customer.subscription.deleted", "free", user="u-2"),
        _billing("5", "INITIAL_PURCHASE", "premium", "started", provider="revenuecat", user="u-3"),
    ]
    synthetic, summary = founder_analytics._billing_lifecycle_rows(rows, [])
    names = sorted(r["event"] for r in synthetic)
    assert names == ["churned", "feature_use", "subscribed", "trial_started"]
    assert summary["stripe"]["trial_converted"] == 1
    assert summary["revenuecat"]["trial_started"] == 1
    assert all(r["user_key"].startswith("acct_") for r in synthetic)
    # a Python-emitted row for the same account/time suppresses the derived one
    ts = synthetic[0]["ts"]
    existing = [{"event": "trial_started", "user_key": la.hash_account_id("u-1"), "ts": ts + 5}]
    again, _ = founder_analytics._billing_lifecycle_rows(rows[:1], existing)
    assert again == []


def test_build_report_counts_billing_lifecycle_in_premium(monkeypatch, tmp_path):
    monkeypatch.setattr(la, "read_events_with_source", lambda **kw: ([], "supabase"))
    monkeypatch.setattr(
        founder_analytics,
        "_fetch_billing_webhook_events",
        lambda **kw: [_billing("1", "customer.subscription.created", "premium", "started")],
    )
    report = founder_analytics.build_report(window_key="all", path=None, now=1.0)
    premium = {r["event"]: r["count"] for r in report["premium"]}
    assert premium["trial_started"] == 1
    assert report["billing_lifecycle"]["stripe"]["trial_started"] == 1
    assert report["event_count"] == 0


def test_build_report_drops_test_environment_rows(tmp_path):
    path = tmp_path / "a.jsonl"
    rows = [
        {"event": "page_view", "ts": 10, "environment": "test", "anon_id": "a", "props": {}},
        {"event": "page_view", "ts": 10, "environment": "production", "anon_id": "b", "props": {}},
        {"event": "page_view", "ts": 10, "anon_id": "c", "props": {}},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    report = founder_analytics.build_report(window_key="all", path=path, now=20.0)
    assert report["event_count"] == 2
