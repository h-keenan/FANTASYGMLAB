from modules import idp_scoring, sleeper

RAW = {
    "gp": 1, "gs": 1, "def_snp": 56.0, "tm_def_snp": 62.0, "idp_tkl_solo": 4.0, "idp_tkl_ast": 2.0,
    "idp_tkl": 6.0, "idp_tkl_loss": 1.0, "idp_sack": 1.5, "pts_idp": 12.0,
}


def test_weekly_row_keeps_idp_fields_and_def_snap_share():
    row = sleeper._extract_week_observation(5, RAW)
    assert row["idp_tkl_solo"] == 4.0 and row["idp_sack"] == 1.5
    assert row["defensive_snaps"] == 56 and row["team_defensive_snaps"] == 62
    assert abs(row["def_snap_share"] - 56 / 62) < 1e-9
    assert row["games_started"] == 1.0
    assert "idp_int" not in row  # Sleeper omitted it: not reported, never a fabricated 0


def test_offense_rows_unchanged_by_idp_retention():
    row = sleeper._extract_week_observation(1, {"gp": 1, "rec": 5, "rec_tgt": 7, "pts_ppr": 14.0, "off_snp": 40, "tm_off_snp": 60})
    assert not any(k.startswith("idp_") or k.startswith("def") for k in row)


def test_cache_marker():
    row = sleeper._extract_week_observation(5, RAW)
    assert sleeper.season_stats_cache_has_idp({"1": {"weekly": [row]}})
    assert not sleeper.season_stats_cache_has_idp({"1": {"weekly": [{"week": 1, "games_played": 1}]}})
    assert not sleeper.season_stats_cache_has_idp({})


def test_points_use_league_scoring_and_bonus():
    row = sleeper._extract_week_observation(5, {**RAW, "idp_tkl": 11.0})
    tackle_heavy = {"idp_tkl_solo": 1, "idp_tkl_ast": 0.5, "idp_sack": 2, "bonus_tkl_10p": 2, "bonus_def_int_td_50p": 2}
    w = idp_scoring.idp_scoring_weights(tackle_heavy)
    assert idp_scoring.idp_weekly_points(row, w) == 4 + 1 + 3 + 2
    assert idp_scoring.unscored_idp_keys(tackle_heavy) == ["bonus_def_int_td_50p"]
    big_play = idp_scoring.idp_scoring_weights({"idp_tkl_solo": 0.5, "idp_sack": 6})
    assert idp_scoring.idp_weekly_points(row, big_play) == 2 + 9


def test_unknown_when_no_defensive_data_and_played_zero_is_zero():
    assert idp_scoring.idp_weekly_points({"week": 1, "games_played": 1}, {"idp_sack": 1}) is None
    assert idp_scoring.idp_weekly_points({"week": 1, "defensive_snaps": 30}, {"idp_sack": 1}) == 0.0


def test_season_points_are_point_in_time():
    rows = [{"week": 1, "defensive_snaps": 50, "idp_sack": 1.0}, {"week": 2, "defensive_snaps": 50, "idp_sack": 2.0}]
    out = idp_scoring.idp_season_points(rows, {"idp_sack": 4}, through_week=1)
    assert out == {"games": 1, "points": 4.0, "ppg": 4.0}


def test_slot_helpers():
    assert idp_scoring.league_has_idp(["QB", "RB", "IDP_FLEX"])
    assert not idp_scoring.league_has_idp(["QB", "RB", "WR", "FLEX", "K", "DEF"])
    assert idp_scoring.idp_slot_family("CB") == "DB" and idp_scoring.idp_slot_family("DE") == "DL"
    assert idp_scoring.idp_slot_family("WR") is None


def test_ensure_idp_stats_rebuilds_an_old_cache_once_and_never_shrinks_it(tmp_path, monkeypatch):
    import json

    cache = tmp_path / "sleeper_player_stats_{season}.json"
    monkeypatch.setattr(sleeper, "PLAYER_STATS_CACHE_TEMPLATE", str(cache))
    monkeypatch.setattr(sleeper, "_idp_rebuild_attempted", set())
    sleeper._season_stats_memo.clear()
    old = {"9": {"stats_season": 2025, "weekly": [{"week": 1, "games_played": 1}, {"week": 2, "games_played": 1}]}}
    (tmp_path / "sleeper_player_stats_2025.json").write_text(json.dumps(old))
    calls = []

    def fake_request(_name, url, timeout=20):
        week = int(url.rsplit("/", 1)[1])
        calls.append(week)
        return {"9": RAW} if week <= 2 else {}

    monkeypatch.setattr(sleeper, "_request_json", fake_request)
    out = sleeper.ensure_season_idp_stats(2025)
    assert sleeper.season_stats_cache_has_idp(out)
    n = len(calls)
    sleeper.ensure_season_idp_stats(2025)  # already IDP-bearing: no more fetches
    assert len(calls) == n
    # A rebuild that fetched fewer weeks than the cache holds must not replace it.
    (tmp_path / "sleeper_player_stats_2024.json").write_text(json.dumps(old))
    monkeypatch.setattr(sleeper, "_request_json", lambda *_a, **_k: {"9": RAW} if _a[1].endswith("/1") else (_ for _ in ()).throw(RuntimeError("down")))
    sleeper._season_stats_memo.clear()
    kept = sleeper.ensure_season_idp_stats(2024)
    assert not sleeper.season_stats_cache_has_idp(kept)
