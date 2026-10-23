"""Trade Analyzer assembly: construction is isolated from analysis."""

from __future__ import annotations

import ast
import time
from pathlib import Path

import pandas as pd

from modules import session_integrity
from modules import trade_analyzer_assembly as assembly
from modules import trade_analyzer_builder as builder


ROOT = Path(__file__).resolve().parents[1]
ASSEMBLY = (ROOT / "modules" / "trade_analyzer_assembly.py").read_text(encoding="utf-8")


def _player_row(pid: str, name: str, *, position: str, team: str, score: int, owner: str):
    return {
        "player_id": pid,
        "name": name,
        "position": position,
        "team": team,
        "value_score": score,
        "score": score,
        "age": 25,
        "status": "Active",
        "owner_roster_id": owner,
        "owner_team_name": "Roster",
    }


def _pick(label: str, *, owner: str, season=2027, round_no=1, score=800):
    return {
        "label": label,
        "season": season,
        "round": round_no,
        "score": score,
        "owner_roster_id": owner,
        "owner_team_name": "Roster",
    }


def test_filter_and_search_do_not_call_mutate_or_analysis():
    catalog = {
        "players": [
            assembly.player_asset_from_mapping(
                _player_row("1", "Star WR", position="WR", team="MIA", score=4000, owner="p")
            ),
            assembly.player_asset_from_mapping(
                _player_row("2", "Backup RB", position="RB", team="NE", score=900, owner="p")
            ),
        ],
        "picks": [
            assembly.pick_asset_from_mapping(_pick("2027 1st", owner="p")),
        ],
    }
    started = time.perf_counter()
    wr = assembly.filter_assets(catalog, kind="Players", position="WR", query="")
    rb = assembly.filter_assets(catalog, kind="Players", position="RB", query="backup")
    picks = assembly.filter_assets(catalog, kind="Picks", query="2027")
    none = assembly.filter_assets(catalog, kind="Players", query="zzz-no-match")
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert [row["player_id"] for row in wr] == ["1"]
    assert [row["player_id"] for row in rb] == ["2"]
    assert len(picks) == 1
    assert none == []
    assert elapsed_ms < 15


def test_add_remove_preserves_unrelated_side_and_skips_analysis():
    state = {
        "trade_send_assets": [],
        "trade_receive_assets": [],
        "trade_analyzer_analyzed_signature": "prior",
        "trade_analyzer_result_payload": {"fit": {"available": True}},
    }
    receive = assembly.player_asset_from_mapping(
        _player_row("r1", "Partner WR", position="WR", team="KC", score=3000, owner="partner")
    )
    send = assembly.player_asset_from_mapping(
        _player_row("s1", "My RB", position="RB", team="NO", score=2200, owner="me")
    )
    assembly.mutate_package(
        state,
        asset=receive,
        package_key=assembly.RECEIVE_KEY,
        action="add",
        partner_roster_id="partner",
        my_roster_id="me",
    )
    assembly.mutate_package(
        state,
        asset=send,
        package_key=assembly.SEND_KEY,
        action="add",
        partner_roster_id="partner",
        my_roster_id="me",
    )
    assert len(state["trade_receive_assets"]) == 1
    assert len(state["trade_send_assets"]) == 1
    assert state["trade_analyzer_analyzed_signature"] == ""
    assert state.get("trade_analyzer_result_payload") == {"fit": {"available": True}}
    assembly.mutate_package(
        state,
        package_key=assembly.RECEIVE_KEY,
        action="remove",
        index=0,
    )
    assert state["trade_receive_assets"] == []
    assert state["trade_send_assets"][0]["player_id"] == "s1"


