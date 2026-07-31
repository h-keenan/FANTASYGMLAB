from pathlib import Path
from unittest.mock import Mock, patch

from modules import account_ui, premium
from modules.app_styles import APP_CSS
from modules.interface_reimagining_styles import INTERFACE_REIMAGINING_CSS
from modules.mobile_workflow_styles import MOBILE_WORKFLOW_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_mobile_workflow_layer_loads_last_and_is_dashboard_scoped():
    assert APP_CSS.rfind(MOBILE_WORKFLOW_CSS) > APP_CSS.rfind(
        INTERFACE_REIMAGINING_CSS
    )
    assert "main:has(.home-command-shell)" in MOBILE_WORKFLOW_CSS
    assert ".stApp {" not in MOBILE_WORKFLOW_CSS
    assert ".block-container {" not in MOBILE_WORKFLOW_CSS


def test_next_moves_cannot_wrap_vertically_on_phone():
    assert ".home-command-team" in MOBILE_WORKFLOW_CSS
    assert ".dg-ui-section-title" in MOBILE_WORKFLOW_CSS
    assert "white-space: normal !important" in MOBILE_WORKFLOW_CSS
    assert "word-break: normal !important" in MOBILE_WORKFLOW_CSS
    assert "writing-mode: horizontal-tb !important" in MOBILE_WORKFLOW_CSS
    assert ".home-command-hero > div:last-child" in MOBILE_WORKFLOW_CSS
    assert "min-width: 0 !important" in MOBILE_WORKFLOW_CSS


def test_next_moves_cards_own_full_phone_width_across_320_to_430_pixels():
    assert "@media (max-width: 700px)" in MOBILE_WORKFLOW_CSS
    assert ".home-command-grid {" in MOBILE_WORKFLOW_CSS
    assert "grid-template-columns: minmax(0, 1fr) !important" in MOBILE_WORKFLOW_CSS
    assert ".home-command-card-wide" in MOBILE_WORKFLOW_CSS
    assert "grid-column: 1 / -1 !important" in MOBILE_WORKFLOW_CSS
    assert "flex: 1 1 100% !important" in MOBILE_WORKFLOW_CSS
    assert "max-width: 100% !important" in MOBILE_WORKFLOW_CSS
    assert "width: 100% !important" in MOBILE_WORKFLOW_CSS


def test_dashboard_command_shell_markup_is_balanced():
    source = (ROOT / "modules" / "workspace_ui.py").read_text(encoding="utf-8")
    block = source.split("def render_home_command_hero(", 1)[1].split(
        "\ndef _recommendation_player_row", 1
    )[0]
    assert "+ \"</div></div></div></div>\"" in block
    assert block.count("home-command-shell") == 1


def test_mobile_dashboard_masthead_is_compact_and_metrics_remain_available():
    assert "min-height: 5.5rem !important" in MOBILE_WORKFLOW_CSS
    assert ".dg-workspace-page-note" in MOBILE_WORKFLOW_CSS
    assert "grid-template-columns: repeat(4, minmax(6.5rem, 1fr))" in MOBILE_WORKFLOW_CSS
    assert "overflow-x: auto !important" in MOBILE_WORKFLOW_CSS
    assert "var(--touch-target-min)" in MOBILE_WORKFLOW_CSS


def test_unresolved_durable_auth_read_is_pending_not_logged_out():
    config = {
        "enabled": True,
        "url": "https://example.supabase.co",
        "anon_key": "anon",
    }
    result = Mock()
    result.status = None
    result.stored = None
    with patch.object(account_ui.st, "session_state", {}), patch.object(
        account_ui,
        "AUTH_STORAGE_COMPONENT",
        return_value=result,
    ):
        actions = account_ui.render_durable_auth_bridge(config=config)

    assert actions["pending"] is True
    assert actions["restored"] is False
    assert actions["error"] == ""


def test_completed_empty_durable_auth_read_remains_guest_flow():
    config = {
        "enabled": True,
        "url": "https://example.supabase.co",
        "anon_key": "anon",
    }
    result = Mock()
    result.status = {
        "action": "read",
        "ok": True,
        "reason": "mount",
        "durableAuthPresent": False,
    }
    result.stored = None
    with patch.object(account_ui.st, "session_state", {}), patch.object(
        account_ui,
        "AUTH_STORAGE_COMPONENT",
        return_value=result,
    ):
        actions = account_ui.render_durable_auth_bridge(config=config)

    assert actions["pending"] is False
    assert actions["restored"] is False


def test_app_holds_startup_shell_while_auth_storage_is_unresolved():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    pending = source.index('if auth_restore.get("pending") and startup.active:')
    stop = source.index("st.stop()", pending)
    profile = source.index(
        "startup.advance(startup_coordinator.StartupPhase.PROFILE_LOADING)"
    )

    assert pending < stop < profile


def test_cold_start_has_explicit_import_dashboard_compute_and_render_timings():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '"application_module_import"' in source
    assert '"dashboard_computation"' in source
    assert '"dashboard_rendering"' in source
    for existing_phase in (
        '"public_player_data_load"',
        '"supabase_session_restoration"',
        '"supabase_profile_load"',
        '"saved_league_restoration"',
        '"active_league_context_restoration"',
        '"shared_league_context_generation"',
    ):
        assert existing_phase in source


def test_news_and_explanation_resources_are_lazy_at_startup():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    import_region = source.split("DB_PATH =", 1)[0]
    assert "from modules.news import" not in import_region
    assert "from modules.chat import" not in import_region
    assert "def fetch_news(" in source
    assert "def explain_player_decision(" in source


def test_authenticated_premium_is_canonical_for_shell_and_upgrade_boundary():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "entitlement_label=current_user_entitlement().title()" in source
    assert "if current_user_is_premium():\n        return" in source
    state = {
        "auth_session": {"user_id": "premium-user"},
        "auth_user": {"id": "premium-user"},
        "account_profile": {"entitlement": "premium"},
        "account_profile_status": "loaded",
    }
    assert (
        premium.effective_entitlement(
            session_state=state,
            environ={},
            secrets={},
        )
        == premium.PREMIUM
    )


def test_profile_refresh_retries_errors_and_preserves_last_known_entitlement():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    block = source.split(
        "def _refresh_supabase_account_profile(*, force: bool = False) -> None:",
        1,
    )[1].split("\ndef resolve_active_league_context", 1)[0]
    error_block = block.split("if error:", 1)[1].split("return", 1)[0]
    assert 'pop("account_profile"' not in error_block
    assert "st.session_state[cache_key] = True" in block.split("if error:", 1)[1]
    assert "time.time() - loaded_at" in block


def test_workspace_is_single_page_hero_and_legacy_league_summary_is_not_mounted():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    main_block = source.split("def main():", 1)[1]
    assert "render_platform_topbar(" in main_block
    assert "render_top_league_identity_header(" not in main_block
    page_shell = source.split("def render_page_shell(", 1)[1].split(
        "\ndef style_tier_table", 1
    )[0]
    assert "<h2 class='dg-page-title'>" not in page_shell
    assert "dg-page-context" in page_shell
