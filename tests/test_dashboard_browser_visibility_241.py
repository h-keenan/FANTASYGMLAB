"""#241 Dashboard browser visibility — parent DOM probe / overlay watchdog."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

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


def test_probe_acks_to_python_with_stable_token():
    assert "setTriggerValue('visibility_ack'" in VIS or 'setTriggerValue("visibility_ack"' in VIS
    assert "ack_token" in VIS
    assert "Date.now()" not in VIS.split("setTriggerValue('visibility_ack'")[1][:800]


def test_canary_and_safe_visibility_wiring():
    assert "render_dashboard_canary" in APP
    assert "DASHBOARD_CANARY_" in VIS
    assert "FGL_SAFE_VISIBILITY_MODE" in VIS
    assert "apply_safe_visibility_css_if_enabled" in APP


def test_canary_renders_plain_text_under_startup_flag(monkeypatch):
    monkeypatch.setenv("DYNASTYGM_STARTUP", "1")
    state: dict = {}
    auth_restore_lifecycle.ensure_startup_session(state)
    with patch.object(dashboard_visibility, "st") as mock_st:
        token = dashboard_visibility.render_dashboard_canary(state)
    assert token.startswith("DASHBOARD_CANARY_")
    mock_st.text.assert_called()
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


def test_safe_visibility_mode_gated(monkeypatch):
    monkeypatch.delenv("FGL_SAFE_VISIBILITY_MODE", raising=False)
    assert dashboard_visibility.safe_visibility_mode_enabled() is False
    monkeypatch.setenv("FGL_SAFE_VISIBILITY_MODE", "1")
    assert dashboard_visibility.safe_visibility_mode_enabled() is True