def test_team_change_drops_only_stale_assets():
    keep_send = assembly.player_asset_from_mapping(
        _player_row("s1", "My WR", position="WR", team="DAL", score=1000, owner="me")
    )
    stale_send = assembly.player_asset_from_mapping(
        _player_row("x1", "Other", position="QB", team="BUF", score=1000, owner="other")
    )
    stale_receive = assembly.player_asset_from_mapping(
        _player_row("p1", "Old partner", position="TE", team="SF", score=1000, owner="old")
    )
    keep_receive = assembly.player_asset_from_mapping(
        _player_row("p2", "New partner", position="WR", team="MIA", score=1000, owner="new")
    )
    state = {
        "trade_send_assets": [keep_send, stale_send],
        "trade_receive_assets": [stale_receive, keep_receive],
        "trade_analyzer_analyzed_signature": "sig",
        assembly.MATCHUP_KEY: "me|old",
    }
    changed = assembly.apply_matchup_change(
        state, my_roster_id="me", partner_roster_id="new"
    )
    assert changed is True
    assert [asset["player_id"] for asset in state["trade_send_assets"]] == ["s1"]
    assert [asset["player_id"] for asset in state["trade_receive_assets"]] == ["p2"]
    assert state["trade_analyzer_analyzed_signature"] == ""


def test_pick_asset_from_mapping_stamps_round_trippable_pick_id():
    # Same `{season}:{round}:{original_roster_id}` format
    # services/mobile_api_service.py's GET .../draft-picks already uses for
    # DraftPickAsset.pick_id — a caller (trade_offer_analyzer's counter
    # guidance) needs this to name the *exact* pick a suggestion is about,
    # the same way a player asset's player_id already lets it.
    asset = assembly.pick_asset_from_mapping(
        {
            "label": "2027 1st",
            "season": 2027,
            "round": 1,
            "original_roster_id": "7",
            "owner_roster_id": "3",
            "owner_team_name": "Roster",
            "score": 800,
        }
    )
    assert asset["pick_id"] == "2027:1:7"


def test_player_and_pick_catalog_and_identity():
    frame = pd.DataFrame(
        [
            _player_row("10", "Alpha QB", position="QB", team="KC", score=5000, owner="me"),
            _player_row("11", "Beta WR", position="WR", team="CHI", score=2000, owner="partner"),
        ]
    )
    catalog = assembly.build_side_catalog(
        players_df=frame,
        player_ids=["10"],
        picks=[_pick("2026 2nd", owner="me", season=2026, round_no=2, score=700)],
        player_owner_map={"10": {"owner_roster_id": "me", "owner_team_name": "Mine"}},
        pick_score_multiplier=1.0,
    )
    assert [row["player_id"] for row in catalog["players"]] == ["10"]
    assert catalog["players"][0]["position"] == "QB"
    assert catalog["picks"][0]["asset_type"] == "pick"
    assert builder.asset_identity(catalog["players"][0]).startswith("player:")
    assert builder.asset_identity(catalog["picks"][0]).startswith("pick:")
    players_only = assembly.filter_assets(catalog, kind="Players")
    picks_only = assembly.filter_assets(catalog, kind="Picks")
    assert all(item["asset_type"] == "player" for item in players_only)
    assert all(item["asset_type"] == "pick" for item in picks_only)


def test_session_clear_includes_assembly_catalog_keys():
    for key in assembly.ASSEMBLY_STATE_KEYS:
        assert key in session_integrity.TRADE_ANALYZER_PACKAGE_KEYS
    state = {key: 1 for key in session_integrity.TRADE_ANALYZER_PACKAGE_KEYS}
    session_integrity.clear_trade_analyzer_package(state)
    assert assembly.CATALOG_PLAYERS_ME not in state
    assert "trade_send_assets" not in state


