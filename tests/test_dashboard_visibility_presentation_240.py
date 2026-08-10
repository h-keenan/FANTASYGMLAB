"""#240 Dashboard visibility / non-destructive auth persistence regressions."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from modules import account_ui
from modules import auth_restore_lifecycle
from modules import auth_supabase
from modules import dashboard_visibility
from modules import startup_cold_path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
ACCOUNT_UI = (ROOT / "modules" / "account_ui.py").read_text(encoding="utf-8")


def test_post_usable_auth_path_does_not_call_st_rerun():
    flush = APP.index("post_usable_auth_save_flushed")
    block = APP[flush - 500 : flush + 350]
    assert "flush_durable_auth_persistence" in block
    assert "st.rerun()" not in block


def test_auth_storage_js_skips_trigger_on_save_and_settled_session():
    assert "do not setTriggerValue on save" in ACCOUNT_UI
    assert "skip timestamped status emit every run" in ACCOUNT_UI
    # Executable save path must return without calling setTriggerValue.
    save_idx = ACCOUNT_UI.index('if (command === "save")')
    save_block = ACCOUNT_UI[save_idx : ACCOUNT_UI.index('if (command === "clear")', save_idx)]
    assert "return" in save_block
    assert "setTriggerValue(" not in save_block
    clear_idx = ACCOUNT_UI.index('if (command === "clear")')
    settled_idx = ACCOUNT_UI.index("if (hasSession)")
    clear_block = ACCOUNT_UI[clear_idx:settled_idx]
    assert "setTriggerValue(" not in clear_block
    settled_block = ACCOUNT_UI[settled_idx : ACCOUNT_UI.index("readStoredAuth", settled_idx)]
    assert "setTriggerValue(" not in settled_block
    assert "return" in settled_block


def test_flush_durable_auth_persistence_consumes_pending_without_rerun():
    state = {
        auth_supabase.DURABLE_AUTH_PENDING_SAVE_KEY: {
            "access_token": "a",
            "refresh_token": "r",
            "expires_at": 9999999999,
            "user": {"id": "u1"},
        }
    }
    component = MagicMock(return_value=MagicMock())
    with patch.object(account_ui, "AUTH_STORAGE_COMPONENT", component):
        result = account_ui.flush_durable_auth_persistence(
            state,
            config={"enabled": True, "url": "https://example.supabase.co", "anon_key": "x"},
        )
    assert result["flushed"] is True
    assert result["command"] == "save"
    assert auth_supabase.DURABLE_AUTH_PENDING_SAVE_KEY not in state
    assert component.call_args.kwargs["data"]["command"] == "save"
    assert component.call_args.kwargs["key"] == "supabase_auth_storage_flush"


def test_dashboard_render_milestones_are_instrumented():
    sources = "\n".join(
        [
            APP,
            Path("modules/dashboard_workflow.py").read_text(encoding="utf-8"),
            Path("modules/dashboard_visibility.py").read_text(encoding="utf-8"),
            Path("modules/startup_coordinator.py").read_text(encoding="utf-8"),
        ]
    )
    for name in (
        "dashboard_render_start",
        "dashboard_header_complete",
        "dashboard_game_plan_emit_start",
        "dashboard_game_plan_emit_complete",
        "dashboard_summary_tiles_complete",
        "dashboard_what_changed_complete",
        "dashboard_deep_analysis_complete",
        "dashboard_sections_complete",
        "dashboard_render_function_return",
        "dashboard_python_render_complete",
        "final_app_render_return",
    ):
        assert name in sources
    assert "mount_browser_visibility_probe" in APP
    assert 'data-fgl-dashboard-root="1"' in APP


def test_dashboard_workflow_emits_section_milestones():
    source = Path("modules/dashboard_workflow.py").read_text(encoding="utf-8")
    assert "dashboard_header_complete" in source
    assert "dashboard_summary_tiles_complete" in source
    assert "dashboard_deep_analysis_complete" in source


def test_visibility_probe_js_does_not_set_trigger_value():
    source = Path("modules/dashboard_visibility.py").read_text(encoding="utf-8")
    js_start = source.index('js="""')
    js_end = source.index('"""', js_start + 5)
    js = source[js_start:js_end]
    assert "setTriggerValue" not in js
    assert "browser_dashboard_visible" in source
    assert "data-fgl-browser-dashboard-visible" in source


def test_python_render_milestone_once_gate(monkeypatch):
    monkeypatch.setenv("DYNASTYGM_STARTUP", "1")
    state: dict = {}
    auth_restore_lifecycle.ensure_startup_session(state)
    dashboard_visibility.log_python_render_milestone(state, "dashboard_render_start")
    dashboard_visibility.log_python_render_milestone(state, "dashboard_render_start")
    logged = state.get("_dashboard_render_milestones_once") or {}
    assert logged.get("dashboard_render_start") is True


def test_startup_shell_css_hides_hero_only_while_shell_present():
    source = Path("modules/startup_coordinator.py").read_text(encoding="utf-8")
    assert "body:has(.dg-startup-shell) .app-hero" in source
    assert "display: none !important" in source
    # complete() empties the placeholder so :has(.dg-startup-shell) clears.
    assert "self.placeholder.empty()" in source
