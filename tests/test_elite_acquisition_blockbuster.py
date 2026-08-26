"""Elite explicit-acquisition search must construct bounded blockbuster packages."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd

from modules import trade_ideas
from tests.test_trade_trust_and_player_headshots import ONE_QB_DYNASTY, pick, player, source


ROOT = Path(__file__).resolve().parents[1]


def _shape(**overrides):
    payload = {
        "mode": "retool",
        "strategy": "retool",
        "needs": ["WR"],
        "surplus": ["RB"],
        "draft_capital_tier": "mid",
        "roster_at_limit": False,
        "roster_over_limit": False,
    }
    payload.update(overrides)
    return payload


@contextmanager
def _search_gates():
    with ExitStack() as stack:
        stack.enter_context(patch.object(trade_ideas, "get_team_vs_league", return_value={"strategy": "retool"}))
        stack.enter_context(
            patch.object(
                trade_ideas,
                "_build_team_shape",
                side_effect=lambda *_args, **_kwargs: _shape(),
            )
        )
        stack.enter_context(patch.object(trade_ideas, "_fit_priority", return_value=2))
        stack.enter_context(
            patch.object(
                trade_ideas,
                "_trade_fit_context",
                return_value={"score": 4, "partner_score": 6, "rationale": "Fits both rosters.", "my_score": 2},
            )
        )
        stack.enter_context(
            patch.object(
                trade_ideas,
                "_trade_reasoning_context",
                return_value={"score": 10, "summary": "Coherent package.", "tags": ["Need-Based"]},
            )
        )
        stack.enter_context(patch.object(trade_ideas, "build_trade_ideas", return_value=[]))
        yield


def _player_row(player_id, name, position, score, *, team="DAL", age=26):
    return {
        "player_id": player_id,
        "name": name,
        "position": position,
        "team": team,
        "value_score": score,
        "dynasty_score": score,
        "age": age,
    }


def _owned_pick(label, score, round_num, season, roster_id):
    return {
        "asset_type": "pick",
        "label": label,
        "score": score,
        "season": season,
        "round": round_num,
        "original_roster_id": roster_id,
        "owner_roster_id": roster_id,
        "owner_team_name": "Mine" if roster_id == 1 else "Partner",
        "original_team_name": "Mine" if roster_id == 1 else "Partner",
    }


def _twelve_team_league(*, user_players, partner_players, user_picks, thin_user=False):
    rows = list(user_players) + list(partner_players)
    players_by_roster = {
        1: [row["player_id"] for row in user_players],
        2: [row["player_id"] for row in partner_players],
    }
    summary_rows = [
        {"roster_id": 1, "team_name": "Mine", "mode": "contend"},
        {"roster_id": 2, "team_name": "Partner", "mode": "retool"},
    ]
    pick_assets = {1: list(user_picks), 2: []}
    for roster_id in range(3, 13):
        pid = f"filler-{roster_id}"
        rows.append(_player_row(pid, f"Filler {roster_id}", "WR", 900, team="CHI", age=27))
        players_by_roster[roster_id] = [pid]
        summary_rows.append({"roster_id": roster_id, "team_name": f"Team {roster_id}", "mode": "retool"})
        pick_assets[roster_id] = []
    if thin_user:
        pass
    frame = pd.DataFrame(rows)
    summary = pd.DataFrame(summary_rows)
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
    draft_status = {"draft_year": 2026, "current_year_picks_active": False, "draft_completed": True}
    return frame, summary, rosters, adapter, draft_status, pick_assets


def _elite_positive_league():
    return _twelve_team_league(
        user_players=[
            _player_row("high-end-wr", "High-End WR", "WR", 4800, age=26),
            _player_row("depth-rb", "Depth RB", "RB", 1600, age=27),
        ],
        partner_players=[
            _player_row("elite-rb", "Elite RB", "RB", 11340, team="ATL", age=24),
            _player_row("partner-wr", "Partner WR", "WR", 3200, team="KC", age=25),
            _player_row("partner-te", "Partner TE", "TE", 2100, team="BAL", age=26),
        ],
        user_picks=[
            _owned_pick("2026 Round 1", 2400, 1, 2026, 1),
            _owned_pick("2027 Round 1", 2300, 1, 2027, 1),
            _owned_pick("2028 Round 1", 2200, 1, 2028, 1),
            _owned_pick("2027 Round 2", 1400, 2, 2027, 1),
            _owned_pick("2028 Round 2", 1300, 2, 2028, 1),
        ],
    )


def _insufficient_league():
    return _twelve_team_league(
        user_players=[
            _player_row("bench-wr", "Bench WR", "WR", 1100, age=28),
        ],
        partner_players=[
            _player_row("elite-rb", "Elite RB", "RB", 11340, team="ATL", age=24),
            _player_row("partner-wr", "Partner WR", "WR", 3200, team="KC", age=25),
        ],
        user_picks=[
            _owned_pick("2027 Round 3", 700, 3, 2027, 1),
        ],
    )


def test_no_player_specific_elite_exceptions_in_engine():
    ideas_src = source("modules/trade_ideas.py").casefold()
    for banned in ("bijan", "robinson", "superstar_ids", "elite_name"):
        assert banned not in ideas_src


def test_automatic_board_still_hard_fails_light_headline_for_cornerstone():
    send = [
        player("High-End WR", 4800, "WR", role="Flex", age=26),
        pick("2026 R1", 2400, 1, 2026),
        pick("2027 R1", 2300, 1, 2027),
        pick("2028 R1", 2200, 1, 2028),
    ]
    send[0]["player_id"] = "high-end-wr"
    receive = [player("Elite RB", 11340, "RB", age=24)]
    receive[0]["player_id"] = "elite-rb"
    board = trade_ideas.evaluate_trade_market_realism(
        send_assets=send,
        receive_assets=receive,
        my_shape=_shape(),
        partner_shape=_shape(needs=["WR"], surplus=["RB"]),
        partner_name="Partner",
        league_settings=ONE_QB_DYNASTY,
    )
    acquire = trade_ideas.evaluate_trade_market_realism(
        send_assets=send,
        receive_assets=receive,
        my_shape=_shape(),
        partner_shape=_shape(needs=["WR"], surplus=["RB"]),
        partner_name="Partner",
        league_settings=ONE_QB_DYNASTY,
        explicit_player_focus=True,
        focused_player_ids=["elite-rb"],
        explicit_acquisition_target=True,
    )
    assert board["hard_fail"] is True
    assert "best_asset_problem" in board["hard_fail_flags"] or "cornerstone_protection" in board["hard_fail_flags"]
    assert acquire["hard_fail"] is False
    automatic_call = source("modules/trade_ideas.py").split("lambda: evaluate_trade_market_realism(", 1)[1]
    automatic_call = automatic_call.split("),", 1)[0]
    assert "explicit_acquisition_target" not in automatic_call


def test_elite_target_search_returns_owned_blockbuster_package():
    frame, summary, rosters, adapter, draft_status, picks = _elite_positive_league()
    with _search_gates():
        result = trade_ideas.build_player_trade_hub_ideas(
            df_players=frame,
            league_id="L1",
            df_summary=summary,
            my_roster_id=1,
            role_map={"high-end-wr": "Flex", "depth-rb": "Bench"},
            untouchable_names=[],
            mode="target_player",
            selected_player_id="elite-rb",
            max_ideas=6,
            adapter=adapter,
            league_settings=ONE_QB_DYNASTY,
            draft_status=draft_status,
            prefetched_roster_map={row["roster_id"]: row["players"] for row in rosters},
            prefetched_pick_assets=picks,
        )
    diag = result["diagnostics"]
    assert result["ideas"], diag
    owned_player_ids = {"high-end-wr", "depth-rb"}
    owned_pick_labels = {pick["label"] for pick in picks[1]}
    for idea in result["ideas"]:
        receive_ids = {str(asset.get("player_id") or "") for asset in idea.get("receive_assets") or []}
        assert "elite-rb" in receive_ids
        assert all(
            str(asset.get("player_id") or "") in owned_player_ids
            for asset in idea.get("send_assets") or []
            if asset.get("asset_type") == "player"
        )
        assert all(
            str(asset.get("label") or "") in owned_pick_labels
            for asset in idea.get("send_assets") or []
            if asset.get("asset_type") == "pick"
        )
        send_score = trade_ideas._score_assets(idea.get("send_assets") or [])
        assert send_score >= 11340 - trade_ideas.BLOCKBUSTER_VALUE_HIGH
        assert len(idea.get("send_assets") or []) <= trade_ideas.BLOCKBUSTER_MAX_ASSETS
    smallest = min(len(idea.get("send_assets") or []) for idea in result["ideas"])
    assert smallest <= 4
    report = trade_ideas.player_search_founder_report(result)
    assert report["target_value"] == 11340
    assert report["blockbuster_mode_triggered"] is True
    assert report["visible_ideas"] >= 1
    assert report["empty_reason"] == ""
    assert adapter.get_rosters.call_count == 0
    assert diag["search_elapsed_ms"] < 2000
    assert "bijan" not in str(result).casefold()


def test_insufficient_assets_stay_empty():
    frame, summary, rosters, adapter, draft_status, picks = _insufficient_league()
    with _search_gates():
        result = trade_ideas.build_player_trade_hub_ideas(
            df_players=frame,
            league_id="L1",
            df_summary=summary,
            my_roster_id=1,
            role_map={"bench-wr": "Bench"},
            untouchable_names=[],
            mode="target_player",
            selected_player_id="elite-rb",
            max_ideas=6,
            adapter=adapter,
            league_settings=ONE_QB_DYNASTY,
            draft_status=draft_status,
            prefetched_roster_map={row["roster_id"]: row["players"] for row in rosters},
            prefetched_pick_assets=picks,
        )
    assert result["ideas"] == []
    diag = result["diagnostics"]
    report = trade_ideas.player_search_founder_report(result)
    assert report["empty_reason"] == "insufficient_owned_value"
    assert diag["normal_package_max_value"] < 11340 - trade_ideas.BLOCKBUSTER_VALUE_HIGH
    assert adapter.get_rosters.call_count == 0
