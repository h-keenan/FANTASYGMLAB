"""Founder Ops dashboard access and read-only contract tests."""

from __future__ import annotations

from pathlib import Path

from modules import founder_ops
from modules import founder_ops_ui
from modules.ui_architecture import (
    PLATFORM_DESTINATIONS,
    current_platform_destinations,
    mobile_primary_destinations,
)


ROOT = Path(__file__).resolve().parents[1]


def test_founder_ops_destination_is_hidden_by_default():
    keys = {page.key for page in current_platform_destinations(False)}
    assert "founder_ops" not in keys
    primary = {page.key for page in mobile_primary_destinations(False)}
    assert "founder_ops" not in primary


def test_founder_ops_destination_requires_explicit_flag():
    hidden = {page.key for page in current_platform_destinations(False, show_founder_ops=False)}
    shown = {page.key for page in current_platform_destinations(False, show_founder_ops=True)}
    assert "founder_ops" not in hidden
    assert "founder_ops" in shown
    page = next(item for item in PLATFORM_DESTINATIONS if item.key == "founder_ops")
    assert page.category == "FOUNDER_OPS"
    assert page.beta_visible is False


def test_founder_ops_flag_is_independent_of_customer_debug_lock():
    # Managed hosts still allow founder ops when the dedicated flag is set.
    assert founder_ops.founder_ops_enabled(
        environ={"RENDER": "true", "DYNASTYGM_FOUNDER_OPS": "1"},
        secrets={},
    )
    assert not founder_ops.founder_ops_enabled(
        environ={"RENDER": "true"},
        secrets={},
    )


def test_collect_ops_snapshot_is_redacted_and_structured():
    snapshot = founder_ops.collect_ops_snapshot(
        environ={"DYNASTYGM_FOUNDER_OPS": "1", "APP_BASE_URL": "https://fantasygmlab.com"},
        secrets={},
        session_state={},
    )
    payload = snapshot.as_dict()
    assert payload["build_sha"]
    assert payload["environment"]
    assert "feedback_count" in payload
    assert "analytics_event_counts" in payload
    assert "stripe_mode" in payload
    blob = str(payload).casefold()
    assert "sk_live" not in blob
    assert "sk_test" not in blob
    assert "service_role" not in blob
    assert "whsec_" not in blob


def test_app_wires_founder_ops_page_behind_flag():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'show_founder_ops": founder_ops.founder_ops_enabled' in source or "show_founder_ops" in source
    assert 'current_page == founder_ops.FOUNDER_OPS_PAGE_KEY' in source
    assert "render_founder_ops_dashboard(" in source
    assert "render_access_denied(" in source
    assert "DYNASTYGM_FOUNDER_OPS" in (ROOT / "modules" / "app_config.py").read_text(
        encoding="utf-8"
    )


def test_founder_ops_ui_has_no_destructive_actions():
    source = (ROOT / "modules" / "founder_ops_ui.py").read_text(encoding="utf-8")
    for banned in ("delete", "drop table", "unsubscribe", "refund", "cancel subscription"):
        assert banned not in source.casefold()
    assert "Read-only diagnostics" in source


def test_heartbeat_round_trip(tmp_path, monkeypatch):
    path = tmp_path / "heartbeat.json"
    monkeypatch.setattr(founder_ops, "HEARTBEAT_PATH", path)
    founder_ops.record_ops_heartbeat("supabase", ok=True, detail="profile ok")
    payload = founder_ops._read_heartbeat()
    assert payload["supabase"]["ok"] is True
    assert "ts" in payload["supabase"]
