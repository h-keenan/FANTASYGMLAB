"""Per-week box-score retention (modules.sleeper) and the external
week-result / weekly recap endpoints built on it (modules.weekly_box_scores,
docs/external-api-contract.md "Weekly recap").

Everything here runs on injected fixtures: no Sleeper/nflverse network
call, and no read or write of the real data/ caches.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch

import pandas as pd
import pytest

from modules import nfl_schedule, sleeper, weekly_box_scores

SEASON = 2026

# Real 2026 Week 6 Sleeper lines (verified against the live payload while
# building this change), trimmed to the fields under test.
CMC_RAW = {
    "gp": 1.0, "rec_tgt": 10.0, "rec": 9.0, "rec_yd": 53.0, "rush_att": 16.0,
    "rush_yd": 64.0, "rush_td": 2.0, "fum_lost": 1.0, "off_snp": 53.0,
    "tm_off_snp": 62.0, "pts_ppr": 30.7, "pts_half_ppr": 26.2, "pts_std": 21.7,
}
NABERS_RAW = {
    "gp": 1.0, "rec_tgt": 15.0, "rec": 12.0, "rec_yd": 165.0,
    "pts_ppr": 28.5, "pts_half_ppr": 22.5, "pts_std": 16.5,
}
LAWRENCE_RAW = {
    "gp": 1.0, "pass_att": 41.0, "pass_cmp": 24.0, "pass_yd": 306.0, "pass_td": 4.0,
    "pass_int": 1.0, "rush_att": 3.0, "rush_yd": 11.0,
    "pts_ppr": 28.34, "pts_half_ppr": 28.34, "pts_std": 28.34,
}

PLAYERS = {
    "4034": {"full_name": "Christian McCaffrey", "team": "SF", "position": "RB", "active": True},
    "8112": {"full_name": "Malik Nabers", "team": "NYG", "position": "WR", "active": True},
    "6904": {"full_name": "Trevor Lawrence", "team": "JAX", "position": "QB", "active": True},
    "9001": {"full_name": "Inactive Receiver", "team": "SF", "position": "WR", "active": True},
    "9002": {"full_name": "Traded Back", "team": "KC", "position": "RB", "active": True},
    "9003": {"full_name": "Upcoming Guy", "team": "DAL", "position": "WR", "active": True},
    "9004": {"full_name": "Free Agent", "team": None, "position": "WR", "active": False},
    "9005": {"full_name": "Some Linebacker", "team": "SF", "position": "LB", "active": True},
    "9006": {"full_name": "Bye Week Guy", "team": "KC", "position": "TE", "active": True},
}


def _game(week, home, away, *, home_score=None, away_score=None, gameday="2026-10-19", gametime="20:15"):
    return {
        "season": SEASON,
        "week": week,
        "game_type": "REG",
        "home_team": home,
        "away_team": away,
        "home_score": home_score,
        "away_score": away_score,
        "gameday": gameday,
        "gametime": gametime,
        "game_id": f"{SEASON}_{week:02d}_{away}_{home}",
        "spread_line": None,
        "total_line": None,
    }


def _games() -> pd.DataFrame:
    rows = [
        _game(6, "SF", "WAS", home_score=23, away_score=17, gameday="2026-10-19", gametime="20:15"),
        _game(6, "NYG", "NO", home_score=20, away_score=27, gameday="2026-10-19", gametime="13:00"),
        _game(6, "JAX", "HOU", home_score=31, away_score=28, gameday="2026-10-19", gametime="13:00"),
        # Kicked off, no final score yet.
        _game(6, "DAL", "PHI", gameday="2026-10-20", gametime="20:15"),
        # KC plays weeks 5 and 7, so week 6 is a synthesized bye.
        _game(5, "KC", "DEN", home_score=24, away_score=10, gameday="2026-10-12"),
        _game(7, "KC", "LV", gameday="2026-10-26"),
        _game(7, "DAL", "NYG", gameday="2026-10-26"),
    ]
    return pd.DataFrame(rows)


def _weekly_stats(*, with_box_scores: bool = True) -> dict:
    payload = {
        "4034": CMC_RAW,
        "8112": NABERS_RAW,
        "6904": LAWRENCE_RAW,
        # Sleeper row with snaps but no games-played line: inactive.
        "9001": {"off_snp": 0.0, "tm_off_snp": 62.0},
        # Played this week for a team that wasn't KC (current team on bye).
        "9002": {"gp": 1.0, "rush_att": 8.0, "rush_yd": 30.0, "pts_ppr": 3.0, "pts_half_ppr": 3.0, "pts_std": 3.0},
        "9003": {"gp": 1.0, "rec": 2.0, "rec_tgt": 3.0, "rec_yd": 20.0, "pts_ppr": 4.0, "pts_half_ppr": 3.0, "pts_std": 2.0},
        "9004": {"gp": 1.0, "rec": 1.0, "pts_ppr": 1.0, "pts_half_ppr": 0.5},
    }
    if not with_box_scores:
        stripped = {}
        for pid, raw in payload.items():
            stripped[pid] = {k: v for k, v in raw.items() if k in sleeper.WEEKLY_RETAIN_SOURCE_FIELDS}
        payload = stripped
    aggregated = sleeper._aggregate_player_week_stats([(6, payload)], SEASON, retain_weekly=True)
    if not with_box_scores:
        # Simulate a cache written before box-score retention shipped.
        for record in aggregated.values():
            for row in record.get("weekly", []):
                for target in sleeper.WEEKLY_BOX_SCORE_FIELD_MAP.values():
                    row.pop(target, None)
    return aggregated


# Monday night after the SF game: stats fetched well after every final.
STATS_WRITTEN_AT = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc).timestamp()
NOW = datetime(2026, 10, 21, 13, 0, tzinfo=timezone.utc)


@contextmanager
def _inputs(*, weekly_stats=None, stats_written_at=STATS_WRITTEN_AT, players=None):
    stats = weekly_stats if weekly_stats is not None else _weekly_stats()
    with patch.object(sleeper, "get_players", return_value=players or PLAYERS), \
         patch.object(sleeper, "get_season_player_stats", return_value=stats), \
         patch.object(sleeper, "season_stats_cache_written_at", return_value=stats_written_at), \
         patch.object(nfl_schedule, "load_games", return_value=_games()):
        yield


def _result(player_id, week=6, **kwargs):
    with _inputs(**kwargs):
        return weekly_box_scores.build_player_week_result(player_id, week, SEASON, now=NOW)


# --------------------------------------------------------------------------
# Prerequisite: per-week box-score retention in modules.sleeper
# --------------------------------------------------------------------------


def test_weekly_row_keeps_real_box_score_fields_from_same_payload():
    row = sleeper._extract_week_observation(6, CMC_RAW)
    assert row["rushing_yards"] == 64
    assert row["rushing_tds"] == 2
    assert row["receiving_yards"] == 53
    assert row["fumbles_lost"] == 1
    assert row["fantasy_points_standard"] == pytest.approx(21.7)
    assert row["fantasy_points_half_ppr"] == pytest.approx(26.2)
    # The pre-existing fields are untouched.
    assert row["fantasy_points_ppr"] == pytest.approx(30.7)
    assert row["receptions"] == 9
    assert row["snap_share"] == pytest.approx(53 / 62)
    # Sleeper omitted rec_td (a zero): never written as 0.
    assert "receiving_tds" not in row
    assert isinstance(row["rushing_yards"], int)


def test_box_score_fields_alone_never_create_a_weekly_row():
    """Row existence is still decided only by the original retained fields,
    so no existing weekly-stats consumer sees new rows."""

    assert sleeper._extract_week_observation(6, {"rec_yd": 40.0, "pts_std": 4.0}) is None


def test_season_cache_rebuild_writes_box_scores_to_disk(tmp_path):
    template = str(tmp_path / "sleeper_player_stats_{season}.json")

    def fake_request(label, url, **kwargs):
        return {"4034": CMC_RAW} if url.endswith("/6") else {}

    sleeper._season_stats_memo.clear()
    sleeper._season_stats_memo_mtime_ns.clear()
    sleeper._season_stats_memo_has_weekly.clear()
    with patch.object(sleeper, "PLAYER_STATS_CACHE_TEMPLATE", template), \
         patch.object(sleeper, "_ensure_data_dir"), \
         patch.object(sleeper, "_request_json", side_effect=fake_request):
        result = sleeper.get_season_player_stats(season=SEASON, refresh=True, max_week=7)
        written_at = sleeper.season_stats_cache_written_at(SEASON)
    sleeper._season_stats_memo.clear()
    sleeper._season_stats_memo_mtime_ns.clear()
    sleeper._season_stats_memo_has_weekly.clear()

    on_disk = json.loads((tmp_path / f"sleeper_player_stats_{SEASON}.json").read_text())
    week_row = on_disk["4034"]["weekly"][0]
    assert week_row["week"] == 6
    assert week_row["rushing_tds"] == 2
    assert week_row["fantasy_points_standard"] == pytest.approx(21.7)
    assert sleeper.season_stats_cache_has_box_scores(result) is True
    assert written_at is not None


def test_cache_written_at_is_none_without_a_cache_file(tmp_path):
    with patch.object(sleeper, "PLAYER_STATS_CACHE_TEMPLATE", str(tmp_path / "s_{season}.json")):
        assert sleeper.season_stats_cache_written_at(SEASON) is None


def test_pre_retention_cache_is_detected():
    assert sleeper.season_stats_cache_has_box_scores(_weekly_stats(with_box_scores=False)) is False
    assert sleeper.season_stats_cache_has_box_scores(_weekly_stats()) is True
    assert sleeper.season_stats_cache_has_box_scores({}) is False


# --------------------------------------------------------------------------
# week-result
# --------------------------------------------------------------------------


def test_ok_week_result_has_identity_game_and_real_stat_line():
    result = _result("4034")
    assert result["status"] == "ok"
    assert result["unavailable_reason"] is None
    assert result["id_namespace"] == "sleeper"
    assert result["display_name"] == "Christian McCaffrey"
    assert (result["team"], result["position"], result["position_group"]) == ("SF", "RB", "skill")
    assert result["opponent"] == "WAS"
    assert result["is_home"] is True
    assert result["game_id"] == "2026_06_WAS_SF"
    assert result["game_status"] == "final"
    assert result["week_complete"] is True
    assert (result["team_score"], result["opponent_score"]) == (23.0, 17.0)
    assert result["stats_captured_after_final"] is True
    assert result["box_score_status"] == "ok"
    box = result["box_score"]
    assert box["rushing_yards"] == 64 and box["rushing_tds"] == 2 and box["receptions"] == 9
    assert box["receiving_tds"] is None  # omitted by Sleeper: not a fabricated 0
    assert set(box) == set(weekly_box_scores.BOX_SCORE_FIELDS)
    assert result["fantasy_points_ppr"] == pytest.approx(30.7)
    assert result["fantasy_points_standard"] == pytest.approx(21.7)
    assert result["fantasy_points_half_ppr"] == pytest.approx(26.2)
    assert result["correction_version"] is None
    assert result["correction_version_unavailable_reason"]
    assert len(result["stat_line_fingerprint"]) == 16
    assert result["source"]["weekly_stats"] == "sleeper_weekly_stats"
    assert result["stats_as_of"].startswith("2026-10-21T12:00:00")


def test_fingerprint_is_deterministic_and_changes_on_a_corrected_line():
    first = _result("4034")["stat_line_fingerprint"]
    assert _result("4034")["stat_line_fingerprint"] == first

    corrected = dict(CMC_RAW, rush_yd=66.0, pts_ppr=30.9, pts_half_ppr=26.4, pts_std=21.9)
    stats = sleeper._aggregate_player_week_stats([(6, {"4034": corrected})], SEASON, retain_weekly=True)
    assert _result("4034", weekly_stats=stats)["stat_line_fingerprint"] != first


@pytest.mark.parametrize(
    ("player_id", "week", "expected"),
    [
        ("nope", 6, "unknown_player"),
        ("9005", 6, "unsupported_position"),
        ("9004", 6, "no_team"),
        ("9006", 6, "bye_week"),
        ("9002", 6, "team_schedule_mismatch"),
        ("9003", 6, "game_not_final"),
        ("9003", 7, "not_yet_played"),
        ("9001", 6, "did_not_play"),
        ("6904", 9, "no_schedule_data"),
    ],
)
def test_non_ok_statuses_never_carry_a_stat_line(player_id, week, expected):
    result = _result(player_id, week=week)
    assert result["status"] == expected
    assert result["unavailable_reason"]
    assert result["fantasy_points_ppr"] is None
    assert result["fantasy_points_standard"] is None
    assert all(value is None for value in result["box_score"].values())
    assert result["box_score_status"] == "unavailable"
    assert result["stat_line_fingerprint"] is None


def test_stat_line_cached_before_the_game_could_finish_is_pending():
    # SF kicked off 2026-10-20T00:15Z; a cache fetched 2h later may be partial.
    early = datetime(2026, 10, 20, 2, 15, tzinfo=timezone.utc).timestamp()
    result = _result("4034", stats_written_at=early)
    assert result["status"] == "stats_pending"
    assert result["stats_captured_after_final"] is False
    assert result["fantasy_points_ppr"] is None


def test_pre_retention_cache_returns_only_fields_it_really_kept():
    result = _result("4034", weekly_stats=_weekly_stats(with_box_scores=False))
    assert result["status"] == "ok"
    assert result["box_score_status"] == "unavailable"
    assert "box-score retention" in result["box_score_unavailable_reason"]
    assert result["fantasy_points_ppr"] == pytest.approx(30.7)
    assert result["box_score"]["receptions"] == 9
    assert result["box_score"]["rushing_yards"] is None
    assert result["fantasy_points_standard"] is None


def test_week_outside_regular_season_is_rejected():
    with pytest.raises(ValueError):
        weekly_box_scores.validate_week(19)
    with pytest.raises(ValueError):
        weekly_box_scores.validate_week(0)


# --------------------------------------------------------------------------
# recap
# --------------------------------------------------------------------------


def _recap(**kwargs):
    inputs = {key: kwargs.pop(key) for key in ("weekly_stats", "stats_written_at") if key in kwargs}
    with _inputs(**inputs):
        return weekly_box_scores.build_week_recap(6, SEASON, now=NOW, **kwargs)


def test_recap_ranks_only_final_ok_lines_by_ppr():
    recap = _recap()
    overall = recap["top_performers"]["overall"]
    assert [item["display_name"] for item in overall] == [
        "Christian McCaffrey",
        "Malik Nabers",
        "Trevor Lawrence",
    ]
    assert [item["rank"] for item in overall] == [1, 2, 3]
    assert recap["counts"]["ranked_players"] == 3
    statuses = recap["counts"]["stat_lines_by_status"]
    assert statuses["ok"] == 3
    assert statuses["game_not_final"] == 1
    assert statuses["team_schedule_mismatch"] == 1
    assert statuses["no_team"] == 1
    assert statuses["did_not_play"] == 1
    assert recap["top_performers"]["by_position"]["QB"][0]["display_name"] == "Trevor Lawrence"
    assert recap["top_performers"]["by_position"]["TE"] == []


def test_recap_standard_scoring_reorders_by_sleeper_pts_std():
    recap = _recap(scoring_format="standard")
    names = [item["display_name"] for item in recap["top_performers"]["overall"]]
    assert names == ["Trevor Lawrence", "Christian McCaffrey", "Malik Nabers"]


def test_recap_notable_lines_cite_real_values_and_thresholds():
    notable = {item["display_name"]: item["notable_reasons"] for item in _recap()["notable_lines"]}
    assert {r["code"] for r in notable["Malik Nabers"]} == {"receiving_100_yards", "receptions_10"}
    assert {r["code"] for r in notable["Trevor Lawrence"]} == {"passing_300_yards", "passing_4_tds"}
    assert {r["code"] for r in notable["Christian McCaffrey"]} == {"scrimmage_2_tds"}
    nabers_yards = next(r for r in notable["Malik Nabers"] if r["code"] == "receiving_100_yards")
    assert (nabers_yards["value"], nabers_yards["threshold"]) == (165, 100)


def test_recap_week_status_reports_unfinished_games():
    status = _recap()["week_status"]
    assert status["games_scheduled"] == 4
    assert status["games_final"] == 3
    assert status["pending_game_ids"] == ["2026_06_PHI_DAL"]
    assert status["week_complete"] is False
    assert status["stats_captured_after_all_final_games"] is True


def test_recap_position_filter_and_limit():
    recap = _recap(position="wr", limit=1)
    assert recap["position_scope"] == ["WR"]
    assert [item["display_name"] for item in recap["top_performers"]["overall"]] == ["Malik Nabers"]
    assert list(recap["top_performers"]["by_position"]) == ["WR"]


def test_recap_on_pre_retention_cache_has_no_notable_lines_or_standard_ranking():
    old = _weekly_stats(with_box_scores=False)
    ppr = _recap(weekly_stats=old)
    assert ppr["box_score_status"] == "unavailable"
    assert ppr["ranking_status"] == "ok"
    assert ppr["notable_lines"] == []
    assert len(ppr["top_performers"]["overall"]) == 3
    standard = _recap(weekly_stats=old, scoring_format="standard")
    assert standard["ranking_status"] == "unavailable"
    assert standard["top_performers"]["overall"] == []


@pytest.mark.parametrize(
    "kwargs",
    [{"scoring_format": "dynasty"}, {"limit": 0}, {"limit": 51}, {"position": "DEF"}],
)
def test_recap_rejects_invalid_params(kwargs):
    with pytest.raises(ValueError):
        _recap(**kwargs)


# --------------------------------------------------------------------------
# HTTP routes: auth, validation, wiring
# --------------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from services import mobile_api_service

    monkeypatch.setenv("FANTASYDESK_EXTERNAL_API_KEY", "the-real-secret-key")
    return TestClient(mobile_api_service.app)


AUTH = {"Authorization": "Bearer the-real-secret-key"}


@pytest.mark.parametrize(
    "path",
    ["/v1/external/players/4034/week-result?week=6", "/v1/external/recap?week=6"],
)
def test_routes_require_the_external_api_key(client, path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer wrong"}).status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        "/v1/external/players/4034/week-result?week=19",
        "/v1/external/recap?week=0",
        "/v1/external/recap?week=6&scoring_format=dynasty",
        "/v1/external/recap?week=6&limit=500",
        "/v1/external/recap",
    ],
)
def test_routes_reject_invalid_params_with_422(client, path):
    with _inputs():
        assert client.get(path, headers=AUTH).status_code == 422


def test_routes_return_module_output(client):
    with _inputs():
        one = client.get("/v1/external/players/4034/week-result", params={"week": 6, "season": SEASON}, headers=AUTH)
        recap = client.get("/v1/external/recap", params={"week": 6, "season": SEASON, "limit": 2}, headers=AUTH)
    assert one.status_code == 200
    body = one.json()
    assert body["player_id"] == "4034"
    assert body["display_name"] == "Christian McCaffrey"
    assert body["box_score"]["rushing_tds"] == 2
    assert recap.status_code == 200
    assert recap.json()["limit"] == 2
    assert len(recap.json()["top_performers"]["overall"]) == 2
