from __future__ import annotations

from pathlib import Path
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

import app
from modules import render_ownership
from modules import trade_hub_player_search as player_search


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def _signature(*, league: str, player: str, mode: str) -> str:
    return player_search.search_signature(
        league_id=league,
        roster_id="1",
        strategy="balanced",
        mode=mode,
        player_id=player,
        score_field="value_score",
        pick_score_multiplier=1,
        value_version="balanced",
    )


def _initiate_pqv_handoff(*, on_roster: bool, player: str = "p1", league: str = "A") -> dict:
    state: dict = {
        "platform_nav_page": "my_team",
        "selected_league_name": f"League {league}",
    }
    with (
        patch("streamlit.session_state", state),
        patch.object(
            app,
            "resolve_active_league_context",
            return_value={
                "selected_league_id": league,
                "selected_league_name": f"League {league}",
                "username": "fixture",
            },
        ),
        patch.object(app, "_player_on_active_roster", return_value=on_roster),
        patch.object(app, "_capture_workflow_handoff"),
        patch.object(app, "_clear_player_quick_view"),
        patch.object(app, "_queue_platform_route"),
        patch("streamlit.rerun"),
    ):
        app._open_trade_hub_for_player_focus(
            player_row=pd.Series({"player_id": player, "name": f"Player {player}"}),
            selected_league_id=league,
            my_roster_id=1,
        )
    return state


def test_real_pqv_initiating_action_executes_your_player_search_contract():
    state = _initiate_pqv_handoff(on_roster=True)
    assert state["player_trade_hub_mode_A"] == "Your Player"
    assert state["trade_hub_focus_mode_A"] == "my_player"
    signature = _signature(league="A", player="p1", mode="my_player")
    assert player_search.execute_queued_player_focus(
        state, league_id="A", player_id="p1", signature=signature
    )
    assert player_search.is_executed(state, signature)
    assert "trade_hub_pending_focus_A" not in state


def test_real_return_explorer_auto_executes_and_renders_ideas_from_pqv_action():
    state = _initiate_pqv_handoff(on_roster=True)
    players = pd.DataFrame(
        [
            {
                "player_id": "p1",
                "name": "Player p1",
                "position": "RB",
                "team": "NYG",
                "age": 24,
                "player_tier": "Starter",
                "value_score": 5000,
                "injury_level": "healthy",
            }
        ]
    )
    idea = {"id": "idea-1", "tag": "Return path", "receive_assets": []}

    def selectbox(_label, options, *, key):
        return state.get(key, options[0])

    with (
        patch("streamlit.session_state", state),
        patch("streamlit.selectbox", side_effect=selectbox),
        patch("streamlit.button", return_value=False),
        patch("streamlit.spinner", side_effect=lambda *_a, **_k: nullcontext()),
        patch.object(
            app.trade_detail_navigation,
            "current",
            return_value=SimpleNamespace(trade_key=""),
        ),
        patch.object(app, "cached_player_trade_hub_ideas", return_value={"ideas": [idea]}),
        patch.object(app, "enforce_cached_trade_ideas", side_effect=lambda ideas, **_k: ideas),
        patch.object(app, "enrich_trade_ideas_with_manager_tendencies", side_effect=lambda ideas, _df: ideas),
        patch.object(app, "render_summary_tiles"),
        patch.object(app, "split_trade_surface_ideas", return_value=([idea], [])),
        patch.object(app, "select_trade_hub_headline_idea", return_value=None),
        patch.object(app, "render_player_trade_hub_card") as render_card,
    ):
        visible = app.render_trade_return_explorer(
            all_players_df=players,
            owned_player_df=players,
            league_id="A",
            df_summary=pd.DataFrame(),
            my_roster_id=1,
            untouchables=(),
            role_map={},
            score_field="value_score",
            pick_score_multiplier=1,
            team_strategy="balanced",
            league_settings={},
            key_prefix="real_focus",
            team_archetype="balanced",
            preselected_player_id="p1",
            show_header=False,
        )

    assert visible == [idea]
    render_card.assert_called_once()
    assert state["player_trade_hub_mode_A"] == "Your Player"
    assert "trade_hub_pending_focus_A" not in state


def test_real_pqv_initiating_action_executes_league_target_search_contract():
    state = _initiate_pqv_handoff(on_roster=False)
    assert state["player_trade_hub_mode_A"] == "League Target"
    assert state["trade_hub_focus_mode_A"] == "target_player"
    signature = _signature(league="A", player="p1", mode="target_player")
    assert player_search.execute_queued_player_focus(
        state, league_id="A", player_id="p1", signature=signature
    )
    assert player_search.is_executed(state, signature)
    assert "trade_hub_pending_focus_A" not in state


def test_focus_is_not_cleared_until_exact_player_consumes_it():
    state = _initiate_pqv_handoff(on_roster=True, player="A")
    wrong = _signature(league="A", player="B", mode="my_player")
    assert not player_search.execute_queued_player_focus(
        state, league_id="A", player_id="B", signature=wrong
    )
    assert state["trade_hub_pending_focus_A"] == "A"
    correct = _signature(league="A", player="A", mode="my_player")
    assert player_search.execute_queued_player_focus(
        state, league_id="A", player_id="A", signature=correct
    )
    assert "trade_hub_pending_focus_A" not in state


def test_focus_a_to_b_replaces_and_league_switch_isolates_without_cache():
    state: dict = {}
    player_search.queue_player_focus(state, league_id="A", player_id="A")
    player_search.queue_player_focus(state, league_id="A", player_id="B")
    assert state["trade_hub_pending_focus_A"] == "B"
    player_search.clear_league_search(state, "B")
    assert "trade_hub_pending_focus_A" not in state


def test_header_has_one_run_scoped_owner_and_one_stable_slot():
    state: dict = {}
    render_ownership.begin_script_run(state)
    assert render_ownership.claim(state, render_ownership.OWNER_COMMAND_HEADER)
    assert not render_ownership.claim(state, render_ownership.OWNER_COMMAND_HEADER)
    main = APP.split("def main():", 1)[1]
    assert 'command_header_slot = st.container(key="application_command_header_slot")' in main
    assert "host_slot=command_header_slot" in main
    assert "and not returning_authenticated" in main
    assert APP.count("render_platform_topbar(") == 2


def test_actual_command_header_winning_selectors_are_square():
    css = (ROOT / "modules" / "executive_command_header_styles.py").read_text(
        encoding="utf-8"
    )
    assert '[data-testid="stPopover"] button[data-testid="stPopoverButton"]' in css
    assert '[data-testid="stPopover"] > div[aria-haspopup="true"]' in css
    assert '[data-baseweb="button"]' in css
    square_rule = css.split("The visible BaseWeb trigger surface", 1)[1].split("}", 1)[0]
    assert "border-radius: 0 !important" in square_rule


def test_my_player_and_target_call_sites_share_execution_api():
    assert APP.count("player_search.execute_queued_player_focus(") == 2
    assert "player_search.has_queued_player_focus(" in APP
    old_clear = (
        'if trade_hub_focus_mode == "my_player":\n'
        '                            st.session_state.pop'
    )
    assert old_clear not in APP


def test_production_header_browser_validator_checks_intermediate_dom():
    source = (ROOT / "scripts" / "validate_post_367_header.py").read_text(
        encoding="utf-8"
    )
    assert "MutationObserver" in source
    assert 'min(transition["counts"]) != 1' in source
    assert "buttonRadii" in source and "wrapperRadii" in source and "shellRadii" in source
    assert "header-route-transition-{width}x844.png" in source
