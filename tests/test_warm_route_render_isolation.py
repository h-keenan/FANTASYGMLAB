"""Warm-route render attribution and My Team advisor presentation memo."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from modules import hot_path_profile
from modules import prepared_player_frame
from modules import warm_route_render


ROOT = Path(__file__).resolve().parents[1]
PROVIDER_TOKENS = (
    "get_league(",
    "get_matchups(",
    "get_transactions(",
    "get_rosters(",
    "get_league_drafts(",
)


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
