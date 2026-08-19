from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

import app
from modules import canonical_recommendation_narrative as crn
from modules import navigation_state
from modules import trade_detail_navigation
from modules import trade_hub_ui
from modules import trade_ideas


ROOT = Path(__file__).resolve().parents[1]


def _idea(partner: str, send_id: str, receive_id: str) -> dict:
    return {
        "partner_roster_id": partner,
        "partner_team_name": partner,
        "tag": f"{send_id} for {receive_id}",
        "send_assets": [{"asset_type": "player", "player_id": send_id, "name": send_id}],
        "receive_assets": [{"asset_type": "player", "player_id": receive_id, "name": receive_id}],
        "my_score": 4000,
        "their_score": 4100,
        "trade_gain": 100,
    }


def test_real_dashboard_action_resolves_and_opens_exact_trade_detail():
    target = _idea("Exact Partner", "send-exact", "receive-exact")
    other = _idea("Other Partner", "send-other", "receive-other")
    rec_id = crn.trade_recommendation_id(target)
    narrative = SimpleNamespace(recommendation_id=rec_id)
    item = SimpleNamespace(
        destination="trade_hub",
        kind="trade",
        route_player_id="",
        route_focus_mode="",
        reason="Review this exact package.",
        recommendation_narrative=narrative,
    )
    state = {"platform_nav_page": "dashboard", "selected_league_id": "L1"}
    with (
        patch("streamlit.session_state", state),
        patch.object(app.canonical_recommendation_narrative, "bind_narrative"),
        patch.object(app, "_capture_workflow_handoff"),
        patch.object(app, "_queue_platform_route"),
    ):
        app._open_daily_gm_briefing_item(item)
    assert state["trade_hub_focus_recommendation_id_L1"] == rec_id

    ranked, status, trade_key = trade_hub_ui.resolve_handoff_trade_detail(
        [other, target], rec_id, page_context="trade_hub_feed"
    )
    assert status == "focused"
    assert ranked[0] is target
    trade_detail_navigation.open_trade(state, trade_key)
    assert trade_detail_navigation.current(state).trade_key == trade_key
    assert trade_key == trade_hub_ui.trade_summary_key(
        target, page_context="trade_hub_feed", instance_token=0
    )


def test_stale_dashboard_trade_handoff_opens_nothing():
    remaining = [_idea("Current Partner", "a", "b")]
    stale = crn.trade_recommendation_id(_idea("Gone Partner", "x", "y"))
    ranked, status, trade_key = trade_hub_ui.resolve_handoff_trade_detail(
        remaining, stale, page_context="trade_hub_feed"
    )
    assert ranked == remaining
    assert status == "stale"
    assert trade_key == ""
    assert "no longer a current recommendation" in trade_hub_ui.handoff_stale_copy()


def test_pqv_anchor_request_survives_generic_route_reset_and_consumes_once():
    state = {"platform_nav_page": "dashboard"}
    token = navigation_state.request_scroll_anchor(
        state,
        "trade_hub",
        anchor="trade-hub-player-search",
        reason="player_quick_view",
    )
    navigation_state.queue_destination_navigation(
        state,
        "trade_hub",
        current_destination="dashboard",
        source="player_quick_view",
    )
    pending = navigation_state.consume_scroll_reset(state, "trade_hub")
    assert pending == {
        "token": token,
        "destination": "trade_hub",
        "reason": "player_quick_view",
        "mode": "anchor",
        "anchor": "trade-hub-player-search",
    }
    assert navigation_state.consume_scroll_reset(state, "trade_hub") is None


def _elite_fixture() -> tuple[pd.DataFrame, pd.DataFrame, object]:
    players = [
        {"player_id": "elite", "name": "Elite Target", "position": "RB", "team": "LV", "value_score": 10000, "age": 22},
        *[
            {"player_id": f"mine-{idx}", "name": f"My Asset {idx}", "position": "WR", "team": "X", "value_score": 3200, "age": 25}
            for idx in range(1, 5)
        ],
    ]
    frame = pd.DataFrame(players)
    summary = pd.DataFrame(
        [
            {"roster_id": 1, "team_name": "My Team", "mode": "balanced"},
            {"roster_id": 2, "team_name": "Elite Owner", "mode": "balanced"},
        ]
    )
    adapter = SimpleNamespace(
        get_rosters=lambda _league: [
            {"roster_id": 1, "players": [f"mine-{idx}" for idx in range(1, 5)]},
            {"roster_id": 2, "players": ["elite"]},
        ]
    )
    return frame, summary, adapter


