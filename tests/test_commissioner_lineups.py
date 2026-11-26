"""Commissioner lineup check: pure row math (modules.commissioner_lineups) and the Pro gate on the endpoint."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from modules import commissioner_lineups as cl
from tests.test_paywall_leaks import (  # noqa: F401
    AUTH,
    _PRO_FEATURE_ENTITLEMENTS,
    _set_profile,
    pro_feature_client,
)


def _p(pid, slot, pts, **extra):
    base = {"player_id": pid, "name": f"P{pid}", "position": "RB", "team": "BUF", "slot": slot,
            "injury_status": "", "status": "Active", "injury_label": "",
            "projection": {"status": "ok", "point_estimate": pts, "low": pts - 3, "high": pts + 3}}
    base.update(extra)
    return base


def _row(real_starters, best, empty=None, has_live=True, ready=True, moves=None):
    return cl.build_team_row(
        roster_id="1", team_name="T", owner_name="o", avatar_url=None,
        real={"real_starters": real_starters, "real_empty_slots": empty or [], "has_live_data": has_live},
        suggested_starters=best, moves=moves, projection_ready=ready,
    )


def test_gap_and_tanking_flag():
    row = _row([_p(1, "RB", 5.0), _p(2, "WR", 4.0)], [_p(3, "RB", 15.0), _p(4, "WR", 12.0)])
    assert row["set_points"] == 9.0 and row["best_points"] == 27.0 and row["gap"] == 18.0
    assert row["possible_tanking"] is True


def test_small_gap_not_flagged():
    row = _row([_p(1, "RB", 14.0)], [_p(3, "RB", 15.0)])
    assert row["gap"] == 1.0 and row["possible_tanking"] is False


def test_out_ir_bye_and_empty_flags_and_zero_points():
    out = _p(1, "RB", 10.0, injury_status="Out")
    ir = _p(2, "WR", 10.0, status="Injured Reserve", injury_status="IR")
    bye = _p(3, "TE", 0, projection={"status": "bye_week"})
    row = _row([out, ir, bye], [_p(4, "RB", 10.0)], empty=["QB"])
    kinds = sorted(f["kind"] for f in row["flags"])
    assert kinds == ["bye", "empty", "ir", "out"]
    assert row["set_points"] == 0.0 and row["gap"] == 10.0


def test_no_lineup_set():
    row = _row([], [_p(4, "RB", 10.0)], has_live=False)
    assert row["flags"][0]["kind"] == "no_lineup" and row["gap"] == 10.0


def test_locked_starter_counted_and_gap_never_negative():
    locked = _p(1, "RB", 6.0, game_started=True, actual_points=20.0, game_final=True)
    row = _row([locked], [locked])
    assert row["locked_count"] == 1 and row["gap"] == 0.0


def test_unmodeled_starter_does_not_flag_tanking():
    unmodeled = _p(1, "RB", 0, projection={"status": "insufficient_player_data"})
    row = _row([unmodeled], [_p(3, "RB", 20.0)])
    assert row["partial"] is True and row["possible_tanking"] is False


def test_no_projections_leaves_points_null():
    row = _row([_p(1, "RB", 5.0)], [_p(3, "RB", 15.0)], ready=False)
    assert row["gap"] is None and row["set_points"] is None and row["possible_tanking"] is False


def test_sort_worst_first_none_last():
    a, b, c = ({"gap": g, "flags": [], "team_name": n} for g, n in ((2.0, "a"), (9.0, "b"), (None, "c")))
    assert [t["team_name"] for t in cl.sort_teams([c, a, b])] == ["b", "a", "c"]


@pytest.mark.parametrize("entitlement,allowed", _PRO_FEATURE_ENTITLEMENTS)
def test_endpoint_is_pro_only(pro_feature_client, monkeypatch, entitlement, allowed):
    _set_profile(monkeypatch, entitlement)
    with patch("modules.sleeper.get_league", return_value={"status": "pre_draft", "settings": {}}):
        body = pro_feature_client.get("/v1/leagues/abc/commissioner/lineups", headers=AUTH).json()
    if allowed:
        assert body["is_premium"] is True and body["reason"] == "no_current_week" and body["teams"] == []
    else:
        assert body["reason"] == "premium_required" and body["teams"] == [] and body["upsell"]["title"]
