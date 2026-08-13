"""Experimental reincorporation contracts (#232)."""

from __future__ import annotations

from pathlib import Path

from modules import decision_memory, experimental_graduation, gm_targets, share_recommendation_cards
from modules import premium_page
from modules.ui_architecture import (
    ARCHIVED_DESTINATION_KEYS,
    PLATFORM_DESTINATIONS,
    current_platform_destinations,
)


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "experimental-feature-reincorporation.md"
LEGACY_DOC = ROOT / "docs" / "experimental-feature-graduation.md"


def test_reincorporation_doc_and_matrix():
    text = DOC.read_text(encoding="utf-8")
    assert "002e4db8" in text
    assert "FINISH → GRADUATED" in text or "FINISH THEN GRADUATE" in text
    assert "Decision Memory" in text
    assert "GM Targets" in text
    assert "Share Recommendation" in text
    assert "Rollback boundary" in text
    matrix = experimental_graduation.matrix_by_feature()
    assert matrix["Decision Memory"]["final"] == experimental_graduation.FINISHED_GRADUATED
    assert matrix["GM Targets"]["final"] == experimental_graduation.FINISHED_GRADUATED
    assert matrix["Share Recommendation"]["final"] == experimental_graduation.FINISHED_GRADUATED
    assert matrix["Player Explorer"]["final"] == experimental_graduation.GRADUATE_NOW
    assert matrix["Trade Analyzer"]["final"] == experimental_graduation.GRADUATE_NOW
    assert matrix["Weekly Report"]["final"] == experimental_graduation.DEFER_HIDE
    assert matrix["Teams route"]["final"] == experimental_graduation.MERGE_INTO_EXISTING
    assert matrix["Manager Tendencies"]["final"] == experimental_graduation.MERGE_INTO_EXISTING
    assert matrix["ESPN"]["final"] == experimental_graduation.KEEP_EXPERIMENTAL
    assert matrix["Live Draft"]["final"] == experimental_graduation.ALREADY_GRADUATED


def test_graduated_kill_switches_default_on():
    assert experimental_graduation.GRADUATED_DEFAULT_ON is True
    assert decision_memory.experiment_enabled(environ={}) is True
    assert gm_targets.experiment_enabled(environ={}) is True
    assert share_recommendation_cards.experiment_enabled(environ={}) is True
    assert decision_memory.experiment_enabled(
        environ={"DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY": "0"}
    ) is False
    assert gm_targets.experiment_enabled(
        environ={"DYNASTYGM_EXPERIMENTAL_GM_TARGETS": "false"}
    ) is False
    assert share_recommendation_cards.experiment_enabled(
        environ={"DYNASTYGM_EXPERIMENTAL_SHARE_CARDS": "off"}
    ) is False


def test_players_core_and_duplicates_archived():
    by_key = {page.key: page for page in PLATFORM_DESTINATIONS}
    assert by_key["players"].category == "CORE"
    assert by_key["players"].beta_visible is True
    assert by_key["gm_targets"].category == "CONDITIONAL"
    assert by_key["trade_analyzer"].category == "CORE"
    assert by_key["trade_analyzer"].beta_visible is True
    for key in (
        "teams",
        "weekly_report",
        "manager_tendencies",
        "player_detail",
        "news",
        "archetypes",
    ):
        assert by_key[key].category == "ARCHIVED"
        assert key in ARCHIVED_DESTINATION_KEYS
    visible = {page.key for page in current_platform_destinations(False)}
    assert "players" in visible
    assert "gm_targets" not in visible
    assert "trade_analyzer" in visible
    assert "teams" not in visible
    conditional = {
        page.key
        for page in current_platform_destinations(
            False, enabled_experimental=("gm_targets", "live_draft")
        )
    }
    assert "gm_targets" in conditional
    assert "live_draft" in conditional


