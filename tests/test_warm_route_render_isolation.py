"""Warm-route render attribution and My Team advisor presentation memo."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from modules import hot_path_profile
from modules import prepared_player_frame
from modules import warm_route_render


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
PROVIDER_TOKENS = (
    "get_league(",
    "get_matchups(",
    "get_transactions(",
    "get_rosters(",
    "get_league_drafts(",
)


def test_my_team_advisor_is_presentation_memo_not_game_plan_headline():
    assert "family=\"my_team_advisor\"" in APP or "family='my_team_advisor'" in APP
    advisor_region = APP.split("def _build_my_team_advisor_model")[1].split(
        "my_team_snapshot_insights"
    )[0]
    assert "apply_strategy_age_curve" in advisor_region
    assert "cached_trade_ideas" in advisor_region
    assert "get_or_build_trade_headline" not in advisor_region
    assert "cached_dashboard_trade_headline" not in advisor_region


def test_route_local_blocks_cover_my_team_and_shared_tail():
    for name in (
        "post_football_players_refresh_arm",
        "my_team_league_context",
        "my_team_injury_enrichment",
        "my_team_roles_strategy_canon",
        "my_team_lineup_model",
        "my_team_advice_model",
        "my_team_advisor_model",
        "my_team_age_curve",
        "my_team_cached_trade_ideas",
        "my_team_fa_preview",
        "my_team_snapshot_insights",
        "my_team_workspace_emit",
        "player_scan_cards",
        "my_team_deferred_tables_emit",
        "league_overview_standings_bundle",
        "player_quick_view_modal",
        "legal_footer_emit",
    ):
        assert name in APP


def test_blocks_are_sequential_and_exclusive():
    warm_route_render.clear_presentation_models()
    state: dict = {}
    warm_route_render.begin_route(state, "my_team")
    with warm_route_render.block(state, "first", owner="owner_a", work_kind="compute"):
        time.sleep(0.05)
    with warm_route_render.block(state, "second", owner="owner_b", work_kind="html"):
        time.sleep(0.05)
    rows = warm_route_render.recorded_blocks(state)
    assert [row["block"] for row in rows] == ["first", "second"]
    assert rows[0]["owner"] == "owner_a"
    assert rows[1]["work_kind"] == "html"
    assert rows[0]["duration_ms"] >= 40
    assert rows[1]["duration_ms"] >= 40
    summary = warm_route_render.finish_route(state)
    assert summary["accounted_ms"] >= 80
    assert summary["route"] == "my_team"


def test_advisor_presentation_hit_skips_builder_role_change_misses():
    warm_route_render.clear_presentation_models()
    builds = {"count": 0}

    def _builder():
        builds["count"] += 1
        return {"ideas": [{"id": "a"}], "top_waiver": {"name": "Waive"}}

    first_sig = warm_route_render.presentation_signature("frame", "L1", "7", (("p1", "Flex"),))
    model, hit = warm_route_render.get_or_build_presentation_model(
        family="my_team_advisor",
        signature=first_sig,
        builder=_builder,
    )
    assert hit is False
    assert builds["count"] == 1
    assert model["ideas"][0]["id"] == "a"

    model, hit = warm_route_render.get_or_build_presentation_model(
        family="my_team_advisor",
        signature=first_sig,
        builder=_builder,
    )
    assert hit is True
    assert builds["count"] == 1
    assert model["top_waiver"]["name"] == "Waive"

    role_sig = warm_route_render.presentation_signature("frame", "L1", "7", (("p1", "Core"),))
    _, hit = warm_route_render.get_or_build_presentation_model(
        family="my_team_advisor",
        signature=role_sig,
        builder=_builder,
    )
    assert hit is False
    assert builds["count"] == 2


def test_prepared_frame_clear_drops_presentation_models():
    warm_route_render.clear_presentation_models()
    warm_route_render.get_or_build_presentation_model(
        family="my_team_advisor",
        signature="abc",
        builder=lambda: {"ideas": [1]},
    )
    prepared_player_frame.clear_prepared_player_frame({})
    _, hit = warm_route_render.get_or_build_presentation_model(
        family="my_team_advisor",
        signature="abc",
        builder=lambda: {"ideas": [2]},
    )
    assert hit is False


def test_named_blocks_advance_script_complete_cursor(monkeypatch):
    monkeypatch.setenv("DYNASTYGM_HOT_PATH", "1")
    hot_path_profile._PROCESS.update({"spans": [], "origin": 0.0, "path": "", "last_phase_at": 0.0})
    state: dict = {}
    hot_path_profile.begin("my_team", session_state=state)
    hot_path_profile.mark_phase("football_ready", session_state=state)
    with warm_route_render.block(
        state,
        "my_team_advisor_model",
        owner="cached_trade_ideas",
        work_kind="compute",
    ):
        time.sleep(0.12)
    leftover_ms = hot_path_profile.mark_phase("script_complete", session_state=state)
    assert leftover_ms < 50.0
    payload = hot_path_profile.report(state, top_n=30)
    names = [row["name"] for row in payload["spans"]]
    assert "phase_my_team_advisor_model" in names
    assert "phase_script_complete" in names
    assert any(row.get("block") == "my_team_advisor_model" for row in payload["warm_route_blocks"])


def test_hot_path_block_line_is_printed(monkeypatch, capsys):
    monkeypatch.setenv("DYNASTYGM_HOT_PATH", "1")
    hot_path_profile.begin("my_team", session_state={})
    state: dict = {}
    warm_route_render.begin_route(state, "my_team")
    with warm_route_render.block(
        state, "my_team_workspace_emit", owner="my_team_ui", work_kind="html"
    ):
        pass
    captured = capsys.readouterr().out
    assert "HOT_PATH_BLOCK " in captured
    assert "my_team_workspace_emit" in captured


def test_substages_do_not_inflate_exclusive_accounted_ms():
    state: dict = {}
    warm_route_render.begin_route(state, "my_team")
    with warm_route_render.block(state, "parent", owner="p", work_kind="compute"):
        with warm_route_render.substage(state, "child", owner="c", work_kind="compute"):
            time.sleep(0.03)
        time.sleep(0.03)
    summary = warm_route_render.finish_route(state)
    assert summary["block_count"] == 1
    assert summary["accounted_ms"] >= 50
    children = [row for row in warm_route_render.recorded_blocks(state) if row["block"] == "child"]
    assert children and children[0]["exclusive"] is False


def test_diff_adds_no_provider_calls():
    diff = subprocess.check_output(
        ["git", "diff", "origin/main", "--", "app.py", "modules/warm_route_render.py"],
        cwd=ROOT,
        text=True,
    )
    added = [
        line[1:]
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    for line in added:
        for token in PROVIDER_TOKENS:
            assert token not in line, line
