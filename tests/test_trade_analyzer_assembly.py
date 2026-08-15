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
APP = (ROOT / "app.py").read_text(encoding="utf-8")
UI = (ROOT / "modules" / "trade_analyzer_ui.py").read_text(encoding="utf-8")
ASSEMBLY = (ROOT / "modules" / "trade_analyzer_assembly.py").read_text(encoding="utf-8")
HARNESS = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")
VALIDATOR = (ROOT / "scripts" / "validate_mobile_ui.py").read_text(encoding="utf-8")


def _route_block() -> str:
    return APP[
        APP.index('if current_page == "trade_analyzer":') : APP.index(
            'if current_page == "premium":'
        )
    ]


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


def test_assembly_and_ui_never_execute_analysis():
    for source in (ASSEMBLY, UI):
        assert "evaluate_trade_analyzer_fit" not in source
        assert "decide_offer_verdict" not in source
        assert "search_trade_assets" not in source
        assert "get_shared_league_context" not in source
        assert "apply_strategy_age_curve" not in source
    tree = ast.parse(ASSEMBLY)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append((node.module or "").split(".")[0])
    assert "requests" not in imported
    assert "sleeper" not in imported


def test_analyze_trade_is_the_only_execution_boundary():
    block = _route_block()
    assert block.count("evaluate_trade_analyzer_fit(") == 1
    assert "if analyze_clicked:" in block
    analyze_at = block.index("if analyze_clicked:")
    fit_at = block.index("evaluate_trade_analyzer_fit(")
    assert fit_at > analyze_at
    assert "render_trade_analyzer_assembly(" in block
    assert "search_trade_assets_for_side(" not in block
    assert "st.columns(2)" not in block
    assert "+ Add asset" not in block
    assert "st.rerun(" not in block
    assert "@st.fragment" in UI
    assert "st.rerun(" not in UI
    assert "Analyze Trade" not in UI
    assert "Analyze Trade" in block


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


def test_no_duplicate_assembly_widget_trees():
    assert UI.count("def render_trade_analyzer_assembly(") == 1
    assert UI.count('key=f"toa_add_{side}_{token}"') == 1
    assert UI.count('key=f"toa_rm_{side}_{idx}_{token}"') == 1
    assert UI.count('key=f"toa_{side}_kind"') == 1
    assert UI.count('f"trade_{side}_search_query"') == 1
    block = _route_block()
    assert block.count("render_trade_analyzer_assembly(") == 1
    assert "def render_asset_adder(" not in APP
    assert "def add_trade_asset(" not in APP


def test_session_clear_includes_assembly_catalog_keys():
    for key in assembly.ASSEMBLY_STATE_KEYS:
        assert key in session_integrity.TRADE_ANALYZER_PACKAGE_KEYS
    state = {key: 1 for key in session_integrity.TRADE_ANALYZER_PACKAGE_KEYS}
    session_integrity.clear_trade_analyzer_package(state)
    assert assembly.CATALOG_PLAYERS_ME not in state
    assert "trade_send_assets" not in state


def test_search_widget_keys_are_not_assigned_after_inputs():
    assert 'st.session_state["trade_send_search_query"] = ""' not in UI
    assert 'st.session_state["trade_receive_search_query"] = ""' not in UI
    text_at = UI.index("st.text_input(")
    add_marker = 'key=f"toa_add_{side}_{token}"'
    assert add_marker in UI
    assert UI.index(add_marker) > text_at


def test_mobile_and_harness_contracts():
    css = (ROOT / "modules" / "trade_analyzer_styles.py").read_text(encoding="utf-8")
    assert "st-key-toa_roster_" in css
    assert "max-height: min(40vh, 16.5rem)" in css
    assert "flex-wrap: wrap" in css
    assert "You receive" in UI
    assert "You send" in UI
    assert "st.columns(2)" not in UI
    harness_fn = HARNESS[
        HARNESS.index("def _trade_analyzer()") : HARNESS.index("def _player_asset_explorer()")
    ]
    assert "render_trade_analyzer_assembly(" in harness_fn
    assert "+ Add asset" not in harness_fn
    assert "st.columns(2)" not in harness_fn
    assert '"trade-analyzer"' in VALIDATOR
    assert "You receive" in VALIDATOR


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
