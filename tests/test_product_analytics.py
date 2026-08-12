"""Founder Beta product analytics contracts."""

from __future__ import annotations

import json
from pathlib import Path

from modules import launch_analytics as la
from modules import founder_ops


ROOT = Path(__file__).resolve().parents[1]


def test_unknown_events_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(la, "ENABLED", True)
    monkeypatch.setattr(la, "ANALYTICS_PATH", str(tmp_path / "e.jsonl"))
    la.clear_emitted()
    assert la.track_event("not_a_real_event") is False
    assert not (tmp_path / "e.jsonl").exists()


def test_sensitive_props_stripped_and_allowlist_enforced(tmp_path, monkeypatch):
    path = tmp_path / "e.jsonl"
    monkeypatch.setattr(la, "ENABLED", True)
    monkeypatch.setattr(la, "ANALYTICS_PATH", str(path))
    la.clear_emitted()
    assert la.track_event(
        "checkout_started",
        props={
            "interval": "monthly",
            "email": "secret@example.com",
            "access_token": "tok",
            "player_blob": {"a": 1},
            "route": "premium",
        },
        once_key="u1",
    )
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert row["event"] == "checkout_started"
    assert "email" not in row["props"]
    assert "access_token" not in row["props"]
    assert "player_blob" not in row["props"]
    assert row["props"]["interval"] == "monthly"
    assert row["props"]["route"] == "premium"
    assert row["anon_id"].startswith("anon_")


def test_rerun_dedupe_and_route_entry(tmp_path, monkeypatch):
    path = tmp_path / "e.jsonl"
    monkeypatch.setattr(la, "ENABLED", True)
    monkeypatch.setattr(la, "ANALYTICS_PATH", str(path))
    la.clear_emitted()
    state = {}
    assert la.track_route_opened("dashboard", state=state, changed=True) is True
    assert la.track_route_opened("dashboard", state=state, changed=True) is False
    assert la.track_route_opened("dashboard", state=state, changed=False) is False
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["event"] == "dashboard_reached"


def test_league_switch_allows_new_route_once_key(tmp_path, monkeypatch):
    path = tmp_path / "e.jsonl"
    monkeypatch.setattr(la, "ENABLED", True)
    monkeypatch.setattr(la, "ANALYTICS_PATH", str(path))
    la.clear_emitted()
    state = {"selected_league_id": "L1"}
    la.set_league_scope(state, "L1")
    assert la.track_route_opened("trade_hub", state=state, changed=True) is True
    la.set_league_scope(state, "L2")
    state["selected_league_id"] = "L2"
    assert la.track_route_opened("trade_hub", state=state, changed=True) is True
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_logout_clears_scope(tmp_path, monkeypatch):
    path = tmp_path / "e.jsonl"
    monkeypatch.setattr(la, "ENABLED", True)
    monkeypatch.setattr(la, "ANALYTICS_PATH", str(path))
    la.clear_emitted()
    state = {la.SESSION_ANON_KEY: "anon_keep"}
    assert la.track_event("landing_viewed", once_key="session", state=state) is True
    assert la.track_event("landing_viewed", once_key="session", state=state) is False
    la.clear_analytics_session(state)
    assert la.SESSION_ANON_KEY not in state
    assert la.track_event("landing_viewed", once_key="session", state=state) is True


def test_disabled_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(la, "ENABLED", False)
    monkeypatch.setattr(la, "ANALYTICS_PATH", str(tmp_path / "e.jsonl"))
    monkeypatch.setattr(la, "analytics_enabled", lambda **kwargs: False)
    assert la.track_event("landing_viewed") is False
    assert not (tmp_path / "e.jsonl").exists()


def test_failed_write_does_not_raise(tmp_path, monkeypatch):
    monkeypatch.setattr(la, "ENABLED", True)
    monkeypatch.setattr(la, "ANALYTICS_PATH", str(tmp_path / "missing" / "no" / "e.jsonl"))

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "mkdir", boom)
    assert la.track_event("feedback_submitted") is False


def test_funnel_and_founder_ops_math(tmp_path, monkeypatch):
    path = tmp_path / "e.jsonl"
    monkeypatch.setattr(la, "ENABLED", True)
    monkeypatch.setattr(la, "ANALYTICS_PATH", str(path))
    la.clear_emitted()
    for event in (
        "landing_viewed",
        "signup_completed",
        "league_import_completed",
        "dashboard_reached",
        "trade_hub_opened",
        "premium_viewed",
        "checkout_started",
        "checkout_completed",
    ):
        la.track_event(event)
    counts = la.read_event_counts(path=path)
    funnel = la.funnel_summary(counts)
    assert funnel[0]["step"] == "Landing"
    assert funnel[0]["count"] == 1
    assert funnel[-1]["step"] == "Entitlement Active"
    assert any(row["step"] == "Checkout Complete" for row in funnel)
    metrics = la.founder_ops_metrics(counts)
    assert metrics["signups"] == 1
    assert metrics["trade_hub_opens"] == 1
    assert metrics["retention_days"] == la.RETENTION_DAYS


def test_legacy_event_names_map_when_reading(tmp_path):
    path = tmp_path / "legacy.jsonl"
    path.write_text(
        json.dumps({"event": "landing_visit", "ts": 1})
        + "\n"
        + json.dumps({"event": "account_created", "ts": 2})
        + "\n",
        encoding="utf-8",
    )
    counts = la.read_event_counts(path=path)
    assert counts["landing_viewed"] == 1
    assert counts["signup_completed"] == 1


def test_prune_retention(tmp_path, monkeypatch):
    path = tmp_path / "e.jsonl"
    monkeypatch.setattr(la, "ANALYTICS_PATH", str(path))
    path.write_text(
        json.dumps({"event": "landing_viewed", "ts": 1})
        + "\n"
        + json.dumps({"event": "dashboard_reached", "ts": 9_999_999_999})
        + "\n",
        encoding="utf-8",
    )
    removed = la.prune_expired_events(now=10_000_000_000, retention_days=1)
    assert removed == 1
    remaining = path.read_text(encoding="utf-8")
    assert "dashboard_reached" in remaining
    assert "landing_viewed" not in remaining


def test_contract_doc_exists():
    text = (ROOT / "docs" / "founder-beta-product-analytics-contract.md").read_text(
        encoding="utf-8"
    )
    assert "Privacy model" in text
    assert "DYNASTYGM_LAUNCH_ANALYTICS" in text
    assert "120 days" in text


def test_founder_ops_snapshot_includes_funnel_fields():
    snap = founder_ops.collect_ops_snapshot(environ={}, secrets={})
    assert isinstance(snap.analytics_event_counts, dict)
    assert isinstance(snap.analytics_funnel, tuple)
    assert isinstance(snap.analytics_metrics, dict)
