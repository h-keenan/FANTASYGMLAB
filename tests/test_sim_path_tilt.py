"""player-model-5: the in-season path tilt (flat expected weekly mean, season totals unchanged), v4 frozen."""

from __future__ import annotations

import numpy as np

from modules.sim import player_model_v5 as v5
from modules.sim import player_model_v4 as v4


def path(module, pos: str, proj: float, n: int = 700):
    """Mean of (weekly mean / season mean) over many profiles, by week (available weeks only)."""

    num, den = np.zeros(17), np.zeros(17)
    for seed in range(n):
        p = {"player_id": f"{pos}{seed}", "pos": pos, "age": 26.0, "team": "KC", "projection_mean_ppg": proj, "is_rookie": False}
        prof = module.draw_season_profile(p, module.profile_rng(seed, p["player_id"]))
        for w in range(1, 18):
            if prof.games_available_mask[w - 1] and prof.season_mean_ppg > 0:
                num[w - 1] += module._week_mean(prof, w, module.INSEASON) / prof.season_mean_ppg
                den[w - 1] += 1
    return num / np.maximum(den, 1), den


def slope(y):
    keep = [i for i in range(14) if y[i] > 0]  # the byes (no available weeks) carry no information
    return float(np.polyfit(keep, y[keep], 1)[0] / np.mean(y[keep]))


def test_the_expected_weekly_mean_is_flat_for_starters_where_v4_fell_off():
    for pos, proj in (("WR", 14.0), ("RB", 13.0)):
        p4, _ = path(v4, pos, proj)
        p5, _ = path(v5, pos, proj)
        assert slope(p4) < -0.004, (pos, slope(p4))  # the old trend
        assert abs(slope(p5)) < 0.005 and slope(p5) > slope(p4) + 0.004, (pos, slope(p4), slope(p5))
        assert p5[12] > p4[12] * 1.02  # late-season weeks are no longer 8% lighter than the season mean
    q4, _ = path(v4, "QB", 19.0)
    q5, _ = path(v5, "QB", 19.0)
    assert abs(slope(q5)) <= abs(slope(q4)) + 0.0005  # quarterbacks barely changed role in v4; the tilt is 30% there


def test_season_totals_and_depth_are_unchanged():
    p4, n4 = path(v4, "WR", 14.0)
    p5, n5 = path(v5, "WR", 14.0)
    assert abs(np.average(p5, weights=n5) - np.average(p4, weights=n4)) < 0.006  # centered tilt: the season average moves under 0.6%
    d4, dn4 = path(v4, "WR", 2.5)
    d5, dn5 = path(v5, "WR", 2.5)
    assert np.allclose(d4, d5)  # depth players already match the real rise; no tilt


def test_v4_is_untouched_and_v5_has_the_tilt():
    assert v4.MODEL_VERSION == "player-model-4" and not hasattr(v4, "PATH_TILT")
    assert v5.MODEL_VERSION == "player-model-5" and v5.PATH_TILT["starter"] > 0 and v5.PATH_TILT["depth"] == 0.0
    # same season story: the draws that define a season do not change between v4 and v5
    p = {"player_id": "x", "pos": "WR", "age": 25.0, "team": "KC", "projection_mean_ppg": 12.0, "is_rookie": False}
    a = v4.draw_season_profile(p, v4.profile_rng(3, "x"))
    b = v5.draw_season_profile(p, v5.profile_rng(3, "x"))
    assert a.season_mean_ppg == b.season_mean_ppg and [e.to_dict() for e in a.injury_events] == [e.to_dict() for e in b.injury_events] and [c.to_dict() for c in a.role_changes] == [c.to_dict() for c in b.role_changes] and a.form == b.form
