"""Production-shaped data path for player-centered Trade Hub search."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd

from modules import trade_ideas


def _shape(**overrides):
    payload = {
        "mode": "retool",
        "strategy": "retool",
        "needs": ["WR"],
        "surplus": ["TE"],
        "draft_capital_tier": "mid",
        "roster_at_limit": False,
    }
    payload.update(overrides)
    return payload


@contextmanager
def _pass_soft_gates():
    with ExitStack() as stack:
        stack.enter_context(patch.object(trade_ideas, "get_team_vs_league", return_value={"strategy": "retool"}))
        stack.enter_context(
            patch.object(
                trade_ideas,
                "_build_team_shape",
                return_value=_shape(),
            )
        )
        stack.enter_context(patch.object(trade_ideas, "_fit_priority", return_value=2))
        stack.enter_context(
            patch.object(
                trade_ideas,
                "_trade_fit_context",
                return_value={"score": 4, "partner_score": 6, "rationale": "Fits."},
            )
        )
        stack.enter_context(
            patch.object(
                trade_ideas,
                "_trade_reasoning_context",
                return_value={"score": 10, "summary": "Coherent.", "tags": ["Need-Based"]},
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


def _twelve_team_league():
    rows = [
        {
            "player_id": "loveland",
            "name": "Colston Loveland",
            "position": "TE",
            "team": "CHI",
            "dynasty_score": 7126,
            "value_score": 7126,
            "age": 22,
        }
    ]
    players_by_roster = {1: ["loveland"]}
    for roster_id in range(2, 13):
        pid = f"wr-{roster_id}"
        rows.append(
            {
                "player_id": pid,
                "name": f"Partner WR {roster_id}",
                "position": "WR",
                "team": "KC",
                "dynasty_score": 3900 + roster_id * 40,
                "value_score": 3900 + roster_id * 40,
                "age": 24,
            }
        )
        bench = f"rb-{roster_id}"
        rows.append(
            {
                "player_id": bench,
                "name": f"Bench RB {roster_id}",
                "position": "RB",
                "team": "NYG",
                "dynasty_score": 2100 + roster_id * 15,
                "value_score": 2100 + roster_id * 15,
                "age": 26,
            }
        )
        players_by_roster[roster_id] = [pid, bench]
    frame = pd.DataFrame(rows)
    summary = pd.DataFrame(
        [
            {"roster_id": roster_id, "team_name": f"Team {roster_id}", "mode": "retool", "total_score": 20000 - roster_id * 100}
            for roster_id in range(1, 13)
        ]
    )
    rosters = [
        {"roster_id": roster_id, "players": player_ids}
        for roster_id, player_ids in players_by_roster.items()
    ]
    traded = [
        {
            "season": 2027,
            "round": 1,
            "roster_id": 3,
            "owner_id": 2,
        }
    ]
    adapter = SimpleNamespace(
        get_rosters=lambda _league: rosters,
        get_league=lambda _league: {
            "season": 2027,
            "settings": {"draft_rounds": 4, "type": 2},
        },
        get_traded_picks=lambda _league: traded,
        normalize_roster=lambda raw: raw,
    )
    settings = {"league_format": "Dynasty"}
    draft_status = {
        "draft_year": 2026,
        "current_year_picks_active": False,
        "draft_completed": True,
    }
    return frame, summary, rosters, adapter, settings, draft_status, players_by_roster


def test_owned_future_first_survives_pick_preparation_and_hydration():
    frame, summary, rosters, adapter, settings, draft_status, _players = _twelve_team_league()
    built = trade_ideas._build_roster_pick_assets(
        "L1",
        rosters,
        summary,
        league_settings=settings,
        draft_status=draft_status,
        adapter=adapter,
    )
    team2 = built[2]
    assert team2
    moved = [
        pick
        for pick in team2
        if int(pick["round"]) == 1
        and int(pick["season"]) == 2027
        and int(pick["original_roster_id"]) == 3
        and int(pick["owner_roster_id"]) == 2
    ]
    assert moved, "traded 2027 1st must sit on current owner 2, not original 3"
    assert not any(
        int(pick["round"]) == 1
        and int(pick["season"]) == 2027
        and int(pick["original_roster_id"]) == 3
        for pick in built.get(3, [])
    )
    frozen = trade_ideas.freeze_player_search_pick_assets(built)
    thawed = trade_ideas.thaw_player_search_pick_assets(frozen)
    assert any(
        int(pick["round"]) == 1 and int(pick["owner_roster_id"]) == 2
        for pick in thawed[2]
    )
    listed = trade_ideas.list_draft_pick_assets(
        "L1", summary, league_settings=settings, draft_status=draft_status, adapter=adapter
    )
    thawed_list = trade_ideas.thaw_player_search_pick_assets(
        trade_ideas.freeze_player_search_pick_assets(listed)
    )
    assert any(
        int(pick["round"]) == 1 and int(pick["owner_roster_id"]) == 2
        for pick in thawed_list[2]
    )


def test_twelve_team_hydrated_search_finds_pick_balanced_package_for_7k_te():
    frame, summary, rosters, adapter, settings, draft_status, players = _twelve_team_league()
    built_picks = trade_ideas._build_roster_pick_assets(
        "L1",
        rosters,
        summary,
        league_settings=settings,
        draft_status=draft_status,
        adapter=adapter,
    )
    roster_map = {roster["roster_id"]: roster["players"] for roster in rosters}
    adapter.get_rosters = Mock(side_effect=AssertionError("rosters already hydrated"))
    adapter.get_league = Mock(side_effect=AssertionError("league already hydrated"))
    adapter.get_traded_picks = Mock(side_effect=AssertionError("picks already hydrated"))
    with _pass_soft_gates():
        result = trade_ideas.build_player_trade_hub_ideas(
            df_players=frame,
            league_id="L1",
            df_summary=summary,
            my_roster_id=1,
            role_map={"loveland": "Flex"},
            untouchable_names=[],
            mode="my_player",
            selected_player_id="loveland",
            max_ideas=6,
            score_field="dynasty_score",
            adapter=adapter,
            league_settings=settings,
            draft_status=draft_status,
            prefetched_roster_map=roster_map,
            prefetched_pick_assets=built_picks,
        )
    diag = result["diagnostics"]
    assert diag["focal_found"] == 1
    assert diag["focal_value"] == 7126
    assert diag["score_field_used"] == "dynasty_score"
    assert diag["league_teams"] == 12
    assert diag["eligible_partner_teams"] == 11
    assert diag["future_picks_visible"] > 0
    assert diag["pick_source"] == "hydrated_context"
    assert diag["roster_source"] == "hydrated_context"
    assert diag["player_plus_pick_candidates"] > 0
    assert diag.get("closest_player_plus_pick_delta") is not None
    assert result["ideas"], diag
    assert all(
        any(str(asset.get("player_id") or "") == "loveland" for asset in idea.get("send_assets") or [])
        for idea in result["ideas"]
    )
    assert all(
        str(asset.get("score_field") or "") == "dynasty_score"
        for idea in result["ideas"]
        for asset in (idea.get("send_assets") or []) + (idea.get("receive_assets") or [])
        if asset.get("asset_type") == "player"
    )


def test_all_partner_rosters_enter_before_value_filter():
    frame, summary, rosters, adapter, settings, draft_status, _players = _twelve_team_league()
    picks = trade_ideas._build_roster_pick_assets(
        "L1", rosters, summary, league_settings=settings, draft_status=draft_status, adapter=adapter
    )
    with _pass_soft_gates():
        result = trade_ideas.build_player_trade_hub_ideas(
            df_players=frame,
            league_id="L1",
            df_summary=summary,
            my_roster_id=1,
            role_map={"loveland": "Flex"},
            untouchable_names=[],
            mode="my_player",
            selected_player_id="loveland",
            score_field="dynasty_score",
            adapter=adapter,
            league_settings=settings,
            draft_status=draft_status,
            prefetched_roster_map={row["roster_id"]: row["players"] for row in rosters},
            prefetched_pick_assets=picks,
        )
    assert result["diagnostics"]["partners_skipped_empty_join"] == 0
    assert result["diagnostics"]["partner_teams_considered"] == 11


def test_true_impossible_league_still_empty():
    frame = pd.DataFrame(
        [
            {"player_id": "star", "name": "Star", "position": "TE", "team": "CHI", "dynasty_score": 7126, "age": 22},
            {"player_id": "crumb", "name": "Crumb", "position": "WR", "team": "TEN", "dynasty_score": 80, "age": 29},
        ]
    )
    summary = pd.DataFrame(
        [
            {"roster_id": 1, "team_name": "Mine", "mode": "retool", "total_score": 8000},
            {"roster_id": 2, "team_name": "Theirs", "mode": "retool", "total_score": 200},
        ]
    )
    adapter = SimpleNamespace(
        get_rosters=lambda _league: [
            {"roster_id": 1, "players": ["star"]},
            {"roster_id": 2, "players": ["crumb"]},
        ],
        get_league=lambda _league: {"season": 2026, "settings": {"draft_rounds": 4, "type": 0}},
        get_traded_picks=lambda _league: [],
        normalize_roster=lambda raw: raw,
    )
    with _pass_soft_gates():
        result = trade_ideas.build_player_trade_hub_ideas(
            df_players=frame,
            league_id="L1",
            df_summary=summary,
            my_roster_id=1,
            role_map={},
            untouchable_names=[],
            mode="my_player",
            selected_player_id="star",
            score_field="dynasty_score",
            adapter=adapter,
            league_settings={"league_format": "Redraft"},
            draft_status={"draft_year": 2026, "current_year_picks_active": False, "draft_completed": True},
        )
    assert result["ideas"] == []


def test_founder_report_omits_identifiers():
    report = trade_ideas.player_search_founder_report(
        {
            "ideas": [{}],
            "primary_count": 0,
            "expanded_count": 1,
            "exploratory_count": 0,
            "diagnostics": {
                "focal_value": 7126,
                "partner_teams_considered": 11,
                "closest_player_plus_pick_delta": -80,
                "pick_source": "hydrated_context",
            },
        }
    )
    blob = str(report)
    assert "7126" in blob
    assert "@" not in blob
    assert "token" not in blob.casefold()
    assert "league_id" not in blob.casefold()
