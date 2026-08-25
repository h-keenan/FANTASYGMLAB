"""Founder Beta performance + coherent-render contracts (draft measurement pass)."""

from __future__ import annotations

import inspect
from pathlib import Path

import pandas as pd

import app
from modules import game_plan_process_cache
from modules import notification_center as nc
from modules import prepared_player_frame
from modules import trade_ideas


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def test_player_search_builder_does_not_hash_universe_through_streamlit_cache():
    source = inspect.getsource(app.cached_player_trade_hub_ideas)
    assert not source.lstrip().startswith("@st.cache_data")
    assert "@st.cache_data" not in source.split("def cached_player_trade_hub_ideas", 1)[0]
    assert "if not status_items and league_id and not pick_asset_items:" in source


def test_player_search_session_cache_remains_the_reuse_owner():
    search = (ROOT / "modules" / "trade_hub_player_search.py").read_text(encoding="utf-8")
    assert "CACHE_KEY = \"trade_hub_player_search_cache\"" in search
    assert "search_signature(" in search
    assert "Streamlit DataFrame hashing" in search


def test_header_alerts_compose_from_inbox_snapshot_not_alerts_page():
    header = APP.split("def render_platform_topbar(", 1)[1].split(
        "def render_header_league_switcher", 1
    )[0]
    assert "list_founder_beta_notifications(" in header
    assert "render_alerts_page(" not in header
    compose = inspect.getsource(nc.compose_activity_inbox)
    assert "ACTIVITY_INBOX_SNAPSHOT_KEY" in compose
    assert "alerts_activity_ui.render_alerts_page" not in compose


def test_draft_overview_does_not_prefetch_assistant_or_scouting():
    draft = APP.split("draft_center_ui.render_draft_center_nav(", 1)[1]
    overview = draft.split('if draft_center_pane == "Overview":', 1)[1].split(
        "elif draft_center_pane in", 1
    )[0]
    assert "render_draft_assistant(" not in overview
    assert "render_future_scouting_pane(" not in overview
    assistant = draft.split('elif draft_center_pane in {"Current Draft", "History"}:', 1)[1].split(
        'elif draft_center_pane == "Scouting":', 1
    )[0]
    assert "render_draft_assistant(" in assistant
    scouting = draft.split('elif draft_center_pane == "Scouting":', 1)[1].split(
        "else:", 1
    )[0]
    assert "render_future_scouting_pane(" in scouting


def test_founder_player_search_diagnostics_are_opt_in():
    helper = APP.split("def _render_player_search_founder_diagnostics(", 1)[1].split(
        "def _render_player_search_grouped_cards(", 1
    )[0]
    assert "founder_labs_authorized" in helper
    assert 'Show stage timings' in helper
    assert "if not show_details:" in helper
    assert "player_search_founder_report(search_result)" in helper.split(
        "if not show_details:", 1
    )[1]


def test_warm_my_team_and_trade_hub_skip_pending_placeholder():
    my_team = APP.split("my_team_pending = st.empty()", 1)[1][:900]
    assert "process_league_context_warm()" in my_team
    assert "if not _my_team_warm:" in my_team
    hub = APP.split("trade_hub_pending = st.empty()", 1)[1][:900]
    assert "if not _trade_hub_warm:" in hub
    assert "surface_pending_html(" in hub.split("if not _trade_hub_warm:", 1)[1]


def test_player_search_groups_mount_as_coherent_containers():
    helper = APP.split("def _render_player_search_grouped_cards(", 1)[1].split(
        "def select_trade_hub_headline_idea(", 1
    )[0]
    assert "with st.container(key=group_key):" in helper
    assert "split_player_search_ideas(ideas)" in helper.split("with st.container", 1)[0]


def test_apply_strategy_age_curve_is_idempotent_for_same_lens():
    frame = pd.DataFrame(
        [
            {
                "player_id": "p1",
                "name": "A",
                "position": "WR",
                "age": 24,
                "dynasty_score": 1000,
                "value_score": 1000,
                "rebuild_score": 1000,
            }
        ]
    )
    first = app.apply_strategy_age_curve(frame, "rebuild", "dynasty_score")
    second = app.apply_strategy_age_curve(first, "rebuild", "dynasty_score")
    assert second is first
    rebuilt = app.apply_strategy_age_curve(first, "contender", "dynasty_score")
    assert rebuilt is not first


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


def test_player_search_named_stages_cover_previously_unaccounted_owners():
    keys = trade_ideas.PLAYER_SEARCH_FOUNDER_KEYS
    for key in (
        "stage_ms_frame_normalize",
        "stage_ms_universe",
        "stage_ms_roster_index",
        "stage_ms_team_shape",
        "stage_ms_partner_prep",
        "stage_ms_construction",
        "stage_ms_market",
    ):
        assert key in keys


def test_process_stores_stay_bounded():
    inventory = game_plan_process_cache.bounded_store_inventory()
    assert inventory["game_plan_league"]["max"] == 48
    assert inventory["trade_hub_boards"]["max"] == 16
    assert inventory["warm_route_presentation"]["max"] == 16
    assert inventory["team_shapes"]["max"] == 64
    assert inventory["public_player_hydrate"]["max"] == 4
    assert inventory["team_shapes"]["scope"] == "process"


def test_superset_reuse_contract_still_wired():
    cache = (ROOT / "modules" / "game_plan_process_cache.py").read_text(encoding="utf-8")
    assert "def context_flags_cover(" in cache
    assert "Never serve a narrower cache" in cache
    assert "identity=league_identity_sig" in APP
    assert "flags=context_key" in APP


def test_explicit_player_search_skips_automatic_board_rebuild():
    source = inspect.getsource(trade_ideas.build_player_trade_hub_ideas)
    assert "skipped_automatic_board" in source
    assert "build_trade_ideas(" not in source.split("if mode_key == \"my_player\":", 1)[1].split(
        "target_roster_id = _find_roster_id_for_player", 1
    )[0]
