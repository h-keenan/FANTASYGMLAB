"""Process-cold Game Plan caches + compose/package diagnostics (#221)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules import daily_gm_briefing
from modules import dashboard_workflow
from modules import game_plan_package
from modules import game_plan_process_cache
from modules import startup_cold_path
from modules import startup_coordinator


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def test_league_process_cache_hit_equals_miss_payload():
    game_plan_process_cache.clear_process_game_plan_caches()
    calls = {"n": 0}
    frame = pd.DataFrame({"roster_id": [1], "team_name": ["A"]})

    def builder():
        calls["n"] += 1
        return {"team_direction_summary": frame.copy(), "league_maturity": {"dashboard_phase": "in_season"}}

    sig = game_plan_process_cache.build_league_process_signature(
        prepared_frame_signature="frame-1",
        league_id="L1",
        score_field="value_score",
        league_settings_key="settings",
        flags=game_plan_package.GAME_PLAN_CONTEXT_FLAGS,
    )
    first, miss = game_plan_process_cache.get_or_build_league_context(
        signature=sig, builder=builder
    )
    second, hit = game_plan_process_cache.get_or_build_league_context(
        signature=sig, builder=builder
    )
    assert miss is False
    assert hit is True
    assert calls["n"] == 1
    assert list(first["team_direction_summary"]["roster_id"]) == list(
        second["team_direction_summary"]["roster_id"]
    )


def test_trade_process_cache_skips_builder_on_hit():
    game_plan_process_cache.clear_process_game_plan_caches()
    calls = {"n": 0}

    def builder():
        calls["n"] += 1
        return [{"idea_id": "t1", "trade_gain": 12}]

    sig = game_plan_process_cache.build_trade_process_signature(
        prepared_frame_signature="frame-1",
        league_id="L1",
        roster_id="7",
        team_strategy="contend",
        role_items=(("p1", "Core"),),
    )
    a, miss = game_plan_process_cache.get_or_build_trade_headline(
        signature=sig, builder=builder
    )
    b, hit = game_plan_process_cache.get_or_build_trade_headline(
        signature=sig, builder=builder
    )
    assert miss is False and hit is True
    assert calls["n"] == 1
    assert a[0]["idea_id"] == b[0]["idea_id"]
    assert a is not b  # deep-copied isolation


def test_trade_signature_isolates_roster_and_roles():
    base = dict(
        prepared_frame_signature="frame",
        league_id="L1",
        roster_id="7",
        team_strategy="contend",
        role_items=(("p1", "Core"),),
    )
    a = game_plan_process_cache.build_trade_process_signature(**base)
    b = game_plan_process_cache.build_trade_process_signature(
        **{**base, "roster_id": "8"}
    )
    c = game_plan_process_cache.build_trade_process_signature(
        **{**base, "role_items": (("p1", "Bench"),)}
    )
    assert a != b
    assert a != c


def test_league_process_signature_excludes_roster_identity():
    # League-reusable — same key regardless of which roster is viewing.
    a = game_plan_process_cache.build_league_process_signature(
        prepared_frame_signature="f",
        league_id="L1",
        score_field="value_score",
        flags=(False, True, True, True),
    )
    b = game_plan_process_cache.build_league_process_signature(
        prepared_frame_signature="f",
        league_id="L1",
        score_field="value_score",
        flags=(False, True, True, True),
    )
    assert a == b
    assert "roster" not in a  # digest only; ensure builder API has no roster arg


def test_compose_diagnostics_report_hit_miss():
    daily_gm_briefing.clear_compose_memo()
    briefing = dashboard_workflow.DashboardBriefing(
        immediate=(),
        primary={
            "label": "Trade Opportunity",
            "value": "Partner",
            "note": "Path",
            "route_key": "trade_hub",
            "recommendation_id": "rec-1",
        },
        additional=(),
        intelligence=(),
    )
    first = daily_gm_briefing.compose_daily_gm_briefing(
        briefing, league_id="L1", context_fingerprint="fp"
    )
    assert daily_gm_briefing.last_compose_diagnostics()["cache_status"] == "miss"
    second = daily_gm_briefing.compose_daily_gm_briefing(
        briefing, league_id="L1", context_fingerprint="fp"
    )
    assert daily_gm_briefing.last_compose_diagnostics()["cache_status"] == "hit"
    assert [i.recommendation_id for i in first.items] == [
        i.recommendation_id for i in second.items
    ]


def test_app_wires_process_caches_and_cache_events():
    assert "game_plan_process_cache.get_or_build_league_context" in APP
    assert "game_plan_process_cache.get_or_build_trade_headline" in APP
    assert "log_startup_cache_event" in APP
    assert "game_plan_briefing_assembly" in APP
    assert "game_plan_compose_cache_lookup" in APP
    assert "include_intelligence=True" not in APP.split(
        "def _load_game_plan_league_context()", 1
    )[1].split("render_home_dashboard(", 1)[0]


def test_package_lookup_logs_cache_status_without_slow_gate():
    assert 'cache_status="hit" if game_plan_package_hit else "miss"' in APP
    assert "log_startup_cache_event" in APP


def test_startup_cache_event_emits_without_elapsed_gate(monkeypatch, capsys):
    monkeypatch.setenv("DYNASTYGM_STARTUP", "1")
    startup_cold_path.log_startup_cache_event(
        "game_plan_package",
        cache_status="hit",
        signature_prefix="abcdef12",
        elapsed_ms=0.0,
    )
    out = capsys.readouterr().out
    assert "startup_cache_event" in out
    assert "cache_status" in out
    assert "hit" in out


def test_milestone_accepts_cache_status(monkeypatch, capsys):
    monkeypatch.setenv("DYNASTYGM_STARTUP", "1")
    state: dict = {}
    from modules import auth_restore_lifecycle

    auth_restore_lifecycle.ensure_startup_session(state)
    startup_coordinator.log_startup_milestone(
        state,
        "game_plan_package_cache_lookup",
        once=False,
        cache_status="miss",
        detail={"signature_prefix": "deadbeef"},
    )
    out = capsys.readouterr().out
    assert "cache_status" in out
    assert "miss" in out


def test_auth_handshake_documents_clock_domains():
    from modules import auth_storage_handshake

    state: dict = {}
    auth_storage_handshake.mark_component_mount_start(state)
    summary = auth_storage_handshake.record_payload_received(
        state,
        payload={"_handshake": {"emit_wall_ms": 1, "js_emit_ms": 0.1}},
        source="test",
    )
    assert summary["clock_domains"]["python_mount_to_receive_ms"] == "perf_counter"
    assert summary["clock_domains"]["frontend_to_python_ms"] == "wall_ms"
