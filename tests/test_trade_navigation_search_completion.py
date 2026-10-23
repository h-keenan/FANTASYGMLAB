from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from modules import canonical_recommendation_narrative as crn
from modules import trade_hub_presentation
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
        {"player_id": "core-wr", "name": "Core WR", "position": "WR", "team": "MIN", "value_score": 6800, "age": 24, "player_tier": "Core Starter", "trust_enforcement": "pass", "trust_evidence_confidence": "high"},
        {"player_id": "starter-qb", "name": "Starter QB", "position": "QB", "team": "GB", "value_score": 5200, "age": 26, "player_tier": "Starter", "trust_enforcement": "pass", "trust_evidence_confidence": "high"},
        {"player_id": "young-wr", "name": "Young WR", "position": "WR", "team": "CAR", "value_score": 4100, "age": 23, "player_tier": "Starter", "trust_enforcement": "pass", "trust_evidence_confidence": "high"},
        {"player_id": "starter-te", "name": "Starter TE", "position": "TE", "team": "DAL", "value_score": 3300, "age": 25, "player_tier": "Starter", "trust_enforcement": "pass", "trust_evidence_confidence": "high"},
        {"player_id": "depth-rb", "name": "Depth RB", "position": "RB", "team": "CHI", "value_score": 2800, "age": 26, "player_tier": "Contributor", "trust_enforcement": "pass", "trust_evidence_confidence": "high"},
        {"player_id": "depth-wr", "name": "Depth WR", "position": "WR", "team": "NYG", "value_score": 2100, "age": 27, "player_tier": "Depth", "trust_enforcement": "pass", "trust_evidence_confidence": "high"},
        {"player_id": "partner-wr", "name": "Partner WR", "position": "WR", "team": "SEA", "value_score": 3600, "age": 25, "player_tier": "Starter", "trust_enforcement": "pass", "trust_evidence_confidence": "high"},
        {"player_id": "partner-qb", "name": "Partner QB", "position": "QB", "team": "NE", "value_score": 3000, "age": 27, "player_tier": "Contributor", "trust_enforcement": "pass", "trust_evidence_confidence": "high"},
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