def test_gm_targets_free_premium_guest_contracts():
    free = {
        "auth_session": {
            "user_id": "11111111-1111-1111-1111-111111111111",
            "access_token": "tok",
        },
        "auth_user": {"id": "11111111-1111-1111-1111-111111111111"},
        "account_profile": {"entitlement": "free"},
    }
    premium = {
        "auth_session": {
            "user_id": "22222222-2222-2222-2222-222222222222",
            "access_token": "tok",
        },
        "auth_user": {"id": "22222222-2222-2222-2222-222222222222"},
        "account_profile": {"entitlement": "premium"},
    }
    assert gm_targets.can_access_targets(free) is True
    assert gm_targets.can_access_targets(premium) is True
    assert gm_targets.can_access_targets({}) is False
    assert gm_targets.can_show_discovery({}) is True
    assert gm_targets.max_targets_for_session(free) == gm_targets.MAX_TARGETS_FREE
    assert gm_targets.max_targets_for_session(premium) == gm_targets.MAX_TARGETS_PREMIUM


def test_decision_memory_premium_history_free_session():
    free = {
        "auth_session": {
            "user_id": "11111111-1111-1111-1111-111111111111",
            "access_token": "tok",
        },
        "auth_user": {"id": "11111111-1111-1111-1111-111111111111"},
        "account_profile": {"entitlement": "free"},
    }
    premium = {
        "auth_session": {
            "user_id": "22222222-2222-2222-2222-222222222222",
            "access_token": "tok",
        },
        "auth_user": {"id": "22222222-2222-2222-2222-222222222222"},
        "account_profile": {"entitlement": "premium"},
    }
    assert decision_memory.can_show_discovery(free) is True
    assert decision_memory.can_access_history(free) is False
    assert decision_memory.should_sync_durable(free) is False
    assert decision_memory.can_access_history(premium) is True
    assert decision_memory.should_sync_durable(premium) is True


def test_share_is_free_and_surfaces_wired():
    assert share_recommendation_cards.EXPERIMENTAL_LABEL == ""
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "share_recommendation_ui.render_share_controls" in app
    trade = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    assert "share_recommendation_ui.render_share_controls" in trade
    assert 'expander("Player actions"' not in trade
    waivers = (ROOT / "modules" / "waivers_ui.py").read_text(encoding="utf-8")
    assert "share_recommendation_ui.render_share_controls" in waivers


def test_premium_marketing_includes_graduated_premium_depth():
    included = {title for title, _ in premium_page.PREMIUM_INCLUDED_NOW}
    free = {title for title, _ in premium_page.FREE_INCLUDES}
    assert "Decision Memory" in included
    assert "GM Targets (full board)" in included
    assert "Share Recommendation" in free
    assert "GM Targets (limited)" in free
    assert premium_page.PREMIUM_EXPERIMENTAL_WHEN_ENABLED == ()


def test_cross_workflow_entry_points():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "gm_targets_ui.render_pqv_target_control" in app
    ui = (ROOT / "modules" / "gm_targets_ui.py").read_text(encoding="utf-8")
    assert "Open Trade Hub" in ui
    assert "Open Waivers" in ui
    assert "_workflow_handoff_destination" in ui
    assert 'enabled_experimental_keys.append("gm_targets")' in app
    assert '("Experimental", "warning")' not in app[
        app.index('if current_page == "gm_targets"') : app.index(
            'if current_page == "players"'
        )
    ]


def test_player_explorer_css_lazy_not_in_cold_app_css():
    from modules.app_styles import APP_CSS
    from modules.player_asset_explorer_styles import PLAYER_ASSET_EXPLORER_CSS

    assert PLAYER_ASSET_EXPLORER_CSS not in APP_CSS
    explorer = (ROOT / "modules" / "player_asset_explorer_ui.py").read_text(
        encoding="utf-8"
    )
    assert "inject_global_styles(PLAYER_ASSET_EXPLORER_CSS)" in explorer


def test_no_game_plan_fingerprint_pollution():
    for rel in (
        "modules/gm_targets.py",
        "modules/decision_memory.py",
        "modules/share_recommendation_cards.py",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "game_plan_process_cache" not in text
        assert "invalidate_game_plan" not in text
        assert "fingerprint_inputs" not in text
        assert "build_game_plan_fingerprint" not in text


def test_legacy_graduation_doc_still_present():
    assert LEGACY_DOC.is_file()
    assert "be6bfa6" in LEGACY_DOC.read_text(encoding="utf-8")
