"""Founder Analytics aggregation, privacy, and internal-traffic exclusion."""

from __future__ import annotations

import json
from pathlib import Path

from modules import founder_analytics
from modules import founder_labs_ui
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


def test_analytics_ui_is_labs_gated_and_not_a_customer_route():
    source = Path(__file__).resolve().parents[1].joinpath("modules", "ui_architecture.py").read_text(
        encoding="utf-8"
    )
    assert "founder_analytics" not in source
    labs_ui = Path(founder_labs_ui.__file__).read_text(encoding="utf-8")
    assert "render_founder_analytics" in labs_ui
    analytics_ui = Path(__file__).resolve().parents[1].joinpath(
        "modules", "founder_analytics_ui.py"
    ).read_text(encoding="utf-8")
    assert "founder_labs.founder_labs_authorized" in analytics_ui


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
