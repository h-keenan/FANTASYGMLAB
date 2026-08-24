"""#241 Dashboard browser visibility — parent DOM probe / overlay watchdog."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from modules import auth_restore_lifecycle
from modules import dashboard_visibility


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
VIS = (ROOT / "modules" / "dashboard_visibility.py").read_text(encoding="utf-8")


def test_probe_observes_parent_document_not_iframe_only():
    assert "window.parent" in VIS
    assert "host.document" in VIS
    assert "probe_document" in VIS


def test_probe_installs_mutation_observer_and_overlay_watchdog():
    assert "MutationObserver" in VIS
    assert "dismissStaleStartupOverlay" in VIS
    assert "browser_startup_overlay_watchdog" in VIS
    assert "dg-startup-shell" in VIS


def test_probe_reports_visibility_without_triggering_python_rerun():
    assert "setTriggerValue('visibility_ack'" not in VIS
    assert 'setTriggerValue("visibility_ack"' not in VIS
    assert "data-fgl-browser-dashboard-visible" in VIS
    assert "Passive visibility diagnostics must never mutate Python state" in VIS


def test_visible_canary_and_safe_css_bypass_removed_from_production_path():
    assert "render_dashboard_canary" in VIS
    assert "DASHBOARD_CANARY_" not in VIS
    assert "apply_safe_visibility_css_if_enabled" not in APP
    assert "p0_render_canary" not in APP
    assert "FGL_P0_" not in APP


def test_visibility_token_is_server_only_under_startup_flag(monkeypatch):
    monkeypatch.setenv("DYNASTYGM_STARTUP", "1")
    state: dict = {}
    auth_restore_lifecycle.ensure_startup_session(state)
    with patch.object(dashboard_visibility, "st") as mock_st:
        token = dashboard_visibility.render_dashboard_canary(state)
    assert token.startswith("dash_vis_")
    mock_st.text.assert_not_called()
    assert state.get(dashboard_visibility.CANARY_RENDERED_KEY) is True


def test_browser_ack_logs_python_milestone(monkeypatch):
    monkeypatch.setenv("DYNASTYGM_STARTUP", "1")
    state: dict = {}
    auth_restore_lifecycle.ensure_startup_session(state)
    dashboard_visibility._log_browser_ack(
        state,
        {
            "kind": "browser_dashboard_visible",
            "useful_present": True,
            "overlay_absent": True,
            "probe_document": "parent",
        },
    )
    assert state.get(dashboard_visibility.BROWSER_VISIBILITY_ACK_KEY)
    logged = state.get("_dashboard_render_milestones_once") or {}
    assert logged.get("browser_dashboard_visible") is True


def test_safe_visibility_css_bypass_retired(monkeypatch):
    monkeypatch.setenv("FGL_SAFE_VISIBILITY_MODE", "1")
    assert dashboard_visibility.apply_safe_visibility_css_if_enabled() is False