def _realistic_jeanty_fixture() -> tuple[pd.DataFrame, pd.DataFrame, object, dict]:
    players = [
        {"player_id": "jeanty", "name": "Ashton Jeanty", "position": "RB", "team": "LV", "value_score": 9730, "age": 22, "player_tier": "Elite", "trust_enforcement": "pass", "trust_evidence_confidence": "high"},
        {"player_id": "core-wr", "name": "Core WR", "position": "WR", "team": "MIN", "value_score": 6800, "age": 24, "player_tier": "Core Starter"},
        {"player_id": "starter-qb", "name": "Starter QB", "position": "QB", "team": "GB", "value_score": 5200, "age": 26, "player_tier": "Starter"},
        {"player_id": "young-wr", "name": "Young WR", "position": "WR", "team": "CAR", "value_score": 4100, "age": 23, "player_tier": "Starter"},
        {"player_id": "starter-te", "name": "Starter TE", "position": "TE", "team": "DAL", "value_score": 3300, "age": 25, "player_tier": "Starter"},
        {"player_id": "depth-rb", "name": "Depth RB", "position": "RB", "team": "CHI", "value_score": 2800, "age": 26, "player_tier": "Contributor"},
        {"player_id": "depth-wr", "name": "Depth WR", "position": "WR", "team": "NYG", "value_score": 2100, "age": 27, "player_tier": "Depth"},
        {"player_id": "partner-wr", "name": "Partner WR", "position": "WR", "team": "SEA", "value_score": 3600, "age": 25, "player_tier": "Starter"},
        {"player_id": "partner-qb", "name": "Partner QB", "position": "QB", "team": "NE", "value_score": 3000, "age": 27, "player_tier": "Contributor"},
    ]
    frame = pd.DataFrame(players)
    summary = pd.DataFrame(
        [
            {"roster_id": 1, "team_name": "Fringe Contender", "mode": "fringe_contender"},
            {"roster_id": 2, "team_name": "KING TITUS", "mode": "retool", "activity_level": "Highly Active", "asset_behavior": "Pick Hoarder"},
            {"roster_id": 3, "team_name": "Balanced Club", "mode": "balanced"},
        ]
    )
    adapter = SimpleNamespace(
        get_rosters=lambda _league: [
            {"roster_id": 1, "players": ["core-wr", "starter-qb", "young-wr", "starter-te", "depth-rb", "depth-wr"]},
            {"roster_id": 2, "players": ["jeanty", "partner-wr", "partner-qb"]},
            {"roster_id": 3, "players": []},
        ]
    )
    picks = {
        1: [
            {"asset_type": "pick", "label": "2027 Round 1", "season": 2027, "round": 1, "score": 3600, "original_roster_id": 1, "owner_roster_id": 1},
            {"asset_type": "pick", "label": "2028 Round 1", "season": 2028, "round": 1, "score": 3200, "original_roster_id": 1, "owner_roster_id": 1},
            {"asset_type": "pick", "label": "2027 Round 2", "season": 2027, "round": 2, "score": 1500, "original_roster_id": 1, "owner_roster_id": 1},
            {"asset_type": "pick", "label": "2028 Round 2", "season": 2028, "round": 2, "score": 1300, "original_roster_id": 1, "owner_roster_id": 1},
        ],
        2: [],
        3: [],
    }
    return frame, summary, adapter, picks


def test_realistic_jeanty_market_surfaces_bounded_multi_pick_path():
    frame, summary, adapter, picks = _realistic_jeanty_fixture()
    my_shape = {"mode": "contender", "strategy": "fringe_contender", "needs": ["RB"], "surplus": ["WR"], "draft_capital_tier": "high", "roster_at_limit": True}
    partner_shape = {"mode": "retool", "strategy": "retool", "needs": ["WR", "QB"], "surplus": ["RB"], "draft_capital_tier": "low", "roster_at_limit": False}
    with (
        patch.object(trade_ideas, "_build_roster_pick_assets", return_value=picks),
        patch.object(trade_ideas, "get_team_vs_league", return_value={"strategy": "fringe_contender"}),
        patch.object(trade_ideas, "_build_team_shape", side_effect=lambda _summary, roster_id, *_args, **_kwargs: my_shape if roster_id == 1 else partner_shape),
    ):
        result = trade_ideas.build_player_trade_hub_ideas(
            df_players=frame,
            league_id="realistic-L1",
            df_summary=summary,
            my_roster_id=1,
            role_map={"core-wr": "Core", "starter-qb": "Core", "young-wr": "Flex", "starter-te": "Flex", "depth-rb": "Bench", "depth-wr": "Bench"},
            untouchable_names=["Core WR"],
            mode="target_player",
            selected_player_id="jeanty",
            max_ideas=8,
            team_strategy="fringe_contender",
            adapter=adapter,
        )
    assert result["ideas"]
    idea = result["ideas"][0]
    assert [asset["label"] for asset in idea["send_assets"]] == [
        "2027 Round 1",
        "2028 Round 1",
        "2027 Round 2",
        "2028 Round 2",
    ]
    assert idea["receive_assets"][0]["player_id"] == "jeanty"
    diagnostics = result["diagnostics"]
    assert diagnostics["strict_candidate_count"] == 36
    assert diagnostics["expanded_candidate_count"] <= 85
    assert diagnostics["soft_partner_fit_widened"] == 1
    assert diagnostics["market_realism_pass"] == 1
    assert diagnostics["final_visibility"] == 1
    assert len(diagnostics["closest_rejections"]) == 10
    trust_context = app.build_trade_trust_context(
        league_id="realistic-L1",
        df_summary=summary,
        roster_player_map={
            "1": ("core-wr", "starter-qb", "young-wr", "starter-te", "depth-rb", "depth-wr"),
            "2": ("jeanty", "partner-wr", "partner-qb"),
            "3": (),
        },
    )
    enforced = app.enforce_cached_trade_ideas(
        result["ideas"],
        df_players=frame,
        league_id="realistic-L1",
        df_summary=summary,
        my_roster_id=1,
        untouchables=("Core WR",),
        trust_context=trust_context,
    )
    if not enforced:
        canonical_players = {
            str(row["player_id"]): row.to_dict() for _, row in frame.iterrows()
        }
        board = app.enforce_trade_board(
            result["ideas"],
            canonical_players=canonical_players,
            player_enforcement={},
            ownership_by_player=dict(trust_context.ownership_by_player),
            valid_roster_ids=trust_context.valid_roster_ids,
            my_roster_id=1,
            team_name_to_roster=dict(trust_context.team_name_to_roster),
            league_context_valid=True,
            untouchable_names=frozenset({"core wr"}),
        )
        raise AssertionError(board.diagnostics)
    assert len(enforced) == 1


