"""Player-centered search coverage without lowering realism gates."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from modules import trade_ideas


def _shape(**overrides):
    payload = {
        "mode": "retool",
        "strategy": "retool",
        "needs": ["WR"],
        "surplus": ["RB"],
        "draft_capital_tier": "mid",
        "roster_at_limit": False,
    }
    payload.update(overrides)
    return payload


def _adapter(rosters):
    return SimpleNamespace(get_rosters=lambda _league: rosters)


@contextmanager
def _pass_gates():
    with ExitStack() as stack:
        stack.enter_context(patch.object(trade_ideas, "get_team_vs_league", return_value={"strategy": "retool"}))
        stack.enter_context(
            patch.object(
                trade_ideas,
                "_build_team_shape",
                side_effect=lambda _summary, roster_id, *_args, **_kwargs: (
                    _shape(needs=["RB"], surplus=["WR"]) if roster_id == 1 else _shape()
                ),
            )
        )
        stack.enter_context(patch.object(trade_ideas, "_fit_priority", return_value=2))
        stack.enter_context(
            patch.object(
                trade_ideas,
                "_trade_fit_context",
                return_value={"score": 4, "partner_score": 6, "rationale": "Fits both rosters."},
            )
        )
        stack.enter_context(
            patch.object(
                trade_ideas,
                "_trade_reasoning_context",
                return_value={"score": 10, "summary": "Coherent package.", "tags": ["Need-Based"]},
            )
        )
        stack.enter_context(
            patch.object(
                trade_ideas,
                "evaluate_trade_market_realism",
                return_value={"hard_fail": False, "score": 70, "summary": "Plausible."},
            )
        )
        stack.enter_context(patch.object(trade_ideas, "_is_core_or_protected_starter", return_value=False))
        stack.enter_context(patch.object(trade_ideas, "build_trade_ideas", return_value=[]))
        yield


def test_mid_tier_player_plus_pick_is_found_when_one_for_one_misses_value():
    frame = pd.DataFrame(
        [
            {"player_id": "bench-rb", "name": "Bench RB", "position": "RB", "team": "CHI", "value_score": 2100, "age": 26},
            {"player_id": "mid-wr", "name": "Mid WR", "position": "WR", "team": "KC", "value_score": 4300, "age": 24},
        ]
    )
    summary = pd.DataFrame(
        [
            {"roster_id": 1, "team_name": "Mine", "mode": "retool"},
            {"roster_id": 2, "team_name": "Theirs", "mode": "retool"},
        ]
    )
    picks = {
        1: [
            {
                "asset_type": "pick",
                "label": "2027 Round 2",
                "season": 2027,
                "round": 2,
                "score": 2200,
                "original_roster_id": 1,
                "owner_roster_id": 1,
            }
        ],
        2: [],
    }
    adapter = _adapter(
        [
            {"roster_id": 1, "players": ["bench-rb"]},
            {"roster_id": 2, "players": ["mid-wr"]},
        ]
    )
    with (
        patch.object(trade_ideas, "_build_roster_pick_assets", return_value=picks),
        _pass_gates(),
    ):
        result = trade_ideas.build_player_trade_hub_ideas(
            df_players=frame,
            league_id="L1",
            df_summary=summary,
            my_roster_id=1,
            role_map={"bench-rb": "Bench"},
            untouchable_names=[],
            mode="my_player",
            selected_player_id="bench-rb",
            max_ideas=6,
            adapter=adapter,
        )
    assert result["ideas"], result["diagnostics"]
    assert all(
        any(str(asset.get("player_id") or "") == "bench-rb" for asset in idea.get("send_assets") or [])
        for idea in result["ideas"]
    )
    assert any(
        any(asset.get("asset_type") == "pick" for asset in idea.get("send_assets") or [])
        for idea in result["ideas"]
    )
    assert result["diagnostics"].get("no_value_match", 0) > 0


def test_two_for_one_send_is_constructed_for_star_return():
    frame = pd.DataFrame(
        [
            {"player_id": "starter", "name": "Starter", "position": "WR", "team": "DAL", "value_score": 3600, "age": 25},
            {"player_id": "depth", "name": "Depth", "position": "RB", "team": "NYG", "value_score": 2400, "age": 26},
            {"player_id": "star", "name": "Star", "position": "WR", "team": "SF", "value_score": 7200, "age": 24},
        ]
    )
    summary = pd.DataFrame(
        [
            {"roster_id": 1, "team_name": "Mine", "mode": "retool"},
            {"roster_id": 2, "team_name": "Theirs", "mode": "retool"},
        ]
    )
    adapter = _adapter(
        [
            {"roster_id": 1, "players": ["starter", "depth"]},
            {"roster_id": 2, "players": ["star"]},
        ]
    )
    with (
        patch.object(trade_ideas, "_build_roster_pick_assets", return_value={1: [], 2: []}),
        _pass_gates(),
    ):
        result = trade_ideas.build_player_trade_hub_ideas(
            df_players=frame,
            league_id="L1",
            df_summary=summary,
            my_roster_id=1,
            role_map={"starter": "Flex", "depth": "Bench"},
            untouchable_names=[],
            mode="my_player",
            selected_player_id="starter",
            max_ideas=6,
            adapter=adapter,
        )
    assert result["ideas"]
    assert any(len(idea.get("send_assets") or []) >= 2 for idea in result["ideas"])
    assert all(
        any(str(asset.get("player_id") or "") == "starter" for asset in idea.get("send_assets") or [])
        for idea in result["ideas"]
    )


def test_constrained_market_stays_empty_when_realism_hard_fails():
    frame = pd.DataFrame(
        [
            {"player_id": "vet", "name": "Aging Vet", "position": "RB", "team": "TEN", "value_score": 1800, "age": 32},
            {"player_id": "other", "name": "Other", "position": "WR", "team": "MIA", "value_score": 1900, "age": 24},
        ]
    )
    summary = pd.DataFrame(
        [
            {"roster_id": 1, "team_name": "Mine", "mode": "retool"},
            {"roster_id": 2, "team_name": "Theirs", "mode": "retool"},
        ]
    )
    adapter = _adapter(
        [
            {"roster_id": 1, "players": ["vet"]},
            {"roster_id": 2, "players": ["other"]},
        ]
    )
    with (
        patch.object(trade_ideas, "_build_roster_pick_assets", return_value={1: [], 2: []}),
        patch.object(trade_ideas, "get_team_vs_league", return_value={"strategy": "retool"}),
        patch.object(trade_ideas, "_build_team_shape", return_value=_shape()),
        patch.object(trade_ideas, "_fit_priority", return_value=2),
        patch.object(
            trade_ideas,
            "_trade_fit_context",
            return_value={"score": 4, "partner_score": 6, "rationale": ""},
        ),
        patch.object(
            trade_ideas,
            "_trade_reasoning_context",
            return_value={"score": 10, "summary": "", "tags": []},
        ),
        patch.object(
            trade_ideas,
            "evaluate_trade_market_realism",
            return_value={"hard_fail": True, "score": 0, "summary": ""},
        ),
        patch.object(trade_ideas, "build_trade_ideas", return_value=[]),
    ):
        result = trade_ideas.build_player_trade_hub_ideas(
            df_players=frame,
            league_id="L1",
            df_summary=summary,
            my_roster_id=1,
            role_map={},
            untouchable_names=[],
            mode="my_player",
            selected_player_id="vet",
            max_ideas=6,
            adapter=adapter,
        )
    assert result["ideas"] == []


def test_target_search_never_returns_unrelated_board_ideas():
    frame = pd.DataFrame(
        [
            {"player_id": "mine", "name": "Mine", "position": "WR", "team": "DAL", "value_score": 4000, "age": 25},
            {"player_id": "target", "name": "Target", "position": "RB", "team": "DET", "value_score": 4100, "age": 24},
        ]
    )
    summary = pd.DataFrame(
        [
            {"roster_id": 1, "team_name": "Mine", "mode": "retool"},
            {"roster_id": 2, "team_name": "Theirs", "mode": "retool"},
        ]
    )
    adapter = _adapter(
        [
            {"roster_id": 1, "players": ["mine"]},
            {"roster_id": 2, "players": ["target"]},
        ]
    )
    with (
        patch.object(trade_ideas, "_build_roster_pick_assets", return_value={1: [], 2: []}),
        _pass_gates(),
    ):
        result = trade_ideas.build_player_trade_hub_ideas(
            df_players=frame,
            league_id="L1",
            df_summary=summary,
            my_roster_id=1,
            role_map={"mine": "Flex"},
            untouchable_names=[],
            mode="target_player",
            selected_player_id="target",
            max_ideas=6,
            adapter=adapter,
        )
    assert result["ideas"]
    assert all(
        any(str(asset.get("player_id") or "") == "target" for asset in idea.get("receive_assets") or [])
        for idea in result["ideas"]
    )


def test_valuation_lens_is_score_field_not_a_second_search_engine():
    app = (__import__("pathlib").Path(__file__).resolve().parents[1] / "app.py").read_text(
        encoding="utf-8"
    )
    ideas = (__import__("pathlib").Path(__file__).resolve().parents[1] / "modules" / "trade_ideas.py").read_text(
        encoding="utf-8"
    )
    ui = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "modules"
        / "valuation_archetype_ui.py"
    ).read_text(encoding="utf-8")
    assert "score_field=score_field" in app.split("def cached_trade_ideas", 1)[1][:2500] or "score_field=" in ideas
    assert "not a second" in ui.casefold()
    assert "Evaluate using" in app
