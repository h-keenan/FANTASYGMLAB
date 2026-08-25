"""Player-search market_hard_fail false-rejection and subreason coverage."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd

from modules import trade_ideas
from tests.test_trade_trust_and_player_headshots import (
    ONE_QB_DYNASTY,
    neutral_shape,
    pick,
    player,
)

_safe_int = trade_ideas._safe_int
_safe_float = trade_ideas._safe_float


def _asset(player_id, score, position, **kwargs):
    payload = player(player_id, score, position, **kwargs)
    payload["player_id"] = player_id
    payload["label"] = player_id
    return payload


@contextmanager
def _search_without_market_mock():
    with ExitStack() as stack:
        stack.enter_context(patch.object(trade_ideas, "get_team_vs_league", return_value={"strategy": "retool"}))
        stack.enter_context(
            patch.object(
                trade_ideas,
                "_build_team_shape",
                return_value={
                    "mode": "retool",
                    "strategy": "retool",
                    "needs": ["WR"],
                    "surplus": ["TE"],
                    "draft_capital_tier": "mid",
                    "roster_at_limit": False,
                    "roster_over_limit": False,
                },
            )
        )
        stack.enter_context(patch.object(trade_ideas, "_fit_priority", return_value=2))
        stack.enter_context(
            patch.object(
                trade_ideas,
                "_trade_fit_context",
                return_value={"score": 4, "partner_score": 6, "rationale": "Fits.", "my_score": 2},
            )
        )
        stack.enter_context(
            patch.object(
                trade_ideas,
                "_trade_reasoning_context",
                return_value={"score": 10, "summary": "Coherent.", "tags": ["Need-Based"]},
            )
        )
        yield


def _near_even_league():
    rows = [
        {
            "player_id": "focal",
            "name": "Focal TE",
            "position": "TE",
            "team": "CHI",
            "dynasty_score": 9730,
            "value_score": 9730,
            "age": 23,
        },
        {
            "player_id": "peer",
            "name": "Peer WR",
            "position": "WR",
            "team": "KC",
            "dynasty_score": 9636,
            "value_score": 9636,
            "age": 24,
        },
        {
            "player_id": "depth",
            "name": "Depth RB",
            "position": "RB",
            "team": "NYG",
            "dynasty_score": 2100,
            "value_score": 2100,
            "age": 26,
        },
    ]
    for roster_id in range(3, 13):
        pid = f"wr-{roster_id}"
        rows.append(
            {
                "player_id": pid,
                "name": f"WR {roster_id}",
                "position": "WR",
                "team": "DAL",
                "dynasty_score": 3900 + roster_id * 20,
                "value_score": 3900 + roster_id * 20,
                "age": 25,
            }
        )
    frame = pd.DataFrame(rows)
    summary = pd.DataFrame(
        [
            {"roster_id": roster_id, "team_name": f"Team {roster_id}", "mode": "retool", "total_score": 18000}
            for roster_id in range(1, 13)
        ]
    )
    players_by_roster = {1: ["focal"], 2: ["peer", "depth"]}
    for roster_id in range(3, 13):
        players_by_roster[roster_id] = [f"wr-{roster_id}"]
    rosters = [
        {"roster_id": roster_id, "players": player_ids}
        for roster_id, player_ids in players_by_roster.items()
    ]
    adapter = SimpleNamespace(
        get_rosters=Mock(side_effect=AssertionError("hydrated search must not call get_rosters")),
        get_league=Mock(side_effect=AssertionError("hydrated search must not call get_league")),
        get_traded_picks=Mock(side_effect=AssertionError("hydrated search must not call get_traded_picks")),
        normalize_roster=lambda raw: raw,
    )
    settings = {"league_format": "Dynasty", "qb_format": "1QB"}
    draft_status = {"draft_year": 2026, "current_year_picks_active": False, "draft_completed": True}
    pick_assets = {
        2: [
            {
                "asset_type": "pick",
                "label": "2027 Round 1",
                "score": 80,
                "season": 2027,
                "round": 1,
                "original_roster_id": 2,
                "owner_roster_id": 2,
            }
        ]
    }
    for roster_id in range(1, 13):
        pick_assets.setdefault(roster_id, [])
        if roster_id != 2:
            pick_assets[roster_id].append(
                {
                    "asset_type": "pick",
                    "label": "2027 Round 2",
                    "score": 1500,
                    "season": 2027,
                    "round": 2,
                    "original_roster_id": roster_id,
                    "owner_roster_id": roster_id,
                }
            )
    return frame, summary, rosters, adapter, settings, draft_status, pick_assets


def test_automatic_board_hard_fails_even_protected_one_for_one():
    market = trade_ideas.evaluate_trade_market_realism(
        send_assets=[_asset("focal", 9730, "TE")],
        receive_assets=[_asset("peer", 9636, "WR")],
        my_shape=neutral_shape(),
        partner_shape=neutral_shape(),
        partner_name="Partner",
        league_settings=ONE_QB_DYNASTY,
    )
    assert market["hard_fail"] is True
    assert "protected_outgoing" in market["hard_fail_flags"]
    assert abs(int(market["value_delta"])) <= 100


def test_explicit_focus_allows_near_even_protected_one_for_one():
    market = trade_ideas.evaluate_trade_market_realism(
        send_assets=[_asset("focal", 9730, "TE")],
        receive_assets=[_asset("peer", 9636, "WR")],
        my_shape=neutral_shape(),
        partner_shape=neutral_shape(needs=["WR"]),
        partner_name="Partner",
        league_settings=ONE_QB_DYNASTY,
        explicit_player_focus=True,
        focused_player_ids=["focal"],
    )
    assert market["hard_fail"] is False
    assert "protected_outgoing" not in market["hard_fail_flags"]
    assert "need_leak" in market["flags"]
    assert "protected_outgoing_override" in market["flags"]


def test_explicit_focus_still_hard_fails_quality_dump():
    elite = _asset("focal", 9730, "TE")
    weak = _asset("bench", 4100, "WR")
    third = pick("2027 Round 3", 1400, 3)
    market = trade_ideas.evaluate_trade_market_realism(
        send_assets=[elite],
        receive_assets=[weak, third],
        my_shape=neutral_shape(),
        partner_shape=neutral_shape(),
        partner_name="Partner",
        league_settings=ONE_QB_DYNASTY,
        explicit_player_focus=True,
        focused_player_ids=["focal"],
    )
    assert market["hard_fail"] is True
    assert "asset_quality_downgrade" in market["hard_fail_flags"]
    assert "low_pick_quality_bridge" in market["hard_fail_flags"]


def test_explicit_focus_still_hard_fails_extra_protected_send():
    market = trade_ideas.evaluate_trade_market_realism(
        send_assets=[_asset("focal", 9730, "TE"), _asset("core2", 7000, "WR")],
        receive_assets=[_asset("peer", 9636, "RB")],
        my_shape=neutral_shape(),
        partner_shape=neutral_shape(),
        partner_name="Partner",
        league_settings=ONE_QB_DYNASTY,
        explicit_player_focus=True,
        focused_player_ids=["focal"],
    )
    assert market["hard_fail"] is True
    assert "protected_outgoing" in market["hard_fail_flags"]


def test_roster_limit_hard_fail_remains():
    market = trade_ideas.evaluate_trade_market_realism(
        send_assets=[_asset("focal", 2100, "WR")],
        receive_assets=[_asset("a", 1200, "RB"), _asset("b", 1100, "TE")],
        my_shape=neutral_shape(roster_over_limit=True),
        partner_shape=neutral_shape(),
        partner_name="Partner",
        explicit_player_focus=True,
        focused_player_ids=["focal"],
    )
    assert market["hard_fail"] is True
    assert "roster_limit_pressure" in market["hard_fail_flags"]


def test_hydrated_near_even_search_returns_packages_without_provider_calls():
    frame, summary, rosters, adapter, settings, draft_status, picks = _near_even_league()
    with _search_without_market_mock():
        result = trade_ideas.build_player_trade_hub_ideas(
            df_players=frame,
            league_id="L1",
            df_summary=summary,
            my_roster_id=1,
            role_map={"focal": "Flex"},
            untouchable_names=[],
            mode="my_player",
            selected_player_id="focal",
            max_ideas=6,
            score_field="dynasty_score",
            adapter=adapter,
            league_settings=settings,
            draft_status=draft_status,
            prefetched_roster_map={row["roster_id"]: row["players"] for row in rosters},
            prefetched_pick_assets=picks,
        )
    diag = result["diagnostics"]
    assert result["ideas"], diag
    assert diag["skipped_automatic_board"] == 1
    assert _safe_int(diag.get("market_hard_fail_protected_outgoing"), 0) == 0
    assert diag["search_elapsed_ms"] < 2000
    assert _safe_float(diag.get("stage_ms_market"), 0.0) > 0
    report = trade_ideas.player_search_founder_report(result)
    assert report["visible_ideas"] >= 1
    blob = str(report)
    assert "@" not in blob
    assert "token" not in blob.casefold()
    assert "league_id" not in blob.casefold()
    assert adapter.get_rosters.call_count == 0


def test_founder_report_includes_hard_fail_subreasons_and_shapes():
    diagnostics = trade_ideas._empty_player_search_funnel()
    trade_ideas._count_market_hard_fail(diagnostics, ["protected_outgoing", "need_leak"])
    trade_ideas._record_closest_rejected_packages(
        diagnostics,
        {
            "send_total": 9730,
            "receive_total": 9714,
            "delta": -16,
            "send_player_count": 1,
            "send_pick_count": 0,
            "receive_player_count": 1,
            "receive_pick_count": 1,
            "structure": "player_plus_pick",
            "stage": "market_hard_fail",
            "hard_fail_flags": ["protected_outgoing"],
            "market_score": 27,
            "fit_score": 0,
            "partner_fit_score": 0,
        },
    )
    report = trade_ideas.player_search_founder_report({"diagnostics": diagnostics, "ideas": []})
    assert report["market_hard_fail_total"] == 1
    assert report["market_hard_fail_protected_outgoing"] == 1
    assert report["market_hard_fail_need_leak"] == 1
    assert report["closest_rejected_packages"][0]["delta"] == -16
    assert "name" not in str(report["closest_rejected_packages"])


def test_main_board_candidate_has_same_market_inputs_as_player_search():
    send = [_asset("focal", 9730, "TE")]
    receive = [_asset("peer", 9636, "WR")]
    board = trade_ideas.evaluate_trade_market_realism(
        send_assets=send,
        receive_assets=receive,
        my_shape=neutral_shape(),
        partner_shape=neutral_shape(),
        partner_name="Partner",
        league_settings=ONE_QB_DYNASTY,
    )
    search = trade_ideas.evaluate_trade_market_realism(
        send_assets=send,
        receive_assets=receive,
        my_shape=neutral_shape(),
        partner_shape=neutral_shape(),
        partner_name="Partner",
        league_settings=ONE_QB_DYNASTY,
        explicit_player_focus=True,
        focused_player_ids=["focal"],
    )
    assert set(board) == set(search)
    assert isinstance(board["hard_fail_flags"], list)
    assert isinstance(search["hard_fail_flags"], list)
    assert board["hard_fail"] is True
    assert search["hard_fail"] is False
