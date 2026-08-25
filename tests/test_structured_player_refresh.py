"""Founder Beta structured football freshness — status/injury/depth invalidation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from modules import canonical_player_ranking
from modules import injury_ui
from modules import prepared_player_frame
from modules import session_integrity
from modules import signal_freshness
from modules import sleeper
from modules import structured_player_refresh as spr
from modules import trade_ideas
from modules import trade_hub_ui
from modules.player_quick_view import pqv_hero_html
from modules.player_tiers import assign_player_tiers
from modules.rankings import (
    current_availability_multiplier,
    injury_level,
    injury_multiplier,
    summarize_team_injuries,
)
from scripts.measure_interaction_rerun_architecture import count_explicit_reruns

ROOT = Path(__file__).resolve().parents[1]


def _row(
    player_id: str,
    *,
    name: str,
    position: str,
    team: str,
    depth: int,
    status: str = "Active",
    injury_status: str = "",
    market_score: float = 4000.0,
    age: float = 25.0,
    years_exp: float = 3.0,
    search_rank: int = 40,
    production_score: float = 4000.0,
    **extra,
) -> dict:
    payload = {
        "player_id": player_id,
        "name": name,
        "position": position,
        "team": team,
        "team_abbr": team,
        "status": status,
        "injury_status": injury_status,
        "depth_chart_position": position,
        "depth_chart_order": depth,
        "active": True,
        "news_updated": 1,
        "value": market_score,
        "market_score": market_score,
        "fantasycalc_value": market_score,
        "age": age,
        "years_exp": years_exp,
        "search_rank": search_rank,
        "games_played": 16,
        "targets": 40,
        "receptions": 30,
        "rush_attempts": 180 if position == "RB" else 4,
        "rushing_yards": 800 if position == "RB" else 20,
        "pass_attempts": 500 if position == "QB" else 0,
        "snap_share": 0.72 if depth == 1 else 0.28,
        "rush_share": 0.55 if position == "RB" and depth == 1 else 0.18,
        "target_share": 0.18,
        "route_participation": 0.4,
        "production_score": production_score,
        "age_curve_score": market_score,
        "scarcity_score": 800.0,
        "role_score": 8500 if depth == 1 else 5600,
        "opportunity_score": 8800 if depth == 1 else 4300,
        "opportunity_label": "Elite Opportunity" if depth == 1 else "Backup With Upside",
        "opportunity_confidence": 80,
        "score": int(market_score),
        "dynasty_score": int(market_score),
        "value_score": int(market_score),
        "risk_multiplier": 1.0,
        "injury_level": "healthy",
        "injury_multiplier": 1.0,
        "news_headline": "",
        "sport": "nfl",
        "fantasy_positions": position,
    }
    payload.update(extra)
    return payload


def _sleeper(player_id: str, **overrides) -> dict:
    position = str(overrides.get("position") or "RB")
    order = int(overrides.get("depth_chart_order") or 1)
    record = {
        "full_name": overrides.pop("full_name", "Player"),
        "position": position,
        "team": overrides.get("team", "KC"),
        "team_abbr": overrides.get("team_abbr", overrides.get("team", "KC")),
        "status": "Active",
        "injury_status": "",
        "depth_chart_position": overrides.get("depth_chart_position") or f"{position}{order}",
        "depth_chart_order": order,
        "active": True,
        "news_updated": 1_700_000_000_000,
        "age": 25,
        "years_exp": 3,
        "search_rank": 40,
    }
    record.update(overrides)
    if "depth_chart_position" not in overrides:
        record["depth_chart_position"] = f"{record.get('position') or position}{int(record.get('depth_chart_order') or order)}"
    return record


def _rb_room(*, starter_injury: str = "", starter_status: str = "Active") -> pd.DataFrame:
    return pd.DataFrame(
        [
            _row(
                "rb1",
                name="Starter RB",
                position="RB",
                team="KC",
                depth=1,
                status=starter_status,
                injury_status=starter_injury,
                market_score=8200,
                search_rank=12,
            ),
            _row(
                "rb2",
                name="Backup RB",
                position="RB",
                team="KC",
                depth=2,
                market_score=3100,
                age=23,
                years_exp=1,
                search_rank=90,
            ),
            _row(
                "fa-rb",
                name="Healthy FA RB",
                position="RB",
                team="DAL",
                depth=2,
                market_score=2400,
                search_rank=110,
            ),
        ]
    )


def _sleeper_room(*, starter_injury: str = "", starter_status: str = "Active", starter_depth: int = 1) -> dict:
    return {
        "rb1": _sleeper(
            "rb1",
            full_name="Starter RB",
            position="RB",
            team="KC",
            status=starter_status,
            injury_status=starter_injury,
            depth_chart_order=starter_depth,
        ),
        "rb2": _sleeper(
            "rb2",
            full_name="Backup RB",
            position="RB",
            team="KC",
            depth_chart_order=2,
        ),
        "fa-rb": _sleeper(
            "fa-rb",
            full_name="Healthy FA RB",
            position="RB",
            team="DAL",
            depth_chart_order=2,
        ),
    }


def _refresh(frame: pd.DataFrame, sleeper_players: dict) -> pd.DataFrame:
    return spr.refresh_structured_player_state(frame, sleeper_players)


def test_persisted_healthy_to_sleeper_q_local_patch():
    frame = _rb_room()
    patched = _refresh(frame, _sleeper_room(starter_injury="Questionable"))
    starter = patched.set_index("player_id").loc["rb1"]
    assert injury_level(starter["status"], starter["injury_status"]) == "minor"
    assert float(starter["injury_multiplier"]) == pytest.approx(
        injury_multiplier("Active", "Questionable")
    )
    assert float(starter["risk_multiplier"]) < 1.0
    assert int(starter["score"]) != int(frame.set_index("player_id").loc["rb1", "score"])


def test_q_to_out_updates_immediately():
    q = _refresh(_rb_room(), _sleeper_room(starter_injury="Questionable"))
    out = _refresh(q, _sleeper_room(starter_status="Out", starter_injury="Out"))
    starter = out.set_index("player_id").loc["rb1"]
    assert injury_level(starter["status"], starter["injury_status"]) == "moderate"
    assert starter["opportunity_label"] == "Starter At Risk"


def test_out_to_ir_updates_immediately():
    out = _refresh(_rb_room(), _sleeper_room(starter_status="Out", starter_injury="Out"))
    ir = _refresh(out, _sleeper_room(starter_status="Injured Reserve", starter_injury="IR"))
    starter = ir.set_index("player_id").loc["rb1"]
    assert injury_level(starter["status"], starter["injury_status"]) == "major"
    assert float(starter["injury_multiplier"]) == pytest.approx(0.68)


def test_ir_to_active_clears_ghost_injury_state():
    ir = _refresh(_rb_room(), _sleeper_room(starter_status="Injured Reserve", starter_injury="IR"))
    recovered = _refresh(ir, _sleeper_room())
    starter = recovered.set_index("player_id").loc["rb1"]
    backup = recovered.set_index("player_id").loc["rb2"]
    assert injury_level(starter["status"], starter["injury_status"]) == "healthy"
    assert float(starter["injury_multiplier"]) == pytest.approx(1.0)
    assert float(
        current_availability_multiplier(
            starter["status"], starter["team"], starter["search_rank"], starter["injury_status"]
        )
    ) == pytest.approx(1.0)
    assert float(starter["risk_multiplier"]) == pytest.approx(1.0)
    assert starter["opportunity_label"] != "Starter At Risk"
    assert "injury_overlay" not in str(backup.get("opportunity_source_flags") or "")


def test_teammate_out_increases_backup_opportunity():
    healthy = _refresh(_rb_room(), _sleeper_room())
    injured = _refresh(_rb_room(), _sleeper_room(starter_status="Out", starter_injury="Out"))
    healthy_backup = int(healthy.set_index("player_id").loc["rb2", "opportunity_score"])
    injured_backup = int(injured.set_index("player_id").loc["rb2", "opportunity_score"])
    assert injured_backup > healthy_backup
    flags = str(injured.set_index("player_id").loc["rb2", "opportunity_source_flags"])
    assert "injury_overlay" in flags


@pytest.mark.parametrize("position", ["WR", "TE", "QB"])
def test_teammate_injury_overlay_by_position(position: str):
    frame = pd.DataFrame(
        [
            _row("p1", name="Starter", position=position, team="BUF", depth=1, market_score=7000),
            _row(
                "p2",
                name="Backup",
                position=position,
                team="BUF",
                depth=2,
                market_score=2400,
                age=23,
                years_exp=1,
            ),
        ]
    )
    healthy_meta = {
        "p1": _sleeper("p1", position=position, team="BUF", full_name="Starter"),
        "p2": _sleeper("p2", position=position, team="BUF", depth_chart_order=2, full_name="Backup"),
    }
    out_meta = {
        "p1": _sleeper(
            "p1",
            position=position,
            team="BUF",
            status="Out",
            injury_status="Out",
            full_name="Starter",
        ),
        "p2": _sleeper("p2", position=position, team="BUF", depth_chart_order=2, full_name="Backup"),
    }
    healthy = _refresh(frame, healthy_meta)
    injured = _refresh(frame, out_meta)
    assert int(injured.set_index("player_id").loc["p2", "opportunity_score"]) >= int(
        healthy.set_index("player_id").loc["p2", "opportunity_score"]
    )


def test_teammate_return_removes_backup_bump():
    injured = _refresh(_rb_room(), _sleeper_room(starter_status="Out", starter_injury="Out"))
    recovered = _refresh(injured, _sleeper_room())
    healthy = _refresh(_rb_room(), _sleeper_room())
    assert int(recovered.set_index("player_id").loc["rb2", "opportunity_score"]) == int(
        healthy.set_index("player_id").loc["rb2", "opportunity_score"]
    )


def test_depth_slot_two_to_one_changes_opportunity_without_injury():
    frame = _rb_room()
    base = _refresh(frame, _sleeper_room(starter_depth=2))
    promoted_meta = _sleeper_room()
    promoted_meta["rb1"]["depth_chart_order"] = 2
    promoted_meta["rb1"]["depth_chart_position"] = "RB2"
    promoted_meta["rb2"]["depth_chart_order"] = 1
    promoted_meta["rb2"]["depth_chart_position"] = "RB1"
    promoted = _refresh(frame, promoted_meta)
    rb2_before = base.set_index("player_id").loc["rb2"]
    rb2_after = promoted.set_index("player_id").loc["rb2"]
    assert int(rb2_after["depth_chart_slot"]) == 1
    assert int(rb2_after["role_score"]) > int(rb2_before["role_score"])
    assert int(rb2_after["opportunity_score"]) > int(rb2_before["opportunity_score"])
    assert int(rb2_after["score"]) != int(rb2_before["score"])


def test_risk_and_opportunity_update_together():
    healthy = _refresh(_rb_room(), _sleeper_room())
    out = _refresh(_rb_room(), _sleeper_room(starter_status="Out", starter_injury="Out"))
    h = healthy.set_index("player_id").loc["rb1"]
    o = out.set_index("player_id").loc["rb1"]
    assert float(o["risk_multiplier"]) != float(h["risk_multiplier"])
    assert int(o["opportunity_score"]) != int(h["opportunity_score"])
    assert o["opportunity_label"] == "Starter At Risk"


def test_no_stale_opportunity_after_risk_refresh():
    persisted = _rb_room()
    persisted.loc[persisted["player_id"] == "rb1", "risk_multiplier"] = 0.80
    persisted.loc[persisted["player_id"] == "rb1", "opportunity_score"] = 8800
    persisted.loc[persisted["player_id"] == "rb1", "opportunity_label"] = "Elite Opportunity"
    patched = _refresh(persisted, _sleeper_room(starter_status="Out", starter_injury="Out"))
    starter = patched.set_index("player_id").loc["rb1"]
    assert starter["opportunity_label"] != "Elite Opportunity"
    assert int(starter["opportunity_score"]) != 8800


def test_market_value_preserved_during_local_structured_refresh():
    frame = _rb_room()
    patched = _refresh(frame, _sleeper_room(starter_injury="Questionable"))
    for pid in ("rb1", "rb2", "fa-rb"):
        before = frame.set_index("player_id").loc[pid]
        after = patched.set_index("player_id").loc[pid]
        assert float(after["market_score"]) == float(before["market_score"])
        assert float(after["fantasycalc_value"]) == float(before["fantasycalc_value"])
        assert float(after["value"]) == float(before["value"])


def test_production_stats_preserved():
    frame = _rb_room()
    patched = _refresh(frame, _sleeper_room(starter_status="Out", starter_injury="Out"))
    for column in ("games_played", "rush_attempts", "rushing_yards", "production_score", "snap_share"):
        assert list(patched[column]) == list(frame[column])


def test_no_synchronous_fantasycalc_or_news_fetch():
    frame = _rb_room()
    with (
        patch("modules.rankings.get_dynasty_values", side_effect=AssertionError("fc")),
        patch("modules.sleeper.requests.get", side_effect=AssertionError("http")),
        patch("requests.get", side_effect=AssertionError("requests")),
    ):
        patched = _refresh(frame, _sleeper_room(starter_injury="Out"))
    assert not patched.empty


def test_disk_loader_never_hits_network(tmp_path: Path):
    path = tmp_path / "sleeper_players.json"
    path.write_text(json.dumps({"rb1": _sleeper("rb1")}), encoding="utf-8")
    with patch("modules.sleeper.requests.get", side_effect=AssertionError("network")):
        data, mtime_ns = sleeper.load_cached_players_disk(str(path))
    assert "rb1" in data
    assert mtime_ns > 0


def test_prepared_player_frame_invalidates_on_status_change():
    prepared_player_frame.clear_process_valued_ranked_frames()
    healthy = spr.structured_state_fingerprint(_refresh(_rb_room(), _sleeper_room()))
    injured = spr.structured_state_fingerprint(
        _refresh(_rb_room(), _sleeper_room(starter_status="Out", starter_injury="Out"))
    )
    assert healthy != injured
    kwargs = dict(
        public_fingerprint="pub",
        valuation_lens="value_score",
        score_field="value_score",
        league_settings_key="s1",
        scoring_format="PPR",
        scoring_supported=True,
        archetype_id="balanced",
        season="2025",
        row_count=3,
    )
    sig_a = prepared_player_frame.build_frame_signature(**kwargs, structured_fingerprint=healthy)
    sig_b = prepared_player_frame.build_frame_signature(**kwargs, structured_fingerprint=injured)
    assert sig_a != sig_b
    builds = {"n": 0}

    def builder():
        builds["n"] += 1
        return pd.DataFrame({"player_id": ["rb1"], "value_score": [1]})

    state: dict = {}
    prepared_player_frame.get_or_build_valued_ranked_frame(state, signature=sig_a, builder=builder)
    prepared_player_frame.get_or_build_valued_ranked_frame(state, signature=sig_b, builder=builder)
    assert builds["n"] == 2


def test_frame_invalidates_on_depth_change():
    slot2 = spr.structured_state_fingerprint(_refresh(_rb_room(), _sleeper_room(starter_depth=2)))
    slot1 = spr.structured_state_fingerprint(_refresh(_rb_room(), _sleeper_room(starter_depth=1)))
    assert slot1 != slot2


def test_same_structured_state_stays_cacheable():
    a = spr.structured_state_fingerprint(_refresh(_rb_room(), _sleeper_room()))
    b = spr.structured_state_fingerprint(_refresh(_rb_room(), _sleeper_room()))
    assert a == b
    kwargs = dict(
        public_fingerprint="pub",
        valuation_lens="value_score",
        score_field="value_score",
        league_settings_key="s1",
        scoring_format="PPR",
        scoring_supported=True,
        archetype_id="balanced",
        season="2025",
        row_count=3,
    )
    assert prepared_player_frame.build_frame_signature(
        **kwargs, structured_fingerprint=a
    ) == prepared_player_frame.build_frame_signature(**kwargs, structured_fingerprint=b)
    empty = prepared_player_frame.build_frame_signature(**kwargs)
    assert empty.count("|") == 8


def test_roster_injury_pressure_updates():
    healthy = _refresh(_rb_room(), _sleeper_room())
    injured = _refresh(_rb_room(), _sleeper_room(starter_status="Out", starter_injury="Out"))
    healthy["suggested_starter"] = [True, False, False]
    injured["suggested_starter"] = [True, False, False]
    h = summarize_team_injuries(healthy, healthy)
    i = summarize_team_injuries(injured, injured)
    assert int(i["injured_starters"]) > int(h["injured_starters"])
    assert float(i["injury_impact_score"]) >= float(h["injury_impact_score"])


def test_healthy_backup_coverage_prevents_false_permanent_need():
    covered = _refresh(_rb_room(), _sleeper_room(starter_status="Out", starter_injury="Out"))
    covered["suggested_starter"] = [True, False, False]
    summary = summarize_team_injuries(covered, covered)
    impacts = [
        item
        for item in (summary.get("top_injury_impact_players") or [])
        if item.get("player_id") == "rb1"
    ]
    assert impacts
    assert bool(impacts[0].get("has_position_cover")) is True
    assert "RB" not in set(summary.get("injury_need_positions") or set())


def test_no_cover_injury_creates_waiver_replacement_fit():
    from app import build_home_dashboard_free_agent_preview

    uncovered = pd.DataFrame(
        [
            _row("rb1", name="Starter RB", position="RB", team="KC", depth=1, market_score=8200),
            _row("fa-rb", name="Healthy FA RB", position="RB", team="DAL", depth=2, market_score=2400),
        ]
    )
    patched = _refresh(
        uncovered,
        {
            "rb1": _sleeper("rb1", status="Out", injury_status="Out", full_name="Starter RB"),
            "fa-rb": _sleeper("fa-rb", position="RB", team="DAL", depth_chart_order=2),
        },
    )
    roster = patched[patched["player_id"].astype(str) == "rb1"].copy()
    roster["suggested_starter"] = True
    summary = summarize_team_injuries(roster, roster)
    assert "RB" in set(summary.get("injury_need_positions") or set())
    fa, positions, _injured = build_home_dashboard_free_agent_preview(
        patched,
        "league-a",
        1,
        "value_score",
        {"roster_positions": ["RB", "RB", "WR", "TE", "QB"]},
        rostered_ids={"rb1"},
        injury_need_positions=set(summary.get("injury_need_positions") or set()),
        known_injured_starters=1,
    )
    assert "RB" in positions
    assert bool(fa.set_index("player_id").loc["fa-rb", "injury_replacement_fit"]) is True


def test_recovery_clears_waiver_fit():
    from app import build_home_dashboard_free_agent_preview

    recovered = _refresh(_rb_room(), _sleeper_room())
    recovered["suggested_starter"] = [True, False, False]
    summary = summarize_team_injuries(recovered, recovered)
    fa, positions, _ = build_home_dashboard_free_agent_preview(
        recovered,
        "league-a",
        1,
        "value_score",
        {"roster_positions": ["RB", "RB", "WR"]},
        rostered_ids={"rb1", "rb2"},
        injury_need_positions=set(summary.get("injury_need_positions") or set()),
        known_injured_starters=int(summary.get("injured_starters") or 0),
    )
    assert "RB" not in positions
    if not fa.empty and "fa-rb" in set(fa["player_id"].astype(str)):
        assert bool(fa.set_index("player_id").loc["fa-rb", "injury_replacement_fit"]) is False


def test_trade_hub_injury_guardrail_reacts_and_protects_core():
    result = trade_ideas._temporary_injury_trade_guardrail(
        {
            "needs": [],
            "temporary_injury_need_positions": {"RB"},
            "injured_starter_positions": {"RB"},
        },
        send_assets=[
            {
                "asset_type": "player",
                "position": "RB",
                "score": 8200,
                "role": "core starter",
                "player_id": "rb2",
            }
        ],
        receive_assets=[
            {
                "asset_type": "player",
                "position": "RB",
                "score": 2400,
                "player_id": "fa-rb",
            }
        ],
    )
    assert result["applied"] is True
    assert result["hard_fail"] is True
    assert "Core Starter Protected" in result["tags"]


def test_recovery_clears_temporary_trade_guardrail():
    result = trade_ideas._temporary_injury_trade_guardrail(
        {
            "needs": [],
            "temporary_injury_need_positions": set(),
            "injured_starter_positions": set(),
        },
        send_assets=[
            {"asset_type": "player", "position": "RB", "score": 8200, "role": "core starter"}
        ],
        receive_assets=[{"asset_type": "player", "position": "RB", "score": 2400}],
    )
    assert result["applied"] is False


def test_dashboard_and_my_team_agree_on_injury_state():
    from app import roster_injury_context

    injured = _refresh(_rb_room(), _sleeper_room(starter_status="Out", starter_injury="Out"))
    injured["suggested_starter"] = [True, False, False]
    dashboard = summarize_team_injuries(injured, injured)
    my_team = roster_injury_context(injured, injured)
    assert dashboard["injured_starters"] == my_team["injured_starters"]
    assert dashboard["injury_need_positions"] == my_team["injury_need_positions"]
    alert = injury_ui.my_team_injury_alert(my_team)
    assert int(alert["starter_count"]) == int(dashboard["injured_starters"])
    assert "happened" not in str(alert["note"]).casefold()


def test_alerts_q_and_sleeper_q_remain_q():
    patched = _refresh(_rb_room(), _sleeper_room(starter_injury="Questionable"))
    starter = patched.set_index("player_id").loc["rb1"]
    assert injury_level(starter["status"], starter["injury_status"]) == "minor"
    assert str(starter["injury_status"]).lower() == "questionable"


def test_news_out_does_not_force_out_when_sleeper_is_q():
    frame = _rb_room()
    frame["news_headline"] = "Starter RB ruled OUT for Sunday"
    patched = _refresh(frame, _sleeper_room(starter_injury="Questionable"))
    starter = patched.set_index("player_id").loc["rb1"]
    assert injury_level(starter["status"], starter["injury_status"]) == "minor"
    assert "out" not in str(starter["injury_status"]).lower()
    assert str(starter["news_headline"]).startswith("Starter RB ruled OUT")


def test_sleeper_out_then_updates_evaluation():
    q = _refresh(_rb_room(), _sleeper_room(starter_injury="Questionable"))
    out = _refresh(q, _sleeper_room(starter_status="Out", starter_injury="Out"))
    ranked = canonical_player_ranking.attach_canonical_ranks(
        assign_player_tiers(out, primary_score_field="value_score"),
        scoring_format="PPR",
        score_field="value_score",
        season="2025",
    )
    starter = ranked.set_index("player_id").loc["rb1"]
    backup = ranked.set_index("player_id").loc["rb2"]
    assert injury_level(starter["status"], starter["injury_status"]) == "moderate"
    assert int(starter["overall_rank"]) >= 1
    assert int(backup["opportunity_score"]) > int(
        q.set_index("player_id").loc["rb2", "opportunity_score"]
    )
    assert starter["player_tier"]
    assert int(starter["value_score"]) != int(q.set_index("player_id").loc["rb1", "value_score"])


def test_stale_status_freshness_is_honest():
    unknown = signal_freshness.status_sync_freshness(
        cache_path="/tmp/fantasygm-missing-sleeper-players.json"
    )
    assert unknown["freshness_bucket"] == signal_freshness.BUCKET_UNKNOWN
    assert "unavailable" in unknown["label"].casefold()
    assert "happened" not in unknown["label"].casefold()
    stale = signal_freshness.status_sync_freshness(now=2_000_000_000, synced_at=1_000_000_000)
    assert stale["freshness_bucket"] == signal_freshness.BUCKET_STALE
    assert "Player status synced" in stale["label"]
    html = pqv_hero_html(
        avatar_html="<div></div>",
        name="Starter RB",
        position="RB",
        team="KC",
        age_text="25",
        status_freshness_label="STATUS · synced 18m ago",
    )
    assert "STATUS · synced 18m ago" in html
    assert "happened" not in html
    blocked = pqv_hero_html(
        avatar_html="<div></div>",
        name="Starter RB",
        position="RB",
        team="KC",
        age_text="25",
        status_freshness_label="injury happened 18m ago",
    )
    assert "happened" not in blocked
    note = trade_hub_ui.trade_asset_injury_context(
        {
            "asset_type": "player",
            "status": "Out",
            "injury_status": "Out",
            "news_updated": 1_700_000_000_000,
        },
        injury_level=injury_level,
    )
    assert "happened" not in note["note"].casefold()


def test_league_a_to_b_isolation():
    assert session_integrity.SESSION_KEY_LIFETIMES["players"] == "GLOBAL"
    assert session_integrity.SESSION_KEY_LIFETIMES["news"] == "LEAGUE"
    assert session_integrity.SESSION_KEY_LIFETIMES["activity_inbox_snapshot"] == "LEAGUE"
    ppr = prepared_player_frame.build_frame_signature(
        public_fingerprint="pub",
        valuation_lens="value_score",
        score_field="value_score",
        league_settings_key="league-a",
        scoring_format="PPR",
        scoring_supported=True,
        archetype_id="balanced",
        season="2025",
        row_count=3,
    )
    half = prepared_player_frame.build_frame_signature(
        public_fingerprint="pub",
        valuation_lens="value_score",
        score_field="value_score",
        league_settings_key="league-b",
        scoring_format="Half-PPR",
        scoring_supported=True,
        archetype_id="balanced",
        season="2025",
        row_count=3,
    )
    assert ppr != half


def test_scoring_format_still_invalidates_lens():
    kwargs = dict(
        public_fingerprint="pub",
        valuation_lens="value_score",
        score_field="value_score",
        league_settings_key="s1",
        scoring_supported=True,
        archetype_id="balanced",
        season="2025",
        row_count=3,
    )
    assert prepared_player_frame.build_frame_signature(
        **kwargs, scoring_format="PPR"
    ) != prepared_player_frame.build_frame_signature(**kwargs, scoring_format="Standard")


def test_explicit_rerun_count_unchanged():
    assert count_explicit_reruns() <= 62
    source = (ROOT / "modules" / "structured_player_refresh.py").read_text(encoding="utf-8")
    assert "st.rerun" not in source
    assert "requests.get" not in source
    assert "get_dynasty_values" not in source


def test_unmatched_rows_preserved_and_input_not_mutated():
    frame = _rb_room()
    original_status = list(frame["status"])
    patched = _refresh(frame, {"rb1": _sleeper("rb1", injury_status="Questionable")})
    assert list(frame["status"]) == original_status
    assert "rb2" in set(patched["player_id"].astype(str))
    assert patched.set_index("player_id").loc["rb2", "injury_status"] == ""


def test_skip_recompute_when_structured_state_matches():
    once = _refresh(_rb_room(), _sleeper_room())
    twice = spr.refresh_structured_player_state(once, _sleeper_room())
    assert twice.attrs.get("structured_refresh_recomputed") is False


def test_public_fingerprint_includes_sleeper_metadata():
    from modules.rankings import public_player_source_fingerprint

    fingerprint = public_player_source_fingerprint("data/players.db")
    categories = [item[0] for item in fingerprint]
    assert "sleeper_metadata" in categories
    assert "sqlite" in categories


def test_join_is_player_id_only():
    source = Path(spr.__file__).read_text(encoding="utf-8")
    assert "name_key" not in source
    assert spr.STRUCTURED_PATCH_FIELDS == (
        "team",
        "team_abbr",
        "status",
        "injury_status",
        "depth_chart_position",
        "depth_chart_order",
        "active",
        "news_updated",
    )