def test_elite_target_progressively_surfaces_valid_three_asset_package():
    frame, summary, adapter = _elite_fixture()
    shape = {"mode": "balanced", "strategy": "balanced", "needs": [], "strengths": []}
    with (
        patch.object(trade_ideas, "_build_roster_pick_assets", return_value={1: [], 2: []}),
        patch.object(trade_ideas, "get_team_vs_league", return_value={"ok": True}),
        patch.object(trade_ideas, "_build_team_shape", return_value=shape),
        patch.object(trade_ideas, "_player_trade_fit", return_value=1),
        patch.object(trade_ideas, "_fit_priority", return_value=1),
        patch.object(trade_ideas, "_trade_fit_context", return_value={"score": 1, "partner_score": 1, "rationale": "Fits both teams."}),
        patch.object(trade_ideas, "_trade_reasoning_context", return_value={"score": 12, "summary": "Depth for elite value.", "tags": []}),
        patch.object(trade_ideas, "evaluate_trade_market_realism", return_value={"hard_fail": False, "score": 70, "summary": "Plausible wider market."}),
    ):
        result = trade_ideas.build_player_trade_hub_ideas(
            df_players=frame,
            league_id="L1",
            df_summary=summary,
            my_roster_id=1,
            role_map={f"mine-{idx}": "Core" for idx in range(1, 5)},
            untouchable_names=[],
            mode="target_player",
            selected_player_id="elite",
            max_ideas=5,
            adapter=adapter,
        )
    assert result["fallback_used"] is True
    assert any(len(idea["send_assets"]) == 3 for idea in result["ideas"])
    assert all(idea.get("hub_search_source") == "expanded" for idea in result["ideas"])
    assert result["diagnostics"]["expanded_soft_pool_added"] == 4


def test_impossible_elite_market_remains_honest_zero():
    frame, summary, adapter = _elite_fixture()
    shape = {"mode": "balanced", "strategy": "balanced", "needs": [], "strengths": []}
    with (
        patch.object(trade_ideas, "_build_roster_pick_assets", return_value={1: [], 2: []}),
        patch.object(trade_ideas, "get_team_vs_league", return_value={"ok": True}),
        patch.object(trade_ideas, "_build_team_shape", return_value=shape),
        patch.object(trade_ideas, "_player_trade_fit", return_value=1),
        patch.object(trade_ideas, "_fit_priority", return_value=1),
        patch.object(trade_ideas, "_trade_fit_context", return_value={"score": 1, "partner_score": 1, "rationale": ""}),
        patch.object(trade_ideas, "_trade_reasoning_context", return_value={"score": 12, "summary": "", "tags": []}),
        patch.object(trade_ideas, "evaluate_trade_market_realism", return_value={"hard_fail": True, "score": 0, "summary": ""}),
    ):
        result = trade_ideas.build_player_trade_hub_ideas(
            df_players=frame,
            league_id="L1",
            df_summary=summary,
            my_roster_id=1,
            role_map={f"mine-{idx}": "Core" for idx in range(1, 5)},
            untouchable_names=[],
            mode="target_player",
            selected_player_id="elite",
            max_ideas=5,
            adapter=adapter,
        )
    assert result["ideas"] == []


def test_route_body_and_text_ownership_contracts_are_production_scoped():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'st.container(key="application_route_body_slot")' in app_source
    assert 'slot=st.empty()' not in app_source
    assert 'data-dg-scroll-anchor="trade-hub-player-search"' in app_source
    css = trade_hub_ui.TRADE_SUMMARY_COMPONENT_CSS
    assert "text-overflow: clip" in css
    assert "word-break: normal" in css
