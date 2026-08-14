from pathlib import Path

from modules import premium


ROOT = Path(__file__).resolve().parents[1]


def app_source() -> str:
    return (ROOT / "app.py").read_text(encoding="utf-8")


def test_effective_entitlement_uses_supabase_profile():
    state = {
        "auth_session": {"user_id": "user-1"},
        "account_profile": {"user_id": "user-1", "entitlement": "premium"},
    }
    assert premium.effective_entitlement(session_state=state, environ={}, secrets={}) == premium.PREMIUM


def test_effective_entitlement_defaults_free_without_supabase_profile():
    state = {
        "auth_session": {"user_id": "user-1"},
        "auth_user": {"id": "user-1", "entitlement": "premium"},
    }
    assert premium.effective_entitlement(session_state=state, environ={}, secrets={}) == premium.FREE


def test_development_override_has_highest_priority():
    state = {
        "auth_session": {"user_id": "user-1"},
        "account_profile": {"user_id": "user-1", "entitlement": "free"},
    }
    assert (
        premium.effective_entitlement(
            session_state=state,
            environ={"DYNASTYGM_PREMIUM_OVERRIDE": "true"},
            secrets={},
        )
        == premium.PREMIUM
    )


def test_dashboard_gate_consumes_canonical_entitlement_snapshot():
    source = app_source()
    dashboard = source.split("def render_home_dashboard(", 1)[1].split("STARTUP_DRAFT_STRATEGIES", 1)[0]
    assert "effective_entitlement: str = premium.FREE" in dashboard
    assert "dashboard_premium_content_state(effective_entitlement)" in dashboard
    assert "is_premium = current_user_is_premium()" not in dashboard


def test_dashboard_premium_content_state_covers_premium_and_free_users():
    import app

    assert app.dashboard_premium_content_state(premium.PREMIUM) == {
        "is_premium": True,
        "show_upgrade_prompts": False,
    }
    assert app.dashboard_premium_content_state(premium.FREE) == {
        "is_premium": False,
        "show_upgrade_prompts": True,
    }


def test_dashboard_upgrade_prompts_are_confined_to_free_entitlement_branches():
    source = app_source()
    dashboard = source.split("def render_home_dashboard(", 1)[1].split(
        "STARTUP_DRAFT_STRATEGIES", 1
    )[0]

    assert '"More next moves"' in dashboard
    assert '"Full League Pulse"' in dashboard
    assert 'if premium_content["show_upgrade_prompts"]' in dashboard
    assert dashboard.count('if premium_content["show_upgrade_prompts"]') == 2
    assert 'button_label="Load League Pulse"' in dashboard
    assert "dashboard_workflow.render_dashboard_workflow(" in dashboard


def test_header_and_all_app_gates_share_effective_entitlement_helper():
    source = app_source()
    helper = source.split("def refresh_current_user_entitlement()", 1)[1].split(
        "def render_premium_lock", 1
    )[0]
    assert "premium.effective_entitlement(" in helper
    assert 'st.session_state["_effective_entitlement"] = entitlement' in helper
    assert "refresh_current_user_entitlement()" in source


def test_dashboard_has_minimal_fallback_candidate_cache():
    source = app_source()
    builder = source.split("def cached_dashboard_trade_headline(", 1)[1].split(
        "def cached_player_trade_hub_ideas(", 1
    )[0]
    assert "max_ideas=1" in builder
    assert 'search_budget="dashboard"' in builder
    assert "prefetched_rosters" in builder
    assert "dashboard_trade_headline_generation" in builder
    dashboard = source.split("def render_home_dashboard(", 1)[1].split(
        "STARTUP_DRAFT_STRATEGIES", 1
    )[0]
    assert "cached_dashboard_trade_headline(" in dashboard
    assert "enforce_cached_trade_ideas(" in dashboard
    assert "enriched_dashboard_trade_candidates[0]" in dashboard
    assert dashboard.index("cached_dashboard_trade_headline(") < dashboard.index(
        "enforce_cached_trade_ideas("
    )
    assert dashboard.index("enforce_cached_trade_ideas(") < dashboard.index(
        "enrich_trade_ideas_with_manager_tendencies("
    )
    assert "max_ideas=4" not in dashboard


def test_transaction_history_never_scans_future_rounds():
    import app

    assert app._league_history_window({"settings": {"leg": 0, "playoff_week_start": 15}}) == (0, 14, 1)
    assert app._league_history_window({"settings": {"leg": 6, "playoff_week_start": 15}}) == (6, 14, 6)
    assert app._league_history_window({"settings": {"leg": 18, "playoff_week_start": 15}}) == (18, 14, 18)


def test_trade_activity_reuses_completed_round_window():
    source = app_source()
    block = source.split("def cached_trade_activity_summary(", 1)[1].split(
        "def cached_manager_behavior_summary(", 1
    )[0]
    assert "_, _, last_round = _league_history_window(league)" in block
    assert "playoff_week_start + 3" not in block


def test_rookie_draft_context_is_lazy_on_dashboard():
    source = app_source()
    assert "def get_rookie_draft_context() -> dict:" in source
    setup = source.split("def get_rookie_draft_context() -> dict:", 1)[0].rsplit(
        "rookie_draft_context: dict | None = None", 1
    )[1]
    assert "cached_rookie_draft_context(" not in setup
