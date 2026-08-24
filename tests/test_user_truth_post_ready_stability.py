from pathlib import Path

from modules import game_plan_package
from modules import game_plan_process_cache
from modules import game_plan_truth_canon as truth_canon


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / "modules" / "dashboard_workflow.py").read_text(encoding="utf-8")
VISIBILITY = (ROOT / "modules" / "dashboard_visibility.py").read_text(encoding="utf-8")


def _package_signature(strategy: str) -> str:
    return game_plan_package.build_package_signature(
        account_user_id="user-a",
        league_id="league-a",
        roster_id="roster-a",
        prepared_frame_signature="frame-a",
        score_field="dynasty_score",
        league_settings_key="settings-a",
        team_strategy=strategy,
        entitlement="premium",
        lifecycle_digest="life-a",
        roster_state_version="roster-v1",
        pick_score_multiplier=1.0,
    )


def _trade_signature(strategy: str) -> str:
    return game_plan_process_cache.build_trade_process_signature(
        prepared_frame_signature="frame-a",
        league_id="league-a",
        roster_id="roster-a",
        score_field="dynasty_score",
        league_settings_key="settings-a",
        team_strategy=strategy,
        pick_score_multiplier=1.0,
        roster_state_version="roster-v1",
    )


def test_explicit_strategy_survives_dashboard_navigation_and_restore_views():
    state: dict = {}
    truth_canon.apply_explicit_strategy_change(
        state,
        truth_signature="truth-a",
        team_strategy="contender",
        team_strategy_label="Contender",
        auto_team_strategy="retool",
        team_strategy_override="Contender",
        pick_score_multiplier=1.0,
        writer="my_team_strategy_select",
    )
    package_before = _package_signature("contender")
    trade_before = _trade_signature("contender")

    for _route in ("dashboard", "my_team", "trade_hub", "dashboard"):
        view = truth_canon.presentation_strategy_view(
            state,
            inferred_strategy="retool",
            inferred_label="Retool",
            inferred_auto_strategy="retool",
            inferred_override="Auto",
        )
        assert view[truth_canon.CANON_STRATEGY_FIELD] == "contender"

    restored = dict(state)
    restored_view = truth_canon.presentation_strategy_view(
        restored,
        inferred_strategy="retool",
        inferred_override="Auto",
    )
    assert restored_view[truth_canon.CANON_STRATEGY_FIELD] == "contender"
    assert _package_signature(restored_view[truth_canon.CANON_STRATEGY_FIELD]) == package_before
    assert _trade_signature(restored_view[truth_canon.CANON_STRATEGY_FIELD]) == trade_before


def test_league_switch_clears_canon_instead_of_leaking_strategy():
    state: dict = {}
    truth_canon.apply_explicit_strategy_change(
        state,
        truth_signature="truth-a",
        team_strategy="contender",
        pick_score_multiplier=1.0,
    )
    truth_canon.clear_canon(state)
    league_b = truth_canon.presentation_strategy_view(
        state,
        inferred_strategy="rebuild",
        inferred_label="Rebuild",
        inferred_override="Auto",
    )
    assert league_b[truth_canon.CANON_STRATEGY_FIELD] == "rebuild"


def test_dashboard_root_does_not_allocate_a_zero_height_marker_slot():
    assert '<div class="dashboard-workflow-shell"' not in WORKFLOW
    assert ".dashboard-workflow-shell" not in VISIBILITY
    assert "doc.querySelector('.st-key-dashboard_workflow')" in VISIBILITY


def test_all_production_team_strategy_writers_are_canonical_or_session_mirrors():
    assert 'writer="my_team_strategy_select"' in APP
    assert 'writer="pre_package_canonical_resolver"' in APP
    assert 'writer="valued_shell_chrome_enrichment"' not in APP
    assert APP.count('st.session_state["active_team_strategy"] = active_team_strategy') == 4


def test_league_context_capacity_evicts_one_cold_entry_not_the_active_context(monkeypatch):
    game_plan_process_cache.clear_process_game_plan_caches()
    monkeypatch.setattr(game_plan_process_cache, "_MAX_LEAGUE", 3)
    builds: dict[str, int] = {}

    def load(key: str):
        def builder():
            builds[key] = builds.get(key, 0) + 1
            return {"league": key}

        return game_plan_process_cache.get_or_build_league_context(
            signature=key,
            builder=builder,
            session_state={},
        )

    load("active")
    load("cold-a")
    load("cold-b")
    _, active_hit = load("active")  # refresh LRU ownership
    assert active_hit is True

    load("new-context")
    payload, active_hit_after_capacity = load("active")
    assert active_hit_after_capacity is True
    assert payload["league"] == "active"
    assert builds["active"] == 1
    assert len(game_plan_process_cache._PROCESS_LEAGUE_CONTEXT) == 3
    game_plan_process_cache.clear_process_game_plan_caches()
