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
    assert "Evaluation" in app
    assert "not a second" in ui.casefold()


def test_skattebo_class_player_plus_pick_survives_neutral_partner_fit():
    frame = pd.DataFrame(
        [
            {
                "player_id": "skattebo",
                "name": "Cam Skattebo",
                "position": "RB",
                "team": "NYG",
                "value_score": 6332,
                "age": 23,
            },
            {
                "player_id": "mid-wr",
                "name": "Mid WR",
                "position": "WR",
                "team": "KC",
                "value_score": 4100,
                "age": 24,
            },
        ]
    )
    summary = pd.DataFrame(
        [
            {"roster_id": 1, "team_name": "Mine", "mode": "retool"},
            {"roster_id": 2, "team_name": "Theirs", "mode": "retool"},
        ]
    )
    picks = {
        1: [],
        2: [
            {
                "asset_type": "pick",
                "label": "2027 Round 1",
                "season": 2027,
                "round": 1,
                "score": 2400,
                "original_roster_id": 2,
                "owner_roster_id": 2,
            }
        ],
    }
    adapter = _adapter(
        [
            {"roster_id": 1, "players": ["skattebo"]},
            {"roster_id": 2, "players": ["mid-wr"]},
        ]
    )
    with (
        patch.object(trade_ideas, "_build_roster_pick_assets", return_value=picks),
        patch.object(trade_ideas, "get_team_vs_league", return_value={"strategy": "retool"}),
        patch.object(
            trade_ideas,
            "_build_team_shape",
            side_effect=lambda _summary, roster_id, *_args, **_kwargs: (
                _shape(needs=["WR"], surplus=["RB"]) if roster_id == 1 else _shape()
            ),
        ),
        patch.object(trade_ideas, "_fit_priority", return_value=2),
        patch.object(
            trade_ideas,
            "_trade_fit_context",
            return_value={"score": 1, "partner_score": 0, "rationale": "Neutral partner metadata."},
        ),
        patch.object(
            trade_ideas,
            "_trade_reasoning_context",
            return_value={"score": 10, "summary": "Coherent package.", "tags": ["Need-Based"]},
        ),
        patch.object(
            trade_ideas,
            "evaluate_trade_market_realism",
            return_value={"hard_fail": False, "score": 70, "summary": "Plausible."},
        ),
        patch.object(trade_ideas, "_is_core_or_protected_starter", return_value=False),
        patch.object(trade_ideas, "build_trade_ideas", return_value=[]),
    ):
        result = trade_ideas.build_player_trade_hub_ideas(
            df_players=frame,
            league_id="L1",
            df_summary=summary,
            my_roster_id=1,
            role_map={"skattebo": "Flex"},
            untouchable_names=[],
            mode="my_player",
            selected_player_id="skattebo",
            max_ideas=6,
            adapter=adapter,
        )
    assert result["ideas"], result["diagnostics"]
    assert all(
        any(str(asset.get("player_id") or "") == "skattebo" for asset in idea.get("send_assets") or [])
        for idea in result["ideas"]
    )
    assert any(
        any(asset.get("asset_type") == "pick" for asset in idea.get("receive_assets") or [])
        for idea in result["ideas"]
    )
    funnel = result["diagnostics"]
    assert funnel.get("partner_teams_considered", 0) >= 1
    assert funnel.get("raw_packages_constructed", 0) >= 1
    assert funnel.get("packages_containing_focal", 0) >= 1
    assert funnel.get("no_value_match", 0) > 0


def test_your_player_results_always_send_focal_player():
    frame = pd.DataFrame(
        [
            {"player_id": "mine", "name": "Mine", "position": "RB", "team": "NYG", "value_score": 4000, "age": 24},
            {"player_id": "theirs", "name": "Theirs", "position": "WR", "team": "DAL", "value_score": 4100, "age": 25},
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
            {"roster_id": 2, "players": ["theirs"]},
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
            mode="my_player",
            selected_player_id="mine",
            max_ideas=6,
            adapter=adapter,
        )
    assert result["ideas"]
    assert all(
        any(str(asset.get("player_id") or "") == "mine" for asset in idea.get("send_assets") or [])
        for idea in result["ideas"]
    )


def test_exploratory_low_confidence_when_partner_fit_is_hostile_but_value_holds():
    frame = pd.DataFrame(
        [
            {"player_id": "mine", "name": "Mine", "position": "RB", "team": "NYG", "value_score": 4000, "age": 24},
            {"player_id": "theirs", "name": "Theirs", "position": "WR", "team": "DAL", "value_score": 4050, "age": 25},
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
            {"roster_id": 2, "players": ["theirs"]},
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
            return_value={"score": -1, "partner_score": -80, "rationale": ""},
        ),
        patch.object(
            trade_ideas,
            "_trade_reasoning_context",
            return_value={"score": 10, "summary": "Value coherent.", "tags": []},
        ),
        patch.object(
            trade_ideas,
            "evaluate_trade_market_realism",
            return_value={"hard_fail": False, "score": 70, "summary": "Plausible."},
        ),
        patch.object(trade_ideas, "_is_core_or_protected_starter", return_value=False),
        patch.object(trade_ideas, "build_trade_ideas", return_value=[]),
    ):
        result = trade_ideas.build_player_trade_hub_ideas(
            df_players=frame,
            league_id="L1",
            df_summary=summary,
            my_roster_id=1,
            role_map={"mine": "Flex"},
            untouchable_names=[],
            mode="my_player",
            selected_player_id="mine",
            max_ideas=6,
            adapter=adapter,
        )
    assert result["ideas"], result["diagnostics"]
    assert all(str(idea.get("hub_search_source") or "") == "exploratory" for idea in result["ideas"])
    assert all(str(idea.get("trade_confidence_label") or "") == "Low" for idea in result["ideas"])
    assert result["exploratory_count"] >= 1
    assert result["primary_count"] == 0


def test_true_empty_state_copy_has_no_numeric_thresholds():
    lead, reason = trade_ideas.player_search_empty_state_copy(
        {
            "ideas": [],
            "diagnostics": {"rejected_partner_fit": 9, "rejected_value_window": 2},
        }
    )
    assert "value-coherent package" in lead
    assert "don't own" in reason
    assert not any(char.isdigit() for char in reason)


def test_player_search_fallback_does_not_make_provider_calls():
    source = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "modules"
        / "trade_ideas.py"
    ).read_text(encoding="utf-8")
    fallback = source.split("def _build_my_player_fallback_ideas", 1)[1].split(
        "def build_player_trade_hub_ideas", 1
    )[0]
    assert "get_rosters(" not in fallback
    assert "get_league(" not in fallback
    assert "get_traded_picks(" not in fallback


def test_trade_setup_controls_are_compact():
    app = (__import__("pathlib").Path(__file__).resolve().parents[1] / "app.py").read_text(
        encoding="utf-8"
    )
    hub = app.split('if current_page == "trade_hub"', 1)[1].split("# TRADE ANALYZER", 1)[0]
    assert "trade_hub_setup" in hub
    assert "TRADE_SETUP_CAPTION" in hub
    assert 'label="Evaluation"' in hub
    assert "compact=True" in hub
