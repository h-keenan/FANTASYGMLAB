"""Elite explicit-acquisition search must construct bounded blockbuster packages."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd

from modules import trade_ideas
from modules.trust_enforcement import enforce_player_record, enforce_trade_board
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
        "trust_enforcement": "pass",
        "trust_evidence_confidence": "high",
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
            _player_row("high-end-wr", "High-End WR", "WR", 7200, age=26),
            _player_row("depth-rb", "Depth RB", "RB", 1600, age=27),
        ],
        partner_players=[
            _player_row("elite-rb", "Elite RB", "RB", 11340, team="ATL", age=24),
            _player_row("partner-wr", "Partner WR", "WR", 3200, team="KC", age=25),
            _player_row("partner-te", "Partner TE", "TE", 2100, team="BAL", age=26),
        ],
        user_picks=[
            _owned_pick("2026 Round 1", 1450, 1, 2026, 1),
            _owned_pick("2027 Round 1", 1400, 1, 2027, 1),
            _owned_pick("2028 Round 1", 1350, 1, 2028, 1),
            _owned_pick("2027 Round 2", 1100, 2, 2027, 1),
            _owned_pick("2028 Round 2", 1000, 2, 2028, 1),
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
        player("High-End WR", 7200, "WR", role="Flex", age=26),
        pick("2026 R1", 1450, 1, 2026),
        pick("2027 R1", 1400, 1, 2027),
        pick("2028 R1", 1350, 1, 2028),
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


def _trust_context_for_league(frame, rosters):
    players = {str(row["player_id"]): row for _, row in frame.iterrows()}
    enforcement = {
        player_id: enforce_player_record(
            row,
            eligible=True,
            canonical_player_ids=frozenset(players),
        )
        for player_id, row in players.items()
    }
    ownership = {}
    for roster in rosters:
        roster_id = int(roster["roster_id"])
        for player_id in roster["players"]:
            ownership[str(player_id)] = roster_id
    team_name_to_roster = {"mine": 1, "partner": 2}
    for roster_id in range(3, 13):
        team_name_to_roster[f"team {roster_id}"] = roster_id
    return {
        "canonical_players": players,
        "player_enforcement": enforcement,
        "ownership_by_player": ownership,
        "valid_roster_ids": frozenset(range(1, 13)),
        "my_roster_id": 1,
        "team_name_to_roster": team_name_to_roster,
        "league_context_valid": True,
        "untouchable_names": frozenset(),
    }


def test_elite_acquisition_survives_rendered_search_trust():
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
    raw = list(result["ideas"] or [])
    assert raw
    assert result["diagnostics"]["blockbuster_mode_triggered"] is True
    assert any(bool(asset.get("is_protected")) for idea in raw for asset in idea.get("send_assets") or [])
    untagged = [{**idea, "hub_mode": ""} for idea in raw]
    automatic = enforce_trade_board(untagged, **_trust_context_for_league(frame, rosters))
    assert automatic.blocked_count == len(untagged)
    assert "protected_constraint" in dict(automatic.blocked_reason_counts)

    visible = enforce_trade_board(
        raw,
        **{
            **_trust_context_for_league(frame, rosters),
            "explicit_acquisition_target": True,
        },
    )
    diagnostics = dict(result["diagnostics"] or {})
    trade_ideas.record_player_search_trust_funnel(
        diagnostics,
        raw_ideas=raw,
        enforced_ideas=list(visible.recommendations),
        blocked_reason_counts=dict(visible.blocked_reason_counts),
        trust_elapsed_ms=1.0,
    )
    from modules import trade_hub_ui

    presentation = trade_hub_ui.present_player_search_ideas(list(visible.recommendations))
    lead, _reason = trade_ideas.player_search_empty_state_copy(
        {"ideas": list(visible.recommendations), "diagnostics": diagnostics}
    )
    assert visible.blocked_count == 0
    assert len(visible.recommendations) >= 1
    assert diagnostics["candidates_before_trust"] >= 1
    assert diagnostics["candidates_after_trust"] >= 1
    assert diagnostics["expanded_count_visible"] >= 1
    assert presentation["show_empty"] is False
    assert lead == ""
    assert any(
        str(asset.get("player_id") or "") == "elite-rb"
        for idea in visible.recommendations
        for asset in idea.get("receive_assets") or []
    )
    assert adapter.get_rosters.call_count == 0


def test_explicit_acquisition_still_blocks_untouchables_and_unowned_assets():
    send = [
        {**player("High-End WR", 7200, "WR"), "player_id": "high-end-wr", "is_protected": True, "label": "High-End WR"},
        pick("2026 R1", 1450, 1, 2026),
    ]
    send[1]["owner_roster_id"] = 1
    send[1]["original_roster_id"] = 1
    receive = [{**player("Elite RB", 11340, "RB"), "player_id": "elite-rb"}]
    idea = {
        "send_assets": send,
        "receive_assets": receive,
        "partner_team_name": "Partner",
        "partner_roster_id": 2,
        "hub_mode": "target_player",
        "trade_confidence_label": "Low",
    }
    players = {
        "high-end-wr": {
            "player_id": "high-end-wr",
            "name": "High-End WR",
            "position": "WR",
            "team": "DAL",
            "active": True,
            "status": "Active",
            "fantasy_positions": ["WR"],
            "sport": "nfl",
        },
        "elite-rb": {
            "player_id": "elite-rb",
            "name": "Elite RB",
            "position": "RB",
            "team": "ATL",
            "active": True,
            "status": "Active",
            "fantasy_positions": ["RB"],
            "sport": "nfl",
        },
    }
    enforcement = {
        player_id: enforce_player_record(row, eligible=True, canonical_player_ids=frozenset(players))
        for player_id, row in players.items()
    }
    context = {
        "canonical_players": players,
        "player_enforcement": enforcement,
        "ownership_by_player": {"high-end-wr": 1, "elite-rb": 2},
        "valid_roster_ids": frozenset({1, 2}),
        "my_roster_id": 1,
        "team_name_to_roster": {"partner": 2},
        "league_context_valid": True,
        "explicit_acquisition_target": True,
    }
    blocked = enforce_trade_board(
        [idea],
        **{**context, "untouchable_names": frozenset({"high-end wr"})},
    )
    assert blocked.blocked_count == 1
    assert "protected_constraint" in dict(blocked.blocked_reason_counts)
    unowned = dict(idea)
    unowned["send_assets"] = [
        {**player("Other WR", 7200, "WR"), "player_id": "other-wr", "is_protected": True}
    ]
    players["other-wr"] = {**players["high-end-wr"], "player_id": "other-wr"}
    enforcement["other-wr"] = enforce_player_record(
        players["other-wr"], eligible=True, canonical_player_ids=frozenset(players)
    )
    stolen = enforce_trade_board(
        [unowned],
        **{
            **context,
            "canonical_players": players,
            "player_enforcement": enforcement,
            "untouchable_names": frozenset(),
        },
    )
    assert stolen.blocked_count == 1
    assert "ownership_conflict" in dict(stolen.blocked_reason_counts)


SUPERFLEX_DYNASTY = {
    "league_format": "Dynasty",
    "qb_format": "Superflex",
    "league_size": 12,
    "qb_count": 1,
    "superflex_count": 1,
    "rb_count": 2,
    "wr_count": 3,
    "te_count": 1,
}


def _format_economics_league():
    return _twelve_team_league(
        user_players=[
            _player_row("elite-qb", "Elite QB", "QB", 9800, age=27),
            _player_row("star-wr", "Star WR", "WR", 7200, age=26),
            _player_row("depth-rb", "Depth RB", "RB", 1600, age=27),
        ],
        partner_players=[
            _player_row("elite-rb", "Elite RB", "RB", 11340, team="ATL", age=24),
            _player_row("partner-wr", "Partner WR", "WR", 3200, team="KC", age=25),
            _player_row("partner-te", "Partner TE", "TE", 2100, team="BAL", age=26),
        ],
        user_picks=[
            _owned_pick("2026 Round 1", 2300, 1, 2026, 1),
            _owned_pick("2027 Round 1", 2200, 1, 2027, 1),
            _owned_pick("2028 Round 1", 2100, 1, 2028, 1),
            _owned_pick("2027 Round 2", 1100, 2, 2027, 1),
            _owned_pick("2028 Round 2", 1000, 2, 2028, 1),
        ],
    )


def _consolidation_league():
    return _twelve_team_league(
        user_players=[
            _player_row("star-wr", "Star WR", "WR", 7200, age=26),
            _player_row("depth-one", "Depth One", "WR", 2400, age=28),
            _player_row("depth-two", "Depth Two", "RB", 2200, age=27),
            _player_row("depth-three", "Depth Three", "WR", 1800, age=29),
        ],
        partner_players=[
            _player_row("elite-rb", "Elite RB", "RB", 11340, team="ATL", age=24),
            _player_row("partner-wr", "Partner WR", "WR", 3200, team="KC", age=25),
        ],
        user_picks=[
            _owned_pick("2026 Round 1", 1450, 1, 2026, 1),
            _owned_pick("2027 Round 1", 1400, 1, 2027, 1),
            _owned_pick("2028 Round 1", 1350, 1, 2028, 1),
            _owned_pick("2027 Round 2", 1100, 2, 2027, 1),
            _owned_pick("2028 Round 2", 1000, 2, 2028, 1),
        ],
    )


def _difficult_league():
    return _twelve_team_league(
        user_players=[
            _player_row("mid-wr", "Mid WR", "WR", 6400, age=27),
            _player_row("depth-rb", "Depth RB", "RB", 1600, age=28),
        ],
        partner_players=[
            _player_row("elite-rb", "Elite RB", "RB", 11340, team="ATL", age=24),
            _player_row("partner-wr", "Partner WR", "WR", 3200, team="KC", age=25),
        ],
        user_picks=[
            _owned_pick("2026 Round 1", 1450, 1, 2026, 1),
            _owned_pick("2027 Round 1", 1400, 1, 2027, 1),
            _owned_pick("2028 Round 1", 1350, 1, 2028, 1),
            _owned_pick("2027 Round 2", 1000, 2, 2027, 1),
        ],
    )


def _run_target_search(league, settings, role_map):
    frame, summary, rosters, adapter, draft_status, picks = league
    with _search_gates():
        result = trade_ideas.build_player_trade_hub_ideas(
            df_players=frame,
            league_id="L1",
            df_summary=summary,
            my_roster_id=1,
            role_map=role_map,
            untouchable_names=[],
            mode="target_player",
            selected_player_id="elite-rb",
            max_ideas=6,
            adapter=adapter,
            league_settings=settings,
            draft_status=draft_status,
            prefetched_roster_map={row["roster_id"]: row["players"] for row in rosters},
            prefetched_pick_assets=picks,
        )
    return result, adapter


def _send_headliner(idea):
    players = [
        asset
        for asset in idea.get("send_assets") or []
        if str(asset.get("asset_type") or "") == "player"
    ]
    if not players:
        return None
    return max(players, key=lambda asset: int(asset.get("score") or 0))


def test_production_shaped_fixture_is_one_qb_dynasty():
    assert ONE_QB_DYNASTY["qb_format"] == "1QB"
    assert ONE_QB_DYNASTY["league_size"] == 12
    assert int(ONE_QB_DYNASTY.get("qb_count") or 0) == 1
    assert int(ONE_QB_DYNASTY.get("superflex_count") or 0) == 0
    result, _adapter = _run_target_search(
        _elite_positive_league(),
        ONE_QB_DYNASTY,
        {"high-end-wr": "Flex", "depth-rb": "Bench"},
    )
    report = trade_ideas.player_search_founder_report(result)
    assert report["league_format"] == "1QB"
    assert report["ranking_explain"]


def test_superflex_elite_qb_for_rb_hard_fails_automatic_but_not_explicit():
    send = [
        player("Elite QB", 9800, "QB", role="Core", tier="Star", age=27),
        pick("2027 R1", 2300, 1, 2027),
    ]
    send[0]["player_id"] = "elite-qb"
    receive = [player("Elite RB", 11340, "RB", age=24)]
    receive[0]["player_id"] = "elite-rb"
    automatic = trade_ideas.evaluate_trade_market_realism(
        send_assets=send,
        receive_assets=receive,
        my_shape=_shape(),
        partner_shape=_shape(needs=["WR"], surplus=["RB"]),
        partner_name="Partner",
        league_settings=SUPERFLEX_DYNASTY,
    )
    explicit = trade_ideas.evaluate_trade_market_realism(
        send_assets=send,
        receive_assets=receive,
        my_shape=_shape(),
        partner_shape=_shape(needs=["WR"], surplus=["RB"]),
        partner_name="Partner",
        league_settings=SUPERFLEX_DYNASTY,
        explicit_player_focus=True,
        focused_player_ids=["elite-rb"],
        explicit_acquisition_target=True,
    )
    one_qb = trade_ideas.evaluate_trade_market_realism(
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
    assert automatic["hard_fail"] is True
    assert "superflex_qb_scarcity" in automatic["hard_fail_flags"]
    assert explicit["hard_fail"] is False
    assert "superflex_qb_scarcity" in explicit["flags"]
    assert explicit["positional_market_adjustment"] == -26
    assert one_qb["positional_market_adjustment"] == -6
    assert "superflex_qb_scarcity" not in one_qb["flags"]
    assert explicit["consolidation_premium_required"] > 0


def test_superflex_search_does_not_rank_elite_qb_overpay_first():
    result, adapter = _run_target_search(
        _format_economics_league(),
        SUPERFLEX_DYNASTY,
        {"elite-qb": "Flex", "star-wr": "Flex", "depth-rb": "Bench"},
    )
    assert result["ideas"], result["diagnostics"]
    top = result["ideas"][0]
    headliner = _send_headliner(top)
    assert headliner is not None
    assert str(headliner.get("position") or "").upper() != "QB"
    qb_ideas = [
        idea
        for idea in result["ideas"]
        if any(str(asset.get("player_id") or "") == "elite-qb" for asset in idea.get("send_assets") or [])
    ]
    wr_capital = [
        idea
        for idea in result["ideas"]
        if any(str(asset.get("player_id") or "") == "star-wr" for asset in idea.get("send_assets") or [])
        and any(int(asset.get("round") or 99) == 1 for asset in idea.get("send_assets") or [])
    ]
    assert wr_capital
    if qb_ideas:
        assert int(wr_capital[0]["acquisition_quality_score"]) > int(qb_ideas[0]["acquisition_quality_score"])
        assert str(qb_ideas[0].get("hub_search_source") or "") == "exploratory"
        assert "Harder" in str(qb_ideas[0].get("hub_path") or "")
        assert str(qb_ideas[0].get("trade_confidence_label") or "") == "Low"
    report = trade_ideas.player_search_founder_report(result)
    assert report["league_format"] == "Superflex"
    assert adapter.get_rosters.call_count == 0


def test_one_qb_search_ranks_qb_package_differently():
    sf, _adapter_sf = _run_target_search(
        _format_economics_league(),
        SUPERFLEX_DYNASTY,
        {"elite-qb": "Flex", "star-wr": "Flex", "depth-rb": "Bench"},
    )
    one_qb, adapter = _run_target_search(
        _format_economics_league(),
        ONE_QB_DYNASTY,
        {"elite-qb": "Flex", "star-wr": "Flex", "depth-rb": "Bench"},
    )
    assert one_qb["ideas"]
    one_qb_top = _send_headliner(one_qb["ideas"][0])
    assert one_qb_top is not None
    assert str(one_qb_top.get("player_id") or "") == "elite-qb"
    sf_top = _send_headliner(sf["ideas"][0])
    assert str(sf_top.get("player_id") or "") != "elite-qb"
    assert adapter.get_rosters.call_count == 0


def test_cornerstone_consolidation_prefers_star_and_capital():
    result, _adapter = _run_target_search(
        _consolidation_league(),
        ONE_QB_DYNASTY,
        {"star-wr": "Flex", "depth-one": "Bench", "depth-two": "Bench", "depth-three": "Bench"},
    )
    assert result["ideas"]
    top = result["ideas"][0]
    send_ids = {str(asset.get("player_id") or "") for asset in top.get("send_assets") or []}
    firsts = sum(1 for asset in top.get("send_assets") or [] if int(asset.get("round") or 99) == 1)
    assert "star-wr" in send_ids
    assert firsts >= 1
    pile = [
        idea
        for idea in result["ideas"]
        if "star-wr" not in {str(asset.get("player_id") or "") for asset in idea.get("send_assets") or []}
        and len([asset for asset in idea.get("send_assets") or [] if asset.get("asset_type") == "player"]) >= 2
    ]
    if pile:
        assert int(top.get("acquisition_quality_score") or 0) > int(pile[0].get("acquisition_quality_score") or 0)
    assert int(top.get("consolidation_premium_required") or 0) > 0
    path = str(top.get("hub_path") or "").casefold()
    assert "star + capital" in path or "elite consolidation" in path or "player + pick" in path


def test_difficult_target_stays_low_confidence():
    result, _adapter = _run_target_search(
        _difficult_league(),
        ONE_QB_DYNASTY,
        {"mid-wr": "Flex", "depth-rb": "Bench"},
    )
    assert result["ideas"]
    labels = {str(idea.get("trade_confidence_label") or "") for idea in result["ideas"]}
    assert "High" not in labels
    assert any(
        "Harder" in str(idea.get("hub_path") or "") or str(idea.get("trade_confidence_label") or "") == "Low"
        for idea in result["ideas"]
    )


def test_elite_search_copy_is_not_health_relief():
    frame, summary, rosters, adapter, draft_status, picks = _elite_positive_league()
    with ExitStack() as stack:
        stack.enter_context(patch.object(trade_ideas, "get_team_vs_league", return_value={"strategy": "retool"}))
        stack.enter_context(
            patch.object(trade_ideas, "_build_team_shape", side_effect=lambda *_args, **_kwargs: _shape())
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
                return_value={
                    "score": 10,
                    "summary": "The return brings healthy help at RB.",
                    "tags": ["Health Relief"],
                },
            )
        )
        stack.enter_context(patch.object(trade_ideas, "build_trade_ideas", return_value=[]))
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
    from modules import trade_hub_ui

    assert result["ideas"]
    for idea in result["ideas"]:
        assert "Health Relief" not in (idea.get("reasoning_tags") or [])
        assert "health relief" not in str(idea.get("hub_path") or "").casefold()
        assert trade_hub_ui.trade_hub_display_section(idea) != "Health Relief"
        path = str(idea.get("hub_path") or "").casefold()
        assert any(
            token in path
            for token in (
                "star + capital",
                "elite consolidation",
                "premium pick",
                "player + pick",
                "positional swap",
                "future value",
                "harder to execute",
            )
        )


def test_health_relief_renders_when_receive_covers_injury_hole():
    frame, summary, rosters, adapter, draft_status, picks = _elite_positive_league()
    with ExitStack() as stack:
        stack.enter_context(patch.object(trade_ideas, "get_team_vs_league", return_value={"strategy": "retool"}))
        stack.enter_context(
            patch.object(
                trade_ideas,
                "_build_team_shape",
                side_effect=lambda *_args, **_kwargs: _shape(
                    needs=["RB"],
                    injured_starter_positions=["RB"],
                ),
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
                return_value={
                    "score": 10,
                    "summary": "Your current starters are banged up at RB, and the return brings healthy cover there.",
                    "tags": ["Health Relief"],
                },
            )
        )
        stack.enter_context(patch.object(trade_ideas, "build_trade_ideas", return_value=[]))
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
    from modules import trade_hub_ui

    assert result["ideas"]
    for idea in result["ideas"]:
        assert idea.get("injury_motivated") is True
        assert "Health Relief" in (idea.get("reasoning_tags") or [])
        assert trade_hub_ui.trade_hub_display_section(idea) == "Health Relief"


def test_unrelated_roster_injury_does_not_label_health_relief():
    frame, summary, rosters, adapter, draft_status, picks = _elite_positive_league()
    with ExitStack() as stack:
        stack.enter_context(patch.object(trade_ideas, "get_team_vs_league", return_value={"strategy": "retool"}))
        stack.enter_context(
            patch.object(
                trade_ideas,
                "_build_team_shape",
                side_effect=lambda *_args, **_kwargs: _shape(
                    needs=["RB"],
                    injured_starter_positions=["WR"],
                ),
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
                return_value={
                    "score": 10,
                    "summary": "The return brings healthy help at RB.",
                    "tags": ["Health Relief"],
                },
            )
        )
        stack.enter_context(patch.object(trade_ideas, "build_trade_ideas", return_value=[]))
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
    from modules import trade_hub_ui

    assert result["ideas"]
    for idea in result["ideas"]:
        assert idea.get("injury_motivated") is False
        assert "Health Relief" not in (idea.get("reasoning_tags") or [])
        assert trade_hub_ui.trade_hub_display_section(idea) != "Health Relief"
        assert trade_hub_ui.trade_hub_display_section(idea).casefold() in {
            "star + capital",
            "elite consolidation",
            "premium pick package",
            "player + pick path",
            "positional swap",
            "future value package",
            "cheapest acquisition path",
        }


def test_presentation_cleanup_does_not_change_package_order():
    result, adapter = _run_target_search(
        _format_economics_league(),
        SUPERFLEX_DYNASTY,
        {"elite-qb": "Flex", "star-wr": "Flex", "depth-rb": "Bench"},
    )
    signatures = [
        tuple(str(asset.get("label") or "") for asset in idea.get("send_assets") or [])
        for idea in result["ideas"]
    ]
    assert signatures == [
        ("Star WR", "2026 Round 1", "2027 Round 1"),
        ("Star WR", "2026 Round 1", "2028 Round 1"),
        ("Elite QB", "2026 Round 1", "2027 Round 1"),
    ]
    assert [str(idea.get("hub_search_source") or "") for idea in result["ideas"]] == [
        "expanded",
        "expanded",
        "exploratory",
    ]
    assert str(result["ideas"][-1].get("trade_confidence_label") or "") == "Low"
    assert adapter.get_rosters.call_count == 0


def test_live_card_category_path_omits_health_relief_without_injury():
    from modules import trade_hub_ui

    result, adapter = _run_target_search(
        _elite_positive_league(),
        ONE_QB_DYNASTY,
        {"high-end-wr": "Flex", "depth-rb": "Bench"},
    )
    assert result["ideas"]
    for idea in result["ideas"]:
        stale = dict(idea)
        stale["reasoning_tags"] = ["Health Relief"]
        stale["reasoning_summary"] = "The return brings healthy help at RB."
        stale["_display_section"] = "Health Relief"
        stale["injury_motivated"] = False
        assert trade_hub_ui.trade_summary_card_category(stale) == ""
        assert "health relief" not in trade_hub_ui.trade_summary_card_category(stale).casefold()
    assert adapter.get_rosters.call_count == 0
