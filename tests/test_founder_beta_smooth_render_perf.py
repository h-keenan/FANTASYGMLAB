"""Founder Beta performance + coherent-render contracts (draft measurement pass)."""

from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from modules import game_plan_process_cache
from modules import notification_center as nc
from modules import prepared_player_frame
from modules import trade_ideas
from modules import warm_route_render as wrr


def test_team_shape_memo_hits_without_second_lineup(monkeypatch):
    trade_ideas.clear_team_shape_memos()
    roster = pd.DataFrame(
        [
            {
                "player_id": "qb1",
                "name": "QB",
                "position": "QB",
                "team": "CHI",
                "dynasty_score": 8000,
                "value_score": 8000,
                "age": 26,
                "status": "Active",
                "injury_status": "",
            },
            {
                "player_id": "wr1",
                "name": "WR",
                "position": "WR",
                "team": "CHI",
                "dynasty_score": 7000,
                "value_score": 7000,
                "age": 24,
                "status": "Active",
                "injury_status": "",
            },
        ]
    )
    summary = pd.DataFrame(
        [
            {
                "roster_id": 1,
                "team_name": "Mine",
                "mode": "retool",
                "strategy": "retool",
                "total_score": 15000,
                "avg_age": 25,
                "strengths": ["QB"],
                "weaknesses": ["TE"],
            }
        ]
    )
    calls = {"n": 0}
    real = trade_ideas.suggest_optimal_lineup

    def _count(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(trade_ideas, "suggest_optimal_lineup", _count)
    monkeypatch.setattr(
        trade_ideas,
        "get_team_vs_league",
        lambda *_args, **_kwargs: {
            "strategy": "retool",
            "mode": "retool",
            "strengths": ["QB"],
            "weaknesses": ["TE"],
            "avg_age": 25,
        },
    )
    first = trade_ideas._build_team_shape(summary, 1, roster, "dynasty_score", [], [1000], {})
    second = trade_ideas._build_team_shape(summary, 1, roster, "dynasty_score", [], [1000], {})
    assert calls["n"] == 1
    assert first["strategy"] == second["strategy"]
    assert trade_ideas.team_shape_store_size() == 1
    prepared_player_frame.clear_league_scoped_prepared_memos({"_x": 1})
    assert trade_ideas.team_shape_store_size() == 0


def test_explicit_find_inner_blocks_cover_build_children():
    source = inspect.getsource(trade_ideas.build_player_trade_hub_ideas)
    for name in (
        "player_search_frame_prepare",
        "player_search_pick_prepare",
        "player_search_roster_index",
        "player_search_team_shapes",
        "player_search_universe_prepare",
        "player_search_build",
        "build_player_injury_index(",
    ):
        assert name in source
    assert "_emit_team_shape_substages(" in source
    keys = trade_ideas.PLAYER_SEARCH_FOUNDER_KEYS
    for key in (
        "stage_ms_frame_normalize",
        "stage_ms_universe",
        "stage_ms_roster_index",
        "stage_ms_team_shape",
        "stage_ms_partner_prep",
        "stage_ms_construction",
        "stage_ms_market",
        "team_shape_hits",
        "team_shape_misses",
        "roster_index_calls",
        "session_cache_status",
        "streamlit_cache_data_absent",
    ):
        assert key in keys


def test_explicit_find_hot_path_children_and_team_shape_memo(monkeypatch):
    trade_ideas.clear_team_shape_memos()
    rows = []
    roster_map: dict[int, list[str]] = {}
    summary_rows = []
    for roster_id in (1, 2, 3):
        summary_rows.append(
            {
                "roster_id": roster_id,
                "team_name": f"Team {roster_id}",
                "mode": "retool",
                "strategy": "retool",
                "total_score": 15000,
                "avg_age": 25,
                "strengths": ["QB"],
                "weaknesses": ["TE"],
            }
        )
        ids = []
        for pos, pid in (("QB", f"qb{roster_id}"), ("WR", f"wr{roster_id}")):
            ids.append(pid)
            rows.append(
                {
                    "player_id": pid,
                    "name": pid.upper(),
                    "position": pos,
                    "team": "CHI",
                    "dynasty_score": 8000 if pos == "QB" else 7000,
                    "value_score": 8000 if pos == "QB" else 7000,
                    "age": 26,
                    "status": "Active",
                    "injury_status": "",
                }
            )
        roster_map[roster_id] = ids
    frame = pd.DataFrame(rows)
    frame.attrs["strategy_curve"] = "retool"
    frame.attrs["strategy_curve_field"] = "dynasty_score"
    summary = pd.DataFrame(summary_rows)
    picks = {roster_id: [] for roster_id in roster_map}
    monkeypatch.setattr(
        trade_ideas,
        "get_team_vs_league",
        lambda *_args, **_kwargs: {
            "strategy": "retool",
            "mode": "retool",
            "strengths": ["QB"],
            "weaknesses": ["TE"],
            "avg_age": 25,
        },
    )
    lineup_calls = {"n": 0}
    real_lineup = trade_ideas.suggest_optimal_lineup

    def _count_lineup(*args, **kwargs):
        lineup_calls["n"] += 1
        return real_lineup(*args, **kwargs)

    monkeypatch.setattr(trade_ideas, "suggest_optimal_lineup", _count_lineup)
    kwargs = dict(
        df_players=frame,
        league_id="L1",
        df_summary=summary,
        my_roster_id=1,
        role_map={"qb1": "Core", "wr1": "Flex"},
        untouchable_names=[],
        mode="my_player",
        selected_player_id="wr1",
        max_ideas=4,
        score_field="dynasty_score",
        prefetched_roster_map=roster_map,
        prefetched_pick_assets=picks,
        adapter=SimpleNamespace(get_rosters=lambda _league: []),
    )
    state: dict = {}
    wrr.begin_route(state, "trade_hub", reset=True)
    try:
        first = trade_ideas.build_player_trade_hub_ideas(hot_path_state=state, **kwargs)
        names = [row["block"] for row in wrr.recorded_blocks(state)]
        for name in (
            "player_search_frame_prepare",
            "player_search_pick_prepare",
            "player_search_roster_index",
            "player_search_team_shapes",
            "player_search_universe_prepare",
            "player_search_build",
        ):
            assert name in names
            assert all(row.get("exclusive") for row in wrr.recorded_blocks(state) if row["block"] == name)
        for name in (
            "player_search_team_shape_lineup",
            "player_search_team_shape_injury",
            "player_search_team_shape_needs",
            "player_search_team_shape_signature",
        ):
            assert name in names
            assert all(not row.get("exclusive") for row in wrr.recorded_blocks(state) if row["block"] == name)
        diag = first["diagnostics"]
        assert diag["draft_context_skipped"] == 1
        assert diag["roster_index_calls"] == 1
        assert diag["streamlit_cache_data_absent"] is True
        assert diag["strategy_curve"] == "retool"
        assert diag["team_shape_misses"] == 3
        assert diag["team_shape_hits"] >= 3
        first_lineups = lineup_calls["n"]
        assert first_lineups == 3
        second = trade_ideas.build_player_trade_hub_ideas(hot_path_state=state, **kwargs)
        assert second["diagnostics"]["team_shape_misses"] == 0
        assert second["diagnostics"]["team_shape_hits"] >= 6
        assert lineup_calls["n"] == first_lineups
        assert second["diagnostics"]["universe_scans"] >= 1
    finally:
        trade_ideas.clear_team_shape_memos()


def test_team_shape_slim_keeps_depth_fields_and_drops_payload_columns():
    assert "depth_chart_slot" in trade_ideas._TEAM_SHAPE_WORK_COLUMNS
    assert "projected_starter" in trade_ideas._TEAM_SHAPE_WORK_COLUMNS
    roster = pd.DataFrame(
        {
            "player_id": ["a", "b"],
            "position": ["RB", "WR"],
            "value_score": [40.0, 30.0],
            "depth_chart_slot": [1, 2],
            "projected_starter": [True, False],
            "news_blob": ["x" * 20, "y" * 20],
        }
    )
    slim = trade_ideas._slim_team_shape_frame(roster, "value_score")
    assert "news_blob" not in slim.columns
    assert list(slim["depth_chart_slot"]) == [1, 2]


def test_explicit_player_search_skips_automatic_board_rebuild():
    source = inspect.getsource(trade_ideas.build_player_trade_hub_ideas)
    assert "skipped_automatic_board" in source
    assert "build_trade_ideas(" not in source.split("if mode_key == \"my_player\":", 1)[1].split(
        "target_roster_id = _find_roster_id_for_player", 1
    )[0]
