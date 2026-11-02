"""Start/sit floor and ceiling: ranges side by side plus a stance-aware lean."""

from __future__ import annotations

from modules import start_sit_range as ssr


def _player(name, low, high, status="ok"):
    return {"name": name, "projection": {"status": status, "low": low, "high": high, "point_estimate": (low + high) / 2}}


def test_range_for_requires_a_real_projection():
    assert ssr.range_for(_player("A", 5, 15), 10.0) == {"name": "A", "projected": 10.0, "low": 5.0, "high": 15.0}
    assert ssr.range_for(_player("A", 5, 15, status="unavailable"), 10.0) is None
    assert ssr.range_for(_player("A", 5, 15), None) is None
    assert ssr.range_for(None, 1.0) is None
    started = _player("A", 5, 15)
    started["game_started"] = True
    assert ssr.range_for(started, 10.0) is None
    assert ssr.range_for({"name": "A", "projection": {"status": "ok", "low": None, "high": 9}}, 5.0) is None
    assert ssr.range_for(_player("A", 15, 5), 10.0) is None  # inverted band is not a range


def test_stance_thresholds_and_unavailable():
    avail = lambda p: {"available": True, "probability": p}  # noqa: E731
    assert ssr.stance(avail(0.22)) == {"kind": "underdog", "win_pct": 22}
    assert ssr.stance(avail(0.30))["kind"] == "underdog"
    assert ssr.stance(avail(0.55))["kind"] == "toss_up"
    assert ssr.stance(avail(0.81)) == {"kind": "favorite", "win_pct": 81}
    assert ssr.stance({"available": False, "reason": "insufficient_coverage"}) is None
    assert ssr.stance(None) is None


def _ranges(a_low, a_high, a_pts, b_low, b_high, b_pts):
    return (
        {"name": "Alpha", "projected": a_pts, "low": a_low, "high": a_high},
        {"name": "Bravo", "projected": b_pts, "low": b_low, "high": b_high},
    )


def test_underdog_favors_higher_ceiling_even_for_slightly_fewer_points():
    a, b = _ranges(8, 20, 13.0, 4, 26, 12.0)  # Bravo: ceiling +6, gives up 1.0 projected point
    out = ssr.lean(a, b, {"kind": "underdog", "win_pct": 22})
    assert out["kind"] == "ceiling" and out["favors"] == "second"
    assert "22% underdog" in out["why"] and "Bravo" in out["why"] and "26 vs 20" in out["why"]
    assert "1.0 fewer projected points" in out["why"]


def test_better_range_with_higher_projection_says_so():
    a, b = _ranges(8, 20, 12.0, 4, 26, 13.0)
    out = ssr.lean(a, b, {"kind": "underdog", "win_pct": 22})
    assert out["favors"] == "second"
    assert "and the higher projection" in out["why"]


def test_underdog_ceiling_costing_points_states_the_cost():
    a, b = _ranges(8, 20, 14.0, 4, 26, 11.5)  # edge 6, giveup 2.5 <= 3
    out = ssr.lean(a, b, {"kind": "underdog", "win_pct": 25})
    assert out["favors"] == "second"
    assert "2.5 fewer projected points" in out["why"]


def test_ceiling_not_worth_too_many_projected_points():
    a, b = _ranges(8, 20, 16.0, 4, 26, 10.0)  # edge 6, giveup 6 > 3
    assert ssr.lean(a, b, {"kind": "underdog", "win_pct": 25}) is None


def test_favorite_favors_higher_floor():
    a, b = _ranges(12, 20, 15.0, 3, 28, 15.5)
    out = ssr.lean(a, b, {"kind": "favorite", "win_pct": 80})
    assert out["kind"] == "floor" and out["favors"] == "first"
    assert "an 80% favorite" in out["why"] and "floor" in out["why"] and "low 12 vs 3" in out["why"]


def test_no_lean_for_toss_up_noise_or_missing_inputs():
    a, b = _ranges(8, 20, 13.0, 4, 26, 12.0)
    assert ssr.lean(a, b, {"kind": "toss_up", "win_pct": 52}) is None
    assert ssr.lean(a, b, None) is None
    near_a, near_b = _ranges(8, 20, 13.0, 8, 20.9, 13.0)
    assert ssr.lean(near_a, near_b, {"kind": "underdog", "win_pct": 20}) is None
    assert ssr.lean(a, None, {"kind": "underdog", "win_pct": 20}) is None


def test_compare_bundles_ranges_stance_and_lean():
    out = ssr.compare(
        _player("Alpha", 8, 20), 13.0, _player("Bravo", 4, 26), 12.0, {"available": True, "probability": 0.2}
    )
    assert out["first"]["name"] == "Alpha" and out["second"]["high"] == 26.0
    assert out["stance"]["kind"] == "underdog"
    assert out["lean"]["favors"] == "second"


def test_article_before_spoken_percentages():
    assert [ssr._a(n) for n in (8, 11, 18, 22, 30, 80, 85, 89, 90)] == ["an", "an", "an", "a", "a", "an", "an", "an", "a"]
