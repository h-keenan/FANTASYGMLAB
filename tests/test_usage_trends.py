"""modules.usage_trends: rolling windows, minimum-sample rules and flags."""

from __future__ import annotations

from modules import usage_trends as ut


def _weeks(rows):
    out = []
    for i, r in enumerate(rows, start=1):
        row = {"week": i, "games_played": 1, "fantasy_points_ppr": r.get("pts", 10.0)}
        row.update({k: v for k, v in r.items() if k != "pts"})
        out.append(row)
    return out


def _adv(shares, through=None):
    weeks = {}
    for i, (ts, ay) in enumerate(shares, start=1):
        weeks[i] = {"target_share": ts, "air_yards_share": ay, "opportunity_share": ts, "rz_targets": 1, "rz_carries": 0}
    return {"available": True, "through_week": through or len(shares), "as_of": "t", "weeks": weeks}


def test_role_expanding_from_snap_and_target_share_with_points_flat():
    sleeper_rows = _weeks([{"snap_share": 0.55, "pts": 10}] * 4 + [{"snap_share": 0.78, "pts": 11}] * 4)
    adv = _adv([(0.15, 0.2)] * 4 + [(0.25, 0.3)] * 4)
    prof = ut.build_usage_profile("WR", sleeper_rows, adv)
    assert prof["status"] == "ok"
    assert [f["key"] for f in prof["flags"]] == ["role_expanding"]
    snap = next(m for m in prof["metrics"] if m["key"] == "snap_share")
    assert round(snap["last4"], 2) == 0.78 and round(snap["prior"], 2) == 0.55
    assert "snap share is 78%" in prof["flags"][0]["explanation"]
    assert "+23 pts" in prof["flags"][0]["explanation"]


def test_usage_up_points_down_is_positive_regression():
    sleeper_rows = _weeks([{"snap_share": 0.5, "pts": 16}] * 4 + [{"snap_share": 0.75, "pts": 8}] * 4)
    adv = _adv([(0.15, 0.2)] * 4 + [(0.24, 0.3)] * 4)
    prof = ut.build_usage_profile("WR", sleeper_rows, adv)
    assert prof["flags"][0]["key"] == "positive_regression"
    assert prof["flags"][0]["tone"] == "positive"


def test_points_up_usage_down_is_unsustainable():
    sleeper_rows = _weeks([{"snap_share": 0.8, "pts": 8}] * 4 + [{"snap_share": 0.6, "pts": 16}] * 4)
    adv = _adv([(0.25, 0.3)] * 4 + [(0.15, 0.2)] * 4)
    prof = ut.build_usage_profile("TE", sleeper_rows, adv)
    assert prof["flags"][0]["key"] == "unsustainable"


def test_role_shrinking():
    sleeper_rows = _weeks([{"snap_share": 0.8, "pts": 12}] * 4 + [{"snap_share": 0.5, "pts": 9}] * 4)
    adv = _adv([(0.25, 0.3)] * 4 + [(0.15, 0.2)] * 4)
    assert ut.build_usage_profile("WR", sleeper_rows, adv)["flags"][0]["key"] == "role_shrinking"


def test_no_flag_when_metrics_disagree():
    sleeper_rows = _weeks([{"snap_share": 0.5, "pts": 10}] * 4 + [{"snap_share": 0.8, "pts": 10}] * 4)
    adv = _adv([(0.25, 0.3)] * 4 + [(0.15, 0.3)] * 4)
    prof = ut.build_usage_profile("WR", sleeper_rows, adv)
    assert prof["status"] == "ok" and prof["flags"] == []


def test_minimum_sample_blocks_flags_but_still_reports_metrics():
    sleeper_rows = _weeks([{"snap_share": 0.5, "pts": 10}] * 3 + [{"snap_share": 0.9, "pts": 10}] * 3)
    prof = ut.build_usage_profile("WR", sleeper_rows, {"available": False, "reason": "advanced_stats_file_unavailable"})
    assert prof["status"] == "building_sample" and prof["flags"] == []
    assert "need 7 played games" in prof["status_note"]
    assert prof["advanced"]["available"] is False
    assert {m["key"] for m in prof["metrics"]} >= {"snap_share", "opportunities"}
    assert not any(m["source"] == "nflverse" for m in prof["metrics"])


def test_long_absence_makes_window_stale_and_unflagged():
    rows = [{"week": w, "games_played": 1, "fantasy_points_ppr": 10.0, "snap_share": 0.5} for w in (1, 2, 3, 4)]
    rows += [{"week": w, "games_played": 1, "fantasy_points_ppr": 10.0, "snap_share": 0.9} for w in (10, 12, 14, 16)]
    prof = ut.build_usage_profile("WR", rows, None)
    assert prof["flags"] == [] and "long absence" in prof["status_note"]


def test_missing_advanced_row_is_zero_only_within_dataset_coverage():
    rows = _weeks([{"snap_share": 0.5, "pts": 5}] * 8)
    adv = {"available": True, "through_week": 6, "as_of": "t", "weeks": {w: {"target_share": 0.2, "air_yards_share": 0.2, "opportunity_share": 0.2} for w in (1, 2, 3)}}
    prof = ut.build_usage_profile("WR", rows, adv)
    ts = next(m for m in prof["metrics"] if m["key"] == "target_share")
    # weeks 4-6 are real zeros (dataset covers them), weeks 7-8 are unknown.
    assert ts["games_with_data"] == 6


def test_rb_uses_opportunities_when_advanced_missing_and_has_no_air_yards():
    rows = _weeks([{"snap_share": 0.5, "rush_attempts": 8, "targets": 1, "pts": 8}] * 4 + [{"snap_share": 0.75, "rush_attempts": 16, "targets": 3, "pts": 9}] * 4)
    prof = ut.build_usage_profile("RB", rows, None)
    assert prof["flags"][0]["key"] == "role_expanding"
    assert "air_yards_share" not in {m["key"] for m in prof["metrics"]}


def test_uncovered_positions_and_empty_inputs_are_explicit():
    assert ut.build_usage_profile("QB", _weeks([{}] * 8), None)["status"] == "not_covered"
    assert ut.build_usage_profile("WR", [], None)["status"] == "no_data"
    assert ut.build_usage_profile("WR", _weeks([{}] * 8), None)["not_available"][0]["key"] == "routes_run"


def test_fringe_player_gets_metrics_but_no_flag():
    rows = _weeks([{"snap_share": 0.1, "pts": 1.0}] * 4 + [{"snap_share": 0.5, "pts": 1.5}] * 4)
    prof = ut.build_usage_profile("WR", rows, None)
    assert prof["status"] == "low_usage" and prof["flags"] == [] and prof["metrics"]
