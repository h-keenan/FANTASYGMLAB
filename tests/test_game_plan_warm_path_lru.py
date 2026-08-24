"""Warm Game Plan package reuse: last-used LRU, fingerprint ownership, persist skip."""

from pathlib import Path
import time

from modules import game_plan_package


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
PACKAGE = (ROOT / "modules" / "game_plan_package.py").read_text(encoding="utf-8")


def test_game_plan_package_capacity_evicts_cold_not_active():
    game_plan_package.clear_process_game_plan_packages()
    original = game_plan_package._MAX_PROCESS_PACKAGES
    game_plan_package._MAX_PROCESS_PACKAGES = 3
    try:
        now = time.time()
        for idx, key in enumerate(("active", "cold-a", "cold-b")):
            game_plan_package._store_process_package(
                key,
                {
                    "league_id": key,
                    "built_at": now,
                    "fingerprint_components": {"league_id": key},
                },
            )
        game_plan_package.lookup_package({"selected_league_id": "active"}, signature="active")
        game_plan_package._store_process_package(
            "new-context", {"league_id": "new", "built_at": time.time()}
        )
        payload, hit = game_plan_package.lookup_package(
            {"selected_league_id": "active"}, signature="active"
        )
        assert hit is True
        assert payload["league_id"] == "active"
        assert "active" in game_plan_package._PROCESS_PACKAGE_STORE
        assert "new-context" in game_plan_package._PROCESS_PACKAGE_STORE
        assert len(game_plan_package._PROCESS_PACKAGE_STORE) == 3
    finally:
        game_plan_package._MAX_PROCESS_PACKAGES = original
        game_plan_package.clear_process_game_plan_packages()


def test_fingerprint_inputs_are_football_not_presentation():
    assert "startup_mode" in PACKAGE
    assert "intentionally ignored" in PACKAGE
    components = game_plan_package.package_fingerprint_components(
        account_user_id="u1",
        league_id="L1",
        roster_id="7",
        prepared_frame_signature="frame",
        score_field="dynasty_score",
        league_settings_key="settings",
        team_strategy="contend",
        role_items=(("p1", "Core"),),
        untouchables=("A",),
        entitlement="premium",
        lifecycle_digest="fp",
        roster_state_version="rv1",
        pick_score_multiplier=1,
        waiver_pool_digest="pool",
    )
    assert "startup_mode" not in components
    assert "news" not in components
    assert "shell" not in components
    assert "presentation" not in components
    changed = game_plan_package.fingerprint_component_diff(
        components,
        {**components, "role_items": "deadbeef"},
    )
    assert changed == ("role_items",)


def test_waiver_generation_is_on_package_miss_not_hit():
    miss_branch = APP.split("if game_plan_package_hit and cached_package:", 1)[1]
    hit_branch, miss_body = miss_branch.split("else:", 1)
    assert "select_top_waiver_opportunity(" not in hit_branch
    assert "select_top_waiver_opportunity(" in miss_body.split(
        "def _render_dashboard_league_pulse()", 1
    )[0]
    assert "build_home_dashboard_free_agent_preview(" in miss_body.split(
        "def _render_dashboard_league_pulse()", 1
    )[0]


def test_dashboard_game_plan_skips_intelligence_before_first_useful():
    loader = APP.split("def _load_game_plan_league_context()", 1)[1].split(
        "def _resolve_dashboard_strategy_tuple()", 1
    )[0]
    assert "include_intelligence=flags[0]" in loader
    assert "include_intelligence=True" not in loader
    assert game_plan_package.GAME_PLAN_CONTEXT_FLAGS[0] is False
    assert "league_core_including_intel" not in loader


def test_recommendation_freshness_is_truth_lock_not_package_invalidation():
    span = APP.split('"recommendation_freshness_decision"', 1)[1].split(
        "render_home_dashboard(", 1
    )[0]
    assert "resolve_or_lock_strategy" in span
    assert "writer=\"pre_package_canonical_resolver\"" in span
    assert "invalidate_recommendation_packages" not in span


def test_duplicate_supabase_account_persist_is_fingerprinted():
    persist = APP.split("def _persist_supabase_account_context(", 1)[1].split(
        "def _resume_saved_supabase_league(", 1
    )[0]
    assert "_persisted_supabase_account_fingerprint" in persist
    assert "save_current_context(" in persist
    assert 'if st.session_state.get("_persisted_supabase_account_fingerprint") == persist_fp:' in persist
