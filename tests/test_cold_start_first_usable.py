"""Cold-start critical path and hang-protection contracts (PR #138)."""

from __future__ import annotations

from pathlib import Path

from modules import auth_supabase
from modules import startup_critical_path


ROOT = Path(__file__).resolve().parents[1]


def test_auth_pending_hang_protection_times_out():
    state: dict = {}
    assert startup_critical_path.should_stop_for_auth_pending(state) is True
    assert startup_critical_path.should_stop_for_auth_pending(state) is False
    assert state.get(startup_critical_path.AUTH_RESTORE_TIMED_OUT_KEY) is True
    assert "Session restore" in state.get(startup_critical_path.STARTUP_DEGRADED_NOTICE_KEY, "")


def test_auth_storage_key_is_versioned_with_legacy_migration():
    assert auth_supabase.DURABLE_AUTH_STORAGE_KEY == "dynastygm_supabase_auth_v2"
    assert "dynastygm_supabase_auth" in auth_supabase.DURABLE_AUTH_LEGACY_STORAGE_KEYS
    account_ui = (ROOT / "modules" / "account_ui.py").read_text(encoding="utf-8")
    assert "legacyStorageKeys" in account_ui
    assert "legacyKeys" in account_ui


def test_first_usable_paint_precedes_dashboard_route_body():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    page_ready = source.index("StartupPhase.PAGE_READY")
    first_usable = source.index('runtime_trace.mark("first_usable_paint")', page_ready)
    dashboard = source.index('if current_page == "dashboard":', page_ready)
    live_draft_discovery = source.index('time_block("live_draft_discovery"', page_ready)
    assert first_usable < dashboard
    assert first_usable < live_draft_discovery
    assert '_cached_live_draft_active' in source


def test_startup_profile_uses_bounded_network_timeout():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    block = source.split("def _refresh_supabase_account_profile", 1)[1].split(
        "def _persist_onboarding_dismissal", 1
    )[0]
    assert "STARTUP_NETWORK_TIMEOUT_SECONDS" in block


def test_render_streamlit_health_uses_stcore_endpoint():
    text = (ROOT / "render.yaml").read_text(encoding="utf-8")
    streamlit_block = text.split("fantasygm-lab-stripe-webhook", 1)[0]
    assert "healthCheckPath: /_stcore/health" in streamlit_block
    assert "\n    healthCheckPath: /\n" not in streamlit_block


def test_cold_start_report_exists():
    doc = (ROOT / "docs" / "cold-start-first-usable-screen.md").read_text(encoding="utf-8")
    for section in (
        "Root causes",
        "First usable screen",
        "Critical vs deferred",
        "Launch verdict",
        "190f9533838a793f504de661a365e32de7ecccd2",
    ):
        assert section in doc
    assert "| Target | Status |" in doc