def test_ensure_catalogs_reuses_cache_without_rebuild():
    frame = pd.DataFrame(
        [_player_row("10", "Alpha QB", position="QB", team="KC", score=5000, owner="me")]
    )
    state: dict = {}
    assembly.ensure_catalogs(
        state,
        context_key="ctx-a",
        my_roster_id="me",
        partner_roster_id="p",
        players_df=frame,
        my_player_ids=["10"],
        partner_player_ids=[],
        my_picks=[],
        partner_picks=[],
    )
    first = state[assembly.CATALOG_PLAYERS_ME]
    frame.loc[0, "name"] = "Changed"
    assembly.ensure_catalogs(
        state,
        context_key="ctx-a",
        my_roster_id="me",
        partner_roster_id="p",
        players_df=frame,
        my_player_ids=["10"],
        partner_player_ids=[],
        my_picks=[],
        partner_picks=[],
    )
    assert state[assembly.CATALOG_PLAYERS_ME] is first
    assembly.ensure_catalogs(
        state,
        context_key="ctx-b",
        my_roster_id="me",
        partner_roster_id="p",
        players_df=frame,
        my_player_ids=["10"],
        partner_player_ids=[],
        my_picks=[],
        partner_picks=[],
    )
    assert state[assembly.CATALOG_PLAYERS_ME] is not first
    assert state[assembly.CATALOG_PLAYERS_ME][0]["name"] == "Changed"


def test_player_asset_score_uses_lens_field_not_canonical_base_score():
    """Regression (logic audit 2026-10): apply_valuation_lens leaves the
    canonical base value in "score" and puts the league-adjusted value
    (Superflex QB scarcity, TE premium, league size) in the lens columns.
    The asset must carry the lens value, or the Trade Analyzer grades a
    Superflex QB trade with 1QB-style numbers."""

    row = _player_row("qb", "SF QB", position="QB", team="BUF", score=7400, owner="p")
    row.update({"dynasty_score": 9900, "rebuild_score": 9800, "value_score": 9500})

    assert assembly.player_asset_from_mapping(row, score_field="dynasty_score")["score"] == 9900
    assert assembly.player_asset_from_mapping(row, score_field="rebuild_score")["score"] == 9800
    assert assembly.player_asset_from_mapping(row, score_field="value_score")["score"] == 9500
    # A row without the lens column still falls back to "score".
    bare = _player_row("wr", "Bare WR", position="WR", team="MIA", score=4000, owner="p")
    assert assembly.player_asset_from_mapping(bare, score_field="dynasty_score")["score"] == 4000
    bare["dynasty_score"] = float("nan")
    assert assembly.player_asset_from_mapping(bare, score_field="dynasty_score")["score"] == 4000


def test_superflex_trade_asset_scores_follow_league_adjustment():
    from modules import league_value_settings as lvs

    base = {"status": "Active", "injury_status": "", "years_exp": 4}
    frame = pd.DataFrame(
        [
            dict(base, player_id="qb1", name="QB One", position="QB", team="BUF", age=27,
                 score=7000, dynasty_score=7000, value_score=7000, market_score=7000),
            dict(base, player_id="rb1", name="RB One", position="RB", team="DET", age=24,
                 score=9000, dynasty_score=9000, value_score=9000, market_score=9000),
        ]
    )
    one_qb = lvs.detect_league_value_settings_from_payload(
        {"roster_positions": ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "FLEX"]}
    )
    superflex = lvs.detect_league_value_settings_from_payload(
        {"roster_positions": ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "SUPER_FLEX"]}
    )
    one_qb_rows = lvs.apply_valuation_lens(frame, "Dynasty", one_qb).set_index("player_id", drop=False)
    sf_rows = lvs.apply_valuation_lens(frame, "Dynasty", superflex).set_index("player_id", drop=False)

    def asset_score(rows, pid):
        return assembly.player_asset_from_mapping(rows.loc[pid].to_dict(), score_field="dynasty_score")["score"]

    # The canonical "score" column is identical across formats...
    assert int(sf_rows.loc["qb1", "score"]) == int(one_qb_rows.loc["qb1", "score"])
    # ...so the asset must follow the league-adjusted lens column instead.
    assert asset_score(sf_rows, "qb1") == int(sf_rows.loc["qb1", "dynasty_score"])
    assert asset_score(sf_rows, "qb1") > asset_score(one_qb_rows, "qb1") * 1.2
    assert asset_score(sf_rows, "rb1") == int(sf_rows.loc["rb1", "dynasty_score"])
