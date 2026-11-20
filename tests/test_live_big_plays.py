from __future__ import annotations

from modules import live_big_plays as lbp

PPR = {"rec": 1.0, "rec_yd": 0.1, "rec_td": 6.0, "rush_yd": 0.1, "rush_td": 6.0, "pass_yd": 0.04, "pass_td": 4.0, "pass_int": -2.0, "fum_lost": -2.0}
HALF = {**PPR, "rec": 0.5}


def test_single_td_catch_quotes_yardage():
    play = lbp.derive_play({"rec": 3, "rec_yd": 30}, {"rec": 4, "rec_yd": 68, "rec_td": 1})
    assert play == {"description": "38-yd TD catch", "approx": False, "kinds": ["td"]}


def test_rush_and_passing_td_single_play():
    assert lbp.derive_play({"rush_att": 5, "rush_yd": 20}, {"rush_att": 6, "rush_yd": 32, "rush_td": 1})["description"] == "12-yd TD run"
    assert lbp.derive_play({"pass_cmp": 9, "pass_yd": 90}, {"pass_cmp": 10, "pass_yd": 128, "pass_td": 1})["description"] == "38-yd TD pass"


def test_td_without_yardage_support_omits_yards():
    play = lbp.derive_play({"rec": 3}, {"rec": 4, "rec_td": 1})
    assert play["description"] == "TD catch" and play["approx"] is False


def test_long_gain_without_td():
    play = lbp.derive_play({"rec": 2, "rec_yd": 15}, {"rec": 3, "rec_yd": 52})
    assert play == {"description": "37-yd catch", "approx": False, "kinds": ["long"]}
    assert lbp.derive_play({"rush_att": 2, "rush_yd": 5}, {"rush_att": 3, "rush_yd": 27})["description"] == "22-yd run"
    assert lbp.derive_play({"rec": 2, "rec_yd": 15}, {"rec": 3, "rec_yd": 30}) is None  # 15 yds is not big


def test_turnovers_are_exact():
    assert lbp.derive_play({"pass_int": 0}, {"pass_int": 1}) == {"description": "interception", "approx": False, "kinds": ["turnover"]}
    assert lbp.derive_play({}, {"fum_lost": 1})["description"] == "fumble lost"


def test_multi_stat_drive_is_combined_and_approx():
    play = lbp.derive_play({"rec": 2, "rec_yd": 10}, {"rec": 5, "rec_yd": 55, "rec_td": 1})
    assert play["description"] == "TD catch and 45 yds"
    assert play["approx"] is True


def test_small_gains_and_no_change_are_ignored():
    assert lbp.derive_play({"rec": 1, "rec_yd": 8}, {"rec": 2, "rec_yd": 14}) is None
    assert lbp.derive_play({"rec": 1}, {"rec": 1}) is None
    assert lbp.derive_play(None, {"rec": 1}) is None


def test_two_point_conversion():
    assert lbp.derive_play({}, {"rec": 1, "rec_2pt": 1}) is not None


def test_points_swing_follows_league_scoring():
    prev, nxt = {"rec": 3, "rec_yd": 30}, {"rec": 4, "rec_yd": 68, "rec_td": 1}
    assert lbp.score_stat_delta(prev, nxt, PPR) == 10.8
    assert lbp.score_stat_delta(prev, nxt, HALF) == 10.3
    assert lbp.score_stat_delta(prev, nxt, None) is None
    assert lbp.score_stat_delta({}, {"pass_int": 1}, PPR) == -2.0


def _starter(pid, pts, stats, name="Lane"):
    return {"player_id": pid, "name": name, "position": "WR", "team": "BUF", "actual_points": pts, "game_started": True, "stats": stats}


def _sides(pts, stats):
    return [("1", [_starter("p1", pts, stats)]), ("2", [_starter("p2", 5.0, {"rec": 1}, "Opp")])]


def test_ingest_baseline_then_event_then_dedupes_across_polls():
    assert lbp.ingest("L", 9, _sides(4.0, {"rec": 3, "rec_yd": 30}), scoring_settings=PPR, now=1000) == []
    events = lbp.ingest("L", 9, _sides(13.8, {"rec": 4, "rec_yd": 68, "rec_td": 1}), scoring_settings=PPR, now=1030)
    assert len(events) == 1 and events[0]["points"] == 9.8 and events[0]["description"] == "38-yd TD catch"
    # the same poll seen again (another worker / viewer): no duplicate
    again = lbp.ingest("L", 9, _sides(13.8, {"rec": 4, "rec_yd": 68, "rec_td": 1}), scoring_settings=PPR, now=1060)
    assert [e["id"] for e in again] == [events[0]["id"]]
    assert lbp.present(again, "1")[0]["side"] == "mine"
    assert lbp.present(again, "2")[0]["side"] == "opponent"


def test_ingest_falls_back_to_scored_stats_when_points_lag():
    lbp.ingest("L", 9, _sides(4.0, {"rec": 3, "rec_yd": 30}), scoring_settings=HALF, now=1000)
    events = lbp.ingest("L", 9, _sides(4.0, {"rec": 4, "rec_yd": 68, "rec_td": 1}), scoring_settings=HALF, now=1030)
    assert events[0]["points"] == 10.3


def test_stale_baseline_rebaselines_without_guessing():
    lbp.ingest("L", 9, _sides(4.0, {"rec": 3, "rec_yd": 30}), scoring_settings=PPR, now=1000)
    out = lbp.ingest("L", 9, _sides(14.0, {"rec": 5, "rec_yd": 90, "rec_td": 1}), scoring_settings=PPR, now=1000 + 3600)
    # No played-by-play guessed from a stale baseline: the only thing shown is the
    # honest "so far" line read from the current stats (re-seeded cold start).
    assert [e["description"] for e in out] == ["1 TD so far"] and all(e["so_far"] for e in out)


def test_ingest_fails_open_without_redis(monkeypatch):
    def boom():
        raise RuntimeError("down")

    monkeypatch.setattr(lbp.redis_cache, "get_redis_client", boom)
    assert lbp.ingest("L", 9, _sides(1.0, {})) == []
